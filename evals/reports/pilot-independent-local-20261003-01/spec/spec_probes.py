"""Independent behavior probes: actual CPU detector and real SDK with MockTransport."""
import json
from pathlib import Path
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from front import test_pipeline
from front.models import AuditLog, Conversation, Department, Message, Prompt, Response, Role
from front.policy import digest
from front.test_document_fidelity import inline_image_pdf
from front.test_local_masking_integration import LocalMaskingIntegrationTests

EVIDENCE = Path(__file__).resolve().parent


class IndependentLocalSpec(LocalMaskingIntegrationTests):
    def test_latest_whole_history_masked_at_sdk_without_rewriting_old_audit(self):
        self.company.system_prompt = 'SYSTEM_KEEP system.person@example.test'
        self.company.ai_config['history'] = {'max_turns': 1, 'max_bytes': 300}
        self.company.save()
        department = Department.objects.create(company=self.company, name='Scoped team',
            system_prompt='DEPARTMENT_KEEP department.person@example.test')
        self.profile.department = department
        self.profile.save()
        observed = []
        self.openai_transport(lambda request: (observed.append(json.loads(request.content)), self.answer('Safe response'))[1])
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            conversation = Conversation.objects.create(user=self.user, title='Synthetic independent review')
            previous = []
            for marker, status in [('OLD_OMIT', 'completed'), ('RECENT_KEEP', 'completed'),
                    ('BLOCKED_OMIT', 'blocked'), ('PENDING_OMIT', 'pending_consent')]:
                text, answer = marker + ' history.person@example.test', 'Reply prior.person@example.test'
                user = Message.objects.create(conversation=conversation, role='user', content=text)
                assistant = Message.objects.create(conversation=conversation, role='assistant', content=answer)
                prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=conversation,
                    user_message=user, content=text, status=status,
                    decision={'history_eligible': True, 'history_digest': digest([text, answer])})
                Response.objects.create(prompt=prompt, assistant_message=assistant, content=answer)
                previous.append((prompt.pk, text, user.pk, answer, assistant.pk))
            audit = AuditLog.objects.create(company=self.company, user=self.user, action='old_review',
                details='Original retained history.person@example.test')
            endpoint = (reverse('front:chat_send_conversation', args=[conversation.pk]) if path == '/chat/send/'
                else reverse('front:chat_conversation', args=[conversation.pk]) if path == '/chat/' else path)
            result = self.send(endpoint, 'CURRENT_KEEP current.person@example.test', conversation_id=conversation.pk)
            prompt = Prompt.objects.latest('pk')
            self.assertEqual(prompt.status, 'completed', prompt.decision)
            data = json.dumps(observed[-1], ensure_ascii=False)
            for value in ('system.person@example.test', 'department.person@example.test',
                    'history.person@example.test', 'prior.person@example.test', 'current.person@example.test',
                    'OLD_OMIT', 'BLOCKED_OMIT', 'PENDING_OMIT'):
                self.assertNotIn(value, data)
            for value in ('SYSTEM_KEEP', 'DEPARTMENT_KEEP', 'RECENT_KEEP', 'CURRENT_KEEP'):
                self.assertIn(value, data)
            self.assertEqual(prompt.decision['history']['sent_turns'], 1)
            self.assertEqual(prompt.decision['history']['omitted_turns'], 1)
            for pk, text, user_pk, answer, assistant_pk in previous:
                self.assertEqual(Prompt.objects.get(pk=pk).content, text)
                self.assertEqual(Message.objects.get(pk=user_pk).content, text)
                self.assertEqual(Message.objects.get(pk=assistant_pk).content, answer)
            audit.refresh_from_db()
            self.assertEqual(audit.details, 'Original retained history.person@example.test')
        self.http.assert_not_called()
        (EVIDENCE / 'history-sdk.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')

    def test_unknown_floor_remains_confidential_with_actual_local_detector(self):
        self.profile.role = Role.objects.create(name='Admin')
        self.profile.save()
        self.configure(local_sensitivity='unknown', destinations={
            'confidential': [f'engine:{self.credential.pk}', 'jev']},
            routing={'mode': 'auto', 'candidates': [{'company_engine_id': self.credential.pk,
                'model_id': self.model.pk, 'level': 'economy', 'quality': {'general': 1.0}}]})
        self.http.side_effect = test_pipeline.jev_http(choices={'category': 'public'})
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            self.send(path, 'Synthetic report with reviewer.person@example.test')
            prompt = Prompt.objects.latest('pk')
            self.assertEqual(prompt.status, 'completed', prompt.decision)
            self.assertEqual(prompt.decision['policy']['sensitivity'], 'confidential')
            self.assertNotIn('reviewer.person@example.test', str(self.provider.call_args))
        result = self.client.post(reverse('front:policy_simulator'), {'mode': 'semantic',
            'sample': 'Synthetic report with reviewer.person@example.test',
            'proposed_config': json.dumps(self.company.ai_config)})
        comparison = result.context['comparison']
        self.assertEqual(comparison['semantic']['status'], 'completed', comparison)
        for version in ('current', 'proposed'):
            self.assertEqual(comparison[version]['policy']['sensitivity'], 'confidential')
        self.assertEqual([call['transport'] for call in comparison['calls']], ['local', 'http'])

    def test_visual_omission_requires_consent_before_actual_local_work_in_three_entries(self):
        self.configure()
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            result = self.send(path, 'Summarize', file=SimpleUploadedFile('inline.pdf', inline_image_pdf())).json()
            self.assertEqual(result['status'], 'pending_consent')
            self.assertEqual(result['consent_reason'], 'coverage_incomplete')
            self.assertEqual(result['receipt']['calls'], [])
            self.assertEqual(result['receipt']['coverage']['disclosures'],
                [{'code': 'images_unread', 'count': 1, 'locators': ['page:1']}])
        self.provider.assert_not_called()
        self.http.assert_not_called()

    def test_numeric_privacy_reaches_all_sdk_entries_after_closure(self):
        sent = []
        def transport(request):
            sent.append(json.loads(request.content))
            for value in ('612345678', '4111111111111111', '6.12345678e8', '4.111111111111111e15'):
                self.assertNotIn(value, request.content.decode())
            self.assertIn('[[REGULAI_', request.content.decode())
            return self.answer('Safe response')
        self.openai_transport(transport)
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            self.send(path, '{"telephone":6.12345678e8,"card":4.111111111111111e15}')
            prompt = Prompt.objects.latest('pk')
            self.assertEqual(prompt.status, 'completed', prompt.decision)
        self.assertEqual(len(sent), 3)
        self.http.assert_not_called()
        (EVIDENCE / 'numeric-sdk.json').write_text(json.dumps(sent, indent=2), encoding='utf-8')
