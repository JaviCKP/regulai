"""Owner-scoped, content-free receipt export and retained evidence retrieval."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .chat_service import request_result
from .models import Profile, Prompt, Response


RECEIPT_KEYS = {
    'schema_version', 'policy', 'coverage', 'route', 'calls', 'verification', 'total',
    'status', 'reason_codes', 'sensitivity', 'allowed_destinations', 'rules', 'id',
    'name', 'severity', 'action', 'version', 'revision', 'extractor_version', 'digest',
    'format', 'units_read', 'units_total', 'warnings', 'file_name', 'file_size',
    'fragment_hashes', 'mode', 'task', 'tier', 'difficulty', 'company_engine_id',
    'model', 'model_id', 'model_requested', 'model_effective', 'provider', 'candidate',
    'purpose', 'tokens_used', 'input_tokens', 'output_tokens', 'usage', 'pricing',
    'input_price', 'output_price', 'currency', 'cost', 'known_cost', 'estimated_cost',
    'duration_ms', 'elapsed_ms', 'latency_ms', 'attempts', 'count', 'complete',
    'cost_status', 'scope', 'checks', 'rubric_version', 'response_status', 'result',
    'passed', 'reason', 'finish_reason', 'references', 'evidence_ids',
    'cost_bound', 'price_snapshot', 'price_date', 'provider_request_id',
    'local_status', 'level', 'quality', 'input_tokens_bound', 'attempt', 'code',
    'notices', 'history', 'sent_turns', 'omitted_turns', 'sent_bytes', 'omitted_bytes',
    'limits', 'jev_state_bytes', 'max_output_tokens', 'call_timeout_seconds', 'deadline_seconds',
    'response_bytes', 'judge_input_bytes_bound', 'consent_reason', 'disclosures', 'locators',
    'jev_call_timeout_seconds', 'history_max_bytes', 'history_max_turns',
}


def public_receipt(value):
    if isinstance(value, dict):
        return {key: public_receipt(item) for key, item in value.items() if key in RECEIPT_KEYS}
    if isinstance(value, list):
        return [public_receipt(item) for item in value]
    return value if value is None or isinstance(value, (str, int, float, bool)) else None


def _owned_prompt(request, request_id):
    profile = get_object_or_404(Profile, user=request.user)
    return get_object_or_404(Prompt.objects.select_related('user_message', 'response__assistant_message'),
        request_id=request_id, user=request.user, company=profile.company)


def _json(data):
    response = JsonResponse(data)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_GET
def request_receipt(request, request_id):
    prompt = _owned_prompt(request, request_id)
    result = request_result(prompt).data
    response = _json({'request_id': str(prompt.request_id), 'status': prompt.status,
        'receipt': public_receipt(result.get('receipt', {}))})
    response['Content-Disposition'] = f'attachment; filename="receipt-{prompt.request_id}.json"'
    return response


@login_required
@require_GET
def request_evidence(request, request_id):
    prompt = _owned_prompt(request, request_id)
    response = Response.objects.filter(prompt=prompt).first()
    return _json({'request_id': str(prompt.request_id), 'evidence': response.evidence if response else {}})
