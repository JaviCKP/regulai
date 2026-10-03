"""Offline persona-specific HTTP checks; no human participation is represented."""
import uuid

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from front.access import can_manage_company_policy, is_platform_operator
from front.models import Company, Conversation, Engine, EngineModel, Message, Profile, Prompt, Response, Role


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
