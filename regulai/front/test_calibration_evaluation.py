"""Synthetic capture/metric contracts without a provider connection."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from .evaluation import (SyntheticPayloadRecorder, adjudicate_calibration_answer,
                         calibration_case_metrics, digest, load_pilot, summarize_calibration)
from .evaluation_budget import BudgetExceeded


class CalibrationCaptureTests(SimpleTestCase):
    def setUp(self):
        self.network = patch('socket.socket.connect', side_effect=AssertionError('No network in capture tests'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_capture_requires_explicit_synthetic_scope(self):
        for value in (False, None, 'true'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SyntheticPayloadRecorder(synthetic=value, configuration={})

    def test_httpx_records_final_body_roles_response_and_key_without_headers(self):
        import httpx
        raw = b'{"model":"synthetic-model","messages":[{"role":"user","content":"masked"}],"max_tokens":8}'
        def reply(request):
            self.assertEqual(request.content, raw)
            return httpx.Response(200, json={'choices': [{'message': {'content': 'result'}}]})
        with httpx.Client(transport=httpx.MockTransport(reply)) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={'rubric_version': 'v1'}) as recorder:
                with recorder.scope(case_id='case-one', configuration='economy'):
                    response = client.post('https://api.deepseek.com/chat/completions', content=raw,
                        headers={'Authorization': 'Bearer do-not-record-header'})
        event = recorder.events[0]
        self.assertEqual(event['body_utf8'].encode(), raw)
        self.assertEqual(event['body_sha256'], digest(raw))
        self.assertEqual(event['roles'], ['user'])
        self.assertEqual(event['case_id'], 'case-one')
        self.assertTrue(event['response_complete'])
        self.assertEqual(event['response_sha256'], digest(response.content))
        self.assertNotIn('do-not-record-header', json.dumps(event))
        self.assertNotIn('Authorization', json.dumps(event))

    def test_requests_stream_capture_keeps_judge_rubric_and_does_not_read_ahead(self):
        import requests
        payload = {'model': 'typesafe-ai/jev', 'state': {'request': 'after masking'},
                   'questions': {'category': {'type': 'choice', 'criteria': ['internal']}}}
        reads = []
        def send(adapter, request, **kwargs):
            response = requests.Response()
            response.status_code, response._content_consumed = 200, True
            response.close = lambda: None
            def chunks(*args, **options):
                reads.append('consumer-read')
                yield b'{"answers":{}}'
            response.iter_content = chunks
            return response
        with patch('requests.adapters.HTTPAdapter.send', send):
            with SyntheticPayloadRecorder(synthetic=True, configuration={}) as recorder:
                response = requests.post('https://ai-gateway.vercel.sh/typesafe/v1/systemone',
                    data=json.dumps(payload).encode(), stream=True, headers={'Authorization': 'never-captured'})
                self.assertEqual(reads, [])
                self.assertEqual(b''.join(response.iter_content(8192)), b'{"answers":{}}')
                response.close()
        event = recorder.events[0]
        self.assertEqual(event['purpose'], 'classification')
        self.assertEqual(event['rubric'], payload['questions'])
        self.assertTrue(event['response_complete'])
        self.assertNotIn('never-captured', json.dumps(event))

    def test_guard_applies_to_each_generation_and_runs_before_transport(self):
        import httpx
        sent, guarded = [], []
        def guard(event):
            guarded.append(event['body_sha256'])
            if event['body_bytes'] > 100:
                raise BudgetExceeded('oversize')
        def send(request):
            sent.append(request.content)
            return httpx.Response(200, json={})
        with httpx.Client(transport=httpx.MockTransport(send)) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, request_guard=guard) as recorder:
                client.post('https://api.deepseek.com/chat/completions', json={'model': 'a', 'messages': []})
                with self.assertRaises(BudgetExceeded):
                    client.post('https://api.deepseek.com/chat/completions',
                                json={'model': 'a', 'messages': [{'role': 'user', 'content': 'x' * 120}]})
        self.assertEqual((len(guarded), len(sent), len(recorder.events)), (2, 1, 2))
        self.assertFalse(recorder.events[1]['transport_started'])
        self.assertEqual(recorder.events[1]['error_type'], 'BudgetExceeded')

    def test_reflected_credentials_are_omitted_and_never_serialized(self):
        import httpx
        secret = 'synthetic-test-header-secret'
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
                json={'error': secret}))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, forbidden_secrets=(secret,)) as recorder:
                client.post('https://api.deepseek.com/chat/completions', json={'model': 'a', 'messages': []})
                with self.assertRaises(BudgetExceeded):
                    client.post('https://api.deepseek.com/chat/completions', json={'model': 'a',
                        'messages': [{'role': 'user', 'content': secret}]})
        self.assertNotIn(secret, json.dumps(recorder.events))
        self.assertTrue(recorder.events[0]['response_omitted_credential_reflection'])
        self.assertIsNone(recorder.events[0]['response_body_utf8'])

    def test_unknown_fields_and_unapproved_destinations_fail_before_capture(self):
        import httpx
        with httpx.Client(transport=httpx.MockTransport(lambda request: self.fail('No transport expected'))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}) as recorder:
                for url, data in [('https://api.deepseek.com/chat/completions', {'api_key': 'secret'}),
                                  ('https://api.typesafe.ai/v1', {'model': 'jev'})]:
                    with self.assertRaises(BudgetExceeded):
                        client.post(url, json=data)
        self.assertEqual(recorder.events, [])

    def test_response_over_limit_is_hashed_and_omitted_without_truncation_claim(self):
        import httpx
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 50))) as client:
            with SyntheticPayloadRecorder(synthetic=True, configuration={}, max_response_bytes=10) as recorder:
                client.post('https://api.deepseek.com/chat/completions', json={'model': 'a', 'messages': []})
        event = recorder.events[0]
        self.assertIsNone(event['response_body_utf8'])
        self.assertTrue(event['response_complete'])
        self.assertTrue(event['response_omitted_over_limit'])
        self.assertEqual(event['response_sha256'], digest(b'x' * 50))

    def test_replay_key_changes_for_context_rubric_and_configuration(self):
        import httpx
        keys = []
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))) as client:
            for config, state, question in [('a', 'context', 'v1'), ('b', 'context', 'v1'),
                                            ('a', 'different', 'v1'), ('a', 'context', 'v2')]:
                with SyntheticPayloadRecorder(synthetic=True, configuration={'version': config}) as recorder:
                    client.post('https://ai-gateway.vercel.sh/typesafe/v1/systemone', json={
                        'model': 'typesafe-ai/jev', 'state': state, 'questions': {'rubric': question}})
                keys.append(recorder.events[0]['replay_key'])
        self.assertEqual(len(set(keys)), 4)


class CalibrationMetricsTests(SimpleTestCase):
    def test_validation_partition_is_preserved_by_existing_pilot_loader(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            data = json.dumps({'id': 'validation-one', 'split': 'validation', 'input': 'Synthetic input'}) + '\n'
            (folder / 'cases.jsonl').write_text(data, encoding='utf-8')
            (folder / 'rubric.md').write_text('Synthetic rubric', encoding='utf-8')
            manifest = {'bank_kind': 'pilot', 'configurations': ['economy', 'strong', 'router'],
                'dataset': 'cases.jsonl', 'dataset_sha256': digest((folder / 'cases.jsonl').read_bytes()),
                'human_rubric': 'rubric.md', 'human_rubric_sha256': digest((folder / 'rubric.md').read_bytes()),
                'input_limit_bytes': 1024}
            (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            _, cases = load_pilot(folder / 'manifest.json')
            self.assertEqual(cases[0]['split'], 'validation')

    def case(self, identity='one'):
        return {'id': identity, 'family_id': 'shared-family', 'category': 'calculation',
                'expected_action': 'respond', 'oracle': {'kind': 'numeric', 'value': '42'}}

    def row(self, **changes):
        return {'mode': 'real', 'configuration': 'economy', 'execution_state': 'completed',
                'delivered': True, 'answer': '42', 'latency_ms': 12, 'calls': [{
                    'purpose': 'generation', 'status': 'completed', 'reserved': '.03', 'cost': '.02',
                    'metadata': {'transport': 'http', 'cost_kind': 'tariff_estimate',
                                 'input_tokens': 20, 'output_tokens': 2}}], **changes}

    def test_withheld_correct_generation_is_not_correct_delivered_and_its_cost_counts(self):
        delivered = calibration_case_metrics(self.case(), self.row())
        withheld = calibration_case_metrics(self.case('two'), self.row(delivered=False, answer=None,
            execution_state='failed', generation_responses=[{'content': '42', 'content_sha256': 'correct'}]))
        self.assertEqual(withheld['retained_response_correctness'], [True])
        self.assertFalse(withheld['correct_delivered'])
        summary = summarize_calibration([delivered, withheld])[0]
        self.assertEqual(summary['families_n'], 1)
        self.assertEqual(summary['correct_delivered'], {'n': 2, 'true': 1, 'rate': .5})
        self.assertEqual(summary['cost_per_correct_estimated_usd'], '0.04')
        self.assertEqual(summary['exposure_usd'], '0.06')

    def test_unknown_cost_and_unresolved_oracles_are_not_zero_or_correct(self):
        row = self.row(calls=[{'purpose': 'generation', 'reserved': '.1', 'cost': None,
            'status': 'outcome_unknown', 'metadata': {'transport': 'http', 'cost_kind': 'unknown'}}])
        metrics = calibration_case_metrics(self.case(), row)
        self.assertEqual(metrics['uncertain_reserved_usd'], '0.1')
        self.assertIsNone(summarize_calibration([metrics])[0]['cost_per_correct_estimated_usd'])
        unresolved = calibration_case_metrics({**self.case(), 'oracle': {'kind': 'manual'}}, row)
        self.assertIsNone(unresolved['correct_delivered'])
        self.assertIsNone(unresolved['entity_precision'])

    def test_offline_fixtures_never_measure_semantics_and_empty_aggregates_are_valid(self):
        metrics = calibration_case_metrics(self.case(), self.row(mode='simulated'))
        self.assertIsNone(metrics['correct_delivered'])
        self.assertFalse(metrics['semantic_quality_measured'])
        self.assertEqual(summarize_calibration([]), [])

    def test_contains_reference_is_presence_only_and_cannot_certify_correctness(self):
        case = {**self.case(), 'oracle': {'kind': 'contains', 'required': ['23']}}
        for answer in ('230', 'no 23 sino 99'):
            metrics = calibration_case_metrics(case, self.row(answer=answer))
            self.assertTrue(metrics['required_content_present'])
            self.assertIsNone(metrics['correct_delivered'])
            self.assertFalse(metrics['reference_evaluable'])
            self.assertIsNone(summarize_calibration([metrics])[0]['cost_per_correct_estimated_usd'])

    def test_numeric_oracle_has_no_eval_or_tolerance_and_p95_reports_n(self):
        oracle = {'kind': 'numeric', 'value': '0.3'}
        self.assertTrue(adjudicate_calibration_answer(oracle, '0,3'))
        self.assertFalse(adjudicate_calibration_answer(oracle, '0.30000000000000004'))
        for value in ('eval(1)', '0.1+0.2', 'NaN', 'The answer is 0.3'):
            self.assertIsNone(adjudicate_calibration_answer(oracle, value))
        metrics = [calibration_case_metrics(self.case(str(index)), self.row(latency_ms=index)) for index in range(1, 21)]
        summary = summarize_calibration(metrics)[0]
        self.assertEqual((summary['latency_n'], summary['p50_latency_ms'], summary['p95_latency_ms']), (20, 10.5, 19))
