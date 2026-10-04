"""Reviewer-owned deterministic probes. Every secret and request is synthetic."""
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from threading import Event

import httpx
import requests
from django.test import SimpleTestCase, TestCase
from unittest.mock import patch

from front.evaluation import SyntheticPayloadRecorder
from front import evaluation
from front.evaluation_budget import BudgetExceeded, EvaluationBudget
from front.models import Engine, EngineModel


SYNTHETIC_SECRET = 'review-only-do-not-persist-credential'


def escaped_json(value):
    return ('{"error":"' + ''.join('\\u%04x' % ord(char) for char in value) + '"}').encode()


class CredentialCaptureProbes(SimpleTestCase):
    def test_httpx_unescaped_reflection_is_omitted_control(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, json={'error': SYNTHETIC_SECRET}))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={},
                    forbidden_secrets=(SYNTHETIC_SECRET,)) as recorder:
                client.post('https://api.deepseek.com/chat/completions', json={'model': 'a', 'messages': []})
        self.assertIsNone(recorder.events[0]['response_body_utf8'])

    def test_httpx_unicode_escaped_reflection_is_not_persisted(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, content=escaped_json(SYNTHETIC_SECRET)))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={},
                    forbidden_secrets=(SYNTHETIC_SECRET,)) as recorder:
                client.post('https://api.deepseek.com/chat/completions', json={'model': 'a', 'messages': []})
        event = recorder.events[0]
        self.assertIsNone(event['response_body_utf8'], 'Reflected credential survives reversible JSON escaping')

    def test_requests_unicode_escaped_reflection_is_not_persisted(self):
        def fake_send(adapter, request, **kwargs):
            response = requests.Response()
            response.status_code, response._content_consumed = 200, True
            response.close = lambda: None
            response.iter_content = lambda *args, **kwargs: iter([escaped_json(SYNTHETIC_SECRET)])
            return response
        with patch('requests.adapters.HTTPAdapter.send', fake_send):
            with SyntheticPayloadRecorder(synthetic=True, configuration={},
                    forbidden_secrets=(SYNTHETIC_SECRET,)) as recorder:
                response = requests.post('https://ai-gateway.vercel.sh/typesafe/v1/systemone',
                    json={'model': 'typesafe-ai/jev', 'state': {}, 'questions': {}}, stream=True)
                b''.join(response.iter_content(8192))
                response.close()
        self.assertIsNone(recorder.events[0]['response_body_utf8'],
            'Reflected credential survives reversible JSON escaping at requests boundary')

    def test_guard_does_not_persist_a_unicode_escaped_request_credential(self):
        encoded = ''.join('\\u%04x' % ord(char) for char in SYNTHETIC_SECRET)
        body = ('{"model":"a","messages":[{"role":"user","content":"' + encoded + '"}]}').encode()
        reached = []
        with httpx.Client(transport=httpx.MockTransport(lambda request:
                reached.append(request) or httpx.Response(200, json={}))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={},
                    forbidden_secrets=(SYNTHETIC_SECRET,)) as recorder:
                try:
                    client.post('https://api.deepseek.com/chat/completions', content=body)
                except ValueError:
                    pass
        self.assertEqual(len(reached), 0, 'Escaped credential reached provider despite forbidden_secrets')
        self.assertEqual(recorder.events, [])


