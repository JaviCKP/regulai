from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from front.connectors import ChatMessage, get_connector


class ConnectorTests(SimpleTestCase):
    def test_anthropic_preserves_both_system_prompts_and_disables_sdk_retries(self):
        with patch('anthropic.Anthropic') as sdk:
            usage = Mock(input_tokens=8, output_tokens=3)
            usage.model_dump.return_value = {'input_tokens': 8, 'output_tokens': 3}
            sdk.return_value.messages.create.return_value = SimpleNamespace(
                content=[SimpleNamespace(text='Hola')], usage=usage, model='synthetic-v1', id='synthetic-id', stop_reason='end_turn')
            connector = get_connector('anthropic', 'synthetic-key')
            result = connector.chat([ChatMessage('system', 'Company'), ChatMessage('system', 'Department'),
                                     ChatMessage('user', 'Hello')], model='synthetic-v1', timeout=4)
            self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)
            self.assertEqual(sdk.return_value.messages.create.call_args.kwargs['system'], 'Company\n\nDepartment')
            self.assertEqual(sdk.return_value.messages.create.call_args.kwargs['timeout'], 4)
            self.assertEqual((result.input_tokens, result.output_tokens, result.tokens_used), (8, 3, 11))

    def test_openai_reports_missing_usage_as_unknown(self):
        with patch('openai.OpenAI') as sdk:
            sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='Hello'), finish_reason='length')],
                usage=None, model='resolved-alias', id='synthetic-id')
            result = get_connector('openai', 'synthetic-key').chat([ChatMessage('user', 'Hello')], 'alias')
            self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)
            self.assertIsNone(result.input_tokens)
            self.assertEqual(result.model, 'resolved-alias')
            self.assertEqual(result.finish_reason, 'length')

    def test_openai_reasoning_and_json_are_explicit_capabilities(self):
        for connector_type in ('openai', 'openai_compatible'):
            with self.subTest(connector_type=connector_type), patch('openai.OpenAI') as sdk:
                sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"claims":[]}'), finish_reason='stop')],
                    usage=None, model='custom-name', id='synthetic-id')
                get_connector(connector_type, 'synthetic-key').chat(
                    [ChatMessage('user', 'Return JSON claims.')], 'custom-name', max_tokens=77,
                    temperature=0.1, supports_json=True, reasoning=True, timeout=4,
                    extra_body={'synthetic_option': 'preserved'})
                payload = sdk.return_value.chat.completions.create.call_args.kwargs
                self.assertEqual(payload.get('response_format'), {'type': 'json_object'})
                self.assertEqual(payload.get('max_completion_tokens'), 77)
                self.assertNotIn('max_tokens', payload)
                self.assertNotIn('temperature', payload)
                self.assertEqual(payload['extra_body'], {'synthetic_option': 'preserved'})
                self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)

    def test_document_temperature_and_json_do_not_depend_on_model_name(self):
        with patch('openai.OpenAI') as sdk:
            sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"claims":[]}'), finish_reason='stop')],
                usage=None, model='o-custom', id='synthetic-id')
            connector = get_connector('openai', 'synthetic-key')
            connector.chat([ChatMessage('user', 'Return JSON claims.')], 'o-custom',
                           max_tokens=88, temperature=0.1, supports_json=True, reasoning=False)
            payload = sdk.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual(payload.get('response_format'), {'type': 'json_object'})
            self.assertEqual((payload['max_tokens'], payload['temperature']), (88, 0.1))
            connector.chat([ChatMessage('user', 'Hello')], 'o-custom', supports_json=False)
            self.assertNotIn('response_format', sdk.return_value.chat.completions.create.call_args.kwargs)

    def test_compatible_provider_missing_finish_reason_cannot_prove_completion(self):
        from front.verification import verify_response
        with patch('openai.OpenAI') as sdk:
            sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='Hello'), finish_reason=None)],
                usage=None, model='compatible-v1', id='synthetic-id')
            response = get_connector('openai_compatible', 'synthetic-key').chat(
                [ChatMessage('user', 'Hello')], 'compatible-v1')
        self.assertIsNone(response.finish_reason)
        checks = verify_response(response.content, response.finish_reason, require_semantic=False)
        self.assertEqual((checks['local_status'], checks['finish_reason']), ('failed', 'unknown'))

    def test_anthropic_json_capability_requests_the_document_schema(self):
        with patch('anthropic.Anthropic') as sdk:
            sdk.return_value.messages.create.return_value = SimpleNamespace(
                content=[SimpleNamespace(text='{"claims":[]}')], usage=None,
                model='custom-name', id='synthetic-id', stop_reason='end_turn')
            connector = get_connector('anthropic', 'synthetic-key')
            connector.chat([ChatMessage('system', 'Return JSON claims.'), ChatMessage('user', 'Question')],
                           'custom-name', max_tokens=77, temperature=0.1, supports_json=True, reasoning=True)
            payload = sdk.return_value.messages.create.call_args.kwargs
            self.assertIn('output_config', payload)
            self.assertEqual(payload['output_config']['format']['type'], 'json_schema')
            schema = payload['output_config']['format']['schema']
            self.assertEqual(schema['required'], ['claims'])
            self.assertFalse(schema['additionalProperties'])
            claim_schema = schema['properties']['claims']['items']
            self.assertEqual(claim_schema['required'], ['text', 'citations'])
            self.assertEqual(claim_schema['properties']['citations']['items']['required'], ['id', 'quote'])
            self.assertNotIn('temperature', payload)
            self.assertEqual(payload['max_tokens'], 77)
            self.assertNotIn('max_completion_tokens', payload)
            self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)
            connector.chat([ChatMessage('user', 'Hello')], 'custom-name', temperature=0.1)
            payload = sdk.return_value.messages.create.call_args.kwargs
            self.assertNotIn('output_config', payload)
            self.assertEqual(payload['temperature'], 0.1)
