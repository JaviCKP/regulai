"""Trusted application side of the private agent protocol. No executor imports."""
from dataclasses import asdict
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from types import SimpleNamespace
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from front.access import authorized_conversations
from front.chat_service import authorized_history, _candidate, _safe_jev_error_code
from front import jev
from front.classification import decide
from front.connectors import ChatMessage, get_connector
from front.governance import GovernedCalls, PipelineStop, destination_identity
from front.masking import mask_cost_bounds, mask_identity, valid_masks
from front.models import (AgentExecution, AgentInference, AgentInput, AgentModelProfile,
    AgentToolResult, CompanyEngine, EngineModel, ObfuscationConfig, Profile, Prompt)
from front.policy import AIConfig, digest, evaluate_policy
from front.routing import route, RoutingError
from .aliases import alias_text, alias_value, preserve_aliases
from .protocol import InferenceRequest, ToolCall, TOOL_PARAMETERS, tool_schema, validate_arguments


class AgentDenied(ValueError):
    """Only fixed codes may cross the internal boundary."""
    def __init__(self, code='agent_authorization_changed'):
        self.code = code
        super().__init__(code)


def _context(prompt, profile_id, *, allow_disabled=False):
    if not allow_disabled and not getattr(settings, 'REGULAY_AGENT_ENABLED', False):
        raise AgentDenied('agent_disabled')
    actor = prompt.user
    profile = Profile.objects.select_related('company', 'department', 'user').get(user=actor)
    actor.profile = profile
    if prompt.conversation and prompt.conversation.mode == 'agent':
        from .jobs import development_profile
        if development_profile(actor, allow_disabled=allow_disabled) != profile_id:
            raise AgentDenied('agent_profile_unavailable')
    if (not profile.user.is_active or profile.company_id != prompt.company_id
            or not authorized_conversations(actor).filter(pk=prompt.conversation_id).exists()):
        raise AgentDenied()
    agent = AgentModelProfile.objects.filter(pk=profile_id, company_id=prompt.company_id, enabled=True).first()
    if not agent or not isinstance(agent.tools, list) or any(t not in TOOL_PARAMETERS for t in agent.tools):
        raise AgentDenied('agent_profile_unavailable')
    if not agent.professional and prompt.conversation and prompt.conversation.mode == 'agent' and (
            not agent.tools or set(agent.tools) - {'create_mock_excel', 'build_excel', 'rename_excel', 'build_document', 'edit_document', 'export_pdf', 'build_presentation', 'edit_presentation', 'save_revision', 'research_sources'}):
        raise AgentDenied('agent_profile_unavailable')
    from .capabilities import limits, grant_binding, GENERAL
    if agent.professional and (not agent.tools or set(agent.tools) - GENERAL):
        raise AgentDenied('agent_profile_unavailable')
    resource_limits = limits(agent)
    if not 2 <= agent.min_group_size <= 1000:
        raise AgentDenied('agent_profile_unavailable')
    engine = CompanyEngine.objects.filter(pk=agent.connection_id, company_id=prompt.company_id,
        active=True).select_related('engine').first()
    model = EngineModel.objects.filter(pk=agent.model_id, active=True,
        engine_id=engine.engine_id if engine else None).first()
    if (not engine or not engine.api_key or not model
            or engine.engine.connector_type not in ('openai', 'openai_compatible', 'vercel_gateway')):
        raise AgentDenied('agent_profile_unavailable')
    cfg = AIConfig.model_validate(profile.company.ai_config)
    # A classifier is not an independent semantic review of the final artifact.
    # Mandatory artifact verification we cannot meet still blocks explicitly.
    if cfg.verification.mode != 'local':
        raise AgentDenied('agent_policy_incompatible')
    masks = list(ObfuscationConfig.objects.filter(company_id=prompt.company_id, active=True).order_by('created_at', 'pk'))
    if not valid_masks(masks):
        raise AgentDenied('masking_required')
    try:
        mask_cost_bounds(masks, cfg.masking.max_call_cost)
    except ValueError:
        raise AgentDenied('agent_policy_incompatible') from None
    destinations = [f'engine:{engine.pk}'] + [f'obfuscation:{m.pk}' for m in masks]
    if cfg.classification == 'required':
        destinations.append('jev')
    texts = [('prompts', prompt.content), ('prompts', profile.company.system_prompt or ''),
             ('prompts', profile.department.system_prompt if profile.department else '')]
    if prompt.conversation and prompt.conversation.mode == 'agent':
        from .jobs import _decode
        from .excel_contract import input_rows
        for asset in AgentInput.objects.filter(execution__prompt=prompt, kind__in=['csv', 'xlsx', 'narrative', 'policy_text']):
            if asset.kind == 'policy_text':
                if digest(asset.original) != asset.digest:
                    raise AgentDenied('input_digest_changed')
                texts.append(('files', json.loads(asset.original)['text']))
                continue
            # Policy may inspect local originals. This list is never model context.
            raw = _decode(asset)
            texts.append(('files', raw.decode('utf-8') if asset.kind == 'narrative'
                else json.dumps(input_rows(raw, asset.kind), ensure_ascii=False)))
    history = authorized_history(actor, prompt.conversation)
    texts += [('prompts', m.content) for m in history]
    decision = evaluate_policy(actor, texts, destinations=destinations)
    if decision.status != 'allow':
        raise AgentDenied('agent_policy_denied')
    binding = digest([prompt.user_id, prompt.company_id, prompt.conversation_id, profile.department_id,
        decision.fingerprint, texts, destination_identity(engine, model),
        [(m.pk, mask_identity(m)) for m in masks], agent.pk, agent.compaction, agent.vision,
        agent.tools, agent.min_group_size, agent.professional, resource_limits, digest(agent.search_config),
        grant_binding(actor, agent.pk), digest(profile.company.jev_api_key)])
    return actor, profile, agent, cfg, engine, model, masks, destinations, texts, history, decision, binding


