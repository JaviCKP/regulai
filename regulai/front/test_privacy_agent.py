import json

from django.test import TestCase, override_settings

from front.local_masking import detector_metadata
from front.models import AgentExecution, PrivacyRevision, ConversationAlias
from front.policy import digest
from front.agents.service import _context
from front.test_agent_inference import AgentFixture


@override_settings(REGULAY_AGENT_ENABLED=True)
class PrivacyAgentTests(AgentFixture, TestCase):
    def setUp(self):
        super().setUp()
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='synthetic', detector_version=digest(detector_metadata()))
        self.company.ai_config['privacy'] = {'version': 1, 'revision_id': revision.pk}
        self.company.save()
        AgentExecution.objects.filter(pk=self.execution.pk).update(
            authorization_digest=_context(self.prompt, self.agent.pk)[-1])
        self.execution.refresh_from_db()

    def test_generation_and_summary_protect_selected_values(self):
        for purpose in ('generation', 'compaction'):
            result = self.infer(self.request(purpose=purpose, messages=[{'role': 'user',
                'content': 'Hola Ana Fixture, ana@example.invalid'}]))
            self.assertEqual(result['status'], 'completed', result)
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, json.dumps(self.requests))
        self.assertEqual(ConversationAlias.objects.count(), 2)

    def test_worker_binary_and_original_resolution_are_denied(self):
        from front.agents.jobs import bootstrap
        self.execution.job = {'source': str(self.asset.pk)}
        self.execution.save(update_fields=['job'])
        from front.agents.service import AgentDenied
        with self.assertRaises(AgentDenied):
            bootstrap(self.token, self.execution.attempt, {})
