"""Desired contract, adapted from the independently preserved original S1 probe."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from front import test_pipeline
from front.chat_service import send_chat_message
from front.evaluation import LedgerObserver
from front.evaluation_budget import EvaluationBudget
from front.models import CompanyEngine, EngineModel
from front.test_chat_flow import ChatFixture


class ObserverDestinationRevocationProbe(ChatFixture):
    def test_revocation_during_external_reservation_has_zero_sdk_transports(self):
        for kind in ('engine_inactive', 'model_inactive', 'credential_changed', 'unchanged'):
            with self.subTest(kind=kind):
                CompanyEngine.objects.filter(pk=self.credential.pk).update(active=True, api_key='synthetic-key')
                EngineModel.objects.filter(pk=self.model.pk).update(active=True, input_price='1', output_price='2')
                events, settled = [], []
                fixture = self

                class Observer:
                    def before_call(self, call):
                        if call['purpose'] == 'generation':
                            if kind == 'engine_inactive':
                                CompanyEngine.objects.filter(pk=fixture.credential.pk).update(active=False)
                            elif kind == 'model_inactive':
                                EngineModel.objects.filter(pk=fixture.model.pk).update(active=False)
                            elif kind == 'credential_changed':
                                CompanyEngine.objects.filter(pk=fixture.credential.pk).update(api_key='synthetic-new-key')
                        return 'synthetic-reserve'

                    def after_call(self, call, token):
                        settled.append(call)

                def transport(request):
                    credential = CompanyEngine.objects.get(pk=fixture.credential.pk)
                    model = EngineModel.objects.get(pk=fixture.model.pk)
                    events.append({'engine_active_at_transport': credential.active,
                                   'model_active_at_transport': model.active,
                                   'credential_matches_current': request.headers['Authorization'] == 'Bearer ' + credential.api_key})
                    return httpx.Response(200, json={'id': 'synthetic-review', 'object': 'chat.completion',
                        'created': 0, 'model': 'synthetic-v1',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Safe answer'},
                                     'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})

                with patch('front.connectors.OpenAIConnector.chat', test_pipeline.OPENAI_CHAT), \
                        patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
                            httpx.Client(transport=httpx.MockTransport(transport), **kwargs)):
                    result = send_chat_message(self.user, {'content': 'Synthetic review request'}, call_observer=Observer())
                generation = next(call for call in settled if call['purpose'] == 'generation')
                print('FOLLOWUP_PROBE ' + json.dumps({'mutation': kind, 'status': result.data['status'],
                    'error_type': result.data.get('error_type'), 'events': events,
                    'generation_status': generation['status'], 'generation_cost': generation['cost'],
                    'generation_cost_kind': generation['cost_kind']}, sort_keys=True))
                if kind == 'unchanged':
                    self.assertEqual(len(events), 1)
                    self.assertEqual(result.data['status'], 'completed')
                else:
                    self.assertEqual(events, [], 'No generation may start after revocation during its reservation')
                    self.assertEqual(result.data['status'], 'validation_error')
                    self.assertEqual(result.data['error_type'], 'authorization_changed')
                    self.assertNotIn('assistant_message', result.data)
                    self.assertEqual(generation['status'], 'not_started')
                    self.assertEqual(generation['cost'], '0')
                    self.assertEqual(generation['cost_kind'], 'not_incurred')
                    self.assertEqual(generation['cost_exposure_bound'], '0')
                    self.assertNotEqual(generation['cost_bound'], '0')

    def test_nonstarted_generation_releases_real_evaluation_ledger_reservation(self):
        EngineModel.objects.filter(pk=self.model.pk).update(input_price='1', output_price='2')
        fixture = self
        manifest = {'call_caps_usd': {'obfuscation': '0', 'generation': '.1'},
                    'model_versions': {'economy': 'synthetic-v1', 'strong': 'synthetic-v1'},
                    'allowed_effective_models': {'synthetic-v1': ['synthetic-v1']}}
        destinations = {'obfuscation': 'obfuscation:' + str(self.required_mask.pk),
                        'generation': 'engine:' + str(self.credential.pk)}

        class RevokingLedgerObserver(LedgerObserver):
            def before_call(self, call):
                token = super().before_call(call)
                if call['purpose'] == 'generation':
                    CompanyEngine.objects.filter(pk=fixture.credential.pk).update(active=False)
                return token

        with TemporaryDirectory() as directory:
            ledger = EvaluationBudget(Path(directory) / 'budget.sqlite3', '1')
            observer = RevokingLedgerObserver(ledger, manifest, destinations,
                case_id='independent-revocation', configuration='economy')
            result = send_chat_message(self.user, {'content': 'Synthetic ledger check'}, call_observer=observer)
            observer.finish()
            snapshot = ledger.snapshot()
            generation = next(call for call in snapshot['calls'] if call['purpose'] == 'generation')
            print('LEDGER_PROBE ' + json.dumps({'request_status': result.data['status'],
                'generation_status': generation['status'], 'reserved': generation['reserved'],
                'cost': generation['cost'], 'cost_kind': generation['metadata']['cost_kind'],
                'exposure': snapshot['budget_exposure_usd'], 'remaining': snapshot['remaining_usd']}, sort_keys=True))
            self.assertEqual(generation['status'], 'not_started')
            self.assertEqual(generation['cost'], '0')
            self.assertEqual(generation['metadata']['cost_kind'], 'not_incurred')
            self.assertNotEqual(generation['reserved'], '0')
            self.assertEqual(snapshot['budget_exposure_usd'], '0')
            self.assertEqual(snapshot['remaining_usd'], '1')
            self.provider.assert_not_called()
