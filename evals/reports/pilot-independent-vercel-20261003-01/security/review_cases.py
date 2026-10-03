"""Independent gateway-boundary tests with synthetic credentials and responses."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import requests
from django.core.management.base import CommandError

from front import evaluation, test_smoke

HERE = Path(__file__).resolve().parent
GATEWAY = 'https://ai-gateway.vercel.sh/typesafe/v1/systemone'
DIRECT = 'https://api.typesafe.ai/v1/systemone'


class GatewaySecurityChecks(test_smoke.SmokeIsolationTests):
    def setUp(self):
        self.gateway_calls = []
        self.gateway_failure = False
        super().setUp()
        self.use_local_mask()
        self.manifest['destinations']['judge'] = GATEWAY
        self.manifest['judge_transport'] = 'vercel'
        self.manifest['model_versions']['judge'] = 'typesafe-ai/jev'
        self.manifest['allowed_effective_models']['typesafe-ai/jev'] = ['typesafe-ai/jev']
        self.manifest['mutable_model_aliases'].append('typesafe-ai/jev')
        self.approval['destinations'] = deepcopy(self.manifest['destinations'])
        self.save_approval()

    def requests_transport(self, method, url, **kwargs):
        self.assertEqual(method.lower(), 'post')
        self.assertEqual(url, GATEWAY)
        self.assertFalse(kwargs['allow_redirects'])
        body = json.loads(kwargs['data'])
        self.assertEqual(body['model'], 'typesafe-ai/jev')
        self.assertEqual(body['providerOptions'], {'gateway': {'only': ['typesafe-ai']}})
        self.assertNotIn('hidden.person@example.invalid', json.dumps(body))
        purpose = 'classification' if 'category' in body['questions'] else 'verification'
        self.assert_reserved(purpose)
        self.gateway_calls.append({'purpose': purpose, 'url': url, 'body': body})
        if self.gateway_failure:
            raise requests.Timeout('synthetic gateway timeout')
        answers = {}
        for key, question in body['questions'].items():
            if question['type'] == 'choice':
                chosen = {'category': 'public', 'task': 'general', 'difficulty': 'economy'}[key]
                answers[key] = {'type': 'choice', 'choice': chosen, 'confidence': 1.0,
                    'probabilities': {value: float(value == chosen) for value in question['criteria']}}
            else:
                answers[key] = {'type': 'noul', 'noul': 0.0}
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'model': 'typesafe-ai/jev', 'answers': answers,
            'usage': {'input_tokens': 50, 'output_tokens': 10},
            'providerMetadata': {'gateway': {'cost': '0.001', 'routing': {
                'originalModelId': 'typesafe-ai/jev', 'resolvedProvider': 'typesafe-ai', 'finalProvider': 'typesafe-ai'}}}}).encode()
        response._content_consumed = True
        return response

    def test_exact_gateway_tuple_uses_only_approved_provider_and_shared_ledger(self):
        self.case['input'] = 'Devuelve 4. Contacto hidden.person@example.invalid.'
        (self.root / 'cases.jsonl').write_text(json.dumps(self.case) + '\n', encoding='utf-8')
        self.manifest['dataset_sha256'] = evaluation.digest((self.root / 'cases.jsonl').read_bytes())
        self.save_approval()
        self.run_smoke('vercel-allowed')
        self.assertEqual(len(self.gateway_calls), 6)
        self.assertEqual(len(self.generation_payloads), 3)
        for payload in self.generation_payloads:
            self.assertNotIn('hidden.person@example.invalid', json.dumps(payload))
        ledger = self.ledger()
        self.assertEqual(ledger['cap_usd'], '1.00')
        self.assertLessEqual(Decimal(ledger['budget_exposure_usd']), Decimal('1'))
        calls = ledger['calls']
        local = [call for call in calls if call['metadata']['transport'] == 'local']
        self.assertEqual(len(local), 6)
        self.assertTrue(all(call['reserved'] == '0' and call['cost'] == '0' for call in local))
        judges = [call for call in calls if call['purpose'] in ('classification', 'verification')]
        self.assertTrue(all(call['metadata']['cost_kind'] == 'provider_reported' and call['cost'] == '0.001' for call in judges))
        (HERE / 'gateway-approved-capture.json').write_text(json.dumps({'calls': self.gateway_calls,
            'generation_count': len(self.generation_payloads), 'ledger': ledger}, indent=2), encoding='utf-8')

    def test_crossed_tuple_and_host_variants_cannot_reach_any_provider(self):
        original = deepcopy(self.manifest)
        original_approval = deepcopy(self.approval)
        rejected = []
        for destination, transport, model in [
                (GATEWAY, 'typesafe', 'jev-1.13.0'), (DIRECT, 'vercel', 'typesafe-ai/jev'),
                (GATEWAY, 'vercel', 'jev-1.13.0'), (DIRECT, 'typesafe', 'jev-latest'),
                (GATEWAY + '/', 'vercel', 'typesafe-ai/jev'),
                ('https://ai-gateway.vercel.sh.attacker.invalid/typesafe/v1/systemone', 'vercel', 'typesafe-ai/jev')]:
            self.manifest = deepcopy(original)
            self.approval = deepcopy(original_approval)
            self.manifest['destinations']['judge'] = destination
            self.manifest['judge_transport'] = transport
            self.manifest['model_versions']['judge'] = model
            self.approval['destinations'] = deepcopy(self.manifest['destinations'])
            self.save_approval()
            report, _ = evaluation.preflight(self.manifest_path, self.approval_path, check_credentials=False)
            self.assertFalse(report['ready_for_real'])
            rejected.append({'destination': destination, 'transport': transport, 'model': model, 'blockers': report['blockers']})
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        self.assertFalse(self.ledger_path.exists())
        (HERE / 'tuple-rejections.json').write_text(json.dumps(rejected, indent=2), encoding='utf-8')

    def test_gateway_timeout_retains_reservation_without_direct_or_model_fallback(self):
        self.gateway_failure = True
        with self.assertRaises(CommandError):
            self.run_smoke('gateway-timeout')
        ledger = self.ledger()
        self.assertEqual(len(self.gateway_calls), 1)
        self.assertEqual(self.generation_payloads, [])
        uncertain = [call for call in ledger['calls'] if call['status'] == 'outcome_unknown']
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(uncertain[0]['purpose'], 'classification')
        self.assertIsNone(uncertain[0]['cost'])
        self.assertEqual(Decimal(ledger['budget_exposure_usd']), Decimal(uncertain[0]['reserved']))
        self.assertGreater(Decimal(ledger['budget_exposure_usd']), 0)
        (HERE / 'gateway-timeout-capture.json').write_text(json.dumps({'calls': self.gateway_calls, 'ledger': ledger}, indent=2), encoding='utf-8')
