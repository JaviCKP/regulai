"""Offline persona-specific HTTP checks; no human participation is represented."""
import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from front.access import can_manage_company_policy, is_platform_operator
from front.models import Company, Conversation, Engine, EngineModel, Message, Profile, Prompt, Response, Role
from front.test_chat_flow import ChatFixture


class BetaDocumentCancellationTests(ChatFixture):
    def test_attached_visual_document_cancels_without_any_provider_on_three_entries(self):
        self.company.name = 'P02 fictitious Beta document flow'
        self.company.save()
        self.profile.role = Role.objects.get_or_create(name='Admin')[0]
        self.profile.save()
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)
        path = Path(__file__).parent / 'snapshot/evals/documents/pilot-20261003/files/text-and-image.docx'
        for entry in ('/chat/', '/chat/send/', '/api/chat/send/'):
            with self.subTest(entry=entry):
                initial = self.send(entry, 'Cual es el precio del contrato?',
                    file=SimpleUploadedFile('text-and-image.docx', path.read_bytes())).json()
                self.assertEqual(initial['status'], 'pending_consent')
                self.assertEqual(initial['receipt']['coverage']['status'], 'complete_text_only')
                row = Prompt.objects.get(request_id=initial['request_id'])
                original = (row.file_name, row.file_sha256, row.user_message_id)
                proof = {'request_id': initial['request_id'], 'consent_token': initial['consent_token']}
                cancelled = self.send(entry, 'Cual es el precio del contrato?', action='cancel', **proof).json()
                self.assertEqual(cancelled['status'], 'cancelled')
                row.refresh_from_db()
                self.assertEqual((row.file_name, row.file_sha256, row.user_message_id), original)
                self.assertFalse(Response.objects.filter(prompt=row).exists())
                self.assertEqual(row.decision.get('calls', []), [])
                self.provider.assert_not_called()
                self.http.assert_not_called()


class BetaAdministratorIsolationTests(TestCase):
    def test_company_administrator_has_no_owner_or_platform_override(self):
        beta = Company.objects.create(name='P02 fictitious Beta')
        alpha = Company.objects.create(name='P02 fictitious Alpha')
        role = Role.objects.create(name='Admin')
        admin = User.objects.create_user('p02-beta-admin', is_staff=False, is_superuser=False)
        Profile.objects.create(user=admin, company=beta, role=role)
        self.assertTrue(can_manage_company_policy(admin))
        self.assertFalse(is_platform_operator(admin))
        self.assertFalse(admin.is_superuser)
        self.assertFalse(admin.is_staff)
        records = []
        for name, company, actor in [('own', beta, admin), ('beta-peer', beta, None), ('alpha-owner', alpha, None)]:
            if actor is None:
                actor = User.objects.create_user('p02-' + name)
                Profile.objects.create(user=actor, company=company)
            conversation = Conversation.objects.create(user=actor, title='P02 ' + name)
            prompt = Prompt.objects.create(user=actor, company=company, conversation=conversation,
                content='Synthetic private ' + name, request_id=uuid.uuid4(), status='completed',
                decision={'schema_version': 1, 'policy': {'status': 'allow'}, 'calls': []})
            assistant = Message.objects.create(conversation=conversation, role='assistant', content='Synthetic ' + name)
            assistant.file_name = name + '.txt'
            assistant.response_file.save(name + '.txt', ContentFile(('Synthetic ' + name).encode()), save=True)
            Response.objects.create(prompt=prompt, assistant_message=assistant, content=assistant.content,
                evidence={'schema_version': 1, 'items': [{'id': name, 'locator': 'line:1', 'excerpt': 'Synthetic ' + name}]})
            records.append((name, conversation, prompt, assistant))
        self.client.force_login(admin)
        self.observations = []
        for name, conversation, prompt, assistant in records:
            expected = 200 if name == 'own' else 404
            urls = [reverse('front:chat_conversation', args=[conversation.pk]),
                    reverse('front:chat_request_receipt', args=[prompt.request_id]),
                    reverse('front:chat_request_evidence', args=[prompt.request_id]),
                    reverse('front:chat_download_file', args=[assistant.pk])]
            for url in urls:
                with self.subTest(owner=name, url=url):
                    result = self.client.get(url)
                    self.assertEqual(result.status_code, expected)
                    self.observations.append({'owner': name, 'url': url, 'status': result.status_code})
                    result.close()
        model = EngineModel.objects.create(engine=Engine.objects.create(name='P02 shared catalog'),
            name='P02 shared model', model_id='p02-synthetic')
        denied = self.client.post(reverse('front:model_edit', args=[model.pk]), {'name': 'P02 forbidden change'})
        self.assertEqual(denied.status_code, 403)
        model.refresh_from_db()
        self.assertEqual(model.name, 'P02 shared model')
