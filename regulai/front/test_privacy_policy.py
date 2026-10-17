"""Deterministic text protection; synthetic fixtures only."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from front.local_masking import detector_metadata
from front.models import PrivacyRevision, Prompt, PrivacyMessage, PrivacyOccurrence, PrivacyUse
from front.policy import digest
from front.privacy import ProtectionContext, protect_message, record_use
from front.privacy_policy import PrivacyConfig, YaraSelection, compatible_strings, detect_ranges, yara_ranges
from front.test_privacy_service import RegistryFixture


class DetectorTests(SimpleTestCase):
    def test_all_literal_ranges_unicode_and_overlaps(self):
        config = PrivacyConfig.model_validate({'categories': {'EMAIL': 'reversible'},
            'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]})
        text = '🙂 Ana Fixture, ana@example.invalid; Ana Fixture'
        ranges = detect_ranges(text, config)
        self.assertEqual([text[a:b] for a, b, *_ in ranges], ['Ana Fixture', 'ana@example.invalid', 'Ana Fixture'])
        config.literals.append(config.literals[0])
        self.assertEqual(detect_ranges(text, config), ranges)
        secret = 'password=Ana Fixture'
        self.assertFalse(detect_ranges(secret, config)[0][3])

    def test_yara_all_instances_utf8_false_condition_and_no_positions(self):
        source = 'rule fixture { strings: $x = "Ana" condition: $x }'
        rule = SimpleNamespace(pk=7, yara_rule=source)
        selection = YaraSelection(rule_id=7, source_hash=digest(source), strings=['$x'])
        text = '🙂 Ana; Ana'
        self.assertEqual([text[a:b] for a,b,*_ in yara_ranges(text, selection, rule)], ['Ana', 'Ana'])
        rule.yara_rule = source.replace('condition: $x', 'condition: $x and false')
        selection.source_hash = digest(rule.yara_rule)
        self.assertEqual(yara_ranges(text, selection, rule), [])
        rule.yara_rule = source.replace('condition: $x', 'condition: $x or filesize > 0')
        selection.source_hash = digest(rule.yara_rule)
        with self.assertRaisesMessage(ValueError, 'privacy_yara_no_positions'):
            yara_ranges('no matching value', selection, rule)

    def test_yara_wide_binary_truncation_split_character_timeout_and_revision(self):
        for source in ('rule x { condition: true }',
            'rule x { strings: $a = "foo" wide condition: $a }',
            'rule x { strings: $a = { 41 42 } condition: $a }'):
            with self.assertRaises(ValueError):
                compatible_strings(source)
        source = 'rule fixture { strings: $x = "Ana" condition: $x }'
        rule = SimpleNamespace(pk=7, yara_rule=source)
        selection = YaraSelection(rule_id=7, source_hash=digest(source), strings=['$x'])
        for offset, length, data in [(1, 1, b'\x9f'), (0, 4, b'\xf0')]:
            instance = SimpleNamespace(offset=offset, matched_length=length, matched_data=data)
            match = SimpleNamespace(strings=[SimpleNamespace(identifier='$x', instances=[instance])])
            with patch('front.privacy_policy.yara.compile') as compile:
                compile.return_value.match.return_value = [match]
                with self.assertRaisesMessage(ValueError, 'privacy_yara_position_invalid'):
                    yara_ranges('🙂 Ana', selection, rule)
        with patch('front.privacy_policy.yara.compile', side_effect=TimeoutError):
            with self.assertRaisesMessage(ValueError, 'privacy_yara_failed'):
                yara_ranges('Ana', selection, rule)
        rule.yara_rule += ' invalid'
        with self.assertRaisesMessage(ValueError, 'privacy_yara_revision_changed'):
            yara_ranges('Ana', selection, rule)


class ProtectedMessageTests(RegistryFixture, TestCase):
    def setUp(self):
        super().setUp()
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='synthetic', detector_version=digest(detector_metadata()))
        self.company.ai_config = {'privacy': {'version': 1, 'revision_id': revision.pk}}
        self.company.save()
        prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation)
        self.context = ProtectionContext.from_prompt(prompt)

    def test_atomic_idempotent_messages_and_use_counts(self):
        original = 'Ana Fixture ana@example.invalid ana@example.invalid'
        protected = protect_message(self.context, original, source_key='input')
        self.assertNotIn('Ana Fixture', protected)
        self.assertNotIn('ana@example.invalid', protected)
        self.assertEqual(protect_message(self.context, original, source_key='input'), protected)
        self.assertEqual(PrivacyMessage.objects.count(), 1)
        self.assertEqual(PrivacyOccurrence.objects.count(), 3)
        for _ in range(2):
            record_use(self.context, 'inference:1', [protected])
        self.assertEqual(sorted(PrivacyUse.objects.values_list('count', flat=True)), [1, 2])
        with self.assertRaisesMessage(ValueError, 'privacy_idempotency_conflict'):
            protect_message(self.context, original + ' changed', source_key='input')

    def test_variants_are_encrypted_and_preserve_exact_spelling(self):
        protect_message(self.context, 'ana@example.INVALID', source_key='first')
        protect_message(self.context, 'ana@example.invalid', source_key='second')
        row = PrivacyMessage.objects.get(source_key='second')
        self.assertEqual(json.loads(row.variants), {'0': 'ana@example.invalid'})
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT variants FROM front_privacymessage WHERE id = %s', [row.pk])
            self.assertNotIn('ana@example.invalid', cursor.fetchone()[0])


class PolicyReviewTests(RegistryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()
        self.company.ai_config = {'version': 1, 'allow_empty_rules': True,
            'local_sensitivity': 'internal', 'destinations': {'internal': ['engine:1']}}
        self.company.save()

    def test_signed_simulation_does_not_activate_and_stale_review_is_rejected(self):
        from front.privacy_policy import simulate_revision, activate_revision
        result = simulate_revision(self.user, {'categories': {'EMAIL': 'reversible'}}, 'fixture@example.invalid')
        self.assertNotIn('fixture@example.invalid', result['protected'])
        self.assertEqual(result['calls'], [])
        self.company.refresh_from_db()
        self.assertNotIn('privacy', self.company.ai_config)
        self.company.ai_config['revision'] = 2
        self.company.save()
        with self.assertRaisesMessage(ValueError, 'privacy_review_stale'):
            activate_revision(self.user, result['revision_id'], result['review_token'])
        result = simulate_revision(self.user, {'categories': {'EMAIL': 'reversible'}}, 'fixture@example.invalid')
        activate_revision(self.user, result['revision_id'], result['review_token'])
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config['privacy']['revision_id'], result['revision_id'])

    def test_yara_selection_never_changes_block_action(self):
        from front.models import Rule, RulesGroup
        from front.privacy_policy import simulate_revision
        source = 'rule fixture { strings: $x = "Ana" condition: $x }'
        rule = Rule.objects.create(name='Fixture rule', rules_group=RulesGroup.objects.create(name='Fixture', company=self.company),
            yara_rule=source, action='block')
        result = simulate_revision(self.user, {'yara': [{'rule_id': rule.pk, 'source_hash': digest(source),
            'strings': ['$x']}]}, 'Ana')
        self.assertEqual(result['decision']['policy']['status'], 'block')
        rule.refresh_from_db()
        self.assertEqual(rule.action, 'block')
