from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase

from .evaluation import PILOT_MANIFEST, REVIEW_FIELDS, attach_reviews, digest, load_pilot, summarize_pilot


class PilotOfflineTests(TestCase):
    def test_default_smoke_runs_all_controls_and_leaves_human_quality_unclaimed(self):
        with TemporaryDirectory() as directory, patch('socket.socket.connect', side_effect=AssertionError('No network')):
            output = Path(directory) / 'offline'
            call_command('smoke_ai', output=str(output), stdout=StringIO())
            rows = [json.loads(line) for line in (output / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 24)
            self.assertTrue(all(row['control_pass'] and row['mode'] == 'simulated' for row in rows))
            self.assertTrue(all(row['masking_backend'] == 'local' and row['masking_execution'] == 'local_detector' for row in rows))
            self.assertEqual({row['configuration'] for row in rows}, {'economy', 'strong', 'router'})
            blocked = [row for row in rows if row['case_id'] in ('blocked', 'consent-pending')]
            self.assertEqual(len(blocked), 6)
            self.assertTrue(all(not row['calls'] for row in blocked))
            accepted = [row for row in rows if row['case_id'] == 'consent-accepted']
            self.assertTrue(all(row['calls_before_consent'] == 0 and row['delivered'] for row in accepted))
            retry = next(row for row in rows if row['case_id'] == 'second-attempt' and row['configuration'] == 'router')
            self.assertEqual(retry['generation_calls'], 2)
            self.assertEqual(len(retry['generation_responses']), 2)
            self.assertIn('30 días', retry['generation_responses'][0]['content'])
            self.assertIn('17 días', retry['generation_responses'][1]['content'])
            self.assertEqual({call['purpose'] for call in retry['calls']}, {'obfuscation', 'classification', 'generation', 'verification'})
            for summary in json.loads((output / 'summary.json').read_text(encoding='utf-8')):
                self.assertEqual(summary['human_reviewed_n'], 0)
                self.assertIsNone(summary['correct_answers'])
                self.assertIsNone(summary['cost_per_correct_estimated_usd'])
                self.assertIsNone(summary['quality_claim'])
                self.assertIsNone(summary['savings_claim'])
                self.assertEqual(summary['real_provider_cases'], 0)
                self.assertEqual(summary['calls_by_purpose']['obfuscation'], 0)
                self.assertEqual(summary['local_api_cost_usd'], '0')
            self.assertTrue((output / 'summary.csv').exists())
            self.assertEqual(len((output / 'completed-cases.jsonl').read_text(encoding='utf-8').splitlines()), 24)
            with self.assertRaises(CommandError):
                call_command('smoke_ai', output=str(output), stdout=StringIO())

    def test_preflight_pending_template_does_not_create_report_or_touch_database(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'never-written'
            console = StringIO()
            with self.assertNumQueries(0), patch('socket.socket.connect', side_effect=AssertionError('No network')):
                call_command('smoke_ai', output=str(output), preflight=True,
                    authorization=str(PILOT_MANIFEST.parent / 'authorization.pending.json'), stdout=console)
            report = json.loads(console.getvalue())
            self.assertFalse(report['ready_for_real'])
            self.assertIn('new_explicit_authorization_required', report['blockers'])
            self.assertNotIn('authorized_mask_destination_required', report['blockers'])
            self.assertEqual(report['masking_observed']['backend'], 'local')
            self.assertEqual(report['network_calls'], 0)
            self.assertFalse(output.exists())

    def test_pilot_never_accepts_a_user_database_even_with_offline_mode(self):
        with TemporaryDirectory() as directory, patch.dict(connection.settings_dict, {'NAME': 'user-data.sqlite3'}):
            with self.assertRaises(CommandError):
                call_command('smoke_ai', output=str(Path(directory) / 'run'), stdout=StringIO())

    def test_human_bank_has_frozen_disjoint_splits_without_reference_labels_in_inputs(self):
        manifest, cases = load_pilot(PILOT_MANIFEST.parent.parent / 'pilot-human' / 'manifest.json')
        self.assertEqual(len(cases), 24)
        development = {case['id'] for case in cases if case['split'] == 'development'}
        reserved = {case['id'] for case in cases if case['split'] == 'reserved'}
        self.assertEqual((len(development), len(reserved)), (12, 12))
        self.assertFalse(development & reserved)
        self.assertTrue(all('expected' not in case and 'reference_draft' not in case for case in cases))


class HumanMetricsTests(SimpleTestCase):
    def test_local_transformations_are_accounted_but_never_external_calls(self):
        rows = self.rows()
        rows[0]['calls'].append({'purpose': 'obfuscation', 'status': 'completed', 'cost': '0', 'reserved': '0',
            'metadata': {'transport': 'local', 'cost_kind': 'configured_zero'}})
        rows[0]['calls'].append({'purpose': 'obfuscation', 'status': 'not_started', 'cost': '0', 'reserved': '0',
            'metadata': {'transport': 'local', 'cost_kind': 'not_incurred'}})
        summary = summarize_pilot(rows)[0]
        self.assertEqual(summary['accounting_entries'], 5)
        self.assertEqual(summary['provider_calls'], 3)
        self.assertEqual(summary['local_transformations'], 1)
        self.assertEqual(summary['calls_by_purpose']['obfuscation'], 0)
        self.assertEqual(summary['local_api_cost_usd'], '0')

    def test_proven_nonstarted_reservation_does_not_count_as_provider_execution(self):
        rows = self.rows()
        rows[0]['calls'][0].update(status='not_started', cost='0', metadata={'cost_kind': 'not_incurred'})
        summary = summarize_pilot(rows)[0]
        self.assertEqual(summary['accounting_entries'], 3)
        self.assertEqual(summary['provider_calls'], 2)
        self.assertEqual(summary['real_provider_cases'], 2)

    def rows(self):
        return [{'case_id': str(index), 'configuration': 'router', 'split': 'reserved', 'mode': 'real',
            'control_pass': True, 'delivered': index != 2, 'generation_calls': 1, 'second_attempt': index == 1,
            'latency_ms': latency, 'human_review': None,
            'calls': [{'purpose': 'generation', 'cost': cost, 'reserved': '.1',
                       'metadata': {'cost_kind': kind}}]}
            for index, (latency, cost, kind) in enumerate([(10, '.02', 'provider_reported'),
                (20, '.03', 'tariff_estimate'), (90, '0', 'configured_zero')])]

    def reviews(self, rows):
        return [{'case_id': row['case_id'], 'configuration': row['configuration'], 'result_sha256': digest(row),
            'status': 'reviewed', 'reviewer': 'synthetic unit-test reviewer', 'reviewed_at': '2026-10-03T12:00:00+00:00',
            'rationale': 'Synthetic test labels; no human product review was performed.',
            **{field: None for field in REVIEW_FIELDS}, 'correct': row['delivered'], 'correct_abstention': not row['delivered']}
            for row in rows]

    def attach(self, rows, reviews):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'reviews.json'
            path.write_text(json.dumps(reviews), encoding='utf-8')
            return attach_reviews(rows, path)

    def test_cost_per_correct_needs_complete_review_and_complete_costs(self):
        rows = self.rows()
        summary = summarize_pilot(rows)[0]
        self.assertEqual((summary['n'], summary['p50_latency_ms'], summary['p95_latency_ms']), (3, 20, 90))
        self.assertIsNone(summary['correct_answers'])
        self.assertIsNone(summary['cost_per_correct_estimated_usd'])
        reviewed = self.attach(deepcopy(rows), self.reviews(rows)[:1])
        self.assertIsNone(summarize_pilot(reviewed)[0]['cost_per_correct_estimated_usd'])
        reviewed = self.attach(deepcopy(rows), self.reviews(rows))
        complete = summarize_pilot(reviewed)[0]
        self.assertEqual(complete['correct_answers'], 2)
        self.assertEqual(complete['correct_abstention'], {'positive': 1, 'negative': 2, 'n': 3})
        self.assertEqual(complete['cost_per_correct_estimated_usd'], '0.025')
        self.assertIsNone(complete['cost_per_correct_reported_usd'])
        self.assertEqual(complete['provider_reported_usd'], '0.02')
        self.assertEqual(complete['tariff_estimated_usd'], '0.03')
        reviewed[2]['calls'][0].update(cost=None)
        self.assertIsNone(summarize_pilot(reviewed)[0]['cost_per_correct_estimated_usd'])
        self.assertEqual(summarize_pilot(reviewed)[0]['uncertain_reserved_usd'], '0.1')

    def test_stale_incomplete_duplicate_and_machine_shaped_reviews_are_rejected(self):
        rows = self.rows()
        valid = self.reviews(rows)
        invalid = [valid + [valid[0]], [{**valid[0], 'result_sha256': 'changed'}],
                   [{**valid[0], 'reviewer': None}], [{**valid[0], 'correct': 1}],
                   [{**valid[0], 'reviewed_at': 'not-a-date'}], [{**valid[2], 'correct': True}]]
        for reviews in invalid:
            with self.subTest(reviews=reviews), self.assertRaises(CommandError):
                self.attach(deepcopy(rows), reviews)
