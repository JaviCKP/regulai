"""Repeatable local benchmark on a cloned database; no real provider traffic.

Runs the three Django HTTP entries and the installed SDK dispatcher over HTTP.
Reports metadata only. The unchanged source/runtime is used for both variants.
"""
import collections
import contextvars
import datetime
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import threading
import time
import uuid
from unittest.mock import patch

import httpx
from openai import OpenAI

settings = runpy.run_path('/run/p1/p1_activation_remote.py')['_configure'](os.environ['BENCH_DATABASE'])
assert settings.DATABASES['default']['NAME'].startswith('regulai_p1_latency_')
settings.REGULAY_AGENT_WORKER_TOKEN = 'latency-fixture-worker-only-20261017'
settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, 'testserver']

from django.core.asgi import get_asgi_application
from django.db.backends.utils import CursorWrapper
from django.test import Client
from django.utils import timezone
from front.connectors import OpenAIConnector
from front.models import AgentExecution, AgentInference, AgentInput, PrivacyMessage

scope_path = contextvars.ContextVar('latency_path', default='driver')
counts = collections.defaultdict(collections.Counter)
sql_callers = collections.Counter()
durations = collections.defaultdict(list)
state = {}
rows = []
dispatcher_ready = threading.Event()
original_execute = CursorWrapper.execute


def execute(cursor, sql, params=None):
    if state.get('measuring') and state.get('provider_at') is None:
        counts[scope_path.get()][sql.lstrip().split()[0].upper()] += 1
        if os.environ.get('BENCH_COUNT') == '1' and scope_path.get().endswith('/inference/'):
            frame, chain = sys._getframe(1), []
            while frame and len(chain) < 5:
                filename = frame.f_code.co_filename
                if '/front/' in filename:
                    chain.append(filename.split('/front/')[-1] + ':' + frame.f_code.co_name)
                frame = frame.f_back
            sql_callers[' > '.join(chain)] += 1
    return original_execute(cursor, sql, params)


class MeasuredASGI:
    def __init__(self):
        self.app = get_asgi_application()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        token = scope_path.set(path)
        started = time.perf_counter()
        if path.endswith('/claim/'):
            dispatcher_ready.set()
        if path.endswith('/inference/') and not state.get('inference_at'):
            state['inference_at'] = timezone.now()
        try:
            await self.app(scope, receive, send)
        finally:
            if state.get('measuring'):
                durations[path].append(time.perf_counter() - started)
            scope_path.reset(token)


