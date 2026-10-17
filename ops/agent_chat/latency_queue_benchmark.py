"""Compare the former 500 ms dispatcher poll with commit wakeups on synthetic PG.

No live account, provider, sandbox or installation is used. Admission uses the
real /chat/send/ fixture; claims use production jobs.claim in two worker threads.
Run with the application venv. The dedicated fixture database is created/dropped.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import math
import os
from statistics import median
import sys
from threading import Barrier, Event, local
import time
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.privacy_test_settings'
import django
django.setup()
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import get_runner
from front.agents import jobs
from front.models import AgentExecution
from front.test_agent_chat import ChatFixture

settings.DATABASES['default']['TEST']['NAME'] = 'test_regulai_queue_latency_bench'
SAMPLES = 20
REPORT = []


@override_settings(REGULAY_AGENT_ENABLED=True)
class QueueBenchmark(ChatFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        AgentExecution.objects.filter(pk=self.execution.pk).update(status='completed')

    def test_compare_poll_and_notification(self):
        self.assertEqual(connection.vendor, 'postgresql')
        state = local()
        original = jobs._claim

        def checked(token, request):
            result = original(token, request)
            if result['status'] == 'idle' and not state.ready:
                state.ready = True
                state.barrier.wait(10)
            return result

        for mode in ('poll_500ms', 'notification'):
            for concurrency in (1, 2):
                group = {'mode': mode, 'concurrent_jobs': concurrency, 'samples': []}
                stop = Event()
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    try:
                        for sample in range(SAMPLES + 1):
                            cache.clear()  # Isolated fixture throttle reset, outside measured interval.
                            barrier = Barrier(concurrency + 1)
                            phase = ((sample * 73) % 430 + 10) / 1000

                            def consume():
                                state.barrier, state.ready = barrier, False
                                query_count = 0
                                def count(execute, sql, params, many, context):
                                    nonlocal query_count
                                    if sql.lstrip().upper().startswith('SELECT'):
                                        query_count += 1
                                    return execute(sql, params, many, context)
                                with connection.execute_wrapper(count):
                                    while not stop.is_set():
                                        result = jobs.claim(self.worker_token, {
                                            'worker_id': str(uuid.uuid4()), 'claim_id': str(uuid.uuid4()),
                                            'worker_protocol': 2,
                                            'wait_seconds': 5 if mode == 'notification' else 0})
                                        if result['status'] == 'claimed':
                                            return result, query_count
                                        time.sleep(.5)
                            with patch.object(jobs, '_claim', side_effect=checked):
                                futures = [executor.submit(consume) for _ in range(concurrency)]
                                barrier.wait(10)
                                time.sleep(phase)
                                runs = [self.queued() for _ in range(concurrency)]
                                results = [future.result(timeout=10) for future in futures]
                            self.assertEqual({result['execution'] for result, _ in results},
                                             {str(run.pk) for run in runs})
                            rows = []
                            for run in runs:
                                run.refresh_from_db()
                                self.assertEqual(run.events.filter(kind='claimed').count(), 1)
                                queries = next(count for result, count in results if result['execution'] == str(run.pk))
                                rows.append({'queue_ms': round((run.started_at - run.created_at).total_seconds() * 1000, 3),
                                             'claim_selects': queries})
                                jobs.cancel(self.user, run.pk)
                            group['samples'].append({'warmth': 'cold_connection' if sample == 0 else 'warm_connection',
                                'phase_seconds': phase, 'jobs': rows})
                            self.assertFalse(self.requests)
                    finally:
                        stop.set()
                        # Close each thread's connection before Django drops the fixture DB.
                        closing = Barrier(concurrency)
                        def close():
                            closing.wait(10)
                            connection.close()
                        list(executor.map(lambda _: close(), range(concurrency)))
                for warmth in ('cold_connection', 'warm_connection'):
                    values = [row for sample in group['samples'] if sample['warmth'] == warmth for row in sample['jobs']]
                    durations = sorted(row['queue_ms'] for row in values)
                    group[warmth] = {'jobs': len(values), 'queue_p50_ms': round(median(durations), 3),
                        'queue_p95_ms': durations[math.ceil(.95 * len(durations)) - 1],
                        'claim_selects_p50': median(row['claim_selects'] for row in values),
                        'claim_selects_max': max(row['claim_selects'] for row in values)}
                REPORT.append(group)


def main():
    global SAMPLES
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--output', type=Path,
        default=ROOT / 'output/latency-optimization-20261017/queue-comparison.json')
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error('samples must be between 1 and 100')
    SAMPLES = args.samples
    failed = get_runner(settings)(verbosity=1, interactive=False).run_tests([__name__ + '.QueueBenchmark'])
    if failed:
        return 1
    report = {'scope': 'Synthetic PostgreSQL admission and production claim function; no provider/network/SDK latency.',
        'conditions': {'postgres': '17-alpine on loopback:55483; isolated tmpfs fixture database',
            'input': 'same synthetic CSV/chat request; independent conversation for every job',
            'cold': 'first claim on a fresh thread/database connection, not a cold application process',
            'warm': 'same worker database connections reused after first claim',
            'baseline': 'production immediate claim followed by the former fixed 500 ms worker idle sleep',
            'after': 'production claim with PostgreSQL commit notification and maximum 5 s timeout',
            'phases': 'same deterministic offsets in the idle interval for both variants',
            'queue': 'AgentExecution.started_at minus created_at; includes admission transaction after row creation',
            'queries': 'SELECTs in worker claim thread, including initial idle checks',
            'transport': 'admission uses Django HTTP TestClient; claims run in process, excluding HTTP transit',
            'free_capacity': True, 'paid_calls': 0,
            'admission_throttle': 'isolated in-process cache reset before each sample, outside measurement'},
        'groups': REPORT}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'groups'}))
    print(json.dumps([{'mode': row['mode'], 'concurrent_jobs': row['concurrent_jobs'],
                      'cold_connection': row['cold_connection'], 'warm_connection': row['warm_connection']}
                     for row in REPORT]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
