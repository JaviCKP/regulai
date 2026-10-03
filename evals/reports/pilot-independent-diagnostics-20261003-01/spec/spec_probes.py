"""Differential synthetic probes of additive diagnostics; no live records or ledger."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

from django.test import SimpleTestCase
import requests

from front import jev
from front.evaluation import LedgerObserver
from front.models import Prompt
from front.test_chat_flow import ChatFixture
from front.test_pipeline import PipelineTests, jev_http

HERE = Path(__file__).resolve().parent
SNAPSHOT = os.environ['SPEC_DIAGNOSTIC_SNAPSHOT']
NEW = SNAPSHOT == 'source'
ORIGINAL_POST = requests.post
SYNTHETIC = 'SYNTHETIC_PRIVATE_NOT_REAL'
RECORDS = []


def strip_additive(value):
    if isinstance(value, dict):
        return {key: strip_additive(item) for key, item in value.items()
                if key not in {'provider_error_code', 'duration_ms'}}
    if isinstance(value, list):
        return [strip_additive(item) for item in value]
    return value


def retain(label, status_code, data):
    RECORDS.append({'case': label, 'http_status': status_code,
        'status': data['status'], 'error_type': data.get('error_type'),
        'requires_consent': data.get('requires_consent'),
        'has_assistant': bool(data.get('assistant_message')),
        'receipt': strip_additive(data['receipt'])})


class DiagnosticBehaviorSpec(ChatFixture):
    configure = PipelineTests.configure

    def setUp(self):
        super().setUp()
        self.required_mask.backend, self.required_mask.api_url = 'local', ''
        self.required_mask.save()
        self.configure(jev={'transport': 'vercel', 'model': jev.VERCEL_MODEL,
            'input_price': '.042', 'output_price': '0', 'max_call_cost': '.003'})
        self.failed_purpose, self.fault = 'classification', 401
        self.enterContext(patch('requests.post', ORIGINAL_POST))
        self.wire = self.enterContext(patch('requests.sessions.Session.request', side_effect=self.transport))
        self.sock = self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('No sockets')))
        self.dns = self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('No DNS')))
        self.sdk = self.enterContext(patch('httpx.Client.send', side_effect=AssertionError('No SDK egress')))

    def transport(self, method, url, **kwargs):
        self.assertEqual((method, url), ('post', jev.VERCEL_ENDPOINT))
        request = json.loads(kwargs['data'])
        purpose = 'classification' if 'category' in request['questions'] else 'verification'
        self.assertEqual(request['providerOptions'], {'gateway': {'only': ['typesafe-ai']}})
        if purpose != self.failed_purpose:
            return jev_http()(url, **kwargs)
        if isinstance(self.fault, Exception):
            raise self.fault
        response = requests.Response()
        response.status_code = self.fault
        response._content = json.dumps({'private_provider_body': SYNTHETIC}).encode()
        response._content_consumed = True
        return response

    def test_classification_known_and_nonstandard_http_errors_preserve_control_flow(self):
        for fault, diagnostic in [(401, 'http_401'), (599, 'unknown_jev_error')]:
            self.fault = fault
            for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
                before = self.wire.call_count
                with self.assertLogs('front.chat_service', level='WARNING') as logged:
                    response = self.send(path)
                data = response.json()
                call = data['receipt']['calls'][-1]
                self.assertEqual(call.get('provider_error_code'), diagnostic if NEW else None)
                self.assertIsNone(call['cost'])
                self.assertEqual(call['cost_bound'], '0.003')
                self.assertEqual(self.wire.call_count, before + 1)
                self.assertNotIn(SYNTHETIC, json.dumps([data, logged.output]))
                self.provider.assert_not_called()
                retain(f'classification-{fault}-{path}', response.status_code, data)

    def test_verification_code_with_embedded_secret_is_sanitized_without_retry(self):
        self.failed_purpose = 'verification'
        self.fault = jev.JevError('timeout\n' + SYNTHETIC, outcome_unknown=True)
        with self.assertLogs('front.chat_service', level='WARNING') as logged:
            response = self.send('/api/chat/send/')
        data = response.json()
        self.assertEqual((data['status'], data['error_type']), ('failed', 'verification_failed'))
        call = data['receipt']['calls'][-1]
        self.assertEqual(call.get('provider_error_code'), 'unknown_jev_error' if NEW else None)
        self.assertEqual(self.provider.call_count, 1)
        self.assertEqual(self.wire.call_count, 2)
        if NEW:
            self.assertNotIn(SYNTHETIC, json.dumps([data, logged.output]))
            self.assertIn('unknown_jev_error', [getattr(item, 'code', None) for item in logged.records])
        retain('verification-unsafe-code', response.status_code, data)

    def test_replay_does_not_invent_missing_historical_cause_or_send_again(self):
        self.fault = 503
        request_id = str(uuid.uuid4())
        self.send('/api/chat/send/', request_id=request_id)
        prompt = Prompt.objects.get(request_id=request_id)
        prompt.decision['calls'][-1].pop('provider_error_code', None)
        prompt.save(update_fields=['decision'])
        historical = deepcopy(prompt.decision)
        calls = self.wire.call_count
        response = self.send('/api/chat/send/', request_id=request_id)
        prompt.refresh_from_db()
        self.assertEqual(prompt.decision, historical)
        self.assertNotIn('provider_error_code', response.json()['receipt']['calls'][-1])
        self.assertEqual(self.wire.call_count, calls)
        retain('replayed-record-without-diagnostic', response.status_code, response.json())

    def test_success_and_consent_do_not_acquire_failure_diagnostics(self):
        self.failed_purpose = None
        response = self.send('/api/chat/send/')
        data = response.json()
        self.assertEqual(data['status'], 'completed')
        self.assertTrue(all('provider_error_code' not in call for call in data['receipt']['calls']))
        retain('success', response.status_code, data)
        self.rule.action = 'consent'
        self.rule.save()
        before = self.wire.call_count
        response = self.send('/api/chat/send/', 'SYNTHETIC_SECRET')
        data = response.json()
        self.assertEqual(data['status'], 'pending_consent')
        self.assertEqual(data['receipt']['calls'], [])
        self.assertEqual(self.wire.call_count, before)
        retain('pending-consent', response.status_code, data)


class DiagnosticObserverSpec(SimpleTestCase):
    def test_observer_only_adds_diagnostic_metadata_to_unchanged_settlement(self):
        ledger = SimpleNamespace(complete=Mock())
        observer = LedgerObserver(ledger, {}, {}, case_id='synthetic', configuration='economy')
        call = {'purpose': 'classification', 'status': 'outcome_unknown', 'cost': None,
            'cost_kind': 'unknown', 'cost_bound': '0.003', 'provider_error_code': 'timeout'}
        observer.after_call(call, 'synthetic-token')
        args, kwargs = ledger.complete.call_args
        self.assertEqual(args, ('synthetic-token',))
        self.assertEqual(kwargs['cost'], None)
        self.assertEqual(kwargs['status'], 'outcome_unknown')
        self.assertEqual(kwargs['cost_kind'], 'unknown')
        self.assertEqual(kwargs['metadata'], {'provider_error_code': 'timeout'} if NEW else {})
        self.assertEqual(observer.stop_reason, 'failed_or_uncertain_provider_call')
        RECORDS.append({'case': 'observer-settlement', 'args': list(args),
            'kwargs': strip_additive(kwargs), 'stop_reason': observer.stop_reason})


def save_records():
    (HERE / (SNAPSHOT + '-behavior.json')).write_text(json.dumps(RECORDS, indent=2), encoding='utf-8')
