"""Three real HTTP entries -> actual SDK -> captured provider transport."""
import json
import uuid
from unittest.mock import patch

import httpx
from openai import OpenAI
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from front.connectors import OpenAIConnector
from front.local_masking import detector_metadata
from front.models import PrivacyRevision, Prompt, ConversationAlias, PrivacyUse
from front.policy import digest
from front.test_chat_flow import ChatFixture
from front.test_pipeline import OPENAI_CHAT


@override_settings(CHAT_STREAM_THREADS=False)
class PrivacyHttpTests(ChatFixture):
    def setUp(self):
        super().setUp()
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='synthetic', detector_version=digest(detector_metadata()))
        self.company.ai_config['privacy'] = {'version': 1, 'revision_id': revision.pk}
        self.company.save()
        self.captured = []
        self.cancel_at = None

        def http(request):
            data = json.loads(request.content)
            self.captured.append({'url': str(request.url), 'headers': dict(request.headers), 'body': data})
            if data.get('stream'):
                from front import chat_streaming
                from front.test_agent_streaming import chunk, USAGE
                text = data['messages'][-1]['content'] + ' Texto neutro para comprobar la entrega progresiva.' * 12
                cancel_at = self.cancel_at
                class Stream(httpx.SyncByteStream):
                    def __iter__(self):
                        for position in range(0, len(text), 7):
                            if cancel_at is not None and position >= cancel_at:
                                next(iter(chat_streaming._REGISTRY.values())).cancel()
                            yield chunk({'content': text[position:position+7]})
                        yield chunk(finish='stop')
                        yield chunk(usage=USAGE)
                        yield b'data: [DONE]\n\n'
                return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=Stream())
            return httpx.Response(200, json={'id': 'synthetic-http', 'object': 'chat.completion',
                'created': 1, 'model': 'synthetic-v1', 'choices': [{'index': 0,
                'message': {'role': 'assistant', 'content': data['messages'][-1]['content']}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})

        def connector(*args):
            result = OpenAIConnector('synthetic-only', 'https://provider.invalid/v1')
            result.client.close()
            result.client = OpenAI(api_key='synthetic-only', base_url='https://provider.invalid/v1', max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(http)))
            self.addCleanup(result.client.close)
            return result

        self.enterContext(patch('front.connectors.OpenAIConnector.chat', new=OPENAI_CHAT))
        self.enterContext(patch('front.chat_service.get_connector', side_effect=connector))

    def test_three_http_entries_and_remote_mask_never_receive_selected_originals(self):
        for path in ('/chat/', '/chat/send/', '/api/chat/send/'):
            with self.subTest(path=path):
                response = self.send(path, 'Hola Ana Fixture, ana@example.invalid')
                prompt = Prompt.objects.latest('pk')
                self.assertEqual(prompt.status, 'completed', (response.status_code, prompt.decision))
                self.assertIn('[[R_PERSON_', self.captured[-1]['body']['messages'][-1]['content'])
                for original in ('Ana Fixture', 'ana@example.invalid'):
                    self.assertNotIn(original, json.dumps(self.captured[-1]))
                    self.assertNotIn(original, str(self.http.call_args_list))
        self.assertEqual(len(self.captured), 3)
        self.assertEqual(ConversationAlias.objects.count(), 6)

    def test_retry_and_history_keep_alias_and_usage(self):
        request_id = str(uuid.uuid4())
        first = self.send('/chat/send/', 'Ana Fixture ana@example.invalid', request_id=request_id).json()
        self.assertEqual(first['status'], 'completed', first)
        before = PrivacyUse.objects.count()
        repeated = self.send('/api/chat/send/', 'Ana Fixture ana@example.invalid', request_id=request_id).json()
        self.assertEqual(repeated['status'], 'completed', repeated)
        self.assertEqual(PrivacyUse.objects.count(), before)
        self.assertEqual(len(self.captured), 1)
        self.send(f"/chat/{first['conversation_id']}/send/", 'Otra vez Ana Fixture')
        self.assertEqual(Prompt.objects.latest('pk').status, 'completed')
        self.assertEqual(ConversationAlias.objects.count(), 2)
        inspector = self.client.get(f"/chat/privacy/conversations/{first['conversation_id']}/inspector/").json()
        name = next(row for row in inspector['aliases'] if row['category'] == 'PERSON')
        second_turn = next(row for row in name['turns'] if row['request_id'] != first['request_id'])
        self.assertEqual(second_turn['input'], 1)
        self.assertEqual(second_turn['history'], 2)
        self.assertEqual(second_turn['response'], 1)
        self.assertEqual(second_turn['provider_calls'], 1)
        self.assertEqual(second_turn['uncertain_calls'], 0)
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, json.dumps(self.captured))

    def test_failure_after_registration_before_dispatch_keeps_counts_and_does_not_resend(self):
        request_id = str(uuid.uuid4())
        from front.models import PrivacyCall
        # Connector construction happens after the atomic allowlist/usage write.
        with patch('front.chat_service.get_connector', side_effect=ValueError('synthetic setup failure')):
            first = self.send('/chat/send/', 'Ana Fixture ana@example.invalid', request_id=request_id).json()
        self.assertNotEqual(first['status'], 'completed')
        before = list(PrivacyUse.objects.values_list('call_key', 'alias_id', 'count'))
        self.assertTrue(before)
        self.assertTrue(PrivacyCall.objects.exists())
        repeated = self.send('/chat/send/', 'Ana Fixture ana@example.invalid', request_id=request_id).json()
        self.assertEqual(repeated['status'], first['status'])
        self.assertEqual(before, list(PrivacyUse.objects.values_list('call_key', 'alias_id', 'count')))
        self.assertEqual(self.captured, [])

    def test_binary_and_policy_failure_stop_before_network(self):
        self.send('/chat/send/', 'fixture', file=SimpleUploadedFile('fixture.pdf', b'%PDF fixture'))
        self.assertEqual(self.captured, [])
        self.company.ai_config['privacy']['revision_id'] = 99999
        self.company.save()
        result = self.send('/chat/send/', 'Ana Fixture ana@example.invalid').json()
        self.assertNotEqual(result['status'], 'completed')
        self.assertEqual(self.captured, [])
        self.http.assert_not_called()

    def test_classifier_and_judge_receive_protected_state(self):
        from front.test_pipeline import PipelineTests
        PipelineTests.configure(self)
        result = self.send('/chat/send/', 'Ana Fixture ana@example.invalid').json()
        self.assertEqual(result['status'], 'completed', result)
        purposes = [call['purpose'] for call in result['receipt']['calls']]
        self.assertIn('classification', purposes)
        self.assertIn('verification', purposes)
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, str(self.http.call_args_list))
            self.assertNotIn(original, json.dumps(self.captured))

    def test_money_and_provider_usage_are_unchanged_when_protection_is_enabled(self):
        from decimal import Decimal
        self.model.input_price, self.model.output_price = Decimal('1'), Decimal('2')
        self.model.save()
        self.company.ai_config.pop('privacy')
        self.company.save()
        plain = self.send('/chat/send/', 'Texto ficticio neutro').json()
        revision = PrivacyRevision.objects.get(company=self.company)
        self.company.ai_config['privacy'] = {'version': 1, 'revision_id': revision.pk}
        self.company.save()
        protected = self.send('/chat/send/', 'Ana Fixture ana@example.invalid').json()
        for field in ('known_cost', 'currency', 'cost', 'cost_status', 'complete', 'attempts'):
            self.assertEqual(plain['receipt']['total'][field], protected['receipt']['total'][field])
        self.assertEqual(len(plain['receipt']['calls']), len(protected['receipt']['calls']))

    def test_client_cannot_supply_a_foreign_alias_or_override_the_policy(self):
        first = self.send('/chat/send/', 'Ana Fixture ana@example.invalid').json()
        foreign = ConversationAlias.objects.filter(conversation_id=first['conversation_id']).first().token
        before = len(self.captured)
        second = self.send('/api/chat/send/', foreign, privacy='off', protected='true').json()
        self.assertNotEqual(second['status'], 'completed')
        self.assertEqual(len(self.captured), before)

    def stream_ready(self):
        from front import chat_streaming
        from front.models import Rule
        chat_streaming._REGISTRY.clear()
        self.enterContext(patch('front.chat_streaming.EMIT_INTERVAL', 0))
        Rule.objects.filter(pk=self.rule.pk).update(applies_to='files')
        self.required_mask.backend, self.required_mask.api_url = 'local', ''
        self.required_mask.save()

    def test_actual_http_stream_two_replays_and_final_natural_text_match(self):
        from front.test_chat_streaming import parse_sse
        self.stream_ready()
        response = self.send('/chat/send/', 'Ana Fixture ana@example.invalid', stream='1')
        events = parse_sse(b''.join(response.streaming_content).decode())
        self.assertEqual(events[-1]['result']['status'], 'completed', events[-1])
        fragments = ''.join(event['projection']['text'] for event in events if event['type'] == 'delta')
        final = events[-1]['result']['assistant_message']['projection']['text']
        self.assertIn('Ana Fixture', fragments)
        self.assertTrue(final.startswith(fragments))
        before = PrivacyUse.objects.count()
        request_id = events[-1]['result']['request_id']
        cut = next(event['seq'] for event in events if event['type'] == 'delta')
        for _ in range(2):
            replay = self.client.get(f'/chat/requests/{request_id}/stream/?after={cut}')
            self.assertIn('no-store', replay['Cache-Control'])
            received = parse_sse(b''.join(replay.streaming_content).decode())
            self.assertTrue(all(event['seq'] > cut for event in received))
            self.assertEqual(received[-1]['result']['assistant_message']['projection']['text'], final)
        self.assertEqual(len(self.captured), 1)
        self.assertEqual(PrivacyUse.objects.count(), before)
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, json.dumps(self.captured))

    def test_cancellation_retracts_natural_fragments_and_preserves_uncertain_receipt(self):
        from front.test_chat_streaming import parse_sse
        from front.models import Message
        self.stream_ready()
        self.cancel_at = 280
        response = self.send('/chat/send/', 'Ana Fixture ana@example.invalid', stream='1')
        events = parse_sse(b''.join(response.streaming_content).decode())
        self.assertEqual(events[-1]['result']['status'], 'cancelled', events[-1])
        self.assertIn('retract', [event['type'] for event in events])
        self.assertFalse(Message.objects.filter(role='assistant').exists())
        self.assertEqual(Prompt.objects.latest('pk').decision['calls'][-1]['status'], 'cancelled')
