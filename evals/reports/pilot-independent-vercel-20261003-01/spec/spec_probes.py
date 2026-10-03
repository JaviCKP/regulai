"""Independent Vercel specification probes: synthetic HTTP only, no credential bridge."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase
import requests

from front import evaluation, jev
from front.evaluation_budget import EvaluationBudget
from front.test_evaluation_pilot import VercelPilotTests

HERE = Path(__file__).resolve().parent


class GatewayBoundarySpec(VercelPilotTests):
    def test_timeout_retains_judge_reservation_and_stops_after_first_boundary(self):
        def timeout(method, url, **kwargs):
            self.assertEqual((method, url), ('post', jev.VERCEL_ENDPOINT))
            self.assert_reserved('classification')
            raise requests.ReadTimeout('Synthetic timeout without invoice')
        self.http.side_effect = timeout
        with self.assertRaises(CommandError):
            self.run_smoke('independent-timeout')
        snapshot = self.ledger()
        local = [call for call in snapshot['calls'] if call['metadata']['transport'] == 'local']
        remote = [call for call in snapshot['calls'] if call['metadata']['transport'] != 'local']
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0]['cost'], '0')
        self.assertEqual(len(remote), 1)
        self.assertEqual(remote[0]['purpose'], 'classification')
        self.assertIsNone(remote[0]['cost'])
        self.assertEqual(Decimal(remote[0]['reserved']), Decimal('.003'))
        self.assertIn(remote[0]['status'], ('failed', 'outcome_unknown'))
        self.assertEqual(Decimal(snapshot['budget_exposure_usd']), Decimal('.003'))
        self.assertEqual(Decimal(snapshot['uncertain_reservations_usd']), Decimal('.003'))
        self.assertEqual(self.http.call_count, 1)
        self.sdk.assert_not_called()
        self.socket.assert_not_called()
        (HERE / 'timeout-ledger.json').write_text(json.dumps(snapshot, indent=2), encoding='utf-8')

    def test_gateway_tariff_estimate_never_releases_conservative_reserve(self):
        original = self.requests_transport
        def without_invoice(method, url, **kwargs):
            response = original(method, url, **kwargs)
            body = response.json()
            for field in ('cost', 'gatewayCost', 'marketCost', 'surchargeCost'):
                body['providerMetadata']['gateway'].pop(field)
            response._content = json.dumps(body).encode()
            return response
        self.http.side_effect = without_invoice
        self.run_smoke('independent-no-invoice')
        snapshot = self.ledger()
        judges = [call for call in snapshot['calls'] if call['purpose'] in ('classification', 'verification')]
        self.assertEqual(len(judges), 6)
        for call in judges:
            self.assertEqual(call['metadata']['cost_kind'], 'tariff_estimate')
            self.assertEqual(Decimal(call['cost']), Decimal('.00001155'))
            self.assertEqual(Decimal(call['reserved']), Decimal('.003'))
            self.assertEqual(EvaluationBudget.exposure(call['reserved'], call['cost'], call['metadata']), Decimal('.003'))
        self.assertGreaterEqual(Decimal(snapshot['budget_exposure_usd']), Decimal('.018'))
        self.socket.assert_not_called()
        (HERE / 'estimate-ledger.json').write_text(json.dumps(snapshot, indent=2), encoding='utf-8')

    def test_approval_revoked_during_local_mask_prevents_gateway_and_generator(self):
        from front.local_masking import mask_local_texts
        def revoke_after_transform(texts, **kwargs):
            value = mask_local_texts(texts, **kwargs)
            revoked = deepcopy(self.approval)
            revoked['status'] = 'revoked'
            self.approval_path.write_text(json.dumps(revoked), encoding='utf-8')
            return value
        with patch('front.masking.mask_local_texts', side_effect=revoke_after_transform):
            with self.assertRaises(CommandError):
                self.run_smoke('independent-revocation')
        snapshot = self.ledger()
        self.assertEqual(len(snapshot['calls']), 1)
        self.assertEqual(snapshot['calls'][0]['metadata']['transport'], 'local')
        self.assertEqual(snapshot['known_cost_usd'], '0')
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        self.socket.assert_not_called()

    def test_only_two_exact_tuples_accepted_even_with_rebound_synthetic_approval(self):
        tuples = [(url, transport, model) for url in (jev.ENDPOINT, jev.VERCEL_ENDPOINT)
            for transport in ('typesafe', 'vercel') for model in ('jev-1.13.0', jev.VERCEL_MODEL)]
        tuples.extend((url, 'vercel', jev.VERCEL_MODEL) for url in (
            jev.VERCEL_ENDPOINT + '/', jev.VERCEL_ENDPOINT + '?x=1',
            jev.VERCEL_ENDPOINT.replace('https:', 'http:'),
            'https://ai-gateway.vercel.sh.attacker.invalid/typesafe/v1/systemone'))
        allowed = {(jev.ENDPOINT, 'typesafe', 'jev-1.13.0'), (jev.VERCEL_ENDPOINT, 'vercel', jev.VERCEL_MODEL)}
        observations = []
        for url, transport, model in tuples:
            self.manifest['destinations']['judge'] = url
            self.manifest['judge_transport'] = transport
            self.manifest['model_versions']['judge'] = model
            self.save_approval()
            report, _ = evaluation.preflight(self.manifest_path, self.approval_path)
            valid = (url, transport, model) in allowed
            self.assertEqual('pinned_judge_destination_required' not in report['blockers'], valid)
            self.assertEqual(report['ready_for_real'], valid, report['blockers'])
            observations.append({'tuple': [url, transport, model], 'ready': report['ready_for_real'], 'blockers': report['blockers']})
        self.assertFalse(self.ledger_path.exists())
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        self.socket.assert_not_called()
        (HERE / 'tuple-matrix.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')


class FrozenScopeSpec(SimpleTestCase):
    def test_actual_authorization_cannot_authorize_human_bank(self):
        root = evaluation.ROOT
        approval = root / 'evals/reports/pilot-real-vercel-20261003-01/authorization.json'
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No HTTP')) as http, \
                patch('socket.socket.connect', side_effect=AssertionError('No socket')) as sock, \
                patch('socket.getaddrinfo', side_effect=AssertionError('No DNS')) as dns, \
                patch.object(evaluation, 'EvaluationBudget', side_effect=AssertionError('No ledger')) as ledger:
            report, _ = evaluation.preflight(root / 'evals/pilot-human/manifest.json', approval,
                now=datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc), check_credentials=False)
        self.assertFalse(report['ready_for_real'])
        self.assertIn('authorization_manifest_mismatch', report['blockers'])
        self.assertIn('reserved_evaluation_not_approved', report['blockers'])
        self.assertIn('independent_reference_review_required', report['blockers'])
        for guard in (http, sock, dns, ledger):
            guard.assert_not_called()
        (HERE / 'human-bank-denied.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    def test_gateway_manifest_keeps_all_execution_and_quality_controls(self):
        root = evaluation.ROOT
        direct = evaluation.read_json(root / 'evals/pilot-real/manifest.json')
        gateway, cases = evaluation.load_pilot(root / 'evals/pilot-real/manifest-vercel.json')
        allowed_changes = {'judge_transport', 'destinations', 'model_versions', 'published_versions',
            'allowed_effective_models', 'mutable_model_aliases', 'pricing_sources', 'source_sha256',
            'runtime_versions', 'masking', 'authorization_id', 'gateway_scope'}
        unexpected = [key for key in direct.keys() | gateway.keys()
            if direct.get(key) != gateway.get(key) and key not in allowed_changes]
        self.assertEqual(unexpected, [])
        self.assertEqual(len(cases), 8)
        self.assertEqual(gateway['configurations'], ['economy', 'strong', 'router'])
        self.assertEqual(gateway['maximum_usd'], '1.00')
        self.assertEqual(gateway['masking'], direct['masking'])
        self.assertEqual(gateway['runtime_versions'], direct['runtime_versions'])
        self.assertEqual(gateway['model_versions']['economy'], direct['model_versions']['economy'])
        self.assertEqual(gateway['model_versions']['strong'], direct['model_versions']['strong'])
        approval = evaluation.read_json(root / 'evals/reports/pilot-real-vercel-20261003-01/authorization.json')
        manifest_hash = evaluation.digest((root / 'evals/pilot-real/manifest-vercel.json').read_bytes())
        self.assertEqual(approval['manifest_sha256s'], [manifest_hash])
        self.assertFalse(approval['reserved_evaluation'])
