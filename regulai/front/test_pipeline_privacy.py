"""HTTP privacy and monetary boundaries, with synthetic transports only."""
import json
from types import SimpleNamespace

from django.urls import reverse

from front.models import Message, ObfuscationConfig, Prompt
from front.test_chat_flow import ChatFixture
from front.test_pipeline import PipelineTests, jev_http


class PipelinePrivacyTests(ChatFixture):
    configure = PipelineTests.configure

    def mask(self, *, bound='0', malformed=False):
        config = ObfuscationConfig.objects.create(company=self.company, name='Batch mask', api_url='https://mask.invalid')
        self.company.ai_config['destinations']['internal'].append(f'obfuscation:{config.pk}')
        self.company.ai_config['masking'] = {'max_call_cost': bound}
        self.company.save()
        evaluator = jev_http()
        def post(url, **kwargs):
            if url.endswith('/api/mask'):
                pending = Prompt.objects.get(status='processing')
                self.assertEqual(pending.decision['calls'][-1]['status'], 'started')
                text = kwargs['json']['text']
                self.assertIsInstance(json.loads(text), list)
                return SimpleNamespace(raise_for_status=lambda: None,
                    json=lambda: {'masked': '[]' if malformed else text.replace('12345678Z', '<DNI_1>')})
            self.assertNotIn('12345678Z', kwargs['data'].decode())
            return evaluator(url, **kwargs)
        self.http.side_effect = post

    def test_structured_masking_preserves_escapes_and_all_segments_in_every_http_entry(self):
        self.configure()
        self.company.system_prompt = 'Policy "12345678Z" \\ [END]'
        self.company.save()
        self.mask()
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            response = self.send(path, '12345678Z\n[END] " ], [ " 12345678Z')
            self.assertEqual(response.status_code, 302 if path == '/chat/' else 200)
            messages = self.provider.call_args.args[0]
            self.assertEqual(messages[0].content, 'Policy "<DNI_1>" \\ [END]')
            self.assertEqual(messages[-1].content, '<DNI_1>\n[END] " ], [ " <DNI_1>')
            completed = Prompt.objects.latest('pk')
            self.assertEqual(completed.decision['calls'][0]['cost'], '0')
            self.assertTrue(completed.decision['total']['complete'])
            self.assertNotIn('12345678Z', completed.user_message.content)

    def test_invalid_mask_segments_stop_before_classifier_or_generator(self):
        self.configure()
        self.mask(malformed=True)
        result = self.send('/api/chat/send/', '12345678Z').json()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.http.call_count, 1)
        self.provider.assert_not_called()

    def test_mask_cost_reserve_prevents_any_call_when_budget_is_insufficient(self):
        self.configure(limits={'budget': '0.01'})
        self.mask(bound='0.02')
        result = self.send('/api/chat/send/').json()
        self.assertEqual(result['error_type'], 'budget_exhausted')
        self.http.assert_not_called()
        self.provider.assert_not_called()
