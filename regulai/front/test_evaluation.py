import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from unittest.mock import patch

from front.management.commands.evaluate_ai import summarize


class EvaluationTests(TestCase):
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
