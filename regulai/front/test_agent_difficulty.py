"""Agent difficulty receipts and invariants through simulated provider HTTP."""
from decimal import Decimal
import json
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from front import test_agent_transparency as transparency
from front.models import AgentExecution, CompanyEngine
from front.test_agent_inference import AgentFixture


def difficulty_answers(choice='easy', confidence=1.0):
    other = 'hard' if choice == 'easy' else 'easy'
    return {'difficulty': {'type': 'choice', 'choice': choice, 'confidence': confidence,
        'probabilities': {choice: confidence, other: 1 - confidence}}}


@override_settings(REGULAY_AGENT_ENABLED=True)
class AgentDifficultyTests(AgentFixture, TestCase):
    configure = transparency.AgentTransparencyTests.configure
    simulated_jev = transparency.AgentTransparencyTests.simulated_jev
    receipt = transparency.AgentTransparencyTests.receipt

    def setUp(self):
        super().setUp()
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('Live network forbidden')))

    def difficulty(self, **config):
        self.configure(classification='local',
            routing={'mode': 'auto', 'strategy': 'difficulty'}, **config)

    def assert_difficulty(self, choice, level, confidence=1.0):
        self.difficulty()
        captured = self.simulated_jev(answers=difficulty_answers(choice, confidence))
        result = self.infer()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(captured), 1)
        self.assertEqual(set(captured[0]['payload']['questions']), {'difficulty'})
        receipt = self.receipt()
        self.assertEqual(receipt['jev']['purpose'], 'difficulty')
        self.assertEqual(receipt['jev']['status'], 'consulted')
        self.assertEqual(receipt['jev']['decision'], {'difficulty': choice})
        self.assertEqual(receipt['jev']['signals'], difficulty_answers(choice, confidence))
        self.assertEqual(receipt['jev']['applied'], {
            'source': 'regulay_policy', 'sensitivity': 'internal', 'difficulty': level})
        self.assertEqual(receipt['policy']['source'], 'local_policy')
        self.assertEqual(receipt['policy']['sensitivity'], 'internal')
        self.assertEqual(receipt['route']['mode'], 'agent_profile')
        self.assertEqual(self.requests[0]['model'], 'agent-pinned-v1')
        self.assertEqual([call['purpose'] for call in receipt['calls']],
            ['obfuscation', 'difficulty', 'generation', 'obfuscation'])
        intervals = list(self.execution.events.filter(kind='interval',
            data__purpose='difficulty').values_list('data', flat=True))
        self.assertEqual(len(intervals), 1)
        self.assertEqual(intervals[0]['category'], 'protection')

    def test_easy_evaluation_keeps_the_explicit_profile_and_local_sensitivity(self):
        self.assert_difficulty('easy', 'economy')

    def test_hard_evaluation_keeps_the_explicit_profile_and_local_sensitivity(self):
        self.assert_difficulty('hard', 'strong')

    def test_uncertain_easy_uses_strong_without_changing_profile(self):
        self.assert_difficulty('easy', 'strong', .79)

    def test_sensitive_state_is_protected_and_replay_never_calls_jev_twice(self):
        self.difficulty()
        captured = self.simulated_jev(answers=difficulty_answers())
        request = self.request(messages=[{'role': 'user',
            'content': 'Summarize for ana@example.invalid. api_key=sk-synthetic-secret-value'}])
        first = self.infer(request)
        self.assertEqual(first['status'], 'completed', first)
        before = self.receipt()
        self.assertEqual(self.infer(request), first)
        self.assertEqual(self.receipt()['calls'], before['calls'])
        self.assertEqual(len(captured), 1)
        self.assertEqual(len(self.requests), 1)
        sent = json.dumps([captured[0]['payload']['state'], self.requests[0], self.receipt()])
        self.assertNotIn('ana@example.invalid', sent)
        self.assertNotIn('sk-synthetic-secret-value', sent)
        self.assertEqual(Decimal(self.receipt()['total']['cost']), Decimal('0.00214'))

    def test_missing_credential_blocks_before_any_mask_or_provider_call(self):
        self.difficulty(credential=False)
        captured = self.simulated_jev(answers=difficulty_answers())
        self.assertEqual(self.infer(), {'status': 'rejected', 'code': 'jev_unavailable'})
        self.assertEqual(captured, [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.receipt()['calls'], [])
        self.assertEqual(self.receipt()['jev']['status'], 'disabled')
        self.assertEqual(self.receipt()['jev']['purpose'], 'difficulty')

    def test_revocation_during_difficulty_withholds_generation_and_preserves_cost(self):
        self.difficulty()
        captured = self.simulated_jev(answers=difficulty_answers(),
            after_request=lambda: CompanyEngine.objects.filter(pk=self.credential.pk).update(active=False))
        result = self.infer()
        self.assertEqual(result['status'], 'rejected', result)
        self.assertEqual(len(captured), 1)
        self.assertEqual(self.requests, [])
        self.assertEqual(Decimal(self.receipt()['total']['cost']), Decimal('0.002'))
        self.assertEqual(next(call for call in self.receipt()['calls']
            if call['purpose'] == 'difficulty')['cost_kind'], 'provider_reported')

    def test_routing_or_jev_permission_change_during_evaluation_blocks_generation(self):
        for changed in ('routing', 'jev_permission'):
            with self.subTest(changed=changed):
                self.difficulty()

                def revoke():
                    if changed == 'routing':
                        self.company.ai_config['routing']['mode'] = 'manual'
                    else:
                        self.company.ai_config['destinations']['internal'].remove('jev')
                    self.company.save(update_fields=['ai_config'])

                captured = self.simulated_jev(answers=difficulty_answers(), after_request=revoke)
                result = self.infer()
                self.assertEqual(result['status'], 'rejected', result)
                self.assertEqual(len(captured), 1)
                self.assertEqual(self.requests, [])
                self.assertEqual(Decimal(self.receipt()['total']['cost']), Decimal('0.002'))

    def test_timeout_is_uncertain_and_replay_does_not_resubmit_evaluation(self):
        self.difficulty()
        captured = self.simulated_jev(error=requests.ReadTimeout('private@example.invalid'))
        request = self.request()
        first = self.infer(request)
        self.assertEqual(first['status'], 'outcome_unknown', first)
        self.assertEqual(self.infer(request), first)
        self.assertEqual(len(captured), 1)
        self.assertEqual(self.requests, [])
        receipt = self.receipt()
        self.assertEqual(receipt['jev']['status'], 'no_response')
        self.assertEqual(receipt['jev']['purpose'], 'difficulty')
        self.assertIsNone(receipt['total']['cost'])
        self.assertFalse(receipt['total']['complete'])
        self.assertNotIn('private@example.invalid', json.dumps(receipt))
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, 'outcome_unknown')

    def test_required_classification_reuses_full_difficulty_without_second_evaluation(self):
        self.configure(routing={'mode': 'auto', 'strategy': 'difficulty'})
        captured = self.simulated_jev()
        result = self.infer()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(len(captured), 1)
        self.assertIn('category', captured[0]['payload']['questions'])
        self.assertIn('difficulty', captured[0]['payload']['questions'])
        self.assertEqual(self.receipt()['jev']['purpose'], 'classification')
        self.assertEqual(self.receipt()['jev']['decision']['difficulty'], 'strong')
        purposes = [call['purpose'] for call in self.receipt()['calls']]
        self.assertEqual(purposes.count('classification'), 1)
        self.assertNotIn('difficulty', purposes)

    def test_manual_route_still_leaves_jev_unconsulted(self):
        self.configure(classification='local', routing={'mode': 'manual', 'strategy': 'difficulty'})
        captured = self.simulated_jev(answers=difficulty_answers())
        self.assertEqual(self.infer()['status'], 'completed')
        self.assertEqual(captured, [])
        self.assertEqual(self.receipt()['jev']['status'], 'not_consulted')

    def test_quality_route_still_leaves_jev_unconsulted(self):
        self.configure(classification='local', routing={'mode': 'auto', 'strategy': 'quality'})
        captured = self.simulated_jev(answers=difficulty_answers())
        self.assertEqual(self.infer()['status'], 'completed')
        self.assertEqual(captured, [])
        self.assertEqual(self.receipt()['jev']['status'], 'not_consulted')

    def test_invalid_difficulty_output_stops_before_generation(self):
        self.difficulty()
        invalid = {'difficulty': {'type': 'choice', 'choice': 'engine:999', 'confidence': 1.0,
            'probabilities': {'engine:999': 1.0, 'easy': 0.0}}}
        captured = self.simulated_jev(answers=invalid)
        request = self.request()
        first = self.infer(request)
        self.assertEqual(first['status'], 'outcome_unknown', first)
        self.assertEqual(self.infer(request), first)
        self.assertEqual(len(captured), 1)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.receipt()['jev']['status'], 'failed')
        self.assertEqual(self.receipt()['jev']['reason_codes'], ['invalid_response'])
        self.assertIsNone(self.receipt()['jev']['decision'])
        self.assertEqual(self.receipt()['jev']['signals'], {})

    def test_unknown_evaluation_price_with_local_budget_blocks_before_jev(self):
        self.difficulty(limits={'budget': '1'})
        captured = self.simulated_jev(answers=difficulty_answers())
        self.assertEqual(self.infer(), {'status': 'rejected', 'code': 'unknown_price'})
        self.assertEqual(captured, [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.receipt()['jev']['status'], 'not_consulted')
        self.assertEqual(self.receipt()['jev']['purpose'], 'difficulty')


@override_settings(REGULAY_AGENT_ENABLED=True, DEBUG=False)
class AgentDifficultyHTTPTests(AgentFixture, TestCase):
    simulated_jev = transparency.AgentTransparencyTests.simulated_jev
    receipt = transparency.AgentTransparencyTests.receipt

    def setUp(self):
        super().setUp()
        from front.agents.capabilities import GENERAL
        from front.models import AgentAccessGrant
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('Live network forbidden')))
        self.agent.professional = True
        self.agent.tools = sorted(GENERAL)
        self.agent.save()
        AgentAccessGrant.objects.create(company=self.company, user=self.user, profile=self.agent, enabled=True)
        self.company.ai_config.update(classification='local',
            routing={'mode': 'auto', 'strategy': 'difficulty'})
        self.company.ai_config['destinations']['internal'].append('jev')
        self.company.jev_api_key = 'synthetic-jev-key'
        self.company.save()
        self.client.force_login(self.user)

    def test_three_public_send_entries_evaluate_once_through_private_http(self):
        import uuid
        from front import test_agent_professional as professional
        captured = self.simulated_jev(answers=difficulty_answers('hard'))
        for index, url in enumerate(('/chat/', '/chat/send/', '/api/chat/send/'), 1):
            with self.subTest(url=url):
                identity = uuid.uuid4()
                first = professional.ProfessionalTests.queued(self, url=url, identity=identity)
                again = professional.ProfessionalTests.queued(self, url=url, identity=identity)
                self.assertEqual(first.pk, again.pk)
                professional.ProfessionalTests.activate(self, first)
                self.prompt = first.prompt
                self.assertEqual(len(captured), index - 1)  # Admission never consults Jev.
                payload = json.dumps(self.request())
                headers = {'HTTP_AUTHORIZATION': 'Bearer ' + self.token,
                    'HTTP_X_REGULAY_ATTEMPT': str(self.execution.attempt)}
                response = self.client.post('/internal/agents/inference/', payload,
                    content_type='application/json', **headers)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['status'], 'completed', response.content)
                replay = self.client.post('/internal/agents/inference/', payload,
                    content_type='application/json', **headers)
                self.assertEqual(replay.status_code, 200, replay.content)
                self.assertEqual(replay.json(), response.json())
                self.assertEqual(len(captured), index)
                self.assertEqual(len(self.requests), index)
                self.assertEqual(set(captured[-1]['payload']['questions']), {'difficulty'})
                self.assertEqual(self.receipt()['jev']['status'], 'consulted')
                self.assertEqual(self.receipt()['jev']['decision'], {'difficulty': 'hard'})
                self.assertEqual(self.requests[-1]['model'], 'agent-pinned-v1')
                snapshot = self.client.get(f'/chat/agent/runs/{first.pk}/')
                self.assertEqual(snapshot.status_code, 200, snapshot.content)
                visible = snapshot.json()['receipt']['jev']
                self.assertEqual(visible['status'], 'consulted')
                self.assertEqual(visible['purpose'], 'difficulty')
                self.assertEqual(visible['decision'], {'difficulty': 'hard'})
                self.assertEqual(visible['applied']['difficulty'], 'strong')
                self.assertEqual(len(captured), index)  # Reading the receipt is not another evaluation.
