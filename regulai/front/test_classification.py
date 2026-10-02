"""Classification contracts using synthetic provider answers only."""
import json
import copy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.test import SimpleTestCase

from front import test_policy_simulator
from front.policy import AIConfig
from front.classification import decide
from front.models import ObfuscationConfig


def answers():
    return json.loads(next(test_policy_simulator.jev_response().iter_content(8192)))['answers']


class OrdinalClassificationTests(SimpleTestCase):
    def test_tail_mass_selects_lowest_safe_level_at_point_two_boundary(self):
        signals = answers()
        signals['category'].update(choice='public', confidence=0.8,
            probabilities={'public': 0.8, 'internal': 0.0, 'confidential': 0.0,
                'restricted': 0.0, 'unknown': 0.2})
        decision = decide(signals, AIConfig(), 'public')
        self.assertEqual(decision.sensitivity, 'public')
        self.assertIsNone(decision.stop_code)
        signals['category']['probabilities'].update(public=0.7999995, unknown=0.2000005)
        signals['category']['confidence'] = 0.79
        self.assertEqual(decide(signals, AIConfig(), 'public').sensitivity, 'confidential')

    def test_unknown_mass_is_configurable_and_local_floor_never_drops(self):
        signals = answers()
        signals['category'].update(choice='unknown', confidence=1.0,
            probabilities={'public': 0.0, 'internal': 0.0, 'confidential': 0.0,
                'restricted': 0.0, 'unknown': 1.0})
        decision = decide(signals, AIConfig(), 'internal')
        self.assertEqual(decision.sensitivity, 'confidential')
        self.assertEqual(decision.notices, ['classification_ambiguous'])
        cfg = AIConfig.model_validate({'classification_policy': {'unknown_level': 'internal'}})
        self.assertEqual(decide(signals, cfg, 'confidential').sensitivity, 'confidential')
        restricted = decide(signals, cfg, 'restricted')
        self.assertEqual((restricted.sensitivity, restricted.stop_code), ('restricted', 'restricted_content'))

    def test_sensitive_signals_restrict_from_point_two(self):
        for key, sensitivity in (('personal_data', 'confidential'), ('business_confidential', 'confidential'),
                                 ('credentials', 'restricted')):
            with self.subTest(signal=key):
                signals = answers()
                signals[key]['noul'] = 0.2
                decision = decide(signals, AIConfig(), 'internal')
                self.assertEqual(decision.sensitivity, sensitivity)
                self.assertEqual(decision.stop_code, 'restricted_content' if key == 'credentials' else None)
                signals[key]['noul'] = 0.199
                self.assertEqual(decide(signals, AIConfig(), 'internal').sensitivity, 'internal')
        signals = answers()
        signals['personal_data']['noul'] = 0.75
        self.assertEqual(decide(signals, AIConfig(), 'restricted').sensitivity, 'restricted')

    def test_uncertain_task_and_difficulty_use_conservative_defaults_and_plausible_tasks(self):
        signals = answers()
        signals['task'].update(confidence=0.4, choice='summary',
            probabilities={'summary': 0.6, 'document_question': 0.4, 'general': 0.0, 'extraction': 0.0})
        signals['difficulty'].update(confidence=0.5, choice='balanced',
            probabilities={'economy': 0.4, 'balanced': 0.6, 'strong': 0.0})
        signals['ambiguous']['noul'] = 0.2
        signals['insufficient_evidence']['noul'] = 0.2
        decision = decide(signals, AIConfig(), 'internal')
        self.assertEqual((decision.task, decision.difficulty), ('general', 'strong'))
        self.assertEqual(decision.plausible_tasks, ['summary', 'document_question'])
        self.assertEqual(decision.notices, ['task_ambiguous', 'difficulty_ambiguous',
            'clarification_required', 'insufficient_evidence'])
        self.assertIsNone(decision.stop_code)
        cfg = AIConfig.model_validate({'classification_policy': {'on_ambiguity': 'stop'}})
        self.assertEqual(decide(signals, cfg, 'internal').stop_code, 'classification_ambiguous')

    def test_manipulation_has_its_own_block_code(self):
        signals = answers()
        signals['manipulation']['noul'] = 0.2
        decision = decide(signals, AIConfig(), 'internal')
        self.assertEqual((decision.stop_code, decision.stop_status), ('classification_manipulation', 'blocked'))

    def test_incoherent_answers_fail_closed(self):
        original = answers()
        mutations = [
            lambda value: value['category'].update(confidence=0.99),
            lambda value: value['category']['probabilities'].update(public=0.5),
            lambda value: value['task'].update(choice='invalid'),
            lambda value: value['difficulty'].update(confidence=float('nan')),
            lambda value: value['credentials'].update(noul=True),
            lambda value: value['credentials'].update(noul=float('inf')),
            lambda value: value.pop('ambiguous'),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                signals = copy.deepcopy(original)
                mutate(signals)
                decision = decide(signals, AIConfig(), 'internal')
                self.assertEqual((decision.stop_code, decision.stop_status), ('security_check_failed', 'validation_error'))


class ClassificationConfigTests(SimpleTestCase):
    def test_shared_configuration_has_conservative_defaults(self):
        config = AIConfig.model_validate({}).model_dump()
        self.assertEqual(config['classification_policy'], {
            'unknown_level': 'confidential', 'signal_threshold': 0.2, 'on_ambiguity': 'warn'})
        self.assertEqual(config['masking'], {'max_call_cost': None})
        self.assertEqual(config['history'], {'max_turns': 20, 'max_bytes': 32768})
        self.assertFalse(config['routing']['allow_cross_engine_fallback'])
        self.assertEqual(config['limits']['call_timeout_seconds'], 30)
        self.assertEqual(config['verification']['min_quote_chars'], 12)
        self.assertEqual(config['verification']['min_quote_words'], 3)

    def test_optional_configuration_is_strict_and_timeouts_are_coherent(self):
        for value in (
            {'history': {'max_turns': '20'}}, {'history': {'max_bytes': -1}},
            {'classification_policy': {'unknown_level': 'unknown'}},
            {'classification_policy': {'signal_threshold': float('nan')}},
            {'classification_policy': {'on_ambiguity': 'ignore'}},
            {'masking': {'max_call_cost': '-1'}}, {'masking': {'max_call_cost': 0}},
            {'limits': {'deadline_seconds': 29}}, {'limits': {'deadline_seconds': 181}},
            {'limits': {'call_timeout_seconds': True}},
            {'routing': {'allow_cross_engine_fallback': 'false'}},
            {'verification': {'min_quote_chars': 0}}, {'verification': {'min_quote_words': 0}},
            {'classification_policy': {'unexpected': True}},
        ):
            with self.subTest(config=value), self.assertRaises(ValueError):
                AIConfig.model_validate(value)
        self.assertEqual(AIConfig.model_validate({'limits': {
            'deadline_seconds': 180, 'call_timeout_seconds': 180}}).limits.call_timeout_seconds, 180)

    def test_prices_are_per_million_but_call_bounds_can_be_smaller(self):
        for field in ('input_price', 'output_price'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                AIConfig.model_validate({'jev': {field: '0.000001'}})
        config = AIConfig.model_validate({'jev': {'input_price': '0', 'output_price': '0.0001',
            'max_call_cost': '0.000001'}, 'masking': {'max_call_cost': '0.000001'}})
        self.assertEqual(config.jev.input_price, '0')
        self.assertEqual(config.masking.max_call_cost, '0.000001')

    def test_budgeted_masking_needs_an_explicit_bound(self):
        config = {'limits': {'budget': '1'}, 'destinations': {'internal': ['obfuscation:1']}}
        with self.assertRaises(ValueError):
            AIConfig.model_validate(config)
        config['masking'] = {'max_call_cost': '0'}
        self.assertEqual(AIConfig.model_validate(config).masking.max_call_cost, '0')


class ClassificationSimulatorTests(TestCase):
    setUp = test_policy_simulator.PolicySimulatorTests.setUp
    command = test_policy_simulator.PolicySimulatorTests.command

    def test_real_distribution_is_conservatively_confidential(self):
        self.company.ai_config.update(classification='required',
            destinations={'internal': ['jev'], 'confidential': ['jev']},
            jev={'input_price': '1', 'output_price': '1', 'max_call_cost': '0.001'},
            limits={'budget': '0.002'})
        self.company.jev_api_key = 'synthetic-key'
        self.company.save()
        payload = json.loads(next(test_policy_simulator.jev_response().iter_content(8192)))
        payload['answers']['category'].update(confidence=0.49, probabilities={
            'public': 0.14, 'internal': 0.59, 'unknown': 0.22,
            'confidential': 0.05, 'restricted': 0.0})
        response = SimpleNamespace(status_code=200, headers={}, close=lambda: None,
            iter_content=lambda **kwargs: iter([json.dumps(payload).encode()]))
        with patch('requests.sessions.Session.request', return_value=response) as network:
            result = self.client.post(self.url, self.command(mode='semantic'))
        self.assertEqual(result.status_code, 200)
        comparison = result.context['comparison']
        self.assertEqual(comparison['current']['policy']['status'], 'allow')
        self.assertEqual(comparison['current']['policy']['sensitivity'], 'confidential')
        self.assertEqual(comparison['semantic']['status'], 'completed')
        self.assertEqual(network.call_count, 1)

    def test_active_mask_without_a_bound_is_rejected_before_semantic_calls(self):
        ObfuscationConfig.objects.create(company=self.company, name='Synthetic mask', api_url='https://mask.invalid')
        self.company.ai_config.update(limits={'budget': '1'})
        self.company.save()
        with patch('requests.sessions.Session.request') as network:
            result = self.client.post(self.url, self.command(mode='semantic'))
        self.assertEqual(result.status_code, 400)
        network.assert_not_called()

    def test_local_classification_ignores_semantic_category_for_routing(self):
        self.company.ai_config.update(classification='local',
            jev={'input_price': '1', 'output_price': '1', 'max_call_cost': '0.001'},
            limits={'budget': '0.002'})
        self.company.jev_api_key = 'synthetic-key'
        self.company.save()
        with patch('requests.sessions.Session.request', return_value=test_policy_simulator.jev_response('restricted')):
            result = self.client.post(self.url, self.command(mode='semantic'))
        self.assertEqual(result.context['comparison']['current']['policy']['sensitivity'], 'internal')
        self.assertEqual(result.context['comparison']['current']['policy']['status'], 'allow')