def begin_execution(prompt, profile_id, *, lifetime=timedelta(minutes=15)):
    """Trusted orchestration seam for task 50; no public start endpoint in 49."""
    if prompt.status != 'processing' or hasattr(prompt, 'response'):
        raise AgentDenied('invalid_execution_prompt')
    context = _context(prompt, profile_id)
    token = secrets.token_urlsafe(32)
    if not timedelta(0) < lifetime <= timedelta(minutes=15):
        raise AgentDenied('invalid_attempt_lifetime')
    _initialize_receipt(prompt, context)
    prompt.save(update_fields=['decision', 'updated_at'])
    execution = AgentExecution.objects.create(prompt=prompt, profile_id=profile_id,
        token_digest=hashlib.sha256(token.encode()).hexdigest(), authorization_digest=context[-1],
        expires_at=timezone.now() + lifetime)
    return execution, token


def authenticate(token, attempt, *, allow_uncertain=False):
    if not isinstance(token, str) or len(token) > 128:
        raise AgentDenied('invalid_execution_credential')
    execution = AgentExecution.objects.select_related('prompt__user', 'prompt__conversation', 'profile').filter(
        token_digest=hashlib.sha256(token.encode()).hexdigest()).first()
    if (execution is None or str(execution.attempt) != str(attempt) or execution.expires_at <= timezone.now()
            or execution.status not in (('active', 'outcome_unknown') if allow_uncertain else ('active',))):
        raise AgentDenied('invalid_execution_credential')
    context = _context(execution.prompt, execution.profile_id)
    if not hmac.compare_digest(execution.authorization_digest, context[-1]):
        raise AgentDenied()
    return execution, context


def _jev_receipt(profile, cfg):
    required = cfg.classification == 'required'
    configured = bool(profile.company.jev_api_key)
    return {'status': 'pending' if required and configured else 'not_consulted' if configured else 'disabled',
        'consulted': False, 'purpose': 'classification', 'consulted_at': None, 'completed_at': None,
        'model_requested': cfg.jev.model, 'model_effective': None, 'transport': cfg.jev.transport,
        'decision': None, 'signals': {}, 'reasons': [], 'recommendations': [],
        # The actual Jev contract contains structured signals, not prose reasons,
        # recommendations, or the model's private reasoning.
        'explanation_available': False, 'scope': 'protected_text_and_tool_context',
        'policy': {'source': 'regulay_policy', 'revision': cfg.revision,
            'classification': cfg.classification, 'threshold': cfg.jev.threshold,
            'signal_threshold': cfg.classification_policy.signal_threshold,
            'on_ambiguity': cfg.classification_policy.on_ambiguity},
        'effect': 'pending' if required else 'not_required',
        'reason_codes': [] if required and configured else [
            'classification_local' if configured else 'jev_not_configured']}


