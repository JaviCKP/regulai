"""Independent S2 probes on real SDK payloads, with HTTP/socket boundaries mocked."""
from copy import deepcopy
import json
from pathlib import Path

from django.core.management.base import CommandError

from front import evaluation
from front.models import Company
from front.test_smoke import SmokeIsolationTests

HERE = Path(__file__).resolve().parent


class ClosureProbes(SmokeIsolationTests):
    def select_case(self, identity):
        source = evaluation.PILOT_MANIFEST.parent
        self.case = next(json.loads(line) for line in (source / 'cases.jsonl').read_text(encoding='utf-8').splitlines()
                         if line.strip() and json.loads(line)['id'] == identity)
        (self.root / 'cases.jsonl').write_text(json.dumps(self.case) + '\n', encoding='utf-8')
        self.manifest['dataset_sha256'] = evaluation.digest((self.root / 'cases.jsonl').read_bytes())
        self.save_approval()

    def assert_payloads(self, identity, option):
        self.select_case(identity)
        self.run_smoke()
        captured = [{'url': 'https://api.deepseek.com/chat/completions',
                     'temperature': body['temperature'], 'model': body['model'],
                     'thinking': body['thinking'], 'max_tokens': body['max_tokens']}
                    for body in self.generation_payloads]
        observed = {'case': identity, 'options_declared': self.manifest['generation_options'],
                    'http_payloads': captured, 'network_socket_calls': self.socket.call_count}
        (HERE / (identity + '-http.json')).write_text(json.dumps(observed, indent=2), encoding='utf-8')
        self.assertTrue(captured)
        self.assertEqual({row['temperature'] for row in captured},
                         {self.manifest['generation_options'][option]})
        self.assertEqual({json.dumps(row['thinking'], sort_keys=True) for row in captured},
                         {json.dumps(self.manifest['generation_options']['thinking'], sort_keys=True)})
        self.socket.assert_not_called()

    def test_general_payload_matches_frozen_options(self):
        self.assert_payloads('arithmetic', 'temperature')

    def test_document_payload_matches_frozen_options(self):
        self.assert_payloads('document-success', 'document_temperature')

    def test_drift_is_rejected_even_when_bound_to_test_approval(self):
        original = deepcopy(self.manifest['generation_options'])
        variants = [
            ('general', {**original, 'temperature': 0.2}),
            ('document', {**original, 'document_temperature': 0.3}),
            ('missing_document', {key: value for key, value in original.items() if key != 'document_temperature'}),
            ('thinking', {**original, 'thinking': {'type': 'enabled'}}),
        ]
        before = Company.objects.count()
        observed = []
        for name, options in variants:
            with self.subTest(name=name):
                self.manifest['generation_options'] = options
                self.save_approval()
                report, _ = evaluation.preflight(self.manifest_path, self.approval_path)
                observed.append({'variant': name, 'blockers': report['blockers'], 'network_calls': report['network_calls']})
                self.assertEqual(report['blockers'], ['unsupported_generation_options'])
                with self.assertRaisesRegex(CommandError, 'unsupported_generation_options'):
                    self.run_smoke(name)
                self.assertEqual(Company.objects.count(), before)
                self.assertFalse(self.ledger_path.exists())
                self.assertFalse((self.root / name).exists())
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        self.socket.assert_not_called()
        (HERE / 'option-drift.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
