"""Trusted application side of the private agent protocol. No executor imports."""
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from front.access import authorized_conversations
from front.chat_service import authorized_history, _candidate
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


def _context(prompt, profile_id):
    if not getattr(settings, 'REGULAY_AGENT_ENABLED', False):
        raise AgentDenied('agent_disabled')
    actor = prompt.user
    profile = Profile.objects.select_related('company', 'department', 'user').get(user=actor)
    actor.profile = profile
    if prompt.conversation and prompt.conversation.mode == 'agent':
        from .jobs import development_profile
        if development_profile(actor) != profile_id:
            raise AgentDenied('agent_profile_unavailable')
    if (not profile.user.is_active or profile.company_id != prompt.company_id
            or not authorized_conversations(actor).filter(pk=prompt.conversation_id).exists()):
        raise AgentDenied()
    agent = AgentModelProfile.objects.filter(pk=profile_id, company_id=prompt.company_id, enabled=True).first()
    if not agent or not isinstance(agent.tools, list) or any(t not in TOOL_PARAMETERS for t in agent.tools):
        raise AgentDenied('agent_profile_unavailable')
    if prompt.conversation and prompt.conversation.mode == 'agent' and (
            not agent.tools or set(agent.tools) - {'build_excel', 'rename_excel', 'build_document', 'edit_document', 'export_pdf'}):
        raise AgentDenied('agent_profile_unavailable')
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
    # This slice implements inference governance, not an alternative classifier or
    # document verifier. Mandatory policies we cannot meet must block explicitly.
    if cfg.classification != 'local' or cfg.verification.mode != 'local':
        raise AgentDenied('agent_policy_incompatible')
    masks = list(ObfuscationConfig.objects.filter(company_id=prompt.company_id, active=True).order_by('created_at', 'pk'))
    if not valid_masks(masks):
        raise AgentDenied('masking_required')
    try:
        mask_cost_bounds(masks, cfg.masking.max_call_cost)
    except ValueError:
        raise AgentDenied('agent_policy_incompatible') from None
    destinations = [f'engine:{engine.pk}'] + [f'obfuscation:{m.pk}' for m in masks]
    texts = [('prompts', prompt.content), ('prompts', profile.company.system_prompt or ''),
             ('prompts', profile.department.system_prompt if profile.department else '')]
    if prompt.conversation and prompt.conversation.mode == 'agent':
        from .jobs import _decode
        from .excel_contract import input_rows
        for asset in AgentInput.objects.filter(execution__prompt=prompt, kind__in=['csv', 'xlsx']):
            # Policy may inspect local originals. This list is never model context.
            texts.append(('files', json.dumps(input_rows(_decode(asset), asset.kind), ensure_ascii=False)))
    history = authorized_history(actor, prompt.conversation)
    texts += [('prompts', m.content) for m in history]
    decision = evaluate_policy(actor, texts, destinations=destinations)
    if decision.status != 'allow':
        raise AgentDenied('agent_policy_denied')
    binding = digest([prompt.user_id, prompt.company_id, prompt.conversation_id, profile.department_id,
        decision.fingerprint, texts, destination_identity(engine, model),
        [(m.pk, mask_identity(m)) for m in masks], agent.pk, agent.compaction, agent.vision,
        agent.tools, agent.min_group_size])
    return actor, profile, agent, cfg, engine, model, masks, destinations, texts, history, decision, binding


def begin_execution(prompt, profile_id, *, lifetime=timedelta(minutes=15)):
    """Trusted orchestration seam for task 50; no public start endpoint in 49."""
    if prompt.status != 'processing' or hasattr(prompt, 'response'):
        raise AgentDenied('invalid_execution_prompt')
    context = _context(prompt, profile_id)
    token = secrets.token_urlsafe(32)
    if not timedelta(0) < lifetime <= timedelta(minutes=15):
        raise AgentDenied('invalid_attempt_lifetime')
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


