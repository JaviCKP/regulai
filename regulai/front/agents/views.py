"""Private authenticated operations; session cookies grant no executor authority."""
import json
import asyncio
from asgiref.sync import sync_to_async
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .data_views import authorize_tool, tool_result
from .service import AgentDenied, authenticate, infer


def _operation(request, handler):
    authorization = request.headers.get('Authorization', '')
    token = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
    attempt = request.headers.get('X-Regulay-Attempt', '')
    try:
        authenticate(token, attempt, allow_uncertain=handler is infer)
        # The large private candidate is authenticated before its bounded read.
        # Other operations retain Django's usual body-size limit.
        if request.path.endswith(('/run/candidate/', '/run/publish/', '/run/image/', '/run/checkpoint/')):
            raw = request.read(40_500_001)
            if len(raw) > 40_500_000:
                raise ValueError('Candidate request too large')
            payload = json.loads(raw)
        else:
            payload = json.loads(request.body)
        result = handler(token, attempt, payload)
        response = JsonResponse(result, status=200)
    except AgentDenied as error:
        response = JsonResponse({'status': 'rejected', 'code': error.code}, status=403)
    except (ValueError, TypeError, KeyError) as error:
        import re
        reason = str(error)
        code = reason if isinstance(error, ValueError) and re.fullmatch(
            r'(artifact|office|pdf|workbook|presentation|checkpoint|image|package|web)_[a-z0-9_]{1,100}', reason) else 'invalid_agent_request'
        response = JsonResponse({'status': 'rejected', 'code': code}, status=400)
    except Exception:
        # Never interpolate raw validation, database, provider or tool exceptions.
        response = JsonResponse({'status': 'unavailable', 'code': 'agent_operation_unavailable'}, status=503)
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@require_POST
def inference(request):
    return _operation(request, infer)


@csrf_exempt
@require_POST
def result(request):
    return _operation(request, tool_result)


@csrf_exempt
@require_POST
def authorize(request):
    def check(token, attempt, payload):
        from .general_tools import begin
        run, context, call = authorize_tool(token, attempt, payload)
        return begin(run, context, call)
    return _operation(request, check)


@csrf_exempt
@require_POST
def worker_claim(request):
    from .jobs import claim
    try:
        header = request.headers.get('Authorization', '')
        token = header.removeprefix('Bearer ') if header.startswith('Bearer ') else ''
        response = JsonResponse(claim(token, json.loads(request.body)))
    except AgentDenied as error:
        response = JsonResponse({'status': 'rejected', 'code': error.code}, status=403)
    except (ValueError, TypeError, KeyError):
        response = JsonResponse({'status': 'rejected', 'code': 'invalid_claim'}, status=400)
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@require_POST
def worker_checkpoints(request):
    """Opaque retention allowlist; only the isolated executor credential."""
    from .jobs import worker_authorized
    from front.models import AgentExport
    from django.utils import timezone
    try:
        header = request.headers.get('Authorization', '')
        worker_authorized(header.removeprefix('Bearer ') if header.startswith('Bearer ') else '')
        if json.loads(request.body) != {}:
            raise ValueError()
        response = JsonResponse({'keep': [str(key) for key in AgentExport.objects.filter(
            expires_at__gt=timezone.now()).values_list('execution_id', flat=True)]})
    except (AgentDenied, ValueError, TypeError):
        response = JsonResponse({'status': 'rejected'}, status=403)
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@require_POST
def execution_operation(request, operation):
    from . import jobs
    from .document_jobs import review_status
    from . import exports
    from . import research
    from . import web_tools, packages, professional_artifacts, vision, general_tools, web_browser, checkpoints
    handlers = {'renew': jobs.renew, 'bootstrap': jobs.bootstrap, 'step': jobs.step,
        'candidate': jobs.candidate, 'local-fields': jobs.local_fields,
        'complete': jobs.complete, 'fail': jobs.fail, 'review-status': review_status,
        'propose-export': exports.propose, 'approval-state': exports.approval_state,
        'save-revision': exports.execute, 'export-complete': exports.complete,
        'reconcile-export': exports.reconcile, 'research': research.execute,
        'web': web_tools.execute, 'packages': packages.execute, 'publish': professional_artifacts.candidate,
        'image': vision.submit, 'output': general_tools.read_output,
        'browser-fetch': web_browser.fetch_resource, 'browser-result': web_browser.submit, 'checkpoint': checkpoints.save}
    if operation not in handlers:
        return JsonResponse({'status': 'rejected'}, status=404)
    return _operation(request, handlers[operation])


