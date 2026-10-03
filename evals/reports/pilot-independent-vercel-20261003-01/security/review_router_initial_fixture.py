"""Independently force failed verification at the Gateway transport boundary."""
from collections import Counter
import json

from review_cases import GatewaySecurityChecks, HERE


class GatewayRouterChecks(GatewaySecurityChecks):
    def requests_transport(self, method, url, **kwargs):
        response = super().requests_transport(method, url, **kwargs)
        payload = json.loads(response.content)
        for answer in payload['answers'].values():
            if answer['type'] == 'noul':
                answer['noul'] = 1.0
        response._content = json.dumps(payload).encode()
        return response

    def test_repeated_negative_gateway_verdict_allows_only_two_router_generations(self):
        self.run_smoke('negative-verification')
        ledger = self.ledger()
        generations = [call for call in ledger['calls'] if call['purpose'] == 'generation']
        counts = Counter(call['metadata']['configuration'] for call in generations)
        self.assertEqual(counts, {'economy': 1, 'strong': 1, 'router': 2})
        self.assertEqual(len(self.generation_payloads), 4)
        self.assertEqual(len(self.gateway_calls), 7)
        self.assertTrue(all('models' not in call['body'] for call in self.gateway_calls))
        router_models = [call['metadata']['model'] for call in generations
                         if call['metadata']['configuration'] == 'router']
        self.assertEqual(router_models, [self.manifest['model_versions']['economy'],
                                         self.manifest['model_versions']['strong']])
        (HERE / 'gateway-router-capture.json').write_text(json.dumps({
            'generation_counts_by_configuration': counts, 'router_models': router_models,
            'gateway_calls': self.gateway_calls, 'ledger': ledger}, indent=2), encoding='utf-8')
