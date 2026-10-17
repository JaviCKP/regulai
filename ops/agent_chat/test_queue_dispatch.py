"""Executor claim protocol, retries and idle backoff without any network."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'regulai'))
from front.agents.worker import run


class QueueDispatcherTests(unittest.TestCase):
    def dispatch(self, respond, *, once=False):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / 'worker-token'
            token.write_text('synthetic-worker-token')
            stop = threading.Event()
            real_client = httpx.Client
            def client(*args, **kwargs):
                kwargs['transport'] = httpx.MockTransport(respond)
                return real_client(*args, **kwargs)
            def job(internal, *, acquire, started):
                stop.set()
                return {'status': 'completed'}
            with patch('front.agents.worker.httpx.Client', side_effect=client), \
                    patch('front.agents.worker.prune_checkpoints'), \
                    patch('front.agents.worker.run_job', side_effect=job), \
                    patch('front.agents.worker.create_clean', side_effect=AssertionError('Text allocated VM')), \
                    patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')):
                return run({'worker_token_file': str(token), 'internal_endpoint': 'http://internal.test/internal',
                            'shutdown_grace_seconds': 1}, once=once, stop_event=stop)

    def test_long_poll_retries_reuse_claim_identity(self):
        claims = []
        def respond(request):
            claims.append(json.loads(request.content))
            if len(claims) == 1:
                raise httpx.ReadError('synthetic lost response', request=request)
            return httpx.Response(200, json={'status': 'claimed', 'execution': str(uuid.uuid4()),
                'attempt': str(uuid.uuid4()), 'token': 'synthetic-execution-token'})
        self.dispatch(respond)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0], claims[1])
        self.assertEqual(claims[0]['wait_seconds'], 5)

    def test_once_does_not_long_poll_and_preserves_idle_result(self):
        claims = []
        def respond(request):
            claims.append(json.loads(request.content))
            return httpx.Response(200, json={'status': 'idle'})
        self.assertEqual(self.dispatch(respond, once=True), {'status': 'idle'})
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]['wait_seconds'], 0)

    def test_server_fallback_retains_bounded_backoff(self):
        claims, sleeps = [], []
        original = threading.Event.wait
        def wait(event, timeout=None):
            if timeout == .5:
                sleeps.append(timeout)
                return False
            return original(event, timeout)
        def respond(request):
            claims.append(json.loads(request.content))
            if len(claims) == 1:
                return httpx.Response(200, json={'status': 'idle', 'retry_after_ms': 500})
            return httpx.Response(200, json={'status': 'claimed', 'execution': str(uuid.uuid4()),
                'attempt': str(uuid.uuid4()), 'token': 'synthetic-execution-token'})
        with patch('threading.Event.wait', new=wait):
            self.dispatch(respond)
        self.assertEqual(sleeps, [.5])
        self.assertEqual(len(claims), 2)
        self.assertNotEqual(claims[0]['claim_id'], claims[1]['claim_id'])


if __name__ == '__main__':
    unittest.main()
