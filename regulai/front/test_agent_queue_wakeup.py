"""Commit-driven queue wakeup; real PostgreSQL claims, no provider network."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event
import time
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.db import close_old_connections, connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from front.agents import jobs, queue_wakeup
from front.models import AgentExecution
from front.test_agent_chat import ChatFixture


@skipUnless(connection.vendor == 'postgresql', 'Queue notification requires PostgreSQL')
@override_settings(REGULAY_AGENT_ENABLED=True)
class AgentQueueWakeupTests(ChatFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        # The inherited inference fixture is not a live dispatched job.
        AgentExecution.objects.filter(pk=self.execution.pk).update(status='completed')

    def payload(self, wait=1):
        return {'worker_id': str(uuid.uuid4()), 'claim_id': str(uuid.uuid4()),
                'worker_protocol': 2, 'wait_seconds': wait}

    def claim_in_thread(self, payload):
        close_old_connections()
        try:
            return jobs.claim(self.worker_token, payload)
        finally:
            connection.close()

    def test_notification_commits_but_rollback_is_silent(self):
        with queue_wakeup.listen() as wake:
            self.assertIsNotNone(wake)
            with transaction.atomic():
                queue_wakeup.notify()
                transaction.set_rollback(True)
            self.assertFalse(wake(.05))
            with transaction.atomic():
                queue_wakeup.notify()
            self.assertTrue(wake(.5))
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_listening_channels()')
            self.assertNotIn((queue_wakeup.CHANNEL,), cursor.fetchall())

    def test_enqueue_between_empty_check_and_wait_cannot_be_lost(self):
        checked, committed = Event(), Event()
        original = jobs._claim

        def after_empty(token, payload):
            result = original(token, payload)
            if result['status'] == 'idle' and not checked.is_set():
                self.assertFalse(connection.in_atomic_block)
                checked.set()
                self.assertTrue(committed.wait(5))
            return result

        with patch.object(jobs, '_claim', side_effect=after_empty):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.claim_in_thread, self.payload())
                self.assertTrue(checked.wait(5))
                run = self.queued()
                started = time.monotonic()
                committed.set()
                result = pending.result(timeout=3)
        self.assertEqual(result['execution'], str(run.pk))
        self.assertLess(time.monotonic() - started, .5)
        self.assertEqual(run.events.filter(kind='claimed').count(), 1)
        self.assertFalse(self.requests)

    def test_two_waiters_wake_but_only_one_claim_and_replay_is_identical(self):
        listeners = Barrier(3)
        original = queue_wakeup.listen

        @contextmanager
        def ready():
            with original() as wake:
                self.assertIsNotNone(wake)
                listeners.wait(5)
                yield wake

        requests = [self.payload(), self.payload()]
        with patch.object(queue_wakeup, 'listen', side_effect=ready):
            with ThreadPoolExecutor(max_workers=2) as executor:
                pending = [executor.submit(self.claim_in_thread, request) for request in requests]
                listeners.wait(5)
                run = self.queued()
                results = [future.result(timeout=3) for future in pending]
        self.assertEqual(sorted(result['status'] for result in results), ['claimed', 'idle'])
        winner = next(index for index, result in enumerate(results) if result['status'] == 'claimed')
        replay = jobs.claim(self.worker_token, {**requests[winner], 'wait_seconds': 0})
        self.assertEqual(replay, results[winner])
        self.assertEqual(run.events.filter(kind='claimed').count(), 1)
        self.assertFalse(self.requests)

    def test_lost_notification_rechecks_on_timeout_without_hot_polling(self):
        ready = Event()
        original = queue_wakeup.listen

        @contextmanager
        def listening():
            with original() as wake:
                def wait(seconds):
                    ready.set()
                    return wake(seconds)
                yield wait

        with patch.object(queue_wakeup, 'listen', side_effect=listening), \
                patch.object(queue_wakeup, 'notify'), \
                patch.object(jobs, '_claim', wraps=jobs._claim) as checks:
            with ThreadPoolExecutor(max_workers=1) as executor:
                started = time.monotonic()
                pending = executor.submit(self.claim_in_thread, self.payload())
                self.assertTrue(ready.wait(5))
                run = self.queued()
                result = pending.result(timeout=3)
        self.assertEqual(result['execution'], str(run.pk))
        self.assertEqual(checks.call_count, 2)
        self.assertGreaterEqual(time.monotonic() - started, .9)
        self.assertFalse(self.requests)

    def test_waiter_limit_falls_back_and_legacy_claim_stays_immediate(self):
        acquired = []
        try:
            while queue_wakeup._WAITERS.acquire(blocking=False):
                acquired.append(True)
            started = time.monotonic()
            self.assertEqual(jobs.claim(self.worker_token, self.payload()),
                             {'status': 'idle', 'retry_after_ms': 500})
            self.assertLess(time.monotonic() - started, .5)
        finally:
            for _ in acquired:
                queue_wakeup._WAITERS.release()
        legacy = self.payload()
        legacy.pop('wait_seconds')
        self.assertEqual(jobs.claim(self.worker_token, legacy), {'status': 'idle'})

    def test_wait_is_validated_and_revocation_rechecked_after_wakeup(self):
        for invalid in (True, -1, 6, '1', 1.5):
            with self.subTest(wait=invalid), self.assertRaises(ValueError):
                jobs.claim(self.worker_token, self.payload(invalid))
        ready = Event()
        original = queue_wakeup.listen

        @contextmanager
        def listening():
            with original() as wake:
                def wait(seconds):
                    ready.set()
                    return wake(seconds)
                yield wait

        with patch.object(queue_wakeup, 'listen', side_effect=listening):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.claim_in_thread, self.payload())
                self.assertTrue(ready.wait(5))
                with transaction.atomic():
                    run = self.queued()
                    type(self.credential).objects.filter(pk=self.credential.pk).update(active=False)
                result = pending.result(timeout=3)
        self.assertEqual(result['status'], 'idle')
        run.refresh_from_db()
        self.assertEqual(run.status, 'interrupted')
        self.assertEqual(run.events.filter(kind='claimed').count(), 0)
        self.assertFalse(self.requests)

    @override_settings(REGULAY_AGENT_CAPACITY={'active_global': 1})
    def test_saturated_queue_wakes_after_capacity_commit_and_replays_once(self):
        occupied = self.queued()
        first = jobs.claim(self.worker_token, self.payload(wait=0))
        self.assertEqual(first['execution'], str(occupied.pk))
        waiting = self.queued()
        ready = Event()
        original = queue_wakeup.listen

        @contextmanager
        def listening():
            with original() as wake:
                def wait(seconds):
                    ready.set()
                    return wake(seconds)
                yield wait

        request = self.payload()
        with patch.object(queue_wakeup, 'listen', side_effect=listening):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.claim_in_thread, request)
                self.assertTrue(ready.wait(5))
                self.assertFalse(pending.done())
                self.assertFalse(waiting.events.filter(kind='claimed').exists())
                with transaction.atomic():
                    occupied.refresh_from_db()
                    jobs._terminal(occupied, 'completed')
                    self.assertFalse(pending.done())
                result = pending.result(timeout=3)
        self.assertEqual(result['execution'], str(waiting.pk))
        self.assertEqual(jobs.claim(self.worker_token, {**request, 'wait_seconds': 0}), result)
        self.assertEqual(waiting.events.filter(kind='claimed').count(), 1)
        self.assertEqual(AgentExecution.objects.filter(status='active').count(), 1)
        self.assertFalse(self.requests)


class QueueASGIIsolationTests(SimpleTestCase):
    def test_two_waiting_http_claims_do_not_block_parallel_inference(self):
        # Use the actual ASGIHandler, not AsyncClient's abbreviated test handler:
        # Django gives each HTTP request its own ThreadSensitiveContext.
        import asyncio
        import httpx
        from django.core.asgi import get_asgi_application
        held, release = Barrier(3), Event()

        def claim(token, payload):
            held.wait(5)
            if not release.wait(5):
                raise AssertionError('Inference did not run beside waiting claims')
            return {'status': 'idle', 'retry_after_ms': 0}

        async def requests():
            application = get_asgi_application()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application),
                                         base_url='http://testserver') as client:
                waiting = [asyncio.create_task(client.post('/internal/agents/claim/', json={
                    'worker_id': str(uuid.uuid4()), 'claim_id': str(uuid.uuid4()),
                    'wait_seconds': 5})) for _ in range(2)]
                try:
                    await asyncio.to_thread(held.wait, 5)
                    start = time.monotonic()
                    inference = await asyncio.wait_for(client.post('/internal/agents/inference/', json={}), 1)
                    self.assertEqual(inference.status_code, 200, inference.text)
                    self.assertLess(time.monotonic() - start, .5)
                    self.assertFalse(release.is_set())
                    self.assertTrue(all(not task.done() for task in waiting))
                finally:
                    release.set()
                    responses = await asyncio.gather(*waiting)
                self.assertTrue(all(response.status_code == 200 for response in responses))

        with patch.object(jobs, 'claim', side_effect=claim), \
                patch('front.agents.views.authenticate', return_value=(None, None)), \
                patch('front.agents.views.infer', return_value={'status': 'completed'}):
            asyncio.run(requests())
