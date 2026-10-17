"""Three real HTTP entries -> actual SDK -> captured provider transport."""
import json
import uuid
from unittest.mock import patch

import httpx
from openai import OpenAI
from django.core.files.uploadedfile import SimpleUploadedFile

from front.connectors import OpenAIConnector
from front.local_masking import detector_metadata
from front.models import PrivacyRevision, Prompt, ConversationAlias, PrivacyUse
from front.policy import digest
from front.test_chat_flow import ChatFixture
from front.test_pipeline import OPENAI_CHAT


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

        def http(request):
            data = json.loads(request.content)
            self.captured.append({'url': str(request.url), 'headers': dict(request.headers), 'body': data})
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
        for original in ('Ana Fixture', 'ana@example.invalid'):
            self.assertNotIn(original, json.dumps(self.captured))

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