class FullFlowCredentialReflectionProbe(TestCase):
    def test_reflected_credential_is_absent_from_generation_response_and_ledger(self):
        repo = Path(__file__).resolve().parents[5]
        manifest = json.loads(subprocess.check_output(['rtk', 'proxy', 'git', 'show',
            '4fdbe1a:evals/adversarial-live/community-additional-20261003/manifest.json'], cwd=repo))
        manifest['price_date'] = date.today().isoformat()
        secret = 'sk-reviewonlysyntheticcredential12345'
        case = {'id': 'review-reflection', 'input': 'Calcula 2 + 2.', 'task': 'general',
            'difficulty': 'economy', 'split': 'development', 'group': 'arithmetic', 'must_block': False}
        engine = Engine.objects.create(name='Reviewer synthetic engine', connector_type='openai_compatible',
            base_url=manifest['destinations']['generation'])
        models = {level: EngineModel.objects.create(engine=engine, name=level,
            model_id=manifest['model_versions'][level], context_window=manifest['context_window'],
            max_tokens=512, supports_json=True,
            input_price=Decimal(manifest['prices_per_million'][level]['input']),
            output_price=Decimal(manifest['prices_per_million'][level]['output']), price_date=date.today())
            for level in ('economy', 'strong')}
        def judge_send(adapter, request, **kwargs):
            body = json.loads(request.body)
            answers = {}
            for key, question in body['questions'].items():
                if question['type'] == 'choice':
                    chosen = {'category': 'public', 'task': 'general', 'difficulty': 'economy'}[key]
                    answers[key] = {'type': 'choice', 'choice': chosen, 'confidence': 1.0,
                        'probabilities': {option: float(option == chosen) for option in question['criteria']}}
                else:
                    answers[key] = {'type': 'noul', 'noul': 0.0}
            response = requests.Response()
            response.status_code, response._content_consumed = 200, True
            response._content = json.dumps({'model': body['model'], 'answers': answers,
                'usage': {'input_tokens': 100, 'output_tokens': 20}}).encode()
            return response
        def generator_send(request):
            body = json.loads(request.content)
            return httpx.Response(200, json={'id': secret, 'object': 'chat.completion', 'created': 0,
                'model': body['model'], 'choices': [{'index': 0,
                    'message': {'role': 'assistant', 'content': secret}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
                'REGULAI_EVAL_GENERATOR_KEY': secret, 'REGULAI_EVAL_JEV_KEY': 'review-synthetic-judge'}), \
             patch('requests.adapters.HTTPAdapter.send', judge_send), \
             patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
                httpx.Client(transport=httpx.MockTransport(generator_send), **kwargs)):
            ledger = EvaluationBudget(Path(directory) / 'synthetic-ledger.sqlite3', '1.00')
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(secret,)) as recorder:
                row = evaluation.exercise_case(case, 'economy', manifest, engine, models, ledger, real=True)
            event = next(item for item in recorder.events if item['purpose'] == 'generation')
            self.assertTrue(event['response_omitted_credential_reflection'])
            findings = {
                'wire_response_omitted': event['response_body_utf8'] is None,
                'retained_response_contains_secret': secret in json.dumps(row['generation_responses']),
                'ledger_contains_secret': secret in json.dumps(ledger.snapshot()),
                'delivered_answer_contains_secret': secret in str(row.get('answer')),
                'generation_calls': row['generation_calls'],
            }
            reviewed_commit = evaluation.ROOT.name.removeprefix('snapshot-')
            evidence = Path(__file__).with_name(reviewed_commit + '-reflection-observed.json')
            with evidence.open('x', encoding='utf-8') as output:
                output.write(json.dumps(findings, indent=2) + '\n')
            self.assertFalse(findings['retained_response_contains_secret'], findings)
            self.assertFalse(findings['ledger_contains_secret'], findings)


class TransportControlProbes(SimpleTestCase):
    def test_openai_sdk_503_causes_one_transport_attempt(self):
        from front.connectors import ChatMessage, OpenAIConnector
        from openai import APIStatusError
        calls = []
        def send(request):
            calls.append(request)
            return httpx.Response(503, json={'error': {'message': 'Synthetic service unavailable'}})
        with patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
                httpx.Client(transport=httpx.MockTransport(send), **kwargs)):
            connector = OpenAIConnector(api_key='review-synthetic', base_url='https://api.deepseek.com')
            try:
                with SyntheticPayloadRecorder(synthetic=True, configuration={}) as recorder:
                    with self.assertRaises(APIStatusError):
                        connector.chat([ChatMessage(role='user', content='Public synthetic text')],
                            model='deepseek-flash', max_tokens=8)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(recorder.events), 1)
            finally:
                connector.client.close()

    def test_second_concurrent_httpx_transport_is_rejected(self):
        first_started, release_first = Event(), Event()
        calls = []
        def send(request):
            calls.append(request)
            first_started.set()
            if not release_first.wait(3):
                raise AssertionError('Synthetic review synchronization timeout')
            return httpx.Response(200, json={})
        with httpx.Client(transport=httpx.MockTransport(send)) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}) as recorder:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    first = pool.submit(client.post, 'https://api.deepseek.com/chat/completions',
                        json={'model': 'deepseek-flash', 'messages': []})
                    try:
                        self.assertTrue(first_started.wait(3))
                        with self.assertRaises(BudgetExceeded):
                            client.post('https://api.deepseek.com/chat/completions',
                                json={'model': 'deepseek-flash', 'messages': []})
                    finally:
                        release_first.set()
                    self.assertEqual(first.result(timeout=3).status_code, 200)
                self.assertEqual(len(calls), 1)
                self.assertFalse(recorder.events[-1]['transport_started'])

    def test_direct_typesafe_destination_never_reaches_transport(self):
        reached = []
        with httpx.Client(transport=httpx.MockTransport(lambda request:
                reached.append(request) or httpx.Response(200, json={}))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}):
                with self.assertRaises(BudgetExceeded):
                    client.post('https://api.typesafe.ai/v1/systemone',
                        json={'model': 'jev-1.13.0', 'state': {}, 'questions': {}})
        self.assertEqual(reached, [])
