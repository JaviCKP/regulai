"""Owner/admin UI contracts on synthetic records; no model calls."""
import json
from django.contrib.auth.models import User
from django.test import Client
from front.models import (Conversation, ConversationAlias, PrivacyRevision, PrivacyMessage,
    PrivacyOccurrence, PrivacySelection, PrivacyUse, Prompt, Profile, AuditLog)
from front.local_masking import detector_metadata
from front.policy import digest
from front.privacy import ProtectionContext, protect_message, record_use
from front.test_chat_flow import ChatFixture


class PrivacyViewTests(ChatFixture):
    def setUp(self):
        super().setUp()
        self.revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='fixture', detector_version=digest(detector_metadata()))
        self.company.ai_config['privacy'] = {'version': 1, 'revision_id': self.revision.pk}
        self.company.save()
        self.conversation = Conversation.objects.create(user=self.user)
        self.prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation)
        self.context = ProtectionContext.from_prompt(self.prompt)
        self.canonical = protect_message(self.context, 'Ana Fixture ana@example.invalid', source_key='fixture')
        record_use(self.context, 'fixture:0', [self.canonical])
        self.base = f'/chat/privacy/conversations/{self.conversation.pk}/'

    def post(self, suffix, data):
        return self.client.post(self.base + suffix + '/', data, content_type='application/json')

    def test_inspector_omits_originals_reveal_is_explicit_audited_and_csrf_protected(self):
        response = self.client.get(self.base + 'inspector/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        value = response.json()
        self.assertEqual(len(value['aliases']), 2)
        self.assertNotIn('Ana Fixture', response.content.decode())
        self.assertNotIn('ana@example.invalid', response.content.decode())
        self.assertTrue(all(row['original'] is None for row in value['aliases']))
        self.assertEqual(value['totals'], {'values': 2, 'occurrences': 2})
        self.assertEqual(value['revision_id'], self.revision.pk)
        self.assertTrue(all(row['locations'][0]['revision_id'] == self.revision.pk for row in value['aliases']))
        row = value['aliases'][0]
        revealed = self.post('reveal', {'ids': [row['id']]}).json()
        self.assertTrue(revealed['aliases'][0]['original'])
        audit = AuditLog.objects.get(action='privacy_reveal')
        self.assertNotIn(revealed['aliases'][0]['original'], audit.details)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.base + 'reveal/', {'ids': [row['id']]}, content_type='application/json').status_code, 403)

    def test_admin_cannot_open_another_owners_chat_or_reveal_foreign_alias(self):
        other = User.objects.create_user('privacy-other-admin', is_superuser=True)
        Profile.objects.create(user=other, company=self.company)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.base + 'inspector/').status_code, 404)
        self.assertEqual(self.post('reveal', {'ids': [ConversationAlias.objects.first().pk]}).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.post('reveal', {'ids': [999999]}).status_code, 400)

    def test_preview_is_local_bounded_and_does_not_write_occurrences_or_uses(self):
        models = (ConversationAlias, PrivacyMessage, PrivacyOccurrence, PrivacyUse, PrivacyRevision)
        before = [model.objects.count() for model in models]
        response = self.post('preview', {'text': 'Ana Fixture ana@example.invalid'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['scope'], 'draft_only')
        self.assertEqual(response.json()['calls'], [])
        self.assertNotIn('ana@example.invalid', response.json()['protected'])
        self.assertEqual(before, [model.objects.count() for model in models])
        self.provider.assert_not_called()
        self.http.assert_not_called()
        self.assertEqual(self.post('preview', {'text': ''}).status_code, 400)

    def test_selection_requires_signed_exact_preview_and_respects_irreversibility(self):
        sample = 'Proyecto Fixture'
        review = self.post('selection', {'text': sample}).json()
        self.assertEqual(PrivacySelection.objects.count(), 0)
        self.assertEqual(self.post('selection', {'text': sample + ' changed', 'review_token': review['review_token']}).status_code, 400)
        self.assertEqual(self.post('selection', {'text': sample, 'review_token': review['review_token']}).status_code, 200)
        self.assertEqual(PrivacySelection.objects.count(), 1)
        existing = self.post('selection', {'text': 'Ana Fixture'})
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(self.post('selection', {'text': 'Ana Fixture', 'review_token': existing.json()['review_token']}).status_code, 200)
        self.assertNotIn(sample, self.post('preview', {'text': sample}).json()['protected'])
        before = ConversationAlias.objects.count()
        PrivacyRevision.objects.filter(pk=self.revision.pk).update(configuration=json.dumps({'categories': {'EMAIL': 'irreversible'}}))
        for text in ('other@example.invalid', 'password=fixture-secret-value'):
            self.assertEqual(self.post('selection', {'text': text}).status_code, 400)
        self.assertEqual(ConversationAlias.objects.count(), before)

    def test_settings_require_admin_signed_review_and_current_diff(self):
        endpoint = '/settings/privacy/configuration/'
        self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.user.is_superuser = True
        self.user.save()
        response = self.client.post(endpoint, {'action': 'simulate', 'synthetic': True,
            'configuration': {'categories': {'EMAIL': 'irreversible'}}, 'sample': 'Ana Fixture ana@example.invalid'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        review = response.json()
        self.assertIn('[[R_PERSON_', review['current'])
        self.assertIn('[[R_EMAIL_', review['current'])
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config['privacy']['revision_id'], self.revision.pk)
        activation = self.client.post(endpoint, {'action': 'activate', 'revision_id': review['revision_id'],
            'review_token': review['review_token']}, content_type='application/json')
        self.assertEqual(activation.status_code, 200)
        page = self.client.get('/settings/privacy/')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('ana@example.invalid', page.content.decode())
        self.assertNotIn('Ana Fixture', page.content.decode())
        self.provider.assert_not_called()
        self.http.assert_not_called()

    def test_options_enable_email_dni_nie_phone_iban_and_card_patterns(self):
        self.user.is_superuser = True
        self.user.save()
        examples = {
            'EMAIL': ['demo@example.invalid'],
            'ID': ['12345678Z', 'X1234567L'],
            'PHONE': ['+34 612 345 678'],
            'ACCOUNT': ['ES91 2100 0418 4502 0005 1332'],
            'CARD': ['4111 1111 1111 1111'],
        }
        sample = '\n'.join(value for values in examples.values() for value in values)
        endpoint = '/settings/privacy/configuration/'
        proposal = {'categories': {category: 'reversible' for category in examples}}
        review = self.client.post(endpoint, {'action': 'simulate', 'synthetic': True,
            'configuration': proposal, 'sample': sample}, content_type='application/json')
        self.assertEqual(review.status_code, 200, review.content)
        result = review.json()
        for category, values in examples.items():
            self.assertIn(f'[[R_{category}_', result['protected'])
            for value in values:
                self.assertNotIn(value, result['protected'])
        activated = self.client.post(endpoint, {'action': 'activate',
            'revision_id': result['revision_id'], 'review_token': result['review_token']},
            content_type='application/json')
        self.assertEqual(activated.status_code, 200, activated.content)
        saved = self.client.get(endpoint).json()
        self.assertTrue(saved['enabled'])
        self.assertEqual(saved['configuration']['categories'], proposal['categories'])
        preview = self.post('preview', {'text': sample})
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()['count'], 6)
        for category in examples:
            self.assertIn(f'[[R_{category}_', preview.json()['protected'])
        # Disabling optional recovery is also persisted through the signed flow;
        # mandatory D2 still hides the identifiers.
        proposal['categories']['ID'] = 'off'
        review = self.client.post(endpoint, {'action': 'simulate', 'synthetic': True,
            'configuration': proposal, 'sample': sample}, content_type='application/json').json()
        self.assertNotIn('[[R_ID_', review['protected'])
        for value in examples['ID']:
            self.assertNotIn(value, review['protected'])
        disabled = self.client.post(endpoint, {'action': 'activate',
            'revision_id': review['revision_id'], 'review_token': review['review_token']},
            content_type='application/json')
        self.assertEqual(disabled.status_code, 200, disabled.content)
        self.assertEqual(self.client.get(endpoint).json()['configuration']['categories']['ID'], 'off')
        self.provider.assert_not_called()
        self.http.assert_not_called()
