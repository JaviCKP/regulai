"""Fresh authorization rows are shared only inside a single egress preflight."""
from copy import deepcopy
import base64
import hashlib
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from front.agents.capabilities import GENERAL
from front.agents.history import for_prompt, _identity
from front.agents.service import AgentDenied, _context, _government, authenticate
from front.chat_service import authorized_history
from front.governance import PipelineStop
from front.models import (AgentAccessGrant, AgentExecution, Company, CompanyEngine,
                          EngineModel, Message, ObfuscationConfig, Profile, Prompt, Response, Rule, RulesGroup)
from front.policy import digest
from front.test_agent_inference import AgentFixture


@override_settings(REGULAY_AGENT_ENABLED=True, DEBUG=False)
class AgentContextPerformanceTests(AgentFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('External network forbidden')))
        self.agent.professional, self.agent.tools = True, sorted(GENERAL)
        self.agent.save(update_fields=['professional', 'tools'])
        # AgentFixture's task-49 grant is plain CSV; chat jobs store its bytes
        # as base64 and use the byte digest checked by jobs._decode.
        raw = self.asset.original.encode()
        self.asset.original, self.asset.digest = base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()
        self.asset.save(update_fields=['original', 'digest'])
        self.grant = AgentAccessGrant.objects.create(company=self.company, user=self.user,
            profile=self.agent, enabled=True)
        self.conversation.mode = 'agent'
        self.conversation.save(update_fields=['mode'])
        self.execution.job = {'kind': 'professional', 'version': 2, 'history': {'pairs': []}}
        self.execution.save(update_fields=['job'])
        self.rebind()

    def rebind(self):
        AgentExecution.objects.filter(pk=self.execution.pk).update(
            authorization_digest=_context(self.prompt, self.agent.pk)[-1])
        self.run, self.context = authenticate(self.token, self.execution.attempt)
        self.government = _government(self.run, self.context, self.token,
            self.execution.attempt, uuid.uuid4())

    def preflight(self, extra=''):
        return self.government.preflight(f'engine:{self.credential.pk}',
            self.context[8] + [('prompts', extra)], model_pk=self.model.pk)

    def test_authentication_reads_execution_once_and_joins_provider_rows(self):
        with CaptureQueriesContext(connection) as queries:
            authenticate(self.token, self.execution.attempt)
        sql = [item['sql'].lower() for item in queries]
        self.assertEqual(sum('from "front_agentexecution"' in query for query in sql), 1)
        self.assertFalse(any('from "front_companyengine"' in query for query in sql))
        self.assertFalse(any('from "front_enginemodel"' in query for query in sql))
        self.assertFalse(any('from "front_agentmodelprofile"' in query for query in sql))
        # Empty immutable history adds no second account/profile read.
        self.assertEqual(sum('from "front_profile"' in query for query in sql), 1)

    def test_preflight_does_not_rebuild_rows_just_authenticated(self):
        with CaptureQueriesContext(connection) as authentication:
            authenticate(self.token, self.execution.attempt)
        with CaptureQueriesContext(connection) as boundary:
            self.preflight()
        # The non-private fixture needs two current privacy-presence reads and
        # the independent exact-output YARA/policy query. It needs no second
        # profile, masks, history, engine or model reconstruction.
        self.assertEqual(len(boundary), len(authentication) + 3)

    def test_each_boundary_observes_revocations_and_changed_authority(self):
        changed_config = deepcopy(self.company.ai_config)
        changed_config['revision'] = 2
        other = Company.objects.create(name='Other context scope')
        cases = [
            (User.objects.filter(pk=self.user.pk), {'is_active': False}, {'is_active': True}),
            (Profile.objects.filter(pk=self.profile.pk), {'company_id': other.pk}, {'company_id': self.company.pk}),
            (AgentAccessGrant.objects.filter(pk=self.grant.pk), {'enabled': False}, {'enabled': True}),
            (AgentAccessGrant.objects.filter(pk=self.grant.pk), {'version': 2}, {'version': 1}),
            (CompanyEngine.objects.filter(pk=self.credential.pk), {'active': False}, {'active': True}),
            (EngineModel.objects.filter(pk=self.model.pk), {'active': False}, {'active': True}),
            (ObfuscationConfig.objects.filter(pk=self.mask.pk), {'language': 'en'}, {'language': self.mask.language}),
            (Company.objects.filter(pk=self.company.pk), {'ai_config': changed_config}, {'ai_config': self.company.ai_config}),
        ]
        for queryset, change, restore in cases:
            with self.subTest(change=change):
                self.preflight()
                queryset.update(**change)
                try:
                    with self.assertRaises((AgentDenied, PipelineStop)):
                        self.preflight()
                finally:
                    queryset.update(**restore)
        self.assertFalse(self.requests)

    def test_same_context_still_checks_new_output_with_yara(self):
        group = RulesGroup.objects.create(name='Boundary exact output', company=self.company)
        Rule.objects.create(name='Block boundary marker', rules_group=group,
            yara_rule='rule Boundary { strings: $s = "boundary-forbidden-marker" condition: $s }')
        self.rebind()
        self.preflight('Allowed output')
        with self.assertRaisesMessage(PipelineStop, 'security_check_failed'):
            self.preflight('boundary-forbidden-marker')
        self.assertFalse(self.requests)

    def test_joined_provider_still_rejects_foreign_tenant_and_model(self):
        other = Company.objects.create(name='Foreign provider scope')
        CompanyEngine.objects.filter(pk=self.credential.pk).update(company=other)
        with self.assertRaisesMessage(AgentDenied, 'agent_profile_unavailable'):
            authenticate(self.token, self.execution.attempt)
        CompanyEngine.objects.filter(pk=self.credential.pk).update(company=self.company)
        from front.models import Engine
        foreign_engine = Engine.objects.create(name='Foreign engine', connector_type='openai')
        EngineModel.objects.filter(pk=self.model.pk).update(engine=foreign_engine)
        with self.assertRaisesMessage(AgentDenied, 'agent_profile_unavailable'):
            authenticate(self.token, self.execution.attempt)
        self.assertFalse(self.requests)

    def test_history_snapshot_changes_are_not_retained_between_authentications(self):
        self.preflight()
        job = deepcopy(self.run.job)
        job['history']['pairs'] = [{'prompt_id': 999999, 'user_id': 1,
            'assistant_id': 2, 'digest': 'missing-history'}]
        AgentExecution.objects.filter(pk=self.run.pk).update(job=job)
        with self.assertRaisesMessage(AgentDenied, 'history_authorization_changed'):
            self.preflight()

    def add_history_pair(self):
        user_message = Message.objects.create(conversation=self.conversation, role='user',
            content='Previously approved question')
        assistant_message = Message.objects.create(conversation=self.conversation, role='assistant',
            content='Previously approved answer')
        previous = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation,
            user_message=user_message, content=user_message.content, status='completed',
            decision={'history_eligible': True, 'history_digest': digest([user_message.content, assistant_message.content])})
        Response.objects.create(prompt=previous, assistant_message=assistant_message, content=assistant_message.content)
        return authorized_history(self.user, self.conversation, window=False, provenance=True, professional=True)['pairs'][0]

    def test_empty_history_preserves_selection_without_materializing_available_messages(self):
        pair = self.add_history_pair()
        self.assertEqual(len(pair['messages']), 2)
        with self.assertNumQueries(0):
            self.assertEqual(for_prompt(self.user, self.prompt, execution=self.run), [])
        # The normal caller still reads the current execution once.
        with self.assertNumQueries(1):
            self.assertEqual(for_prompt(self.user, self.prompt), [])
        self.assertEqual(authenticate(self.token, self.execution.attempt)[1][9], [])

    def test_selecting_valid_history_after_empty_snapshot_invalidates_authorization(self):
        pair = self.add_history_pair()
        job = deepcopy(self.run.job)
        job['history']['pairs'] = [_identity(pair)]
        AgentExecution.objects.filter(pk=self.run.pk).update(job=job)
        # A nonempty selection still checks and includes the exact approved pair.
        self.assertEqual(for_prompt(self.user, self.prompt), pair['messages'])
        with self.assertRaises(AgentDenied):
            authenticate(self.token, self.execution.attempt)
        self.assertFalse(self.requests)

    def test_empty_history_does_not_bypass_changed_conversation_owner(self):
        other = User.objects.create_user('Other conversation owner')
        type(self.conversation).objects.filter(pk=self.conversation.pk).update(user=other)
        with self.assertRaises(AgentDenied):
            authenticate(self.token, self.execution.attempt)
        self.assertFalse(self.requests)

    def test_context_digest_is_identical_with_the_fresh_execution_row(self):
        direct = _context(self.run.prompt, self.agent.pk)
        supplied = _context(self.run.prompt, self.agent.pk, execution=self.run)
        self.assertEqual(direct[-1], supplied[-1])
        self.assertEqual(supplied[-1], self.run.authorization_digest)

    def test_mixed_tenant_conversation_still_revokes_owner_access(self):
        other = Company.objects.create(name='Mixed conversation tenant')
        Prompt.objects.create(user=self.user, company=other, conversation=self.conversation,
            content='Foreign provenance', status='completed')
        with self.assertRaises(AgentDenied):
            authenticate(self.token, self.execution.attempt)
        self.assertFalse(self.requests)

    def test_earlier_foreign_grant_keeps_historical_binding_semantics(self):
        from front.agents.capabilities import grant_binding, profile_for
        other = Company.objects.create(name='Foreign grant provenance')
        # Existing binding selects the first user/profile row independently of
        # the account resolver. Keep this conservative revocation behavior even
        # for inconsistent legacy records instead of silently normalizing it.
        foreign = AgentAccessGrant.objects.create(pk=0, user=self.user, company=other,
            profile=self.agent, enabled=False, version=99)
        self.assertEqual(profile_for(self.user), self.agent.pk)
        self.assertEqual(grant_binding(self.user, self.agent.pk)[0], foreign.pk)
        with self.assertRaises(AgentDenied):
            authenticate(self.token, self.execution.attempt)
        self.grant.delete()
        with self.assertRaisesMessage(AgentDenied, 'agent_access_denied'):
            authenticate(self.token, self.execution.attempt)

