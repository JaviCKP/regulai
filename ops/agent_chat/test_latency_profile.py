"""The optional profiler must not leak data or double-count open spans."""
import json
import unittest

from ops.agent_chat.latency_profile import Recorder


class LatencyProfileTests(unittest.TestCase):
    def setUp(self):
        self.active = True
        self.recorder = Recorder(lambda: self.active, lambda: '/internal/agents/inference/')

    def test_boundary_snapshot_closes_nested_spans_once(self):
        with self.recorder.span('outer'):
            with self.recorder.span('inner'):
                self.active = False
                frozen = self.recorder.snapshot()
        final = self.recorder.snapshot()
        self.assertEqual(final, frozen)
        spans = {row['operation']: row for row in final['spans']}
        self.assertEqual({row['calls'] for row in spans.values()}, {1})
        self.assertAlmostEqual(spans['outer']['self_wall_s'] + spans['inner']['wall_s'],
            spans['outer']['wall_s'])

    def test_sql_report_contains_no_literal_or_parameter_values(self):
        secret = 'private@example.invalid'
        self.assertEqual(self.recorder.execute(lambda sql, params: 123,
            "SELECT * FROM example WHERE private='" + secret + "' AND token=%s", (secret,)), 123)
        report = self.recorder.snapshot()
        self.assertNotIn(secret, json.dumps(report))
        self.assertEqual(report['sql'][0]['calls'], 1)
        self.assertEqual(report['sql'][0]['verb'], 'SELECT')

    def test_exception_preserved_and_span_recorded(self):
        def failing():
            raise RuntimeError('private failure text')
        with self.assertRaisesRegex(RuntimeError, 'private failure text'):
            self.recorder.wrap(failing, 'failed.operation')()
        report = self.recorder.snapshot()
        self.assertEqual(report['spans'][0]['calls'], 1)
        self.assertNotIn('private failure text', json.dumps(report))

    def test_inactive_recorder_preserves_results_without_metrics(self):
        self.active = False
        function = self.recorder.wrap(lambda value: value + 1, 'addition')
        self.assertEqual(function(4), 5)
        self.recorder.execute(lambda sql, params: None, 'SELECT 1', None)
        self.assertEqual(self.recorder.snapshot()['spans'], [])
        self.assertEqual(self.recorder.snapshot()['sql'], [])


if __name__ == '__main__':
    unittest.main()
