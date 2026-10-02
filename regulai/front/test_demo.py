from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from importlib import import_module
import requests
import socket

from django.conf import settings

from front.chat_service import send_chat_message
from front.management.commands.run_demo import offline_demo, seed_demo


@override_settings(DEMO_MODE=True)
class DemoTests(TestCase):
    def test_demo_runs_simple_blocked_and_corrected_document_through_actual_pipeline(self):
        actor = seed_demo()
        with offline_demo() as providers:
            simple = send_chat_message(actor, {'content': 'Devuelve el saludo Hola.'})
            self.assertEqual(simple.data['assistant_message']['content'], 'Hola')
            before = len(providers.events)
            blocked = send_chat_message(actor, {'content': 'SYNTHETIC_SECRET_DEMO'})
            self.assertEqual(blocked.data['status'], 'blocked')
            self.assertEqual(len(providers.events), before)
            document = send_chat_message(actor, {'content': '¿Cuál es el precio del contrato?',
                'file': SimpleUploadedFile('contract.txt', b'El contrato cuesta 10 euros.')})
            self.assertEqual(document.data['status'], 'completed')
            self.assertEqual(document.data['receipt']['total']['attempts'], 2)
            self.assertIn('10 euros', document.data['assistant_message']['content'])
            self.assertTrue(document.data['evidence']['items'])

    @override_settings(DEMO_MODE=False)
    def test_normal_settings_cannot_start_demo(self):
        with self.assertRaises(CommandError):
            call_command('run_demo', seed_only=True, verbosity=0)

    def test_existing_demo_policy_is_preserved_and_unexpected_values_are_rejected(self):
        actor = seed_demo()
        first_password = actor.password
        same = seed_demo()
        self.assertEqual(same.pk, actor.pk)
        self.assertEqual(same.password, first_password)
        company = actor.profile.company
        company.ai_config['revision'] = 2
        company.save(update_fields=['ai_config'])
        with self.assertRaises(CommandError):
            seed_demo()
        company.refresh_from_db()
        self.assertEqual(company.ai_config['revision'], 2)

    def test_demo_blocks_outbound_calls_and_restores_normal_provider_functions(self):
        before_post, before_connect = requests.post, socket.socket.connect
        with offline_demo():
            with self.assertRaises(RuntimeError):
                requests.get('https://example.invalid')
            with socket.socket() as stream, self.assertRaises(RuntimeError):
                stream.connect(('127.0.0.1', 9))
        self.assertIs(requests.post, before_post)
        self.assertIs(socket.socket.connect, before_connect)

    def test_demo_banner_is_explicit_and_settings_import_does_not_mutate_normal_templates(self):
        before = list(settings.TEMPLATES[0]['OPTIONS']['context_processors'])
        demo_settings = import_module('regulai.demo_settings')
        self.assertEqual(settings.TEMPLATES[0]['OPTIONS']['context_processors'], before)
        actor = seed_demo()
        self.client.force_login(actor)
        with override_settings(TEMPLATES=demo_settings.TEMPLATES):
            self.assertContains(self.client.get('/chat/'), 'fallo simulado')
            with override_settings(DEMO_MODE=False):
                self.assertNotContains(self.client.get('/chat/'), 'fallo simulado')
