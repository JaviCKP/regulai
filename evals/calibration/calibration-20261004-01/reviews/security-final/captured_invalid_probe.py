"""Offline replay of the already captured invalid response; no new provider call."""
from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
import requests
from front import jev

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
CAPTURE = REPO / 'evals/calibration/calibration-20261004-01/batches/r4-smoke-01/live-run-01/synthetic-payloads.json'


class CapturedInvalidResponse(SimpleTestCase):
    def test_captured_response_is_invalid_unknown_and_not_a_validated_invoice(self):
        event = json.loads(CAPTURE.read_text(encoding='utf-8'))[-1]
        raw = event['response_body_utf8'].encode()
        request = json.loads(event['body_utf8'])
        payload = json.loads(raw)
        response = requests.Response()
        response.status_code = 200
        response._content = raw
        response._content_consumed = True
        with patch('front.jev.requests.post', return_value=response) as send:
            with self.assertRaises(jev.JevError) as failure:
                jev.evaluate('offline-review-synthetic', request['model'], request['state'], request['questions'], transport='vercel')
        self.assertEqual(failure.exception.code, 'invalid_response')
        self.assertTrue(failure.exception.outcome_unknown)
        self.assertEqual(send.call_count, 1)
        mass = sum(Decimal(str(x)) for x in payload['answers']['category']['probabilities'].values())
        self.assertEqual(mass, Decimal('.99'))
        # A counterfactual copy diagnoses the schema defect. It is never used to
        # alter the captured response, classify content or settle a real ledger.
        corrected = json.loads(raw)
        corrected['answers']['category']['probabilities']['confidential'] = .56
        envelope = jev._Envelope.model_validate(corrected)
        jev._validate_answers(envelope, request['model'], request['questions'])
        result = {'captured_response_sha256': event['response_sha256'], 'http_status': 200,
            'response_complete': event['response_complete'], 'category_probability_sum': str(mass),
            'parser_error_code': failure.exception.code, 'outcome_unknown': failure.exception.outcome_unknown,
            'captured_unvalidated_cost_usd': payload['provider_metadata']['gateway']['cost'],
            'validated_provider_result_returned': False, 'offline_minimal_counterfactual_validates': True,
            'real_ledger_modified': False, 'new_provider_calls': 0}
        with (HERE / 'b3fea6a-captured-invalid-observed.json').open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2)
            handle.write('\n')