def _initialize_receipt(prompt, context):
    _, profile, agent, cfg, engine, model, _, _, _, _, decision, _ = context
    prompt.decision.setdefault('calls', [])
    prompt.decision['schema_version'] = 1
    prompt.decision['policy'] = {**decision.as_dict(), 'source': 'local_policy'}
    prompt.decision.setdefault('jev', _jev_receipt(profile, cfg))
    prompt.decision['route'] = {'mode': 'agent_profile', 'profile_id': agent.pk,
        'company_engine_id': engine.pk, 'model': model.model_id,
        'reason': 'explicit_agent_profile', 'fallback': 'disabled'}
    prompt.decision['limits'] = {'provider_managed': cfg.limits.provider_managed,
        'max_output_tokens': None if cfg.limits.provider_managed else cfg.routing.max_output_tokens}


def _metadata_identifier(value):
    """Only bounded identifiers enter receipts, never arbitrary provider text."""
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}', value)
            or re.match(r'(?i)(sk-|AIza|ghp_|github_pat_|xox[baprs]-|Bearer)', value)):
        return None
    return value


class AgentGovernedCalls(GovernedCalls):
    """Add receipts to the shared boundary without changing its authorization."""

    def start_call(self, purpose, destination, model, *args, **kwargs):
        call, started = super().start_call(purpose, destination, model, *args, **kwargs)
        if destination == 'jev':
            connector = 'vercel_gateway' if self.cfg.jev.transport == 'vercel' else 'typesafe'
            mode, upstream = 'company_jev_policy', 'typesafe-ai'
        elif destination.startswith('engine:'):
            row = self.rows[(int(destination.split(':')[1]), kwargs['model_pk'])]
            connector, mode = row[0].engine.connector_type, 'agent_profile'
            upstream = model.split('/', 1)[0] if connector == 'vercel_gateway' else None
        elif destination.startswith('research:'):
            connector, mode, upstream = 'public_https', 'primary_source_read', None
        else:
            connector, mode, upstream = call['transport'], 'required_masking', None
        call.update(sequence=len(self.prompt.decision['calls']), started_at=timezone.now().isoformat(),
            completed_at=None, model_requested=model, provider_name=connector,
            route={'mode': mode, 'destination': destination, 'connector': connector, 'upstream_provider': upstream},
            fallback={'status': 'not_used', 'reason': 'agent_profile_pinned' if mode == 'agent_profile' else 'single_authorized_destination'})
        self.prompt.save(update_fields=['decision', 'updated_at'])
        return call, started

    def complete_call(self, call, started, result):
        if result is not None:
            # The shared ledger must not persist unbounded model IDs, request IDs
            # or arbitrary usage keys supplied by a compatible provider.
            safe = SimpleNamespace(
                model=_metadata_identifier(getattr(result, 'model', None) or getattr(result, 'effective_model', None)),
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                provider_request_id=_metadata_identifier(getattr(result, 'provider_request_id', None) or getattr(result, 'request_id', None)),
                usage={key: value for key, value in result.usage.items() if key in (
                    'input_tokens', 'output_tokens', 'total_tokens', 'prompt_tokens', 'completion_tokens',
                    'cached_tokens', 'reasoning_tokens')},
                provider_metadata=getattr(result, 'provider_metadata', {}))
        else:
            safe = None
        call['completed_at'] = timezone.now().isoformat()
        return super().complete_call(call, started, safe)


