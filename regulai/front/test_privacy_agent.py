import json
import httpx
from unittest.mock import patch

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
        self.wire = []
        send = httpx.Client.send
        def captured(client, request, *args, **kwargs):
            self.wire.append({'url': str(request.url), 'headers': dict(request.headers),
                'body': request.content.decode()})
            return send(client, request, *args, **kwargs)
        self.enterContext(patch.object(httpx.Client, 'send', new=captured))

    def test_generation_and_summary_protect_selected_values(self):
        for purpose in ('generation', 'compaction'):
            result = self.infer(self.request(purpose=purpose, messages=[{'role': 'user',
                'content': 'Hola Ana Fixture, ana@example.invalid'}]))
            self.assertEqual(result['status'], 'completed', result)
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, json.dumps(self.requests))
            self.assertNotIn(original, json.dumps(self.wire))
        self.assertEqual(len(self.wire), 2)
        self.assertEqual(ConversationAlias.objects.count(), 2)

    def test_worker_binary_and_original_resolution_are_denied(self):
        from front.agents.jobs import bootstrap
        self.execution.job = {'source': str(self.asset.pk)}
        self.execution.save(update_fields=['job'])
        from front.agents.service import AgentDenied
        with self.assertRaises(AgentDenied):
            bootstrap(self.token, self.execution.attempt, {})

    def test_agent_batches_reconstruct_each_consumer_and_finalize_a_truncated_reference(self):
        from front.privacy import ProtectionContext, protect_message, record_use
        from front.privacy_presentation import agent_batch, agent_snapshots
        from front.agents.event_store import append_event, serialized_event, text_snapshot
        from front.privacy_projection import UNAVAILABLE
        context = ProtectionContext.from_prompt(self.prompt)
        protected = protect_message(context, 'Ana Fixture ana@example.invalid', source_key='fixture')
        record_use(context, 'fixture-inference:0', [protected])
        canonical = protected + ' [[R_PERSON_partial'
        rows, offset = [], 0
        for piece in (canonical[:15], canonical[15:54], canonical[54:]):
            rows.append(append_event(self.execution, 'text.delta', public_text=piece,
                message_id='fixture-message', inference_id='fixture-inference', offset=offset))
            offset += len(piece.encode())
        rows.append(append_event(self.execution, 'inference.finished', message_id='fixture-message', inference_id='fixture-inference'))
        first = agent_batch(self.user.pk, self.execution, [serialized_event(row) for row in rows])
        second = agent_batch(self.user.pk, self.execution, [serialized_event(row) for row in rows[1:]], rows[0].pk)
        self.assertEqual(first[1:], second)
        self.assertEqual(''.join(event['data'].get('projection', {}).get('text', '') for event in first),
                         'Ana Fixture ana@example.invalid ' + UNAVAILABLE)
        snapshot = agent_snapshots(self.user.pk, self.execution, text_snapshot(self.execution))[0]
        self.assertTrue(snapshot['projection']['complete'])
        self.assertEqual(snapshot['projection']['text'], 'Ana Fixture ana@example.invalid ' + UNAVAILABLE)
        self.assertNotIn('Ana Fixture', ''.join(row.public_text for row in rows))