def provider(request):
    body = json.loads(request.content)
    if not state.get('provider_at'):
        state['provider_at'] = timezone.now()
        state['sql_before_provider'] = {path: dict(verbs) for path, verbs in counts.items()}
    assert 'latency.person@example.invalid' not in request.content.decode(), 'sensitive_text_reached_provider'
    state['provider_calls'] = state.get('provider_calls', 0) + 1
    if body.get('stream'):
        base = {'id': 'latency-simulated', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model']}
        chunks = [{**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant',
            'content': 'Hola. Â¿En quÃ© puedo ayudarte?'}, 'finish_reason': None}]},
            {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
            {**base, 'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112}}]
        wire = ''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks) + 'data: [DONE]\n\n'
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire.encode())
    return httpx.Response(200, json={
        'id': 'latency-simulated', 'object': 'chat.completion', 'created': 1,
        'model': body['model'], 'choices': [{'index': 0,
            'message': {'role': 'assistant', 'content': 'Hola. Â¿En quÃ© puedo ayudarte?'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112}})


clients = []


def connector(*args):
    # Constructor sees only a synthetic key; credentials from the clone are never sent.
    result = OpenAIConnector('synthetic-only', base_url='https://provider.invalid/v1')
    result.client.close()
    result.client = OpenAI(api_key='synthetic-only', base_url='https://provider.invalid/v1', max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(provider), trust_env=False))
    clients.append(result.client)
    return result


real_connect = socket.socket.connect


def local_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('benchmark_external_network_denied')
    return real_connect(sock, address)


def main():
    import uvicorn
    historical = AgentExecution.objects.filter(conversation_id=11).select_related('prompt__user').latest('created_at')
    actor = historical.prompt.user
    client = Client()
    client.force_login(actor)
    server = uvicorn.Server(uvicorn.Config(MeasuredASGI(), host='127.0.0.1', port=31103,
        access_log=False, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(.02)
    Path('/tmp/latency-ready').touch()
    # Orchestrator starts the real dispatcher after this file appears.
    if not dispatcher_ready.wait(30):
        raise RuntimeError('benchmark_dispatcher_not_ready')
    time.sleep(.2)
    count = int(os.environ.get('BENCH_COUNT', '7'))
    try:
        for index in range(count):
            counts.clear()
            durations.clear()
            state.clear()
            state.update(measuring=True, provider_at=None)
            path = ('/chat/', '/chat/send/', '/api/chat/send/')[index % 3]
            sensitive = bool(index % 2)
            content = 'Hola, mi correo es latency.person@example.invalid' if sensitive else 'Hola'
            started = timezone.now()
            mark = scope_path.set(path)
            response = client.post(path, {'prompt': content, 'content': content,
                'request_id': str(uuid.uuid4()), 'mode': 'agent'})
            scope_path.reset(mark)
            assert response.status_code == 202, ('entry_rejected', response.status_code, response.content[:200])
            run_id = response.json()['agent']['id']
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                run = AgentExecution.objects.get(pk=run_id)
                if run.status not in ('queued', 'active'):
                    break
                time.sleep(.1)
            assert run.status == 'completed', ('run_failed', run.status, run.prompt.decision.get('error_type'))
            state['measuring'] = False
            assert state.get('provider_at') and state['provider_calls'] == 1
            sql = state['sql_before_provider']
            internal_sql = collections.Counter()
            for name, verbs in sql.items():
                if name.startswith('/internal/') and not name.endswith('/claim/'):
                    internal_sql.update(verbs)
            rows.append({'index': index, 'cache': 'process-cold' if index == 0 else 'warm',
                'entry': path, 'sensitive': sensitive, 'catalog_count': len((run.job.get('skills') or {}).get('catalog', [])),
                'queue_s': (run.started_at - run.created_at).total_seconds(),
                'preparation_s': (state['provider_at'] - run.started_at).total_seconds(),
                'first_inference_s': (state['provider_at'] - run.created_at).total_seconds(),
                'entry_to_provider_s': (state['provider_at'] - started).total_seconds(),
                'inference_http_to_provider_s': (state['provider_at'] - state['inference_at']).total_seconds(),
                'sql_preparation': dict(internal_sql), 'sql_by_path': sql,
                'http_durations_s': dict(durations),
                'privacy_fragments': PrivacyMessage.objects.filter(turn__prompt_id=run.prompt_id).count(),
                'checkpoint_count': AgentInput.objects.filter(execution=run, kind='checkpoint').count(),
                'inference_count': AgentInference.objects.filter(execution=run).count(),
                'provider_calls': state['provider_calls'], 'status': run.status,
                'sql_callers': dict(sql_callers.most_common(30))})
            print(json.dumps({'progress': index + 1, 'preparation_s': rows[-1]['preparation_s'],
                              'queue_s': rows[-1]['queue_s']}), flush=True)
            Path('/results/report.json').write_text(json.dumps({'rows': rows,
                'method': 'cloned installed data; real SDK/dispatcher and internal HTTP; Django HTTP entry client; MockTransport provider; external sockets denied'}, indent=2))
            time.sleep((.037, .193, .419, .251, .087, .333)[index % 6])
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for item in clients:
            item.close()


if __name__ == '__main__':
    with patch.object(CursorWrapper, 'execute', execute), \
            patch('front.agents.service.get_connector', side_effect=connector), \
            patch.object(socket.socket, 'connect', local_connect):
        main()