def _government(execution, context, token, attempt, call_id):
    actor, profile, _, cfg, engine, model, masks, destinations, _, history, decision, _ = context
    prompt = execution.prompt
    prompt._started = time.monotonic()
    prompt._call_observer, prompt._observer_tokens = None, []
    _initialize_receipt(prompt, context)
    return AgentGovernedCalls(actor, prompt, profile, cfg, decision, destinations,
        {(engine.pk, model.pk): (engine, model, None)}, masks, history,
        authorize=lambda: authenticate(token, attempt), call_context={
            'execution_id': str(execution.pk), 'attempt': str(execution.attempt), 'call_id': call_id})


def _classify(execution, context, government, messages, policy_texts):
    actor, profile, _, cfg, _, _, _, _, _, _, local, _ = context
    if cfg.classification != 'required':
        return
    receipt = _jev_receipt(profile, cfg)
    execution.prompt.decision['jev'] = receipt
    if not profile.company.jev_api_key:
        receipt.update(effect='block', reason_codes=['jev_unavailable'])
        raise AgentDenied('jev_unavailable')
    # Inspect exactly the protected text and structured tool context about to be
    # sent. Opaque approved image references do not imply visual review by Jev.
    state = {'request': next((message.content for message in reversed(messages) if message.role == 'user'), ''),
        'context': [asdict(message) for message in messages]}
    questions = {**jev.classification_questions(), **jev.task_questions()}
    serialized = json.dumps(state, ensure_ascii=False)
    if not cfg.limits.provider_managed and len(serialized.encode('utf-8')) > jev.MAX_STATE_BYTES:
        receipt.update(status='not_consulted', effect='block', reason_codes=['evaluation_input_too_large'])
        raise AgentDenied('evaluation_input_too_large')
    prices = {key: getattr(cfg.jev, key) for key in ('input_price', 'output_price', 'currency', 'price_date')}
    bound = (Decimal(cfg.jev.max_call_cost) if cfg.jev.max_call_cost is not None
        and cfg.jev.input_price is not None and cfg.jev.output_price is not None else None)
    call, started = government.start_call('classification', 'jev', cfg.jev.model,
        policy_texts + [('prompts', serialized)], bound, prices)
    receipt.update(consulted=True, consulted_at=call['started_at'])
    call['jev'] = receipt
    execution.prompt.save(update_fields=['decision', 'updated_at'])
    timeout = None
    if not cfg.limits.provider_managed:
        seconds = min(120, government.remaining())
        connect = min(seconds / 2, max(3, seconds - 60))
        timeout = (connect, seconds - connect)
    try:
        result = jev.evaluate(profile.company.jev_api_key, cfg.jev.model, state, questions,
            timeout=timeout, transport=cfg.jev.transport, provider_managed=cfg.limits.provider_managed)
    except jev.JevError as error:
        code = _safe_jev_error_code(error.code)
        completed_at = timezone.now().isoformat()
        receipt.update(status='no_response' if code in ('timeout', 'connection_error') else 'failed',
            completed_at=completed_at, effect='block', reason_codes=[code])
        call.update(status='outcome_unknown' if error.outcome_unknown else 'failed',
            provider_error_code=code, completed_at=completed_at,
            duration_ms=round((time.monotonic() - started) * 1000))
        if error.outcome_unknown:
            raise
        raise AgentDenied('jev_failed') from None
    classification = decide(result.answers, cfg, local.sensitivity)
    valid_answers = {} if classification.stop_code == 'security_check_failed' else deepcopy(result.answers)
    receipt.update(status='consulted', completed_at=timezone.now().isoformat(),
        model_effective=_metadata_identifier(result.effective_model), signals=valid_answers,
        decision={key: valid_answers[key]['choice'] for key in ('category', 'task', 'difficulty')} if valid_answers else None,
        applied={'source': 'regulay_policy', 'sensitivity': classification.sensitivity,
            'task': classification.task, 'difficulty': classification.difficulty},
        reason_codes=classification.notices, effect='continue')
    call.update(rubric_version=jev.CLASSIFICATION_RUBRIC_VERSION, task_rubric_version=jev.TASK_RUBRIC_VERSION)
    try:
        government.complete_call(call, started, result)
    except PipelineStop as error:
        receipt.update(effect='block', reason_codes=[error.code])
        raise
    government.sensitivity = classification.sensitivity
    if classification.stop_code:
        receipt.update(effect='block', reason_codes=[classification.stop_code, *classification.notices])
        execution.prompt.decision['policy'] = {**local.as_dict(), 'source': 'regulay_policy',
            'inputs': ['local_policy', 'jev_signals'], 'sensitivity': classification.sensitivity,
            'status': 'block' if classification.stop_status == 'blocked' else 'unavailable',
            'reason_codes': receipt['reason_codes']}
        raise AgentDenied(classification.stop_code)
    classified = evaluate_policy(actor, policy_texts, sensitivity=classification.sensitivity,
        destinations=government.destinations)
    classified.allowed_destinations = sorted(set(classified.allowed_destinations) & set(local.allowed_destinations))
    execution.prompt.decision['policy'] = {**classified.as_dict(), 'source': 'regulay_policy',
        'inputs': ['local_policy', 'jev_signals'], 'rubric_version': jev.CLASSIFICATION_RUBRIC_VERSION}
    government.destinations = sorted(set(government.destinations) & set(classified.allowed_destinations))
    if classified.status != 'allow':
        receipt.update(effect='block', reason_codes=classified.reason_codes)
        raise AgentDenied(classified.reason_codes[0])


