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
        payload = json.loads(request.body)
        result = handler(token, attempt, payload)
        response = JsonResponse(result, status=200)
    except AgentDenied as error:
        response = JsonResponse({'status': 'rejected', 'code': error.code}, status=403)
    except (ValueError, TypeError, KeyError):
        response = JsonResponse({'status': 'rejected', 'code': 'invalid_agent_request'}, status=400)
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
        authorize_tool(token, attempt, payload)
        return {'status': 'authorized'}
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
def execution_operation(request, operation):
    from . import jobs
    handlers = {'renew': jobs.renew, 'bootstrap': jobs.bootstrap, 'step': jobs.step,
        'candidate': jobs.candidate, 'local-fields': jobs.local_fields,
        'complete': jobs.complete, 'fail': jobs.fail}
    if operation not in handlers:
        return JsonResponse({'status': 'rejected'}, status=404)
    return _operation(request, handlers[operation])


def _snapshot(actor, run_id, cursor=None):
    from .jobs import reap, authorized_run, artifact_data, run_data
    reap()
    run = authorized_run(actor, run_id)
    if cursor is not None:
        events = list(run.events.filter(pk__gt=cursor).values('id', 'kind', 'data')[:100])
        return {'run': run_data(run), 'events': events}
    from front.chat_service import request_result
    return {'run': run_data(run), 'result': request_result(run.prompt).data,
        'events': list(run.events.values('id', 'kind', 'data')),
        'artifacts': [artifact_data(row) for row in run.artifacts.filter(status='verified')]
            if run.status == 'completed' else []}


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
        response = HttpResponse(_bytes(artifact), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="excel-{artifact.logical_id}-r{artifact.revision}.xlsx"'
    except (AgentDenied, AgentArtifact.DoesNotExist, ValueError):
        return HttpResponse(status=404)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
