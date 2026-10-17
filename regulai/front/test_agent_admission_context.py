"""Admission reuses preparation rows, then checks fresh authority before commit."""
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings

from front.agents import professional, service
from front.agents.capabilities import GENERAL
from front.models import AgentAccessGrant, AgentExecution, AgentInput, Prompt, Rule, RulesGroup
from front.test_agent_inference import AgentFixture


@override_settings(REGULAY_AGENT_ENABLED=True, DEBUG=False)
class AdmissionContextTests(AgentFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch('socket.create_connection', side_effect=AssertionError('External network forbidden')))
        self.agent.professional, self.agent.tools = True, sorted(GENERAL)
        self.agent.save()
        self.grant = AgentAccessGrant.objects.create(company=self.company, user=self.user,
                                                     profile=self.agent, enabled=True)
        self.client.force_login(self.user)

    def send(self, identity=None):
        return self.client.post('/chat/send/', {'prompt': 'Hola', 'content': 'Hola',
            'mode': 'agent', 'request_id': str(identity or uuid.uuid4())})

    def test_public_begin_execution_keeps_two_value_contract(self):
        prompt = Prompt.objects.create(user=self.user, company=self.company, conversation=self.conversation,
                                       status='processing', content='New synthetic request')
        with patch.object(service, '_context', wraps=service._context) as contexts:
            result = service.begin_execution(prompt, self.agent.pk)
        self.assertEqual(len(result), 2)
        run, token = result
        self.assertEqual(run.prompt_id, prompt.pk)
        self.assertIsInstance(token, str)
        self.assertEqual(contexts.call_count, 1)

    def test_professional_admission_checks_initial_and_final_context(self):
        with patch.object(service, '_context', wraps=service._context) as initial, \
                patch.object(professional, '_context', wraps=professional._context) as final:
            response = self.send()
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(initial.call_count, 1)
        self.assertEqual(final.call_count, 1)
        run = AgentExecution.objects.get(pk=response.json()['agent']['id'])
        self.assertEqual(run.status, 'queued')
        self.assertEqual(run.job['version'], 2)
        self.assertEqual(run.authorization_digest, service._context(run.prompt, run.profile_id)[-1])
        self.assertFalse(self.requests)

    def assert_late_revocation(self, revoke):
        original = professional._begin_execution_with_context
        identity = uuid.uuid4()
        before = (AgentExecution.objects.count(), AgentInput.objects.count(), Prompt.objects.count())

        def after_initial(*args, **kwargs):
            result = original(*args, **kwargs)
            revoke()
            return result

        with patch.object(professional, '_begin_execution_with_context', side_effect=after_initial) as begun:
            response = self.send(identity)
        begun.assert_called_once()
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Prompt.objects.filter(request_id=identity).exists())
        self.assertFalse(AgentExecution.objects.filter(status='queued').exists())
        self.assertEqual((AgentExecution.objects.count(), AgentInput.objects.count(), Prompt.objects.count()), before)
        self.assertFalse(self.requests)

    def test_grant_revocation_after_initial_context_rolls_back_admission(self):
        self.assert_late_revocation(lambda: AgentAccessGrant.objects.filter(pk=self.grant.pk).update(enabled=False))

    def test_connection_revocation_after_initial_context_rolls_back_admission(self):
        self.assert_late_revocation(lambda: type(self.credential).objects.filter(pk=self.credential.pk).update(active=False))

    def test_new_blocking_policy_after_initial_context_rolls_back_admission(self):
        def block():
            group = RulesGroup.objects.create(name='Late synthetic policy', company=self.company)
            Rule.objects.create(name='Late block', rules_group=group, action='block',
                                yara_rule='rule LateBlock { condition: true }')
        self.assert_late_revocation(block)