def _protect_tree(execution, value):
    if isinstance(value, str):
        return alias_text(execution, value)
    if isinstance(value, list):
        return [_protect_tree(execution, item) for item in value]
    if isinstance(value, dict):
        from front.local_masking import _SECRET_KEY
        fields = {'nombre': 'PERSON', 'full_name': 'PERSON', 'titular': 'PERSON',
            'email': 'EMAIL', 'correo': 'EMAIL', 'telefono': 'PHONE', 'dni': 'ID', 'iban': 'ACCOUNT'}
        return {alias_text(execution, key): ('[[REGULAI_SECRET]]' if _SECRET_KEY.fullmatch(key)
                else alias_value(execution, fields[key.lower()], item)
                if key.lower() in fields and isinstance(item, str) else _protect_tree(execution, item))
                for key, item in value.items()}
    return value


def _protect_message(execution, government, message, policy_texts):
    # Structural role, ID and name stay separate from mutable user/model content.
    raw = json.dumps(message.model_dump(), ensure_ascii=False)
    for mask in government.masks:
        government.preflight(f'obfuscation:{mask.pk}', policy_texts + [('prompts', raw)])
    original_content = message.model_dump()['content']
    image_references = {}
    if isinstance(original_content, list):
        for index, part in enumerate(original_content):
            if part.get('type') == 'image_ref':
                image_references[index] = part['reference']
                part['reference'] = ''  # Opaque IDs are structure, not maskable prose.
    try:
        content = _protect_tree(execution, original_content)
        calls = [call.model_dump() for call in message.tool_calls]
        for call in calls:
            call['args'] = _protect_tree(execution, call['args'])
    except ValueError:
        raise AgentDenied('invalid_agent_content') from None
    # A JSON scalar string is indistinguishable from plain text to some masking
    # backends. A one-element array preserves escaping when a secret occurs next
    # to an embedded quote in an approved tool result.
    parts = [json.dumps([content], ensure_ascii=False), *[json.dumps(c['args'], ensure_ascii=False) for c in calls]]
    protected = preserve_aliases(parts, lambda values: government.protect_texts(values, policy_texts))
    envelope = json.loads(protected[0])
    if not isinstance(envelope, list) or len(envelope) != 1:
        raise AgentDenied('invalid_masked_agent_content')
    content = envelope[0]
    for index, reference in image_references.items():
        if (not isinstance(content, list) or index >= len(content)
                or not isinstance(content[index], dict) or content[index].get('type') != 'image_ref'):
            raise AgentDenied('invalid_masked_agent_content')
        content[index]['reference'] = reference
    for call, value in zip(calls, protected[1:]):
        call['args'] = json.loads(value)
        validate_arguments(ToolCall.model_validate(call))
    return ChatMessage(message.role, content, calls, message.tool_call_id, message.name)


