"""Independent synthetic security regressions for immutable c85d019."""
import json
from pathlib import Path
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from front import local_masking, test_chat_flow, test_pipeline
from front.models import Prompt

HERE = Path(__file__).resolve().parent
OBSERVATIONS = []


def record(name, **data):
    OBSERVATIONS.append({'name': name, **data})
    (HERE / 'observations.json').write_text(json.dumps(OBSERVATIONS, indent=2, ensure_ascii=False), encoding='utf-8')


class DetectorSecurityTests(SimpleTestCase):
    def test_numeric_personal_values_in_json_are_masked(self):
        samples = ['Telefono: 612345678; Tarjeta: 4111111111111111',
                   '{"telefono":612345678,"tarjeta":4111111111111111}',
                   '{"telefono":"612345678","tarjeta":"4111111111111111"}',
                   '[612345678,4111111111111111]']
        outputs = local_masking.mask_local_texts(samples, language='es', timeout=30)
        record('numeric_json', inputs=samples, outputs=outputs)
        for index, output in enumerate(outputs):
            with self.subTest(index=index):
                self.assertNotIn('612345678', output)
                self.assertNotIn('4111111111111111', output)

    def test_exact_markers_cannot_hide_values_inside_brackets(self):
        samples = ['[[REGULAI_EMAIL ana@example.invalid]]',
                   '[[REGULAI_EMAIL]] ana@example.invalid [[REGULAI_SECRET]]',
                   '{"id":"ana@example.invalid","source_id":"12345678Z","alias":"S1"}',
                   '{"password":false,"access_token":{"nested":"synthetic-hidden"}}']
        outputs = local_masking.mask_local_texts(samples, timeout=30)
        record('markers_and_structural_fields', outputs=outputs)
        for output in outputs:
            for sensitive in ['ana@example.invalid', '12345678Z', 'synthetic-hidden']:
                self.assertNotIn(sensitive, output)
        self.assertIn('"alias":"S1"', outputs[2])


class ProviderSecurityTests(test_chat_flow.ChatFixture):
    def setUp(self):
        super().setUp()
        self.required_mask.backend = 'local'
        self.required_mask.api_url = ''
        self.required_mask.language = 'es'
        self.required_mask.save()
        self.http.side_effect = AssertionError('Unapproved HTTP call')

    def real_sdk(self, handler):
        self.enterContext(patch('front.connectors.OpenAIConnector.chat', test_pipeline.OPENAI_CHAT))
        self.enterContext(patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
            httpx.Client(transport=httpx.MockTransport(handler), **kwargs)))

    def answer(self, content='Respuesta segura.'):
        return httpx.Response(200, json={'id': 'security-synthetic', 'object': 'chat.completion',
            'created': 0, 'model': 'synthetic-v1',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})

    def test_numeric_json_never_reaches_sdk_from_three_entries(self):
        sent = []
        self.real_sdk(lambda request: (sent.append(json.loads(request.content)), self.answer())[1])
        requests = []
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            result = self.send(path, '{"telefono":612345678,"tarjeta":4111111111111111}')
            prompt = Prompt.objects.latest('pk')
            requests.append({'entry': path, 'http_status': result.status_code, 'status': prompt.status,
                'calls': prompt.decision.get('calls'), 'provider_payload': sent[-1] if sent else None})
        record('numeric_json_sdk', requests=requests)
        self.assertEqual(len(sent), 3)
        for entry in requests:
            with self.subTest(path=entry['entry']):
                payload = json.dumps(entry['provider_payload'])
                self.assertNotIn('612345678', payload)
                self.assertNotIn('4111111111111111', payload)
        self.http.assert_not_called()
