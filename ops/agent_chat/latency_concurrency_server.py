"""Real dispatcher/HTTP concurrency benchmark on the same isolated clone.

Each batch measures two free slots and three jobs sharing two slots. The mock
holds the first two provider requests until their overlap and the third queued
job have been verified. This deliberate hold is reported, never confused with
free-capacity dispatch latency. BENCH_COUNT is batches (five jobs per batch).
"""
import collections
from concurrent.futures import ThreadPoolExecutor
import contextvars
import json
import os
from pathlib import Path
import socket
import threading
import time
import uuid
from unittest.mock import patch

import httpx
import latency_benchmark_server as base
from django.core.asgi import get_asgi_application
from django.db import connection, transaction
from django.db.backends.utils import CursorWrapper
from django.test import Client
from django.utils import timezone
from openai import OpenAI
from front.agents import jobs
from front.connectors import OpenAIConnector
from front.models import AgentExecution, AgentInference, AgentInput


scope_execution = contextvars.ContextVar('concurrency_execution', default=None)
scope_path = contextvars.ContextVar('concurrency_path', default='driver')
lock = threading.RLock()
metrics, token_executions = {}, {}
rows, groups, clients = [], [], []
dispatcher_ready = threading.Event()
current_group = None
capacity_configuration = {}
original_execute, original_claim, original_event = CursorWrapper.execute, jobs._claim, jobs.event


def run_metrics(identifier):
    identifier = str(identifier)
    with lock:
        return metrics.setdefault(identifier, {'execution': identifier, 'provider_calls': 0,
            'sql': collections.defaultdict(collections.Counter), 'group': current_group})


def execute(cursor, sql, params=None):
    execution = scope_execution.get()
    if execution:
        row = run_metrics(execution)
        with lock:
            if not row.get('provider_at'):
                row['sql'][scope_path.get()][sql.lstrip().split()[0].upper()] += 1
    return original_execute(cursor, sql, params)


def claim(*args, **kwargs):
    result = original_claim(*args, **kwargs)
    if result.get('status') == 'claimed':
        with lock:
            token_executions[result['token']] = result['execution']
            run_metrics(result['execution'])
    return result


def event(execution, kind, **data):
    result = original_event(execution, kind, **data)
    if kind == 'queued':
        row = run_metrics(execution.pk)
        transaction.on_commit(lambda: row.update(queue_committed_at=timezone.now()))
    return result


class MeasuredASGI:
    def __init__(self):
        self.app = get_asgi_application()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        headers = dict(scope.get('headers', []))
        credential = headers.get(b'authorization', b'').decode().removeprefix('Bearer ')
        with lock:
            execution = token_executions.get(credential)
        run_token = scope_execution.set(execution)
        path_token = scope_path.set(path)
        if path.endswith('/claim/'):
            dispatcher_ready.set()
        if execution and path.endswith('/inference/'):
            run_metrics(execution).setdefault('inference_at', timezone.now())
        try:
            await self.app(scope, receive, send)
        finally:
            scope_path.reset(path_token)
            scope_execution.reset(run_token)


def provider(request):
    execution = scope_execution.get()
    if execution is None:
        raise AssertionError('concurrent_provider_without_execution')
    row = run_metrics(execution)
    with lock:
        row['provider_calls'] += 1
        if row['provider_calls'] != 1:
            raise AssertionError('concurrent_duplicate_provider_request')
        row['provider_at'] = timezone.now()
        row['sql_before_provider'] = {path: dict(counts) for path, counts in row['sql'].items()}
        group = row['group']
        group['providers'].add(execution)
    if 'latency.person@example.invalid' in request.content.decode():
        raise AssertionError('sensitive_text_reached_provider')
    if not group['release'].wait(30):
        raise AssertionError('concurrent_provider_release_timeout')
    body = json.loads(request.content)
    if body.get('stream'):
        common = {'id': 'latency-concurrent', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model']}
        chunks = [{**common, 'choices': [{'index': 0, 'delta': {'role': 'assistant',
            'content': 'Hola. ¿En qué puedo ayudarte?'}, 'finish_reason': None}]},
            {**common, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
            {**common, 'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112}}]
        wire = ''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks) + 'data: [DONE]\n\n'
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire.encode())
    return httpx.Response(200, json={'id': 'latency-concurrent', 'object': 'chat.completion', 'created': 1,
        'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant',
        'content': 'Hola. ¿En qué puedo ayudarte?'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112}})


def connector(*args):
    result = OpenAIConnector('synthetic-only', base_url='https://provider.invalid/v1')
    result.client.close()
    result.client = OpenAI(api_key='synthetic-only', base_url='https://provider.invalid/v1', max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(provider), trust_env=False))
    with lock:
        clients.append(result.client)
    return result


