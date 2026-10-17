"""Shared registry invariants. PostgreSQL serializes independent writers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings

from front.models import Company, Conversation, ConversationAlias, Profile, Prompt, PrivacyRevision
from front.privacy import ProtectionContext, alias_value, alias_text, resolve_spans, prepare_turn, authorize


class RegistryFixture:
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('privacy-service-fixture')
        self.company = Company.objects.create(name='Privacy synthetic')
        self.conversation = Conversation.objects.create(user=self.user)
        self.context = ProtectionContext(self.company.pk, self.user.pk, self.conversation.pk)
        self.profile = Profile.objects.create(user=self.user, company=self.company)


class RegistryTests(RegistryFixture, TestCase):
    def test_authorization_uses_fresh_company_once_and_rejects_mixed_tenant_history(self):
        with self.assertNumQueries(1):
            self.assertEqual(authorize(self.context).pk, self.profile.pk)
        other = Company.objects.create(name='Foreign prompt provenance')
        Prompt.objects.create(user=self.user, company=other, conversation=self.conversation)
        with self.assertRaisesMessage(ValueError, 'privacy_access_revoked'):
            authorize(self.context)

    def test_revision_is_off_by_default_pinned_and_revoked(self):
        prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation)
        context = ProtectionContext.from_prompt(prompt)
        self.assertIsNone(prepare_turn(context))
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration='{}', fingerprint='synthetic', detector_version='fixture')
        self.company.ai_config = {'privacy': {'version': 1, 'revision_id': revision.pk}}
        self.company.save()
        turn = prepare_turn(context)
        self.assertEqual(prepare_turn(context).pk, turn.pk)
        self.company.ai_config = {}
        self.company.save()
        with self.assertRaisesMessage(ValueError, 'privacy_policy_revoked'):
            prepare_turn(context)
        with self.assertRaisesMessage(ValueError, 'privacy_revision_immutable'):
            revision.save()

    def test_current_tenant_and_owner_are_required(self):
        self.assertEqual(authorize(self.context).pk, self.profile.pk)
        other = User.objects.create_user('privacy-admin-fixture', is_superuser=True)
        Profile.objects.create(user=other, company=self.company)
        with self.assertRaises(ValueError):
            authorize(ProtectionContext(self.company.pk, other.pk, self.conversation.pk))
        Profile.objects.filter(pk=self.profile.pk).update(company=Company.objects.create(name='Other fixture'))
        with self.assertRaises(ValueError):
            authorize(self.context)

    def test_ciphertext_and_lookup_rotation_preserve_existing_identifier(self):
        token = alias_value(self.context, 'EMAIL', 'fixture@example.invalid')
        with connection.cursor() as cursor:
            cursor.execute('SELECT original FROM front_conversationalias WHERE token = %s', [token])
            ciphertext = cursor.fetchone()[0]
        self.assertNotIn('fixture@', ciphertext)
        self.assertTrue(ciphertext.startswith('gAAAAA'))
        from django.conf import settings
        with override_settings(PRIVACY_LOOKUP_KEYS={1: settings.SECRET_KEY, 2: 'synthetic-rotation-key'}):
            self.assertEqual(token, alias_value(self.context, 'EMAIL', 'fixture@example.invalid'))
            other = alias_value(self.context, 'EMAIL', 'another@example.invalid')
            self.assertEqual(ConversationAlias.objects.get(token=other).version, 2)
        self.assertEqual(ConversationAlias.objects.count(), 2)

    def test_no_secret_original_in_registry_even_inside_selected_value(self):
        result = alias_value(self.context, 'PERSON', 'Name api_key=sk-syntheticsecrethere')
        self.assertEqual(result, '[[REGULAI_SECRET]]')
        self.assertEqual(ConversationAlias.objects.count(), 0)

    def test_encryption_key_rotation_and_missing_key_do_not_return_ciphertext(self):
        from cryptography.fernet import Fernet
        from django.conf import settings
        token = alias_value(self.context, 'EMAIL', 'rotation@example.invalid')
        old_key = settings.ENCRYPTION_KEY
        with override_settings(ENCRYPTION_KEY=Fernet.generate_key().decode(), ENCRYPTION_KEY_FALLBACKS=[old_key]):
            self.assertEqual(ConversationAlias.objects.get(token=token).original, 'rotation@example.invalid')
            self.assertEqual(alias_value(self.context, 'EMAIL', 'rotation@example.invalid'), token)
        with override_settings(ENCRYPTION_KEY=Fernet.generate_key().decode(), ENCRYPTION_KEY_FALLBACKS=[]):
            self.assertEqual(ConversationAlias.objects.get(token=token).original, '')

    def test_foreign_scope_references_are_rejected(self):
        token = alias_value(self.context, 'PERSON', 'Ana Fixture')
        other = Conversation.objects.create(user=self.user)
        with self.assertRaises(ValueError):
            alias_text(ProtectionContext(self.company.pk, self.user.pk, other.pk), token)

    def test_overlap_never_recovers_secret_or_ambiguous_union(self):
        spans = [(0, 4, 'PERSON', True, 'literal'), (2, 6, 'EMAIL', True, 'local')]
        self.assertEqual(resolve_spans(spans), [(0, 6, 'SECRET', False, 'overlap')])
        self.assertEqual(resolve_spans(spans + [(1, 5, 'SECRET', False, 'local')]),
                         [(0, 6, 'SECRET', False, 'overlap')])


@skipUnless(connection.vendor == 'postgresql', 'Writer interleaving requires disposable PostgreSQL')
class RegistryConcurrencyTests(RegistryFixture, TransactionTestCase):
    def test_concurrent_writers_share_one_alias(self):
        barrier = Barrier(4)

        def create():
            try:
                barrier.wait(timeout=10)
                return alias_value(self.context, 'PERSON', 'Ana Concurrente Fixture')
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: create(), range(4)))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(ConversationAlias.objects.count(), 1)