def _validate_tool_history(execution, request):
    from .general_tools import result_view
    issued = {}
    for inference in AgentInference.objects.filter(execution=execution, status='completed'):
        for call in inference.response.get('tool_calls', []):
            issued[call['id']] = call
    pending, seen = {}, set()
    for message in request.messages:
        if pending and message.role != 'tool':
            raise AgentDenied('missing_tool_result')
        for call in message.tool_calls:
            if call.id in seen or issued.get(call.id) != call.model_dump():
                raise AgentDenied('unissued_tool_call')
            pending[call.id] = call.name
            seen.add(call.id)
        if message.role == 'tool':
            result = AgentToolResult.objects.filter(execution=execution, call_id=message.tool_call_id).first()
            if (not result or pending.pop(message.tool_call_id, None) != message.name
                    or message.content != json.dumps(result_view(result), sort_keys=True, ensure_ascii=False)):
                raise AgentDenied('unapproved_tool_result')
    if pending:
        raise AgentDenied('missing_tool_result')


def _images(execution, messages, profile, model, cfg):
    for message in messages:
        if not isinstance(message.content, list):
            continue
        converted = []
        for part in message.content:
            if part['type'] == 'text':
                converted.append(part)
                continue
            # Opaque references only; no caller-chosen URLs, bytes or filesystem paths.
            if not profile.vision or not model.supports_vision or not cfg.limits.provider_managed:
                raise AgentDenied('agent_vision_unavailable')
            asset = AgentInput.objects.filter(pk=part['reference'], execution=execution, kind='model_image').first()
            if not asset or digest(asset.original) != asset.digest:
                raise AgentDenied('unapproved_model_image')
            data = json.loads(asset.original)
            if set(data) != {'mime', 'base64'} or data['mime'] not in ('image/png', 'image/jpeg'):
                raise AgentDenied('unapproved_model_image')
            base64.b64decode(data['base64'], validate=True)
            converted.append({'type': 'image_url', 'image_url': {
                'url': f"data:{data['mime']};base64,{data['base64']}"}})
        message.content = converted


def _totals(prompt):
    calls = prompt.decision['calls']
    known = sum((Decimal(c['cost']) for c in calls if c.get('cost') is not None), Decimal(0))
    complete = all(c.get('cost') is not None for c in calls)
    prompt.decision['total'] = {'known_cost': str(known), 'cost': str(known) if complete else None,
        'currency': 'USD', 'complete': complete, 'attempts': sum(c['purpose'] in ('generation', 'compaction', 'vision') for c in calls)}
    prompt.save(update_fields=['decision', 'updated_at'])


