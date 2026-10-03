"""Mandatory privacy barrier exercised through HTTP and provider transports."""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import requests

from django.urls import reverse

from front import test_chat_flow, test_pipeline
from front.models import ObfuscationConfig, Prompt
from front.models import Company, Profile
from front.chat_service import send_chat_message


class RequiredMaskingTests(test_chat_flow.ChatFixture):
    requires_mask = False

    def test_missing_mask_blocks_all_three_http_entries_before_network(self):
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            with self.subTest(path=path):
                response = self.send(path, 'Private synthetic identifier 12345678Z')
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['error_type'], 'masking_required')
                self.assertEqual(Prompt.objects.latest('pk').status, 'validation_error')
                self.provider.assert_not_called()
                self.http.assert_not_called()

    def test_inactive_mask_cannot_disable_privacy_barrier(self):
        ObfuscationConfig.objects.create(company=self.company, name='Inactive mask',
            api_url='https://mask.invalid', active=False)
        result = self.send('/api/chat/send/', 'Private synthetic identifier 12345678Z')
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()['error_type'], 'masking_required')
        self.provider.assert_not_called()
        self.http.assert_not_called()

    def test_semantic_simulation_without_mask_never_sends_original(self):
        self.user.is_superuser = True
        self.user.save()
        self.company.jev_api_key = 'synthetic-jev-key'
        self.company.ai_config.update({
            'classification': 'required',
            'destinations': {'internal': [f'engine:{self.credential.pk}', 'jev']},
            'jev': {'input_price': '1', 'output_price': '2', 'max_call_cost': '0.01'},
            'limits': {'budget': '1'},
        })
        self.company.save()
        self.http.side_effect = test_pipeline.jev_http()
        response = self.client.post(reverse('front:policy_simulator'), {
            'mode': 'semantic', 'sample': 'Private synthetic identifier 12345678Z',
            'proposed_config': json.dumps(self.company.ai_config),
        })
        self.assertEqual(response.status_code, 200)
        semantic = response.context['comparison']['semantic']
        self.assertEqual(semantic['status'], 'not_authorized')
        self.assertEqual(semantic['reason_codes'], ['masking_required'])
        self.http.assert_not_called()
        self.provider.assert_not_called()


