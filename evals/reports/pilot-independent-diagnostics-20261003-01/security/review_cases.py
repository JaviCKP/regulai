"""Independent diagnostics probes through HTTP and the synthetic pilot ledger."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import patch
import uuid

import requests
from django.core.cache import cache
from django.core.management.base import CommandError
from django.test import TestCase

from front import jev, test_chat_flow
from front.models import Prompt
from front.test_pipeline import jev_http
from front.test_smoke import SmokeHarness

HERE = Path(__file__).resolve().parent
RUN = sys.argv[2]
SECRET = 'SYNTHETIC_PRIVATE_CAUSE_7AF15E'
KEY = 'synthetic-diagnostics-review-credential'
PATHS = ('/chat/send/', '/api/chat/send/', '/chat/')


def failure(kind):
    if kind == 'read-timeout':
        raise requests.ReadTimeout(SECRET + KEY)
    if kind == 'connect-timeout':
        raise requests.ConnectTimeout(SECRET + KEY)
    response = requests.Response()
    response.status_code = int(kind[5:]) if kind.startswith('http-') else 200
    response.reason = SECRET
    response.headers['x-error-detail'] = SECRET + KEY
    response._content = ('{"detail": "' + SECRET + KEY).encode()
    response._content_consumed = True
    return response


class HostileString(str):
    def __str__(self):
        return SECRET + KEY


class HttpDiagnosticsChecks(test_chat_flow.ChatFixture):
    def setUp(self):
        super().setUp()
        self.required_mask.backend, self.required_mask.api_url = 'local', ''
        self.required_mask.save()
        self.model.supports_json = True
        self.model.input_price, self.model.output_price = Decimal('.30'), Decimal('1.20')
        self.model.save()
        self.company.jev_api_key = KEY
        self.company.ai_config.update(classification='required',
            jev={'transport': 'vercel', 'model': jev.VERCEL_MODEL,
                 'input_price': '.042', 'output_price': '0', 'max_call_cost': '.003'},
            verification={'mode': 'enforce', 'threshold': .8}, limits={'budget': '1'})
        self.company.ai_config['destinations']['internal'].append('jev')
        self.company.save()
        self.stage, self.kind, self.injected = 'classification', 'read-timeout', None
        self.http.side_effect = self.transport

    def transport(self, url, *, data=None, **kwargs):
        self.assertEqual(url, jev.VERCEL_ENDPOINT)
        self.assertFalse(kwargs['allow_redirects'])
        body = json.loads(data)
        self.assertEqual(body['providerOptions'], {'gateway': {'only': ['typesafe-ai']}})
        stage = 'classification' if 'category' in body['questions'] else 'verification'
        if stage == self.stage:
            if self.injected is not None:
                raise self.injected
            return failure(self.kind)
        return jev_http()(url, data=data, **kwargs)

    def test_classification_matrix_and_duplicate_request_preserve_public_state(self):
        observed = []
        for kind, uncertain in [('connect-timeout', False), ('read-timeout', True),
                                ('http-403', False), ('http-503', True),
                                ('http-599', True), ('malformed-json', True)]:
            self.kind = kind
            for path in PATHS:
                with self.subTest(kind=kind, path=path):
                    # Each fault is an independent request/replay scenario, not a load test.
                    cache.clear()
                    request_id = str(uuid.uuid4())
                    before = self.http.call_count
                    with self.assertLogs('front.chat_service', level='WARNING') as logged:
                        response = self.send(path, request_id=request_id)
                    data = response.json()
                    call = data['receipt']['calls'][-1]
                    expected_status = 'outcome_unknown' if uncertain else 'failed'
                    self.assertEqual((response.status_code, data['status'], data['error_type']),
                        (504 if uncertain else 502, expected_status, 'security_check_failed'))
                    self.assertEqual((call['purpose'], call['status'], call['cost'], call['cost_bound'], call['cost_kind']),
                        ('classification', expected_status, None, '0.003', 'unknown'))
                    saved = Prompt.objects.get(user=self.user, request_id=request_id)
                    self.assertEqual(saved.decision['calls'][-1], call)
                    repeated = self.send(path, request_id=request_id).json()
                    self.assertEqual(repeated['receipt']['calls'], data['receipt']['calls'])
                    self.assertEqual(self.http.call_count, before + 1)
                    public = json.dumps([data, saved.decision, logged.output], ensure_ascii=False)
                    self.assertNotIn(SECRET, public)
                    self.assertNotIn(KEY, public)
                    normalized = {key: call[key] for key in ('purpose', 'status', 'cost', 'cost_bound', 'cost_kind', 'transport')}
                    observed.append({'fault': kind, 'path': path, 'http_status': response.status_code,
                        'status': data['status'], 'error_type': data['error_type'], 'call': normalized,
                        'provider_error_code': call.get('provider_error_code'), 'new_provider_requests': self.http.call_count - before})
        self.provider.assert_not_called()
        (HERE / (RUN + '-http-matrix.json')).write_text(json.dumps(observed, indent=2), encoding='utf-8')

    def test_adversarial_codes_never_enter_receipts_saved_decisions_or_log_records(self):
        values = [SECRET + KEY + '\r\nhttp_503', HostileString('timeout'), {'cause': SECRET + KEY},
                  [SECRET], (SECRET,), b'timeout', 503, None, 'http_200', 'http_599', 'http_503\x00' + SECRET]
        observed = []
        for stage in ('classification', 'verification'):
            self.stage = stage
            for index, value in enumerate(values):
                with self.subTest(stage=stage, kind=type(value).__name__, index=index):
                    self.injected = jev.JevError(value, outcome_unknown=True)
                    path = PATHS[index % len(PATHS)]
                    with self.assertLogs('front.chat_service', level='WARNING') as logged:
                        data = self.send(path).json()
                    call = data['receipt']['calls'][-1]
                    self.assertEqual(call['purpose'], stage)
                    self.assertEqual(call.get('provider_error_code'), 'unknown_jev_error')
                    self.assertEqual((call['status'], call['cost'], call['cost_bound']), ('outcome_unknown', None, '0.003'))
                    saved = Prompt.objects.get(user=self.user, request_id=data['request_id'])
                    public = json.dumps([data, saved.decision, logged.output], ensure_ascii=False)
                    raw_records = '\n'.join(str(record.__dict__) for record in logged.records)
                    for serialized in (public, raw_records):
                        self.assertNotIn(SECRET, serialized)
                        self.assertNotIn(KEY, serialized)
                    self.assertTrue(all(not record.args for record in logged.records))
                    observed.append({'stage': stage, 'input_type': type(value).__name__, 'index': index,
                        'path': path, 'safe_code': call['provider_error_code'], 'status': data['status'],
                        'record_codes': [getattr(record, 'code', None) for record in logged.records]})
        (HERE / (RUN + '-adversarial.json')).write_text(json.dumps(observed, indent=2), encoding='utf-8')


class LedgerDiagnosticsChecks(SmokeHarness, TestCase):
    def setUp(self):
        super().setUp()
        self.use_local_mask()
        self.manifest['destinations']['judge'] = jev.VERCEL_ENDPOINT
        self.manifest['judge_transport'] = 'vercel'
        self.manifest['model_versions']['judge'] = jev.VERCEL_MODEL
        self.manifest['allowed_effective_models'][jev.VERCEL_MODEL] = [jev.VERCEL_MODEL]
        self.manifest['mutable_model_aliases'].append(jev.VERCEL_MODEL)
        self.approval['destinations'] = deepcopy(self.manifest['destinations'])
        self.save_approval()
        self.stage = 'classification'

    def requests_transport(self, method, url, **kwargs):
        self.assertEqual((method.lower(), url), ('post', jev.VERCEL_ENDPOINT))
        body = json.loads(kwargs['data'])
        purpose = 'classification' if 'category' in body['questions'] else 'verification'
        self.assert_reserved(purpose)
        if purpose == self.stage:
            raise jev.JevError(SECRET + KEY, outcome_unknown=True)
        return jev_http()(url, **kwargs)

    def test_unknown_codes_reach_ledger_safely_without_reserve_release_or_replay(self):
        snapshots = []
        for stage in ('classification', 'verification'):
            self.stage = stage
            output = 'unknown-' + stage
            with self.assertRaises(CommandError):
                self.run_smoke(output)
            ledger = self.ledger()
            last = ledger['calls'][-1]
            self.assertEqual(last['purpose'], stage)
            self.assertEqual(last['metadata'].get('provider_error_code'), 'unknown_jev_error')
            self.assertEqual((last['status'], last['cost'], last['reserved']), ('outcome_unknown', None, '0.003'))
            self.assertGreaterEqual(Decimal(ledger['budget_exposure_usd']), Decimal('.003'))
            self.assertNotIn(SECRET, json.dumps(ledger))
            self.assertNotIn(KEY, json.dumps(ledger))
            provider_count = self.http.call_count, self.sdk.call_count
            with self.assertRaises(CommandError):
                self.run_smoke(output)
            self.assertEqual((self.http.call_count, self.sdk.call_count), provider_count)
            self.assertEqual(self.ledger(), ledger)
            snapshots.append(ledger)
        self.assertEqual(len(self.generation_payloads), 1)
        self.assertEqual(Decimal(snapshots[-1]['uncertain_reservations_usd']), Decimal('.006'))
        (HERE / (RUN + '-ledger.json')).write_text(json.dumps(snapshots, indent=2), encoding='utf-8')
