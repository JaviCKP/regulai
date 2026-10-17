"""Privacy operation batching: query budgets and boundary invariants, synthetic only."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from front.local_masking import detector_metadata
from front.models import (Company, Conversation, ConversationAlias, PrivacyMessage,
    PrivacyOccurrence, PrivacyRevision, PrivacySelection, Profile, Prompt, Rule, RulesGroup)
from front.policy import digest
from front.privacy import ProtectionContext, alias_value, protect_batch, protect_tree
from front.test_privacy_service import RegistryFixture


class BatchFixture(RegistryFixture):
    def setUp(self):
        super().setUp()
        self.revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='synthetic-batch', detector_version=digest(detector_metadata()))
        self.company.ai_config = {'privacy': {'version': 1, 'revision_id': self.revision.pk}}
        self.company.save()
        self.prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation)
        self.context = ProtectionContext.from_prompt(self.prompt)


class PrivacyBatchTests(BatchFixture, TestCase):
    def select_count(self, operation):
        with CaptureQueriesContext(connection) as captured:
            operation()
        return sum(query['sql'].lstrip().upper().startswith('SELECT') for query in captured)

    def test_neutral_tree_selects_do_not_scale_with_arbitrary_keys_or_retry(self):
        small = {'one_key': 'ordinary'}
        large = {f'ordinary_key_{index}': f'ordinary value {index}' for index in range(200)}
        cold_small = self.select_count(lambda: protect_tree(self.context, small))
        cold_large = self.select_count(lambda: protect_tree(self.context, large))
        warm_small = self.select_count(lambda: protect_tree(self.context, small))
        warm_large = self.select_count(lambda: protect_tree(self.context, large))
        self.assertEqual(cold_large, cold_small)
        self.assertEqual(warm_large, warm_small)
        self.assertLessEqual(cold_large, 16)
        self.assertEqual(protect_tree(self.context, large), large)

    def test_batch_queries_do_not_scale_with_distinct_sensitive_values(self):
        small = ['one@example.invalid']
        large = [f'fixture{index}@example.invalid' for index in range(80)]
        small_count = self.select_count(lambda: protect_batch(self.prompt, small))
        large_count = self.select_count(lambda: protect_batch(self.prompt, large))
        self.assertEqual(large_count, small_count)
        self.assertLessEqual(large_count, 18)
        self.assertEqual(ConversationAlias.objects.count(), 81)
        first = protect_batch(self.prompt, large)
        occurrences = PrivacyOccurrence.objects.count()
        self.assertEqual(first, protect_batch(self.prompt, large))
        self.assertEqual(occurrences, PrivacyOccurrence.objects.count())

    def test_keys_fields_references_variants_and_secrets_preserve_contract(self):
        first = protect_tree(self.context, {'email': 'ana@example.INVALID'})
        token = first['email']
        value = {'ana@example.invalid': 'Ana Fixture', 'full_name': 'Unselected Name',
            'email': 'ana@example.invalid', 'api_key': 'arbitrary-secret',
            'nested': [token, {'text': token + ' ana@example.invalid'}]}
        protected = protect_tree(self.context, value)
        encoded = json.dumps(protected)
        for original in ('ana@example.invalid', 'Ana Fixture', 'Unselected Name', 'arbitrary-secret'):
            self.assertNotIn(original, encoded)
        self.assertIn(token, protected)
        self.assertEqual(protected['email'], token)
        self.assertEqual(protected['full_name'], '[[REGULAI_PERSON]]')
        self.assertEqual(protected['api_key'], '[[REGULAI_SECRET]]')
        self.assertEqual(protected['nested'][1]['text'], token + ' ' + token)
        self.assertTrue(any(json.loads(row.variants) for row in PrivacyMessage.objects.all()))
        self.assertEqual(protect_tree(self.context, value), protected)

    def test_next_operation_rechecks_owner_tenant_active_user_and_policy(self):
        protect_tree(self.context, {'text': 'Ana Fixture'})
        Profile.objects.filter(pk=self.profile.pk).update(company=Company.objects.create(name='Other batch fixture'))
        with self.assertRaisesMessage(ValueError, 'privacy_access_revoked'):
            protect_tree(self.context, {'text': 'Ana Fixture'})
        Profile.objects.filter(pk=self.profile.pk).update(company=self.company)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        with self.assertRaisesMessage(ValueError, 'privacy_access_revoked'):
            protect_batch(self.prompt, ['Ana Fixture'])
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        self.company.ai_config = {}
        self.company.save()
        with self.assertRaisesMessage(ValueError, 'privacy_policy_revoked'):
            protect_tree(self.context, {'text': 'Ana Fixture'})

    def test_next_operation_rechecks_selections_and_yara_sources(self):
        protect_tree(self.context, {'text': 'Ana Fixture'})
        token = alias_value(self.context, 'FIELD', 'Selected new value')
        PrivacySelection.objects.create(alias=ConversationAlias.objects.get(token=token))
        with self.assertRaisesMessage(ValueError, 'privacy_policy_changed'):
            protect_tree(self.context, {'text': 'Ana Fixture'})
        PrivacySelection.objects.all().delete()
        source = 'rule fixture { strings: $x = "Ana" condition: $x }'
        rule = Rule.objects.create(name='Batch YARA fixture',
            rules_group=RulesGroup.objects.create(name='Batch rules', company=self.company),
            yara_rule=source, action='block')
        PrivacyRevision.objects.filter(pk=self.revision.pk).update(configuration=json.dumps({
            'yara': [{'rule_id': rule.pk, 'source_hash': digest(source), 'strings': ['$x']}]}))
        self.assertNotIn('Ana', json.dumps(protect_tree(self.context, {'content': 'Ana test'})))
        rule.yara_rule = source.replace('Ana', 'Other')
        rule.save(update_fields=['yara_rule'])
        with self.assertRaisesMessage(ValueError, 'privacy_yara_revision_changed'):
            protect_tree(self.context, {'content': 'Ana new text'})

    def test_structural_ids_still_check_explicit_selections(self):
        value = {'reservation_id': '0a410333-7203-4795-a2c9-014728a90544'}
        self.assertEqual(protect_tree(self.context, value), value)
        PrivacyRevision.objects.filter(pk=self.revision.pk).update(configuration=json.dumps({
            'literals': [{'text': value['reservation_id']}]}))
        with self.assertRaisesMessage(ValueError, 'privacy_selected_protocol_identifier'):
            protect_tree(self.context, value)

    def test_foreign_reference_fails_whole_batch_without_partial_registry(self):
        foreign = Conversation.objects.create(user=self.user)
        token = alias_value(ProtectionContext(self.company.pk, self.user.pk, foreign.pk), 'PERSON', 'Foreign fixture')
        before = ConversationAlias.objects.count()
        with self.assertRaisesMessage(ValueError, 'privacy_reference_unavailable'):
            protect_batch(self.prompt, ['new@example.invalid', token])
        self.assertEqual(ConversationAlias.objects.count(), before)
        self.assertFalse(PrivacyMessage.objects.exists())

    def test_large_aggregate_batches_keep_individual_fragment_limits(self):
        texts = ['a' * 270_000, 'b' * 270_000]
        self.assertEqual(protect_batch(self.prompt, texts), texts)
        self.assertEqual(PrivacyMessage.objects.count(), 2)

    def test_near_limit_batch_budgets_expanded_alias_sentinels(self):
        token = alias_value(self.context, 'EMAIL', 'fixture@example.invalid')
        segment = 'x' * (256_000 - len(token)) + token
        texts = [segment, segment]
        self.assertEqual(protect_batch(self.prompt, texts), texts)
        self.assertEqual(PrivacyMessage.objects.count(), 2)

    def test_batch_lookup_rotation_reuses_aliases_and_missing_original_fails(self):
        from django.conf import settings
        from cryptography.fernet import Fernet
        first = protect_batch(self.prompt, ['rotation@example.invalid'])[0]
        with override_settings(PRIVACY_LOOKUP_KEYS={1: settings.SECRET_KEY, 2: 'synthetic-rotation-key'}):
            result = protect_batch(self.prompt, ['rotation@example.invalid', 'new@example.invalid'], prefix='rotation')
        self.assertEqual(result[0], first)
        self.assertEqual(ConversationAlias.objects.get(token=result[1]).version, 2)
        with override_settings(ENCRYPTION_KEY=Fernet.generate_key().decode(), ENCRYPTION_KEY_FALLBACKS=[]):
            # Existing canonical messages do not reveal originals. A new alias
            # lookup must fail closed when encrypted registry values are lost.
            with self.assertRaises(ValueError):
                protect_batch(self.prompt, ['rotation@example.invalid'], prefix='missing-key')

    def test_mask_failure_rolls_back_whole_batch(self):
        with patch('front.local_masking.mask_local_texts', side_effect=TimeoutError('synthetic local timeout')):
            with self.assertRaises(TimeoutError):
                protect_batch(self.prompt, ['new@example.invalid', 'Ana Fixture'])
        self.assertFalse(ConversationAlias.objects.exists())
        self.assertFalse(PrivacyMessage.objects.exists())
        self.assertFalse(PrivacyOccurrence.objects.exists())

    def test_plain_and_selected_tokens_are_stable_in_legacy_mode(self):
        self.company.ai_config = {}
        self.company.save()
        value = {'email': 'legacy@example.invalid', 'nombre': 'Legacy Fixture'}
        first = protect_tree(self.context, value)
        self.assertEqual(protect_tree(self.context, first), first)
        self.assertFalse(PrivacyMessage.objects.exists())


@skipUnless(connection.vendor == 'postgresql', 'Writer interleaving requires disposable PostgreSQL')
class PrivacyBatchConcurrencyTests(BatchFixture, TransactionTestCase):
    def test_overlapping_tree_retries_share_aliases_messages_and_occurrences(self):
        barrier = Barrier(4)
        value = {'text': 'Ana Fixture ana@example.invalid', 'email': 'ana@example.invalid'}

        def protect():
            try:
                barrier.wait(timeout=10)
                return protect_tree(self.context, value)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: protect(), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(ConversationAlias.objects.count(), 2)
        self.assertEqual(PrivacyMessage.objects.count(), 4)
        self.assertEqual(PrivacyOccurrence.objects.count(), 3)
