import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from unittest.mock import patch

from front.management.commands.evaluate_ai import summarize


class EvaluationTests(TestCase):
    def test_development_controls_detect_missing_notices_and_wrong_sensitivity(self):
        source = Path(__file__).resolve().parents[2] / 'evals'
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            shutil.copyfile(source / 'manifest.json', destination / 'manifest.json')
            shutil.copytree(source / 'documents', destination / 'documents')
            lines = []
            for line in (source / 'cases.jsonl').read_text(encoding='utf-8').splitlines():
                if '"id": "ambiguous-es"' in line or '"id": "unknown-sensitivity"' in line:
                    case = json.loads(line)
                    self.assertEqual(case['split'], 'development')
                    if case['id'] == 'ambiguous-es':
                        case['expected_notices'] = ['absent_required_notice']
                    else:
                        case['expected_sensitivity'] = 'restricted'
                    line = json.dumps(case, ensure_ascii=False)
                lines.append(line)
            (destination / 'cases.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            call_command('evaluate_ai', manifest=str(destination / 'manifest.json'),
                         split='development', output=str(destination / 'run'), verbosity=0)
            rows = [json.loads(line) for line in (destination / 'run' / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
            failures = [row for row in rows if not row['control_pass']]
            self.assertEqual(len(failures), 6)
            self.assertEqual({row['case_id'] for row in failures}, {'ambiguous-es', 'unknown-sensitivity'})

    def test_offline_bank_runs_every_case_and_writes_reports(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            call_command('evaluate_ai', output=str(output), verbosity=0)
            results = [json.loads(line) for line in (output / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(results), 150)
            self.assertEqual(len({row['case_id'] for row in results}), 50)
            self.assertEqual({row['configuration'] for row in results}, {'economy', 'strong', 'router'})
            self.assertEqual(sum(row['forbidden_egress'] for row in results), 0)
            self.assertTrue(all(row['control_pass'] for row in results))
            for row in results:
                if row['case_id'] == 'ambiguous-es':
                    self.assertIn('clarification_required', row['notices'])
                elif row['case_id'] == 'document-missing-answer':
                    self.assertIn('insufficient_evidence', row['notices'])
                elif row['case_id'] == 'unknown-sensitivity':
                    self.assertEqual(row['sensitivity'], 'confidential')
                    self.assertEqual(row['generation_calls'], 1)
            self.assertTrue((output / 'summary.csv').is_file())
            self.assertTrue((output / 'report.md').is_file())
            economy = next(row for row in results if row['case_id'] == 'simple-es' and row['configuration'] == 'economy')
            self.assertEqual(economy['known_cost'], '0.00026000')
            timeout = next(row for row in results if row['case_id'] == 'provider-timeout' and row['configuration'] == 'economy')
            self.assertEqual(timeout['unknown_cost_calls'], 1)
            self.assertEqual(timeout['generation_calls'], 1)
            self.assertIsNone(next(row for row in summarize(results) if row['configuration'] == 'economy' and row['split'] == 'all')['total_cost'])
            with self.assertRaises(CommandError):
                call_command('evaluate_ai', output=str(output), verbosity=0)

    def test_identical_manifest_produces_identical_outcome_hashes(self):
        with TemporaryDirectory() as directory:
            hashes = []
            for index in range(2):
                output = Path(directory) / str(index)
                call_command('evaluate_ai', output=str(output), split='reserved', verbosity=0)
                hashes.append(json.loads((output / 'manifest.json').read_text(encoding='utf-8'))['outcomes_hash'])
            self.assertEqual(hashes[0], hashes[1])

    def test_real_mode_and_existing_database_are_rejected_before_writing(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'forbidden'
            with self.assertRaises(CommandError):
                call_command('evaluate_ai', output=str(output), real=True, verbosity=0)
            with patch.dict(connection.settings_dict, {'NAME': 'existing.sqlite3'}), self.assertRaises(CommandError):
                call_command('evaluate_ai', output=str(output), verbosity=0)
            self.assertFalse(output.exists())
