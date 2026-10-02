"""Synthetic command tests: no credential or provider network is used."""
from datetime import date
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.test import TestCase

from .chat_service import ChatResult
from .management.commands import smoke_ai
from .models import Company, CompanyEngine, Engine, Profile


class SmokeIsolationTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.lock = self.root / '.claude' / 'real-provider-smoke.lock'
        self.company = Company.objects.create(name='Community Local Synthetic Demo', jev_api_key='synthetic-key')
        actor = User.objects.create_user('community-local-demo')
        Profile.objects.create(user=actor, company=self.company)
        engine = Engine.objects.create(name='DeepSeek authorized test', connector_type='openai_compatible',
            base_url='https://api.deepseek.com')
        CompanyEngine.objects.create(company=self.company, engine=engine, api_key='synthetic-key')
        settings = SimpleNamespace(DEBUG=True, BASE_DIR=self.root / 'regulai',
            DATABASES={'default': {'NAME': 'community-local.sqlite3'}})
        self.enterContext(patch.object(smoke_ai, 'settings', settings))
        today = self.enterContext(patch.object(smoke_ai, 'date', wraps=date))
        today.today.return_value = date(2026, 10, 2)
        self.network = self.enterContext(patch('requests.sessions.Session.request', side_effect=AssertionError('No network')))
        self.send = self.enterContext(patch.object(smoke_ai.chat_service, 'send_chat_message',
            return_value=ChatResult({'status': 'blocked', 'receipt': {'calls': []}})))
        self.command = smoke_ai.Command(stdout=StringIO(), stderr=StringIO())

    def run_smoke(self, cases=None):
        self.command.handle(real=True, max_usd='1', output=str(self.root / 'report'), case=cases or ['blocked'])

    def test_existing_lock_is_retained_and_prevents_all_effects(self):
        self.lock.parent.mkdir()
        self.lock.write_text('another execution', encoding='utf-8')
        with self.assertRaises(CommandError):
            self.run_smoke()
        self.assertEqual(self.lock.read_text(encoding='utf-8'), 'another execution')
        self.send.assert_not_called()
        self.assertFalse((self.root / 'report').exists())

    def test_owned_lock_and_configuration_are_cleaned_after_failure(self):
        def fail(*args):
            self.assertTrue(self.lock.exists())
            raise RuntimeError('synthetic failure')
        self.send.side_effect = fail
        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
            self.run_smoke()
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config, {})
        self.assertFalse(self.lock.exists())
        self.network.assert_not_called()

    def test_change_before_installation_is_preserved_without_sending(self):
        changed = {'revision': 99}
        with patch.object(Company, 'full_clean', side_effect=lambda: Company.objects.filter(
                pk=self.company.pk).update(ai_config=changed)):
            with self.assertRaises(CommandError):
                self.run_smoke()
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config, changed)
        self.send.assert_not_called()
        self.assertFalse(self.lock.exists())

    def test_change_between_scenarios_stops_run_and_is_not_restored_over(self):
        changed = {'revision': 99}
        def edit(*args):
            Company.objects.filter(pk=self.company.pk).update(ai_config=changed)
            return ChatResult({'status': 'blocked', 'receipt': {'calls': []}})
        self.send.side_effect = edit
        with self.assertRaises(CommandError):
            self.run_smoke(['blocked', 'arithmetic'])
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config, changed)
        self.assertEqual(self.send.call_count, 1)
        self.assertFalse(self.lock.exists())
        report = json.loads((self.root / 'report' / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['configuration_restore'], 'external_change_preserved')
        self.network.assert_not_called()

    def test_success_restores_configuration_and_releases_lock(self):
        self.run_smoke(['blocked', 'document'])
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config, {})
        self.assertFalse(self.lock.exists())
        report = json.loads((self.root / 'report' / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['configuration_restore'], 'restored')
        self.network.assert_not_called()

    def test_change_during_last_scenario_is_preserved_and_reported_as_error(self):
        changed = {'revision': 99}
        def edit(*args):
            Company.objects.filter(pk=self.company.pk).update(ai_config=changed)
            return ChatResult({'status': 'blocked', 'receipt': {'calls': []}})
        self.send.side_effect = edit
        with self.assertRaises(CommandError):
            self.run_smoke()
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config, changed)
        self.assertFalse(self.lock.exists())
        report = json.loads((self.root / 'report' / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['configuration_restore'], 'external_change_preserved')