def write_report(complete=False):
    report = {'rows': rows, 'groups': groups, 'complete': complete, 'scenario': 'concurrency',
        'capacity_configuration': capacity_configuration,
        'instrumented': False, 'method': 'Cloned data; three HTTP admission entries; real HTTP/SDK dispatcher; '
        'two worker slots; loopback-only sockets; MockTransport provider held with Event. SQL counters '
        'exclude admission/claim. Rows marked capacity_blocked include intentional provider hold; '
        'only other rows measure free-capacity queue. Cold is the first batch of this process; '
        'PostgreSQL/OS data caches are not cleared.'}
    temporary = Path('/results/report.json.tmp')
    temporary.write_text(json.dumps(report, indent=2))
    temporary.replace('/results/report.json')


def main():
    global current_group, capacity_configuration
    import uvicorn
    if os.environ.get('BENCH_PROFILE') == '1':
        raise ValueError('concurrency_requires_lightweight_measurement')
    count = int(os.environ.get('BENCH_COUNT', '10'))
    if not 1 <= count <= 100:
        raise ValueError('invalid_concurrency_batch_count')
    offset = int(os.environ.get('BENCH_ROUND', '0'))
    from front.agents.capacity import limits
    installed_capacity = limits()
    # The installed default provider quota is one. Testing two free worker slots
    # requires two provider slots too; this changes only this isolated process.
    # Keep the installed setting visible so this is not represented as live load.
    base.settings.REGULAY_AGENT_CAPACITY = {**installed_capacity,
        'active_global': 2, 'active_company': 2, 'provider': 2}
    capacity_configuration = {'installed_effective': installed_capacity, 'fixture_effective': limits(),
        'scope': 'Process-local synthetic fixture only; baseline/after identical; installation unchanged.'}
    historical = AgentExecution.objects.filter(conversation_id=11).select_related('prompt__user').latest('created_at')
    actor = historical.prompt.user
    http_clients = [Client() for _ in range(3)]
    for client in http_clients:
        client.force_login(actor)
    server = uvicorn.Server(uvicorn.Config(MeasuredASGI(), host='127.0.0.1', port=31103,
        access_log=False, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(.02)
    Path('/tmp/latency-ready').touch()
    if not dispatcher_ready.wait(30):
        raise RuntimeError('benchmark_dispatcher_not_ready')
    time.sleep(.2)
    try:
        for batch in range(count):
            for size in (2, 3):
                group = {'release': threading.Event(), 'providers': set(), 'batch': batch,
                    'concurrent_jobs': size, 'capacity': 2}
                current_group = group

                def admit(index):
                    path = ('/chat/', '/chat/send/', '/api/chat/send/')[(batch + index + offset) % 3]
                    sensitive = bool(index % 2)
                    content = 'Hola, mi correo es latency.person@example.invalid' if sensitive else 'Hola'
                    started = timezone.now()
                    try:
                        response = http_clients[index].post(path, {'prompt': content, 'content': content,
                            'request_id': str(uuid.uuid4()), 'mode': 'agent'})
                        if response.status_code != 202:
                            raise AssertionError('concurrent_admission_rejected_' + str(response.status_code))
                        identifier = response.json()['agent']['id']
                        row = run_metrics(identifier)
                        row.update(entry=path, sensitive=sensitive, entry_at=started)
                        return str(identifier)
                    finally:
                        connection.close()

                with ThreadPoolExecutor(max_workers=size) as executor:
                    identifiers = list(executor.map(admit, range(size)))
                until = time.monotonic() + 20
                while len(group['providers']) < 2 and time.monotonic() < until:
                    time.sleep(.01)
                if len(group['providers']) != 2:
                    raise AssertionError('two_free_worker_slots_did_not_reach_provider_concurrently')
                blocked = set(identifiers) - group['providers']
                if size == 3:
                    blocked_runs = list(AgentExecution.objects.filter(pk__in=blocked))
                    if len(blocked_runs) != 1 or blocked_runs[0].status != 'queued':
                        raise AssertionError('third_execution_did_not_wait_for_worker_capacity')
                    if blocked_runs[0].events.filter(kind='claimed').exists():
                        raise AssertionError('third_execution_claimed_without_worker_capacity')
                elif blocked:
                    raise AssertionError('free_worker_capacity_unused')
                released_at = timezone.now()
                group['release'].set()
                until = time.monotonic() + 60
                while time.monotonic() < until:
                    completed = list(AgentExecution.objects.filter(pk__in=identifiers).order_by('created_at'))
                    if all(run.status not in ('queued', 'active') for run in completed):
                        break
                    time.sleep(.02)
                for run in completed:
                    measured = run_metrics(run.pk)
                    if run.status != 'completed' or measured['provider_calls'] != 1:
                        raise AssertionError('concurrent_execution_not_completed_once')
                    inference_count = AgentInference.objects.filter(execution=run).count()
                    checkpoint_count = AgentInput.objects.filter(execution=run, kind='checkpoint').count()
                    claim_count = run.events.filter(kind='claimed').count()
                    if (inference_count, checkpoint_count, claim_count) != (1, 1, 1):
                        raise AssertionError('concurrent_operation_not_exactly_once')
                    sql = measured['sql_before_provider']
                    internal = collections.Counter()
                    for path, verbs in sql.items():
                        if path.startswith('/internal/') and not path.endswith('/claim/'):
                            internal.update(verbs)
                    row = {'index': len(rows), 'batch': batch, 'concurrent_jobs': size, 'worker_capacity': 2,
                        'cache': 'process-cold' if batch == 0 and size == 2 else 'warm',
                        'entry': measured['entry'], 'sensitive': measured['sensitive'], 'status': run.status,
                        'capacity_blocked': str(run.pk) in blocked, 'provider_calls': measured['provider_calls'],
                        'inference_count': inference_count, 'checkpoint_count': checkpoint_count, 'claim_count': claim_count,
                        'catalog_count': len((run.job.get('skills') or {}).get('catalog', [])),
                        'queue_s': (run.started_at - run.created_at).total_seconds(),
                        'preparation_s': (measured['provider_at'] - run.started_at).total_seconds(),
                        'first_inference_s': (measured['provider_at'] - run.created_at).total_seconds(),
                        'entry_to_provider_s': (measured['provider_at'] - measured['entry_at']).total_seconds(),
                        'inference_http_to_provider_s': (measured['provider_at'] - measured['inference_at']).total_seconds(),
                        'sql_preparation': dict(internal), 'sql_by_path': sql}
                    if measured.get('queue_committed_at'):
                        row.update(queue_admission_s=(measured['queue_committed_at'] - run.created_at).total_seconds(),
                            queue_dispatch_s=(run.started_at - measured['queue_committed_at']).total_seconds())
                    if row['capacity_blocked']:
                        row['capacity_release_to_started_s'] = (run.started_at - released_at).total_seconds()
                    else:
                        row['provider_held_s'] = (released_at - measured['provider_at']).total_seconds()
                    rows.append(row)
                groups.append({'batch': batch, 'concurrent_jobs': size, 'worker_capacity': 2,
                    'provider_overlap_verified': True, 'blocked_until_release': len(blocked),
                    'all_completed_once': True})
                write_report()
                print(json.dumps({'batch': batch, 'concurrent_jobs': size, 'completed_rows': len(rows)}), flush=True)
                time.sleep((.037, .193, .419)[batch % 3])
        write_report(complete=True)
    finally:
        if current_group:
            current_group['release'].set()
        server.should_exit = True
        thread.join(timeout=5)
        for client in clients:
            client.close()


if __name__ == '__main__':
    with patch.object(CursorWrapper, 'execute', execute), \
            patch.object(jobs, '_claim', claim), patch.object(jobs, 'event', event), \
            patch('front.agents.service.get_connector', side_effect=connector), \
            patch.object(socket.socket, 'connect', base.local_connect), \
            patch.object(socket.socket, 'connect_ex', base.local_connect_ex):
        main()