def _events(rows, limit=None):
    rows = rows.values('id', 'kind', 'data', 'created_at')
    return [{**row, 'created_at': row['created_at'].isoformat()} for row in (rows[:limit] if limit else rows)]


def _snapshot(actor, run_id, cursor=None):
    from .jobs import reap, authorized_run, artifact_data, run_data, latest
    from .professional_artifacts import current_artifacts as professional_artifacts_for_run
    reap()
    run = authorized_run(actor, run_id)
    if cursor is not None:
        events = _events(run.events.filter(pk__gt=cursor), limit=100)
        return {'run': run_data(run), 'events': events}
    from front.chat_service import request_result
    current = latest(run.conversation, run.job['logical_id'])
    from .exports import display, writable
    from django.conf import settings
    export_enabled = False
    try:
        if getattr(settings, 'REGULAY_AGENT_ENABLED', False) and run.job.get('kind') != 'professional':
            writable(actor)
            export_enabled = True
    except AgentDenied:
        pass
    result = request_result(run.prompt).data
    # Not repeated inside result: a long run's receipt is large and this endpoint is polled on every event.
    receipt = result.pop('receipt', {})
    from .web_tools import source_summary
    professional = run.job.get('kind') == 'professional'
    return {'run': run_data(run), 'result': result, 'receipt': receipt, 'export': display(run),
        'sources': source_summary(run) if professional else [],
        'operations': [{'name': row.name, 'status': row.status, 'created_at': row.created_at,
            'completed_at': row.completed_at, 'details_url': f'/chat/agent/runs/{run.pk}/operations/{row.pk}/'}
            for row in run.operations.all()] if professional else [],
        'infrastructure': {'cost': None, 'scope': 'sandbox_and_bandwidth', 'status': 'not_reported'} if professional else None,
        'export_enabled': export_enabled,
        'current_revision': artifact_data(current) if current else None,
        'events': _events(run.events.all()),
        'artifacts': [artifact_data(row) for row in (professional_artifacts_for_run(run) if professional else run.artifacts.order_by('revision'))
            if (run.status == 'completed' and row.status == 'verified') or
               (run.status == 'active' and row.verification.get('automated_passed'))]}


@login_required
def run_status(request, run_id):
    try:
        response = JsonResponse(_snapshot(request.user, run_id))
    except (AgentDenied, ValueError):
        response = JsonResponse({'error': 'agent_not_found'}, status=404)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_POST
def cancel_run(request, run_id):
    from .jobs import cancel
    try:
        return JsonResponse({'run': cancel(request.user, run_id)})
    except AgentDenied:
        return JsonResponse({'error': 'agent_not_found'}, status=404)


@login_required
@require_POST
def resume_run(request, run_id):
    from .checkpoints import resume
    try:
        return JsonResponse(resume(request.user, run_id))
    except AgentDenied as error:
        return JsonResponse({'error': error.code}, status=409)


@login_required
def operation_details(request, run_id, operation_id):
    from .jobs import authorized_run
    from .general_tools import result_view
    from front.models import AgentOperation, AgentToolResult
    try:
        run = authorized_run(request.user, run_id)
        row = AgentOperation.objects.get(pk=operation_id, execution=run)
        result = AgentToolResult.objects.filter(execution=run, call_id=row.call_id).first()
        value = {'name': row.name, 'arguments': json.loads(row.request)['args'],
            'result': result_view(result) if result else {'status': row.status}}
        response = JsonResponse(value)
    except (AgentDenied, AgentOperation.DoesNotExist, ValueError, KeyError):
        response = JsonResponse({'error': 'agent_not_found'}, status=404)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
