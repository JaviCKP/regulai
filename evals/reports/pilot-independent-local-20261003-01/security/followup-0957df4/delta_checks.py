"""Own correction/evaluator controls; no live providers or mutable code."""
import json
from pathlib import Path
import time
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from front import evaluation, local_masking, test_smoke
from front.evaluation_budget import EvaluationBudget

HERE = Path(__file__).resolve().parent


class NumericNormalizationControls(SimpleTestCase):
    def test_equivalent_values_and_bounded_exponents_preserve_only_nonsensitive_numbers(self):
        private = ['[6.12345678e8,4.111111111111111e15]',
                   '{"telephone":-612345678,"card":4111111111111111.000000}',
                   '[612345678.0,6.12345678000000000000000e+8]']
        ordinary = '[1.234567890123456789,0,1e100000000,-1e-100000000,0e100000000]'
        started = time.monotonic()
        outputs = local_masking.mask_local_texts(private + [ordinary], timeout=30)
        (HERE / 'numeric-equivalents.json').write_text(json.dumps({'inputs': private + [ordinary], 'outputs': outputs,
            'seconds': round(time.monotonic() - started, 3)}, indent=2), encoding='utf-8')
        for output in outputs[:-1]:
            self.assertNotIn('612345678', output)
            self.assertNotIn('6.12345678', output)
            self.assertNotIn('4111111111111111', output)
            self.assertNotIn('4.111111111111111', output)
            self.assertIn('[[REGULAI_', output)
        self.assertEqual(outputs[-1], ordinary)
        self.assertLess(time.monotonic() - started, 10)


class EvaluatorControls(test_smoke.SmokeIsolationTests):
    def test_numeric_json_is_masked_for_classifier_generator_and_verifier(self):
        self.use_local_mask()
        self.case['input'] = '{"telephone":6.12345678e8,"card":4.111111111111111e15}'
        (self.root / 'cases.jsonl').write_text(json.dumps(self.case) + '\n', encoding='utf-8')
        self.manifest['dataset_sha256'] = evaluation.digest((self.root / 'cases.jsonl').read_bytes())
        self.save_approval()
        self.run_smoke('numeric-local')
        captured = self.generation_payloads + self.judge_payloads
        for body in captured:
            value = json.dumps(body)
            for sensitive in ('612345678', '6.12345678', '4111111111111111', '4.111111111111111'):
                self.assertNotIn(sensitive, value)
        ledger = self.ledger()
        (HERE / 'numeric-evaluator.json').write_text(json.dumps({'events': self.events, 'payloads': captured,
            'ledger': ledger}, indent=2), encoding='utf-8')
        self.assertEqual(self.events.count('generation'), 3)
        self.assertEqual(self.events.count('classification'), 3)
        self.assertEqual(self.events.count('verification'), 3)
        self.assertNotIn('obfuscation', self.events)
        local = [call for call in ledger['calls'] if call['metadata'].get('transport') == 'local']
        self.assertEqual(len(local), 6)
        self.assertTrue(all(call['cost'] == '0' and call['reserved'] == '0' for call in local))

    def test_model_identity_drift_during_reserve_stops_before_real_detector(self):
        self.use_local_mask()
        original = evaluation.local_masking_manifest
        identity = original()
        changed = False
        reserve = EvaluationBudget.reserve
        def mutate(ledger, purpose, maximum, **kwargs):
            nonlocal changed
            token = reserve(ledger, purpose, maximum, **kwargs)
            changed = True
            return token
        def observe():
            return {**identity, 'model_files_sha256': 'synthetic-changed-model'} if changed else original()
        with patch.object(EvaluationBudget, 'reserve', mutate), \
                patch.object(evaluation, 'local_masking_manifest', side_effect=observe), \
                patch('front.masking.mask_local_texts', wraps=local_masking.mask_local_texts) as detector:
            with self.assertRaises(CommandError):
                self.run_smoke('identity-drift')
        detector.assert_not_called()
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        ledger = self.ledger()
        (HERE / 'model-drift-during-reserve.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
        self.assertEqual(len(ledger['calls']), 1)
        call = ledger['calls'][0]
        self.assertEqual((call['status'], call['cost'], call['metadata']['cost_kind']), ('not_started', '0', 'not_incurred'))
