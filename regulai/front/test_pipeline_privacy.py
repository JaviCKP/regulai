"""HTTP privacy and monetary boundaries, with synthetic transports only."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from types import SimpleNamespace

from django.utils import timezone

from front.models import Conversation, Message, ObfuscationConfig, Prompt
from front.test_chat_flow import ChatFixture
from front import test_pipeline


class PipelinePrivacyTests(ChatFixture):
    configure = test_pipeline.PipelineTests.configure

    def mask(self, *, bound='0', malformed=False):
        config = ObfuscationConfig.objects.create(company=self.company, name='Batch mask', api_url='https://mask.invalid')
        self.company.ai_config['destinations']['internal'].append(f'obfuscation:{config.pk}')
        self.company.ai_config['masking'] = {'max_call_cost': bound}
        self.company.save()
        evaluator = test_pipeline.jev_http()
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

    def test_history_window_omits_whole_old_pairs_from_every_destination(self):
        self.configure(history={'max_turns': 1, 'max_bytes': 100})
        first = self.send('/api/chat/send/', 'OLD_SECRETLESS_TURN').json()
        second = self.send('/api/chat/send/', 'RECENT_TURN', conversation_id=first['conversation_id']).json()
        self.mask()
        result = self.send('/api/chat/send/', 'NEXT_TURN', conversation_id=first['conversation_id']).json()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['receipt']['history'], {'sent_turns': 1, 'omitted_turns': 1,
            'sent_bytes': 25, 'omitted_bytes': 33})
        self.assertNotIn('OLD_SECRETLESS_TURN', str(self.provider.call_args))
        self.assertNotIn('OLD_SECRETLESS_TURN', str(self.http.call_args_list[-3:]))
        self.assertIn('RECENT_TURN', str(self.provider.call_args))

    def test_new_cancel_is_idempotent_without_conversation_or_message(self):
        request_id = str(uuid.uuid4())
        for path in ('/api/chat/send/', '/chat/send/'):
            result = self.send(path, '', action='cancel', request_id=request_id).json()
            self.assertEqual(result['status'], 'cancelled', result)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
        self.provider.assert_not_called()

    def test_processing_is_not_marked_uncertain_while_max_deadline_can_still_run(self):
        result = self.send('/api/chat/send/').json()
        pending = Prompt.objects.get(request_id=result['request_id'])
        Prompt.objects.filter(pk=pending.pk).update(status='processing', updated_at=timezone.now()-timedelta(seconds=181))
        repeated = self.send('/api/chat/send/', request_id=result['request_id']).json()
        self.assertEqual(repeated['status'], 'processing')
        Prompt.objects.filter(pk=pending.pk).update(updated_at=timezone.now()-timedelta(seconds=241))
        repeated = self.send('/api/chat/send/', request_id=result['request_id']).json()
        self.assertEqual(repeated['status'], 'outcome_unknown')
        self.assertEqual(self.provider.call_count, 1)