async def events(request, run_id):
    if request.method != 'GET':
        return HttpResponse(status=405)
    if not hasattr(request, 'scope'):
        return JsonResponse({'error': 'agent_sse_requires_asgi'}, status=503)
    actor = await request.auser()
    try:
        cursor = int(request.headers.get('Last-Event-ID') or request.GET.get('cursor', '0'))
        if cursor < 0:
            raise ValueError('Invalid cursor')
        first = await sync_to_async(_snapshot)(actor, run_id, cursor)
    except (AgentDenied, ValueError):
        return HttpResponse(status=404)

    async def stream():
        nonlocal cursor
        batch = first
        try:
            while True:
                for row in batch['events']:
                    cursor = row['id']
                    yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(row, ensure_ascii=False)}\n\n"
                if batch['run']['status'] not in ('queued', 'active', 'outcome_unknown') and len(batch['events']) < 100:
                    yield 'event: terminal\ndata: ' + json.dumps(batch['run']) + '\n\n'
                    return
                yield ': keepalive\n\n'
                await asyncio.sleep(1)
                batch = await sync_to_async(_snapshot)(actor, run_id, cursor)
        except AgentDenied:
            yield 'event: revoked\ndata: {}\n\n'
        except asyncio.CancelledError:
            # A disconnected browser never cancels or reruns execution.
            return

    response = StreamingHttpResponse(stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
def download(request, artifact_id):
    from front.models import AgentArtifact
    from .jobs import authorized_run, _bytes
    try:
        artifact = AgentArtifact.objects.select_related('execution').get(pk=artifact_id,
            status='verified', execution__status='completed')
        authorized_run(request.user, artifact.execution_id)
        selected_format = request.GET.get('format', artifact.format)
        raw = _bytes(artifact)
        if selected_format != artifact.format:
            if artifact.format not in ('docx', 'pdf') or selected_format not in ('docx', 'pdf'):
                raise AgentDenied('artifact_format_unavailable')
            import base64
            from .excel_contract import sha256
            raw = base64.b64decode(json.loads(artifact.render_bundle)['final.' + selected_format], validate=True)
            if sha256(raw) != artifact.verification.get(selected_format + '_sha256'):
                raise AgentDenied('artifact_digest_changed')
        types = {'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'pdf': 'application/pdf',
                 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
        if artifact.verification.get('contract') == 'professional-v1':
            from .professional_artifacts import MIMES
            types = MIMES
        response = HttpResponse(raw, content_type=types[selected_format])
        response['Content-Disposition'] = f'attachment; filename="document-{artifact.logical_id}-r{artifact.revision}.{selected_format}"'
    except (AgentDenied, AgentArtifact.DoesNotExist, ValueError, KeyError, TypeError):
        return HttpResponse(status=404)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def document_page(request, artifact_id, number):
    from front.models import AgentArtifact
    from .jobs import authorized_run
    from .document_jobs import render_page
    try:
        artifact = AgentArtifact.objects.get(pk=artifact_id)
        authorized_run(request.user, artifact.execution_id)
        response = HttpResponse(render_page(artifact, number), content_type='image/png')
    except (AgentDenied, AgentArtifact.DoesNotExist, ValueError, KeyError):
        response = HttpResponse(status=404)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_POST
def document_review(request, artifact_id):
    from front.models import AgentArtifact
    from .document_jobs import review
    try:
        response = JsonResponse(review(request.user, artifact_id, json.loads(request.body)))
    except (AgentDenied, AgentArtifact.DoesNotExist, ValueError, KeyError, TypeError):
        response = JsonResponse({'error': 'visual_review_not_authorized'}, status=409)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_POST
def document_search(request):
    from .document_mcp import search
    try:
        payload = json.loads(request.body)
        if set(payload) != {'query'}:
            raise ValueError()
        response = JsonResponse(search(request.user, payload['query']))
    except AgentDenied as error:
        response = JsonResponse({'error': error.code}, status=403)
    except (ValueError, TypeError, KeyError):
        response = JsonResponse({'error': 'document_query_invalid'}, status=400)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_POST
def export_decision(request, export_id):
    from .exports import decide
    from front.models import AgentExport
    try:
        response = JsonResponse(decide(request.user, export_id, json.loads(request.body)))
    except (AgentDenied, AgentExport.DoesNotExist, ValueError, KeyError, TypeError):
        response = JsonResponse({'error': 'export_approval_not_authorized'}, status=409)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_POST
def export_recovery(request, run_id):
    from .exports import recover
    from front.models import AgentExport
    try:
        response = JsonResponse(recover(request.user, run_id))
    except (AgentDenied, AgentExport.DoesNotExist, ValueError, KeyError):
        response = JsonResponse({'error': 'export_recovery_not_authorized'}, status=409)
    response['Cache-Control'] = 'private, no-store'
    return response
