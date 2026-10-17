import json
from django.test import TestCase
from front.models import PrivacyRevision, PrivacyMessage, Prompt, Profile, ConversationAlias
from front.privacy import ProtectionContext, protect_message, record_use, alias_value
from front.privacy_presentation import Presentation, ChatPresentation, project_message
from front.privacy_projection import UNAVAILABLE
from front.local_masking import detector_metadata
from front.policy import digest
from front.test_privacy_service import RegistryFixture


class PresentationTests(RegistryFixture, TestCase):
    def setUp(self):
        super().setUp()
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'},
                    {'text': '<img src="https://exfil.invalid/">[click](https://exfil.invalid/)\u0001', 'category': 'FIELD'}]}),
            fingerprint='synthetic', detector_version=digest(detector_metadata()))
        self.company.ai_config = {'privacy': {'version': 1, 'revision_id': revision.pk}}
        self.company.save()
        self.prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation)
        self.context = ProtectionContext.from_prompt(self.prompt)
        self.original = 'Ana Fixture escribe a ana@example.invalid.'
        self.protected = protect_message(self.context, self.original, source_key='user')
        record_use(self.context, 'inference-one:0', [self.protected])
        self.prompt.decision = {'privacy_answer': {'inference_id': 'inference-one'}}
        self.prompt.save(update_fields=['decision'])

    def test_two_consumers_replay_and_final_match_complete_with_canonical_offsets(self):
        sessions = [ChatPresentation(self.user.pk, self.prompt.request_id) for _ in range(2)]
        chunks = [self.protected[:14], self.protected[14:37], self.protected[37:]]
        text = ''
        for seq, chunk in enumerate(chunks, 1):
            event = {'type': 'delta', 'seq': seq, 'attempt': 1, 'text': chunk, 'privacy_call_key': 'inference-one:0'}
            views = [session.event(event) for session in sessions]
            self.assertEqual(views[0], views[1])
            self.assertNotIn('projection', event)  # Canonical retained events unchanged.
            text += views[0]['projection']['text']
        self.assertEqual(text, self.original)
        self.assertEqual(views[0]['projection']['protected_end'], len(self.protected.encode()))
        self.assertEqual(project_message(self.user.pk, self.prompt, self.protected)['text'], self.original)
        self.assertNotIn(self.original, PrivacyMessage.objects.get().protected)

    def test_every_feed_revalidates_current_owner_and_tenant(self):
        session = Presentation(self.user.pk, self.prompt)
        session.feed('ordinary ')
        from front.models import Company
        Profile.objects.filter(user=self.user).update(company=Company.objects.create(name='Other synthetic tenant'))
        with self.assertRaisesMessage(ValueError, 'privacy_access_revoked'):
            session.feed(self.protected, final=True)
        with self.assertRaises(ValueError):
            Presentation(self.user.pk + 100, self.prompt)

    def test_inference_allowlist_and_purged_original_fail_closed(self):
        unavailable = project_message(self.user.pk, self.prompt, self.protected, inference_id='another')
        self.assertNotIn('Ana Fixture', unavailable['text'])
        self.assertIn(UNAVAILABLE, unavailable['text'])
        allowed = project_message(self.user.pk, self.prompt, self.protected, inference_id='inference-one')
        self.assertEqual(allowed['text'], self.original)
        ConversationAlias.objects.all().delete()
        self.assertNotIn('Ana Fixture', project_message(self.user.pk, self.prompt, self.protected)['text'])

    def test_revoke_policy_stops_projection_and_nested_values_stay_opaque(self):
        secret = '<img src="https://exfil.invalid/">[click](https://exfil.invalid/)\x01'
        token = alias_value(self.context, 'FIELD', secret)
        from front.models import PrivacyUse
        PrivacyUse.objects.create(turn=self.prompt.privacyturn, call_key='inference-one:1',
                                  alias=ConversationAlias.objects.get(token=token), count=1)
        view = project_message(self.user.pk, self.prompt, token)
        self.assertEqual(view['segments'][0]['kind'], 'original')
        self.assertEqual(view['text'], secret)
        self.assertEqual(view['render'], 'text')
        self.company.ai_config = {}
        self.company.save()
        with self.assertRaises(ValueError):
            project_message(self.user.pk, self.prompt, self.protected)

    def test_purge_revokes_a_live_parser_and_off_revokes_history_recovery(self):
        session = Presentation(self.user.pk, self.prompt, inference_id='inference-one')
        session.feed(self.protected)
        ConversationAlias.objects.all().delete()
        with self.assertRaisesMessage(ValueError, 'privacy_projection_revoked'):
            session.feed(' more')