def infer(token, attempt, payload):
    request = InferenceRequest.model_validate(payload)
    execution, context = authenticate(token, attempt, allow_uncertain=True)
    request_digest = digest(request.model_dump())
    # A uniqueness constraint and an atomic per-execution claim serialize money
    # and receipts on SQLite AND PostgreSQL. Never hold a transaction over HTTP.
    with transaction.atomic():
        if context[2].professional:
            from .capabilities import limits
            budget = limits(context[2])
            if (not AgentInference.objects.filter(execution=execution, call_id=request.call_id).exists()
                    and AgentInference.objects.filter(execution=execution).count() >= budget['model_calls']):
                raise AgentDenied('agent_model_budget_exhausted')
            if execution.started_at and (timezone.now() - execution.started_at).total_seconds() >= budget['run_seconds']:
                raise AgentDenied('execution_deadline')
        record, created = AgentInference.objects.get_or_create(execution=execution, call_id=request.call_id,
            defaults={'attempt': execution.attempt, 'request_digest': request_digest})
        if record.request_digest != request_digest:
            raise AgentDenied('inference_id_conflict')
        if not created:
            return record.response or {'status': 'outcome_unknown', 'code': 'inference_in_progress_or_uncertain'}
        if not AgentExecution.objects.filter(pk=execution.pk, status='active', active_call__isnull=True,
                attempt=execution.attempt).update(active_call=request.call_id):
            raise AgentDenied('execution_busy_or_uncertain')
        record.status = 'processing'
        record.save(update_fields=['status'])
    # The claim may have waited. Reload the ledger only after acquiring it.
    execution.prompt.refresh_from_db()
    government = None
    try:
        execution, context = authenticate(token, attempt)
        _, profile, agent, cfg, engine, model, _, destinations, policy_texts, _, _, _ = context
        government = _government(execution, context, token, attempt, request.call_id)
        if request.purpose == 'compaction' and not agent.compaction:
            raise AgentDenied('agent_compaction_disabled')
        if request.purpose == 'vision' and not agent.vision:
            raise AgentDenied('agent_vision_unavailable')
        if set(request.tools) - set(agent.tools):
            raise AgentDenied('tool_not_allowed')
        _validate_tool_history(execution, request)
        if cfg.classification == 'required' and not profile.company.jev_api_key:
            _classify(execution, context, government, [], policy_texts)
        # Company and department instructions are sourced in the application.
        from .protocol import WireMessage
        instructions = [WireMessage(role='system', content=value) for value in (
            profile.company.system_prompt, profile.department.system_prompt if profile.department else '') if value]
        effective_tools = request.tools
        if agent.professional:
            if execution.job.get('network_sealed'):
                from .capabilities import WEB
                effective_tools = [name for name in effective_tools if name not in WEB | {'install_packages'}]
                instructions.append(WireMessage(role='system', content=(
                    'La red de esta tarea está cerrada porque ya se ha procesado un archivo privado. '
                    'Trabaja con el archivo y la evidencia disponibles; no consultes URLs ni instales paquetes. '
                    'Puedes generar, comprobar y publicar archivos con las herramientas locales.')))
            remaining = budget['model_calls'] - AgentInference.objects.filter(execution=execution).count()
            if remaining <= 4:
                instructions.append(WireMessage(role='system', content=(
                    f'Quedan {remaining} llamadas después de esta. Reserva la última para responder sin herramientas. '
                    'Prioriza publicar los archivos solicitados. Si ya están publicados y cumplen formato y páginas, '
                    'entrega el resultado ahora; no repitas comprobaciones opcionales. '
                    'Declara cualquier trabajo pendiente con honestidad.')))
            if remaining == 0:
                effective_tools = []
                instructions.append(WireMessage(role='system', content=(
                    'Esta es la última llamada autorizada: responde con los entregables ya verificados y los límites reales. '
                    'No puedes ejecutar más herramientas ni afirmar que terminaste lo que falta.')))
        raw_messages = instructions + request.messages
        messages = [_protect_message(execution, government, message, policy_texts) for message in raw_messages]
        _classify(execution, context, government, messages, policy_texts)
        schemas = [tool_schema(name) for name in effective_tools]
        # Bound all structured payload bytes, including IDs, args and tool schemas.
        bound_messages = [ChatMessage('user', json.dumps([asdict(m) for m in messages], ensure_ascii=False)
            + json.dumps(schemas, ensure_ascii=False))]
        selected = route([_candidate(engine, model, None, 'general')], bound_messages,
            allowed_destinations=government.destinations, require_quality=False,
            max_output_tokens=None if cfg.limits.provider_managed else cfg.routing.max_output_tokens,
            provider_managed=cfg.limits.provider_managed)
        _images(execution, messages, agent, model, cfg)
        policy_payload = json.dumps([asdict(m) for m in messages], ensure_ascii=False)
        call, started = government.start_call(request.purpose, f'engine:{engine.pk}', model.model_id,
            policy_texts + [('prompts', policy_payload)], selected.estimated_cost,
            selected.price_snapshot, model_pk=model.pk)
        execution.prompt.model_used = model.model_id
        execution.prompt.save(update_fields=['decision', 'model_used', 'updated_at'])
        connector = get_connector(engine.engine.connector_type, engine.api_key, engine.engine.base_url or None)
        response = connector.chat(messages, model=model.model_id, max_tokens=selected.max_output_tokens,
            temperature=0.1, timeout=government.remaining(), reasoning=model.reasoning, tools=schemas)
        government.complete_call(call, started, response)
        if call.get('model_effective') and len(call['model_effective']) <= 100:
            execution.prompt.model_used = call['model_effective']
            execution.prompt.save(update_fields=['model_used', 'updated_at'])
        if response.finish_reason not in ('stop', 'tool_calls'):
            raise AgentDenied('inference_incomplete')
        if (response.finish_reason == 'tool_calls') != bool(response.tool_calls):
            raise AgentDenied('invalid_provider_tool_calls')
        from .protocol import WireMessage
        reply = WireMessage(role='assistant', content=response.content or '', tool_calls=response.tool_calls)
        ids = set()
        prior_ids = {c['id'] for r in AgentInference.objects.filter(execution=execution, status='completed')
                     for c in r.response.get('tool_calls', [])}
        for tool in reply.tool_calls:
            try:
                validate_arguments(tool)
            except ValueError:
                raise AgentDenied('invalid_provider_tool_calls') from None
            if tool.name not in effective_tools or tool.id in ids | prior_ids:
                raise AgentDenied('invalid_provider_tool_calls')
            ids.add(tool.id)
        clean = _protect_message(execution, government, reply, policy_texts)
        authenticate(token, attempt)  # Revocation during a provider call withholds delivery.
        record.response = {'status': 'completed', 'content': clean.content, 'tool_calls': clean.tool_calls,
            'usage': {'input_tokens': response.input_tokens, 'output_tokens': response.output_tokens},
            'inference': {key: deepcopy(call.get(key)) for key in (
                'sequence', 'call_id', 'purpose', 'provider', 'provider_name', 'model_requested', 'model_effective',
                'route', 'fallback', 'status', 'started_at', 'completed_at', 'duration_ms', 'cost', 'cost_kind', 'currency')}}
        if agent.professional and request.purpose == 'vision':
            # Exact pixels actually dispatched through this inference, not a
            # worker assertion that an image was reviewed.
            record.response['image_sha256'] = []
            for message in request.messages:
                for part in message.content if isinstance(message.content, list) else []:
                    if part.type == 'image_ref':
                        asset = AgentInput.objects.get(pk=part.reference, execution=execution, kind='model_image')
                        image_data = json.loads(asset.original)
                        record.response['image_sha256'].append(hashlib.sha256(base64.b64decode(image_data['base64'])).hexdigest())
        record.status = 'completed'
    except (AgentDenied, PipelineStop, RoutingError) as error:
        record.status = 'rejected'
        record.response = {'status': 'rejected', 'code': error.code}
        receipt = execution.prompt.decision.get('jev', {})
        if receipt.get('status') == 'pending':
            receipt.update(status='not_consulted', effect='block', reason_codes=[error.code])
    except Exception:
        # Once dispatched, timeout/connection loss/invalid response cannot prove
        # non-execution. No SDK or transport fallback is allowed to resubmit it.
        record.status = 'outcome_unknown'
        record.response = {'status': 'outcome_unknown', 'code': 'inference_outcome_unknown'}
    if government is not None:
        for call in execution.prompt.decision['calls']:
            if call['status'] == 'started':
                call['status'] = 'outcome_unknown'
                call['completed_at'] = timezone.now().isoformat()
                if call.get('call_id') == request.call_id:
                    call['duration_ms'] = max(0, round((time.monotonic() - execution.prompt._call_started) * 1000))
                if call.get('jev'):
                    call['jev'].update(status='no_response', effect='block',
                        completed_at=call['completed_at'], reason_codes=['inference_outcome_unknown'])
                record.status = 'outcome_unknown'
                record.response = {'status': 'outcome_unknown', 'code': 'inference_outcome_unknown'}
        _totals(execution.prompt)
    # A crash before settlement leaves the durable claim; replay returns uncertain.
    with transaction.atomic():
        record.save(update_fields=['status', 'response'])
        AgentExecution.objects.filter(pk=execution.pk, active_call=request.call_id,
            attempt=execution.attempt, status='active').update(
            active_call=None, **({'status': 'outcome_unknown'} if record.status == 'outcome_unknown' else {}))
        if record.status == 'completed' and record.response.get('image_sha256'):
            from .professional_artifacts import record_visual_receipts
            record_visual_receipts(execution)
    return record.response