class RequiredMaskingBoundaryTests(test_chat_flow.ChatFixture):
    configure = test_pipeline.PipelineTests.configure

    def test_yara_and_restricted_policy_block_before_even_authorized_private_mask(self):
        self.required_mask.api_url = 'http://127.0.0.1:8099'
        self.required_mask.save()
        for content, sensitivity, reason in (('SYNTHETIC_SECRET', 'internal', 'local_rule_block'),
                ('Ordinary synthetic text', 'restricted', 'restricted_content')):
            with self.subTest(reason=reason):
                self.company.ai_config['local_sensitivity'] = sensitivity
                self.company.ai_config['destinations'][sensitivity] = [
                    f'engine:{self.credential.pk}', f'obfuscation:{self.required_mask.pk}']
                self.company.save()
                for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
                    response = self.send(path, content)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()['error_type'], reason)
                    self.assertEqual(response.json()['receipt']['calls'], [])
                    self.http.assert_not_called()
                    self.provider.assert_not_called()

    def test_semantic_simulator_revalidates_mask_after_original_reaches_authorized_mask(self):
        self.user.is_superuser = True
        self.user.save()
        self.configure()
        evaluator = test_pipeline.jev_http()
        for mutation in ('disable', 'endpoint', 'role'):
            with self.subTest(mutation=mutation):
                def transport(url, **kwargs):
                    if not url.endswith('/api/mask'):
                        return evaluator(url, **kwargs)
                    self.assertIn('12345678Z', kwargs['json']['text'])
                    if mutation == 'disable':
                        ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(active=False)
                    elif mutation == 'endpoint':
                        ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(api_url='https://replaced.invalid')
                    else:
                        type(self.user).objects.filter(pk=self.user.pk).update(is_superuser=False)
                    return test_chat_flow.mask_response(url, **kwargs)
                self.http.side_effect = transport
                response = self.client.post(reverse('front:policy_simulator'), {
                    'mode': 'semantic', 'sample': 'Synthetic 12345678Z',
                    'proposed_config': json.dumps(self.company.ai_config),
                })
                comparison = response.context['comparison']
                self.assertEqual(comparison['semantic']['reason_codes'], ['authorization_changed'])
                self.assertEqual([call['purpose'] for call in comparison['calls']], ['simulation_obfuscation'])
                self.assertEqual(self.http.call_count, 1)
                self.provider.assert_not_called()
                ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(active=True, api_url='https://mask.invalid')
                type(self.user).objects.filter(pk=self.user.pk).update(is_superuser=True)
                self.http.reset_mock()

    def test_every_http_entry_uses_real_sdk_transport_with_only_masked_input(self):
        sent = []
        original = 'Private synthetic identifier 12345678Z'

        def mask(url, **kwargs):
            self.assertTrue(url.endswith('/api/mask'))
            self.assertEqual(kwargs['json']['detect'], ['pii', 'secrets'])
            pending = Prompt.objects.get(status='processing')
            self.assertEqual(pending.decision['calls'][-1]['status'], 'started')
            return SimpleNamespace(raise_for_status=lambda: None,
                json=lambda: {'masked': kwargs['json']['text'].replace('12345678Z', '<DNI_1>')})

        def transport(request):
            payload = json.loads(request.content)
            sent.append(payload)
            self.assertNotIn('12345678Z', request.content.decode())
            self.assertIn('<DNI_1>', request.content.decode())
            self.assertEqual(Prompt.objects.get(status='processing').decision['calls'][-1]['purpose'], 'generation')
            return httpx.Response(200, json={'id': 'synthetic-http-id', 'object': 'chat.completion',
                'created': 0, 'model': 'synthetic-v1',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Safe answer'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})

        self.http.side_effect = mask
        with patch('front.connectors.OpenAIConnector.chat', test_pipeline.OPENAI_CHAT), \
                patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
                    httpx.Client(transport=httpx.MockTransport(transport), **kwargs)):
            for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
                with self.subTest(path=path):
                    result = self.send(path, original)
                    self.assertEqual(result.status_code, 302 if path == '/chat/' else 200)
                    prompt = Prompt.objects.latest('pk')
                    self.assertEqual(prompt.status, 'completed')
                    self.assertEqual([call['purpose'] for call in prompt.decision['calls']],
                        ['obfuscation', 'generation', 'obfuscation'])
                    self.assertEqual(prompt.response.content, 'Safe answer')
                    self.assertNotIn('12345678Z', prompt.user_message.content)
        self.assertEqual(len(sent), 3)
        self.assertEqual(self.http.call_count, 6)

    def test_required_mask_cannot_be_foreign_or_reduce_detection(self):
        for mutation in ('foreign', 'pii', 'secrets', 'invalid_url'):
            with self.subTest(mutation=mutation):
                mask = self.required_mask
                mask.company = self.company
                mask.detect, mask.api_url = 'both', 'https://mask.invalid'
                if mutation == 'foreign':
                    mask.company = Company.objects.create(name='Foreign masking company')
                elif mutation == 'invalid_url':
                    mask.api_url = 'https://[invalid'
                else:
                    mask.detect = mutation
                mask.save()
                response = self.send('/api/chat/send/')
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['error_type'], 'masking_required')
                self.http.assert_not_called()
                self.provider.assert_not_called()

    def test_complete_mask_set_and_actor_revalidated_after_mask_transport(self):
        for mutation in ('disable', 'replace_endpoint', 'add_mask', 'company', 'inactive_actor', 'policy'):
            with self.subTest(mutation=mutation):
                def change(url, **kwargs):
                    if mutation == 'disable':
                        ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(active=False)
                    elif mutation == 'replace_endpoint':
                        ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(api_url='https://replacement.invalid')
                    elif mutation == 'add_mask':
                        ObfuscationConfig.objects.create(company=self.company, name='Added mask', api_url='https://added.invalid')
                    elif mutation == 'company':
                        other = Company.objects.create(name='Other authorization company')
                        Profile.objects.filter(pk=self.profile.pk).update(company=other)
                    elif mutation == 'inactive_actor':
                        type(self.user).objects.filter(pk=self.user.pk).update(is_active=False)
                    else:
                        self.company.ai_config['revision'] = 2
                        self.company.save()
                    return test_chat_flow.mask_response(url, **kwargs)
                self.http.side_effect = change
                result = self.send('/api/chat/send/').json()
                self.assertEqual(result['error_type'], 'security_check_failed' if mutation == 'policy' else 'authorization_changed')
                self.assertEqual(self.http.call_count, 1)
                self.provider.assert_not_called()
                self.assertEqual(result['receipt']['calls'][0]['status'], 'completed')
                ObfuscationConfig.objects.filter(company=self.company).exclude(pk=self.required_mask.pk).delete()
                ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(active=True, api_url='https://mask.invalid')
                Profile.objects.filter(pk=self.profile.pk).update(company=self.company)
                type(self.user).objects.filter(pk=self.user.pk).update(is_active=True)
                self.company.ai_config['revision'] = 1
                self.company.save()
                self.client.force_login(self.user)
                self.http.reset_mock()

    def test_invalid_mask_batches_keep_unknown_cost_and_never_forward_partial_output(self):
        invalid = ({}, {'masked': ''}, {'masked': '[]'}, {'masked': '[1]'},
                   {'masked': '["one", "two"]'}, {'masked': 'null'}, {'masked': '["unterminated]'},)
        self.company.ai_config['masking']['max_call_cost'] = '0.03'
        self.company.save()
        for body in invalid:
            with self.subTest(body=body):
                self.http.side_effect = lambda *args, **kwargs: SimpleNamespace(
                    raise_for_status=lambda: None, json=lambda: body)
                response = self.send('/api/chat/send/').json()
                self.assertEqual(response['status'], 'failed')
                self.assertIsNone(response['receipt']['total']['cost'])
                self.assertEqual(response['receipt']['calls'][0]['cost_bound'], '0.03')
                self.assertEqual(response['receipt']['calls'][0]['status'], 'failed')
                self.assertFalse(response['receipt']['total']['complete'])
                self.provider.assert_not_called()

    def test_timeout_preserves_mask_exposure_and_replay_does_not_send_again(self):
        self.company.ai_config['masking']['max_call_cost'] = '0.03'
        self.company.save()
        self.http.side_effect = requests.ReadTimeout('Synthetic timeout')
        first = self.send('/api/chat/send/').json()
        self.assertEqual(first['status'], 'outcome_unknown')
        self.assertEqual(first['receipt']['calls'][0]['cost_bound'], '0.03')
        self.assertIsNone(first['receipt']['total']['cost'])
        repeated = self.send('/chat/send/', request_id=first['request_id']).json()
        self.assertEqual(repeated['receipt']['calls'], first['receipt']['calls'])
        self.assertEqual(self.http.call_count, 1)
        self.provider.assert_not_called()

    def test_observer_reserves_persisted_intention_before_transport_and_settles_unknown(self):
        observed = []
        fixture = self
        class Observer:
            def before_call(self, call):
                fixture.assertEqual(Prompt.objects.get(status='processing').decision['calls'][-1], call)
                fixture.http.assert_not_called()
                observed.append(deepcopy(call))
                return 'synthetic-reserve-id'
            def after_call(self, call, token):
                fixture.assertEqual(token, 'synthetic-reserve-id')
                observed.append(deepcopy(call))
        self.http.side_effect = requests.ReadTimeout()
        result = send_chat_message(self.user, {'content': 'Never included in observer'}, call_observer=Observer())
        self.assertEqual(result.data['status'], 'outcome_unknown')
        self.assertEqual([call['status'] for call in observed], ['started', 'outcome_unknown'])
        self.assertNotIn('Never included in observer', str(observed))
        self.assertIsNone(observed[-1]['cost'])

    def test_observer_refusal_prevents_every_provider_effect(self):
        class Observer:
            def before_call(self, call):
                raise RuntimeError('Synthetic exhausted evaluation budget')
        result = send_chat_message(self.user, {'content': 'Synthetic'}, call_observer=Observer())
        self.assertEqual(result.data['error_type'], 'external_budget_unavailable')
        self.assertEqual(result.data['receipt']['calls'][0]['status'], 'not_started')
        self.assertEqual(result.data['receipt']['calls'][0]['cost'], '0')
        self.http.assert_not_called()
        self.provider.assert_not_called()

    def test_authorization_revoked_while_external_reserve_waits_prevents_transport(self):
        mask_pk = self.required_mask.pk
        settled = []
        class Observer:
            def before_call(self, call):
                ObfuscationConfig.objects.filter(pk=mask_pk).update(active=False)
                return 'reserved'
            def after_call(self, call, token):
                settled.append(call)
        result = send_chat_message(self.user, {'content': 'Synthetic'}, call_observer=Observer())
        self.assertEqual(result.data['error_type'], 'authorization_changed')
        self.assertEqual(settled[0]['status'], 'not_started')
        self.assertEqual(settled[0]['cost'], '0')
        self.http.assert_not_called()
        self.provider.assert_not_called()