def _government(execution, context, token, attempt, call_id):
    actor, profile, _, cfg, engine, model, masks, destinations, _, history, decision, _ = context
    prompt = execution.prompt
    prompt._started = time.monotonic()
    prompt._call_observer, prompt._observer_tokens = None, []
    prompt.decision.setdefault('calls', [])
    prompt.decision['schema_version'] = 1
    prompt.decision['policy'] = decision.as_dict()
    prompt.decision['route'] = {'mode': 'agent_profile', 'profile_id': execution.profile_id,
        'company_engine_id': engine.pk, 'model': model.model_id}
    prompt.decision['limits'] = {'provider_managed': cfg.limits.provider_managed,
        'max_output_tokens': None if cfg.limits.provider_managed else cfg.routing.max_output_tokens}
    return GovernedCalls(actor, prompt, profile, cfg, decision, destinations,
        {(engine.pk, model.pk): (engine, model, None)}, masks, history,
        authorize=lambda: authenticate(token, attempt), call_context={
            'execution_id': str(execution.pk), 'attempt': str(execution.attempt), 'call_id': call_id})


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
    try:
        content = _protect_tree(execution, message.model_dump()['content'])
        calls = [call.model_dump() for call in message.tool_calls]
        for call in calls:
            call['args'] = _protect_tree(execution, call['args'])
    except ValueError:
        raise AgentDenied('invalid_agent_content') from None
    parts = [json.dumps(content, ensure_ascii=False), *[json.dumps(c['args'], ensure_ascii=False) for c in calls]]
    protected = preserve_aliases(parts, lambda values: government.protect_texts(values, policy_texts))
    content = json.loads(protected[0])
    for call, value in zip(calls, protected[1:]):
        call['args'] = json.loads(value)
        validate_arguments(ToolCall.model_validate(call))
    return ChatMessage(message.role, content, calls, message.tool_call_id, message.name)


def _validate_tool_history(execution, request):
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
                    or message.content != json.dumps(result.view, sort_keys=True, ensure_ascii=False)):
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
        # Company and department instructions are sourced in the application.
        from .protocol import WireMessage
        instructions = [WireMessage(role='system', content=value) for value in (
            profile.company.system_prompt, profile.department.system_prompt if profile.department else '') if value]
        raw_messages = instructions + request.messages
        messages = [_protect_message(execution, government, message, policy_texts) for message in raw_messages]
        schemas = [tool_schema(name) for name in request.tools]
        # Bound all structured payload bytes, including IDs, args and tool schemas.
        bound_messages = [ChatMessage('user', json.dumps([asdict(m) for m in messages], ensure_ascii=False)
            + json.dumps(schemas, ensure_ascii=False))]
        selected = route([_candidate(engine, model, None, 'general')], bound_messages,
            allowed_destinations=destinations, require_quality=False,
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
            validate_arguments(tool)
            if tool.name not in request.tools or tool.id in ids | prior_ids:
                raise AgentDenied('invalid_provider_tool_calls')
            ids.add(tool.id)
        clean = _protect_message(execution, government, reply, policy_texts)
        authenticate(token, attempt)  # Revocation during a provider call withholds delivery.
        record.response = {'status': 'completed', 'content': clean.content, 'tool_calls': clean.tool_calls,
            'usage': {'input_tokens': response.input_tokens, 'output_tokens': response.output_tokens}}
        record.status = 'completed'
    except (AgentDenied, PipelineStop, RoutingError) as error:
        record.status = 'rejected'
        record.response = {'status': 'rejected', 'code': error.code}
    except Exception:
        # Once dispatched, timeout/connection loss/invalid response cannot prove
        # non-execution. No SDK or transport fallback is allowed to resubmit it.
        record.status = 'outcome_unknown'
        record.response = {'status': 'outcome_unknown', 'code': 'inference_outcome_unknown'}
    if government is not None:
        for call in execution.prompt.decision['calls']:
            if call['status'] == 'started':
                call['status'] = 'outcome_unknown'
                record.status = 'outcome_unknown'
                record.response = {'status': 'outcome_unknown', 'code': 'inference_outcome_unknown'}
        _totals(execution.prompt)
    # A crash before settlement leaves the durable claim; replay returns uncertain.
    with transaction.atomic():
        record.save(update_fields=['status', 'response'])
        AgentExecution.objects.filter(pk=execution.pk, active_call=request.call_id,
            attempt=execution.attempt, status='active').update(
            active_call=None, **({'status': 'outcome_unknown'} if record.status == 'outcome_unknown' else {}))
    return record.response
