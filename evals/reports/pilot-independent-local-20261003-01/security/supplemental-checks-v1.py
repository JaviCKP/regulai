"""Independent negative controls beyond the supplied candidate tests."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from front import local_masking, test_chat_flow, test_pipeline
from front.masking import mask_texts
from front.models import ObfuscationConfig, Prompt
import review_checks

HERE = Path(__file__).resolve().parent
OBSERVATIONS = []


def record(name, **data):
    OBSERVATIONS.append({'name': name, **data})
    (HERE / 'supplemental-observations.json').write_text(json.dumps(OBSERVATIONS, indent=2), encoding='utf-8')


class BatchControls(SimpleTestCase):
    def test_oversized_complete_batch_stops_before_http_step(self):
        local = SimpleNamespace(pk=1, backend='local', active=True, api_url='', detect='both', language='es')
        remote = SimpleNamespace(pk=2, backend='http', active=True, api_url='https://mask.example.invalid', detect='both', language='es')
        with patch('requests.post', side_effect=AssertionError('No partial batch may escape')) as http:
            with self.assertRaises(ValueError):
                mask_texts(['ana@example.invalid', 'x' * local_masking.MAX_BATCH_BYTES], [local, remote])
        http.assert_not_called()

    def test_deep_json_and_malformed_json_do_not_exempt_sensitive_strings(self):
        samples = ['[' * 1200 + '"ana@example.invalid"' + ']' * 1200,
                   '{"email":"ana@example.invalid",}',
                   '{"email":"ana@example.invalid","extra":NaN}']
        outputs = local_masking.mask_local_texts(samples, timeout=30)
        for result in outputs:
            self.assertNotIn('ana@example.invalid', result)
        record('json_fallback', input_sizes=[len(item) for item in samples], masked=[True] * 3)


class FlowControls(test_chat_flow.ChatFixture):
    configure = test_pipeline.PipelineTests.configure
    real_sdk = review_checks.ProviderSecurityTests.real_sdk
    answer = review_checks.ProviderSecurityTests.answer

    def setUp(self):
        super().setUp()
        self.required_mask.backend = 'local'
        self.required_mask.api_url = ''
        self.required_mask.language = 'es'
        self.required_mask.save()
        self.http.side_effect = AssertionError('Unexpected HTTP')

    def test_mask_collision_does_not_validate_an_invented_quote(self):
        self.configure()
        evaluator = test_pipeline.jev_http(choices={'task': 'document_question'})
        requests = []
        def judge(url, **kwargs):
            requests.append(json.loads(kwargs['data']))
            return evaluator(url, **kwargs)
        self.http.side_effect = judge
        captured = []
        def transport(request):
            payload = json.loads(request.content)
            source = json.loads(payload['messages'][-1]['content'].split('Sources:\n')[1])[0]
            self.assertIn('[[REGULAI_EMAIL]]', source['text'])
            invented = source['text'].replace('[[REGULAI_EMAIL]]', 'bob@example.invalid')
            captured.append({'source': source['text'], 'invented_quote': invented})
            return self.answer(json.dumps({'claims': [{'text': 'El servicio tiene un contacto autorizado.',
                'citations': [{'id': source['id'], 'quote': invented}]}]}))
        self.real_sdk(transport)
        result = self.send('/api/chat/send/', 'Resume el servicio.', file=SimpleUploadedFile('contacto.txt',
            b'El contacto para este servicio es ana@example.invalid durante todo el periodo.')).json()
        record('citation_collision', status=result['status'], verification=result['receipt'].get('verification'),
               calls=result['receipt']['calls'], captured=captured, judge_requests=len(requests))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['receipt']['verification']['local_status'], 'failed')
        self.assertEqual(len(requests), 1)
        self.assertNotIn('assistant_message', result)

    def test_backend_mutation_during_real_detector_stops_next_output(self):
        actual = local_masking.mask_local_texts
        def mutate(texts, **kwargs):
            masked = actual(texts, **kwargs)
            ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(backend='http', api_url='https://new.example.invalid')
            return masked
        with patch('front.masking.mask_local_texts', side_effect=mutate):
            result = self.send('/api/chat/send/', 'ana@example.invalid').json()
        record('backend_mutation', status=result['status'], code=result.get('error_type'), calls=result['receipt']['calls'])
        self.assertEqual(result['error_type'], 'authorization_changed')
        self.assertEqual([item['transport'] for item in result['receipt']['calls']], ['local'])
        self.assertEqual(result['receipt']['calls'][0]['cost'], '0')
        self.http.assert_not_called()
        self.provider.assert_not_called()

    def test_detector_exception_logs_do_not_contain_original_or_exception_details(self):
        with self.assertLogs('front.chat_service', level='ERROR') as logs, \
                patch('front.local_masking._load_model', side_effect=RuntimeError('ana.error@example.invalid synthetic-secret-details')):
            result = self.send('/api/chat/send/', 'ana.input@example.invalid').json()
        text = str(logs.output) + json.dumps(result['receipt'])
        for sensitive in ('ana.error@example.invalid', 'synthetic-secret-details', 'ana.input@example.invalid'):
            self.assertNotIn(sensitive, text)
        self.http.assert_not_called()
        self.provider.assert_not_called()
        record('sanitized_detector_error', status=result['status'], logs=logs.output, calls=result['receipt']['calls'])
