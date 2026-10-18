"""Repeatable local benchmark on a cloned database; no real provider traffic.

Runs the three Django HTTP entries and the installed SDK dispatcher over HTTP.
Reports metadata only. The unchanged source/runtime is used for both variants.
"""
import collections
from contextlib import nullcontext
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
from django.db import transaction
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
worker_profiles = {}
dispatcher_ready = threading.Event()
original_execute = CursorWrapper.execute
profiling = os.environ.get('BENCH_PROFILE') == '1'
if profiling:
    from latency_profile import Recorder, server_instrumentation
    profiler = Recorder(lambda: state.get('measuring') and state.get('provider_at') is None,
        scope_path.get)
else:
    profiler = None


def execute(cursor, sql, params=None):
    if state.get('measuring') and state.get('provider_at') is None:
        counts[scope_path.get()][sql.lstrip().split()[0].upper()] += 1
        if profiling and scope_path.get().endswith('/inference/'):
            frame, chain = sys._getframe(1), []
            while frame and len(chain) < 5:
                filename = frame.f_code.co_filename
                if '/front/' in filename:
                    chain.append(filename.split('/front/')[-1] + ':' + frame.f_code.co_name)
                frame = frame.f_back
            sql_callers[' > '.join(chain)] += 1
    if profiler:
        return profiler.execute(lambda statement, values: original_execute(cursor, statement, values), sql, params)
    return original_execute(cursor, sql, params)


class MeasuredASGI:
    def __init__(self):
        self.app = get_asgi_application()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if profiling and path == '/__bench/worker-profile':
            body = bytearray()
            while True:
                message = await receive()
                body.extend(message.get('body', b''))
                if len(body) > 2_000_000:
                    raise ValueError('benchmark_profile_too_large')
                if not message.get('more_body'):
                    break
            value = json.loads(body)
            worker_profiles[value['execution']] = value
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{}'})
            return
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
        if profiler:
            state['profile'] = profiler.snapshot()
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
real_connect_ex = socket.socket.connect_ex


def local_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('benchmark_external_network_denied')
    return real_connect(sock, address)


def local_connect_ex(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('benchmark_external_network_denied')
    return real_connect_ex(sock, address)


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
    round_number = int(os.environ.get('BENCH_ROUND', '0'))
    scenario = os.environ.get('BENCH_SCENARIO', 'simple')
    if scenario not in ('simple', 'history'):
        raise ValueError('benchmark_scenario_unknown')
    conversation_id = None
    try:
        for index in range(count):
            counts.clear()
            durations.clear()
            sql_callers.clear()
            state.clear()
            if profiler:
                profiler.reset()
            state.update(measuring=True, provider_at=None)
            path = ('/chat/', '/chat/send/', '/api/chat/send/')[(index + round_number) % 3]
            sensitive = bool(index % 2)
            content = 'Hola, mi correo es latency.person@example.invalid' if sensitive else 'Hola'
            payload = {'prompt': content, 'content': content,
                'request_id': str(uuid.uuid4()), 'mode': 'agent'}
            actual_path = path
            if scenario == 'history' and conversation_id:
                if path == '/api/chat/send/':
                    payload['conversation_id'] = conversation_id
                else:
                    actual_path = f'/chat/{conversation_id}/' + ('send/' if path == '/chat/send/' else '')
            started = timezone.now()
            mark = scope_path.set(path)
            response = client.post(actual_path, payload)
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
            previous_conversation = conversation_id
            if scenario == 'history':
                conversation_id = run.conversation_id
                assert previous_conversation is None or previous_conversation == conversation_id
            sql = state['sql_before_provider']
            internal_sql = collections.Counter()
            for name, verbs in sql.items():
                if name.startswith('/internal/') and not name.endswith('/claim/'):
                    internal_sql.update(verbs)
            rows.append({'index': index, 'cache': 'process-cold' if index == 0 else 'warm',
                'entry': path, 'sensitive': sensitive, 'catalog_count': len((run.job.get('skills') or {}).get('catalog', [])),
                'scenario': scenario, 'history_pairs': len((run.job.get('history') or {}).get('pairs', [])),
                'conversation_data': 'reused' if scenario == 'history' and index else 'new',
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
            if state.get('queue_committed_at'):
                rows[-1].update(
                    queue_admission_s=(state['queue_committed_at'] - run.created_at).total_seconds(),
                    queue_dispatch_s=(run.started_at - state['queue_committed_at']).total_seconds())
            if profiler:
                rows[-1]['profile'] = state['profile']
                until = time.monotonic() + 5
                while str(run.pk) not in worker_profiles and time.monotonic() < until:
                    time.sleep(.02)
                rows[-1]['worker_profile'] = worker_profiles.pop(str(run.pk), None)
            print(json.dumps({'progress': index + 1, 'preparation_s': rows[-1]['preparation_s'],
                              'queue_s': rows[-1]['queue_s']}), flush=True)
            Path('/results/report.json').write_text(json.dumps({'rows': rows, 'instrumented': profiling,
                'round_offset': round_number, 'scenario': scenario,
                'method': 'cloned installed data; real SDK/dispatcher and internal HTTP; Django HTTP entry client; MockTransport provider; external sockets denied'}, indent=2))
            time.sleep((.037, .193, .419, .251, .087, .333)[index % 6])
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        for item in clients:
            item.close()


if __name__ == '__main__':
    from front.agents import jobs
    original_event = jobs.event

    def measured_event(execution, kind, **data):
        result = original_event(execution, kind, **data)
        if kind == 'queued' and state.get('measuring'):
            transaction.on_commit(lambda: state.update(queue_committed_at=timezone.now()))
        return result

    with patch.object(CursorWrapper, 'execute', execute), \
            patch('front.agents.service.get_connector', side_effect=connector), \
            patch.object(socket.socket, 'connect', local_connect), \
            patch.object(socket.socket, 'connect_ex', local_connect_ex), \
            patch.object(jobs, 'event', measured_event), \
            (server_instrumentation(profiler) if profiler else nullcontext()):
        main()
