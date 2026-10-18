"""Evidence gates: incomplete or changed experiments must never score goals."""
import json
from pathlib import Path
import tempfile
import unittest

from ops.agent_chat.latency_report_v2 import build_report, distribution, ENTRIES, ROUNDS


class SecondLatencyReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.harness = {name: 'c' * 64 for name in
            ('latency_benchmark_server.py', 'latency_benchmark_worker.py', 'latency_profile.py')}
        for variant in ('baseline', 'after'):
            images = {kind: 'sha256:' + ('a' if variant == 'baseline' else 'b') * 64 for kind in ('web', 'worker')}
            for number in ROUNDS:
                first = 'baseline' if number % 2 == 0 else 'after'
                slot = 2 * (number - ROUNDS[0]) + int(variant != first)
                started = 1_700_000_000 + slot * 100
                rows = []
                for index in range(7):
                    rows.append({'index': index, 'cache': 'process-cold' if index == 0 else 'warm',
                        'entry': ENTRIES[(index + number) % 3], 'sensitive': bool(index % 2),
                        'scenario': 'simple', 'history_pairs': 0, 'conversation_data': 'new',
                        'queue_s': .1, 'queue_admission_s': .07, 'queue_dispatch_s': .03,
                        'preparation_s': 1., 'first_inference_s': 1.1, 'entry_to_provider_s': 1.2,
                        'inference_http_to_provider_s': .5, 'status': 'completed', 'provider_calls': 1,
                        'inference_count': 1, 'checkpoint_count': 1, 'catalog_count': 1,
                        'sql_preparation': {'SELECT': 525},
                        'sql_by_path': {'/internal/agents/inference/': {'SELECT': 525}}, 'sql_callers': {}})
                report = {'variant': variant, 'round': number, 'round_offset': number,
                    'scenario': 'simple', 'instrumented': False, 'profile': False, 'rows': rows,
                    'image_ids': images, 'harness_sha256': self.harness, 'dataset_sha256': 'd' * 64,
                    'measured_started_at_unix': started, 'measured_finished_at_unix': started + 90}
                self.write(f'bench-{variant}-{number}.json', report)
        self.write('build-0.json', {'images': images})

    def write(self, name, value):
        (self.directory / name).write_text(json.dumps(value), encoding='utf-8')

    def change(self, name, edit):
        value = json.loads((self.directory / name).read_text())
        edit(value)
        self.write(name, value)

    def test_complete_evidence_produces_exact_cohorts_and_observed_goals(self):
        report = build_report(self.directory)
        self.assertEqual(report['issues'], [])
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['accepted_rows'], {'baseline': 140, 'after': 140})
        cohorts = report['variants']['after']['cohorts']
        self.assertEqual(cohorts['process-cold']['n'], 20)
        self.assertEqual(cohorts['warm-simple']['n'], 60)
        self.assertEqual(cohorts['warm-sensitive']['n'], 60)
        self.assertFalse(report['goals']['warm_simple_preparation_p95_under_700ms'])
        self.assertTrue(report['goals']['process_cold_preparation_p95_under_1500ms'])
        self.assertTrue(report['chronology']['verified'])
        self.assertEqual(report['chronology']['n'], 40)

    def test_latest_numeric_build_is_selected_without_overwriting_old_artifacts(self):
        original = (self.directory / 'build-0.json').read_bytes()
        correct = json.loads(original)
        self.write('build-9.json', {'images': {key: 'sha256:' + 'e' * 64 for key in ('web', 'worker')}})
        self.write('build-10.json', correct)
        report = build_report(self.directory)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['final_build']['file'], 'build-10.json')
        self.assertEqual((self.directory / 'build-0.json').read_bytes(), original)
        explicit = build_report(self.directory, build_number=9)
        self.assertEqual(explicit['final_build']['file'], 'build-9.json')
        self.assertFalse(explicit['identity_checks']['after_matches_final_build'])
        self.assertNotIn('goals', explicit)

    def test_missing_timestamp_never_claims_alternation(self):
        self.change('bench-after-20.json', lambda report: report.pop('measured_started_at_unix'))
        report = build_report(self.directory)
        self.assertFalse(report['chronology']['verified'])
        self.assertNotIn('goals', report)

    def test_complete_but_wrong_order_or_overlapping_runs_are_rejected(self):
        # Round 20 must run baseline then after; reverse its two valid intervals.
        self.change('bench-after-20.json', lambda report: report.update(
            measured_started_at_unix=1_699_999_900, measured_finished_at_unix=1_699_999_990))
        report = build_report(self.directory)
        self.assertFalse(report['chronology']['paired_alternating'])
        self.assertTrue(report['chronology']['nonoverlapping'])
        self.assertNotIn('goals', report)
        self.change('bench-after-20.json', lambda report: report.update(
            measured_started_at_unix=1_700_000_050, measured_finished_at_unix=1_700_000_150))
        report = build_report(self.directory)
        self.assertTrue(report['chronology']['paired_alternating'])
        self.assertFalse(report['chronology']['nonoverlapping'])
        self.assertNotIn('goals', report)

    def test_missing_round_never_scores_goals(self):
        (self.directory / 'bench-after-39.json').unlink()
        report = build_report(self.directory)
        self.assertEqual(report['status'], 'incomplete')
        self.assertNotIn('goals', report)

    def test_changed_harness_invalidates_apparent_improvement(self):
        self.change('bench-after-20.json', lambda report: report['harness_sha256'].update(
            {'latency_benchmark_server.py': 'e' * 64}))
        report = build_report(self.directory)
        self.assertFalse(report['identity_checks']['same_harness'])
        self.assertNotIn('goals', report)

    def test_instrumented_or_duplicate_provider_run_is_not_formal(self):
        self.change('bench-after-20.json', lambda report: report.update(instrumented=True))
        self.change('bench-after-21.json', lambda report: report['rows'][0].update(provider_calls=2))
        report = build_report(self.directory)
        self.assertEqual(report['accepted_rows']['after'], 126)
        self.assertNotIn('goals', report)

    def test_nonfinite_or_inconsistent_times_are_rejected(self):
        self.change('bench-after-20.json', lambda report: report['rows'][0].update(preparation_s=float('nan')))
        self.change('bench-after-21.json', lambda report: report['rows'][0].update(queue_s=.5))
        report = build_report(self.directory)
        self.assertEqual(report['accepted_rows']['after'], 126)
        self.assertNotIn('goals', report)

    def test_p95_is_nearest_rank_and_reports_sample_size(self):
        self.assertEqual(distribution(range(1, 21))['p95'], 19)
        self.assertEqual(distribution(range(1, 21))['n'], 20)


if __name__ == '__main__':
    unittest.main()
