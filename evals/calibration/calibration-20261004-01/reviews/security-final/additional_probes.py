"""New independent boundary variants; only synthetic secrets and local transports."""
import json
from unittest.mock import patch

import httpx
import requests
from django.test import SimpleTestCase

from front.evaluation import SyntheticPayloadRecorder
from front.evaluation_budget import BudgetExceeded

SECRET = 'sk-independent-fake-only-ALPHA123456'


class BoundaryVariants(SimpleTestCase):
    def test_escaped_json_keys_arrays_and_overwritten_members_are_rejected(self):
        escaped = ''.join('\\u%04x' % ord(char) for char in SECRET)
        bodies = [
            ('{"' + escaped + '":"ok"}').encode(),
            ('{"outer":[{"safe":"' + escaped + '","safe":"ok"}]}').encode(),
            json.dumps({'outer': ['public', {'nested': SECRET}]}).encode(),
        ]
        for body in bodies:
            with self.subTest(body_hash=__import__('hashlib').sha256(body).hexdigest()):
                with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                    with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(SECRET,)) as recorder:
                        with self.assertRaises(BudgetExceeded):
                            client.post('https://api.deepseek.com/chat/completions', json={'model': 'x', 'messages': []})
                    self.assertIsNone(recorder.events[0]['response_body_utf8'])
                    self.assertTrue(recorder.events[0]['response_omitted_credential_reflection'])

    def test_split_requests_chunks_cannot_reach_caller_parser(self):
        body = json.dumps({'text': SECRET}).encode()
        def send(adapter, request, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content_consumed = True
            response.iter_content = lambda *args, **kwargs: iter([body[:19], body[19:31], body[31:]])
            return response
        with patch('requests.adapters.HTTPAdapter.send', send):
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(SECRET,)) as recorder:
                response = requests.post('https://ai-gateway.vercel.sh/typesafe/v1/systemone', json={'model': 'typesafe-ai/jev', 'state': {}, 'questions': {}}, stream=True)
                try:
                    with self.assertRaises(BudgetExceeded):
                        json.loads(b''.join(response.iter_content(8192)))
                finally:
                    response.close()
        self.assertIsNone(recorder.events[0]['response_body_utf8'])

    def test_reflected_public_request_id_is_rejected_on_both_boundaries(self):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}, headers={'x-request-id': SECRET}))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(SECRET,)) as recorder:
                with self.assertRaises(BudgetExceeded):
                    client.post('https://api.deepseek.com/chat/completions', json={'model': 'x', 'messages': []})
            self.assertIsNone(recorder.events[0]['response_body_utf8'])
        def send(adapter, request, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content_consumed = True
            response.headers['x-request-id'] = SECRET
            return response
        with patch('requests.adapters.HTTPAdapter.send', send):
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(SECRET,)) as recorder:
                with self.assertRaises(BudgetExceeded):
                    requests.post('https://ai-gateway.vercel.sh/typesafe/v1/systemone', json={'model': 'typesafe-ai/jev', 'state': {}, 'questions': {}}, stream=True)
            self.assertIsNone(recorder.events[0]['response_body_utf8'])

    def test_valid_public_json_remains_observable_with_secret_filter_enabled(self):
        body = {'id': 'public-id', 'text': 'Public synthetic text', 'nested': [{'category': 'public'}]}
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(SECRET,)) as recorder:
                response = client.post('https://api.deepseek.com/chat/completions', json={'model': 'x', 'messages': []})
        self.assertEqual(response.json(), body)
        self.assertEqual(json.loads(recorder.events[0]['response_body_utf8']), body)
        self.assertFalse(recorder.events[0]['response_omitted_credential_reflection'])
