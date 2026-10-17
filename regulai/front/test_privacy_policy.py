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
            'rule first { strings: $x="Ana" condition: false } rule second { strings: $x={41 42} condition:$x }',
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

    def test_structured_fields_obey_effective_treatment(self):
        from front.privacy import protect_tree
        from front.models import ConversationAlias
        protected = protect_tree(self.context, {'email': 'ana@example.invalid', 'full_name': 'Nombre no seleccionado'})
        self.assertTrue(protected['email'].startswith('[[R_EMAIL_'))
        self.assertEqual(protected['full_name'], '[[REGULAI_PERSON]]')
        self.assertEqual(ConversationAlias.objects.count(), 1)
        self.assertEqual(PrivacyOccurrence.objects.filter(alias__isnull=False).count(), 1)

    def test_positions_disambiguate_preexisting_same_token(self):
        token = protect_message(self.context, 'ana@example.invalid', source_key='first')
        result = protect_message(self.context, token + ' luego ana@example.INVALID', source_key='second')
        message = PrivacyMessage.objects.get(source_key='second')
        offset = len((token + ' luego ').encode())
        self.assertEqual(message.occurrences.get().start, offset)
        self.assertEqual(json.loads(message.variants), {str(offset): 'ana@example.INVALID'})
        self.assertEqual(result, token + ' luego ' + token)

    def test_final_gate_detects_metadata_without_previous_occurrence(self):
        from front.privacy import outbound
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        with self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
            outbound(prompt, 'metadata', ['hola'], metadata=['https://provider.invalid/ana@example.invalid/v1'])
        with self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
            outbound(prompt, 'remask', ['Ana Fixture'])

    def test_repeated_literal_prefix_is_never_partially_published(self):
        from front.privacy import stream_cut
        revision = PrivacyRevision.objects.get(pk=self.company.ai_config['privacy']['revision_id'])
        PrivacyRevision.objects.filter(pk=revision.pk).update(configuration=json.dumps({
            'literals': [{'text': 'aba aba z', 'category': 'FIELD'}]}))
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        text = 'ordinary aba aba z' + 'x' * 96
        self.assertEqual(stream_cut(prompt, text, len('ordinary aba aba ')), len('ordinary '))

    def test_page_after_protection_cannot_split_original(self):
        from front.privacy import protect_tree
        from front.agents.general_tools import _projection
        raw = 'x' * 2042 + 'Ana Fixture'
        safe = protect_tree(self.context, raw)
        view = _projection(SimpleNamespace(name='read_file', id='fixture'),
            SimpleNamespace(raw=safe, failed=False), 4096)
        combined = view['output'] + safe[view['next_offset']:]
        self.assertEqual(combined, safe)
        self.assertNotIn('Ana Fixture', combined)


    def test_call_identity_includes_the_whole_payload_and_empty_alias_set(self):
        first = protect_message(self.context, 'ana@example.invalid', source_key='one')
        second = protect_message(self.context, 'other@example.invalid', source_key='two')
        record_use(self.context, 'call:one', [first])
        for changed in ([second], [], [first, second]):
            with self.assertRaisesMessage(ValueError, 'privacy_idempotency_conflict'):
                record_use(self.context, 'call:one', changed)
        record_use(self.context, 'call:empty', [])
        with self.assertRaisesMessage(ValueError, 'privacy_idempotency_conflict'):
            record_use(self.context, 'call:empty', [first])
        self.assertEqual(PrivacyUse.objects.count(), 1)

    def test_outbound_checks_decoded_urls_json_strings_and_selected_credentials(self):
        from front.privacy import outbound
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        for value in ('https://example.invalid/Ana%20Fixture', 'https://example.invalid/?q=Ana+Fixture',
                      'https://example.invalid/?q=Ana%2520Fixture'):
            with self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
                outbound(prompt, 'url', [], metadata=[value])
        revision = PrivacyRevision.objects.get(pk=self.company.ai_config['privacy']['revision_id'])
        for original in ('Ana\nFixture', 'Ana"Fixture'):
            PrivacyRevision.objects.filter(pk=revision.pk).update(configuration=json.dumps({'literals': [{'text': original}]}))
            with self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
                outbound(prompt, 'escaped', [json.dumps({'title': original})])
        PrivacyRevision.objects.filter(pk=revision.pk).update(configuration=json.dumps({'literals': [{'text': 'fixture-credential'}]}))
        with self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
            outbound(prompt, 'credential', ['ordinary'], credentials=['fixture-credential'])
        outbound(prompt, 'operational', ['ordinary'], credentials=['sk-synthetic-operational-key'])

    def test_numeric_json_values_and_scientific_notation_cannot_cross_boundary(self):
        from front.privacy import outbound
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        PrivacyRevision.objects.filter(pk=self.company.ai_config['privacy']['revision_id']).update(
            configuration=json.dumps({'categories': {'PHONE': 'reversible', 'CARD': 'reversible'}}))
        for value in ('612345678', '{"telefono":612345678}', '{"telefono":6.12345678e8}',
                      '[612345678]', '{"card":4111111111111111}',
                      '{"card":6212345678901234569.0}', '{"card":6.212345678901234569e18}'):
            with self.subTest(value=value), self.assertRaisesMessage(ValueError, 'privacy_original_at_boundary'):
                outbound(prompt, 'number', [value])
        outbound(prompt, 'counts', ['{"count":42,"enabled":true}'])

    def test_validation_only_does_not_count_an_internal_hop(self):
        from front.privacy import outbound
        from front.models import PrivacyCall
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        value = protect_message(self.context, 'Ana Fixture', source_key='bootstrap')
        outbound(prompt, 'internal', [value], record=False)
        self.assertFalse(PrivacyCall.objects.exists())
        for _ in range(2):
            outbound(prompt, 'worker:response', [value])
        self.assertEqual(PrivacyCall.objects.count(), 1)
        self.assertEqual(PrivacyUse.objects.get().count, 1)

    def test_protocol_reservation_uuid_is_preserved_but_explicit_selection_still_blocks(self):
        from front.privacy import protect_tree, outbound
        prompt = Prompt.objects.get(pk=self.context.prompt_id)
        value = {'reservation_id': '0a410333-7203-4795-a2c9-014728a90544'}
        revision_id = self.company.ai_config['privacy']['revision_id']
        PrivacyRevision.objects.filter(pk=revision_id).update(configuration=json.dumps({'categories': {'CARD': 'reversible'}}))
        self.assertEqual(protect_tree(self.context, value), value)
        outbound(prompt, 'reservation', [json.dumps(value)])
        PrivacyRevision.objects.filter(pk=revision_id).update(configuration=json.dumps({'literals': [{'text': value['reservation_id']}]}))
        with self.assertRaises(ValueError):
            outbound(prompt, 'reservation-selected', [json.dumps(value)])


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
