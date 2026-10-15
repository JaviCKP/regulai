"""Durable general-tool intents and one protected result projection."""
import json
import uuid

from django.db import transaction
from django.utils import timezone

from front.models import AgentExecution, AgentOperation, AgentToolResult
from front.policy import digest
from .capabilities import FILES, WEB, GENERAL, limits
from .service import AgentDenied, authenticate


def result_view(row):
    return json.loads(row.protected_view) if row.protected_view else row.view


def claim_id(run, call):
    return uuid.uuid5(run.attempt, 'tool:' + call.id)


def begin(run, context, call):
    if not context[2].professional:
        return {'status': 'authorized'}
    budget = limits(context[2])
    with transaction.atomic():
        previous = AgentOperation.objects.filter(execution=run, call_id=call.id).first()
        if previous:
            if previous.request_digest != digest(call.model_dump()):
                raise AgentDenied('tool_call_conflict')
            result = AgentToolResult.objects.filter(execution=run, call_id=call.id).first()
            if previous.status == 'completed' and result:
                return {'status': 'authorized', 'replay': result_view(result)}
            # A lost response is not proof that code or a provider did not run.
            raise AgentDenied('tool_outcome_uncertain')
        if AgentOperation.objects.filter(execution=run).count() >= budget['tool_calls']:
            raise AgentDenied('agent_tool_budget_exhausted')
        if not AgentExecution.objects.filter(pk=run.pk, status='active', attempt=run.attempt,
                active_call__isnull=True).update(active_call=claim_id(run, call)):
            raise AgentDenied('execution_busy_or_uncertain')
        run.refresh_from_db()
        if call.name in WEB - {'web_find'} or call.name == 'install_packages':
            if run.job.get('network_sealed'):
                raise AgentDenied('private_computation_network_sealed')
            if AgentOperation.objects.filter(execution=run, name__in=WEB | {'install_packages'}).count() >= budget['web_calls']:
                raise AgentDenied('agent_web_budget_exhausted')
        if run.job.get('private_data') and call.name in FILES | {'inspect_image', 'publish_artifact', 'read_output'}:
            run.job['network_sealed'] = True
            run.save(update_fields=['job'])
        AgentOperation.objects.create(execution=run, call_id=call.id, name=call.name,
            request_digest=digest(call.model_dump()), request=json.dumps(call.model_dump(), ensure_ascii=False))
        from .jobs import event
        kind = ('searching' if call.name == 'web_search' else 'reading' if call.name in WEB else
            'installing' if call.name == 'install_packages' else 'verifying' if call.name in ('publish_artifact', 'inspect_image') else 'executing')
        event(run, kind, call_id=call.id, tool=call.name)
    return {'status': 'authorized'}


def operation(run, call):
    row = AgentOperation.objects.filter(execution=run, call_id=call.id, status='started').first()
    if not row or row.request_digest != digest(call.model_dump()) or run.active_call != claim_id(run, call):
        raise AgentDenied('tool_intent_required')
    return row


def store_result(row, value):
    row.result = json.dumps(value, ensure_ascii=False, allow_nan=False)
    row.save(update_fields=['result'])


def _text(raw):
    # Never merge objects, Command.update, role or metadata into graph state.
    if isinstance(raw, dict) and isinstance(raw.get('content'), str):
        return raw['content']
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, ensure_ascii=False, allow_nan=False)


def finish(run, context, call, request):
    row = operation(run, call)
    maximum = limits(context[2])['output_chars']
    if row.result:
        result = json.loads(row.result)  # Trusted web/artifact operation receipt.
        if call.name == 'web_download' and request.failed:
            result = {**result, 'downloaded': False, 'succeeded': False, 'code': 'workspace_download_failed'}
        if result.get('status') == 'browser_pending':
            result = {'status': 'approved', 'succeeded': False, 'code': 'browser_render_incomplete'}
    else:
        text = _text(request.raw)
        result = {'status': 'approved', 'trust': 'untrusted_tool_data', 'failed': request.failed,
            'output': text[:maximum], 'offset': 0, 'total_characters': len(text),
            'truncated': len(text) > maximum, 'next_offset': maximum if len(text) > maximum else None,
            'call_id': call.id}
    # Contents remain encrypted until the mandatory inference gateway applies
    # policy/masking for its current destination. General traces contain metadata.
    fingerprint = digest(request.model_dump())
    with transaction.atomic():
        previous = AgentToolResult.objects.filter(execution=run, call_id=call.id).first()
        if previous:
            if previous.request_digest != fingerprint:
                raise AgentDenied('tool_result_id_conflict')
            return result_view(previous)
        AgentToolResult.objects.create(execution=run, call_id=call.id, request_digest=fingerprint,
            view={'status': result.get('status', 'approved'), 'call_id': call.id, 'protected': True},
            protected_view=json.dumps(result, ensure_ascii=False), raw=json.dumps(request.raw, ensure_ascii=False))
        row.status, row.completed_at = 'completed', timezone.now()
        row.save(update_fields=['status', 'completed_at'])
        AgentExecution.objects.filter(pk=run.pk, attempt=run.attempt, active_call=claim_id(run, call)).update(active_call=None)
    return result


def read_output(token, attempt, payload):
    from .data_views import authorize_tool
    run, context, call = authorize_tool(token, attempt, payload['call'])
    row = operation(run, call)
    if call.name != 'read_output':
        raise AgentDenied('tool_not_allowed')
    previous = AgentToolResult.objects.filter(execution=run, call_id=call.args['call_id']).first()
    if previous is None:
        raise AgentDenied('output_not_found')
    text = _text(json.loads(previous.raw))
    start, length = call.args.get('offset', 0), limits(context[2])['output_chars']
    result = {'status': 'approved', 'trust': 'untrusted_tool_data', 'output': text[start:start + length],
        'offset': start, 'total_characters': len(text), 'truncated': start + length < len(text),
        'next_offset': start + length if start + length < len(text) else None}
    store_result(row, result)
    return {'status': 'completed'}
