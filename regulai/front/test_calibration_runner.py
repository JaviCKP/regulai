"""Admission limits of the single synthetic paid executor; no real transport."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

PATH = Path(__file__).resolve().parents[2] / 'scripts/run_calibration_campaign.py'
SPEC = importlib.util.spec_from_file_location('calibration_runner_under_test', PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class CalibrationRunnerTests(SimpleTestCase):
    def test_boundary_rejects_unicode_escaped_sensitive_value_and_extra_generation(self):
        manifest = {'campaign_frozen_files': {}}
        guard = runner.make_guard(manifest, ['personañ@example.invalid'])
        body = {'model': 'deepseek-flash', 'max_tokens': 512, 'thinking': {'type': 'disabled'},
                'messages': [{'role': 'user', 'content': 'personañ@example.invalid'}]}
        with self.assertRaisesRegex(ValueError, 'sensitive'):
            guard({'purpose': 'generation', 'body_utf8': json.dumps(body, ensure_ascii=True)})
        body['messages'][0]['content'] = 'Dato público.'
        guard({'purpose': 'generation', 'body_utf8': json.dumps(body)})
        for key, value in (('max_tokens', 513), ('thinking', {'type': 'enabled'}), ('model', 'unapproved-model')):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'limit/options'):
                guard({'purpose': 'generation', 'body_utf8': json.dumps({**body, key: value})})
        body['messages'][0]['content'] = 'a' * 8001
        with self.assertRaisesRegex(ValueError, 'limit/options'):
            guard({'purpose': 'generation', 'body_utf8': json.dumps(body)})

    def test_complete_batch_must_fit_without_spending_confirmation_reserve(self):
        manifest = {'campaign_phase': 'development', 'maximum_additional_exposure_usd': '.308'}
        ledger = SimpleNamespace(snapshot=lambda: {'budget_exposure_usd': '.8'})
        with self.assertRaisesRegex(ValueError, 'confirmation'):
            runner.phase_check(ledger, manifest)
        ledger.snapshot = lambda: {'budget_exposure_usd': '.1'}
        runner.phase_check(ledger, manifest)

    def test_pinned_source_change_prevents_transport(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, patch.object(runner, 'ROOT', Path(directory)):
            source = Path(directory) / 'source.py'
            source.write_text('approved')
            manifest = {'campaign_frozen_files': {'source.py': runner.sha(source)}}
            runner.frozen_check(manifest)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                runner.frozen_check(manifest)
