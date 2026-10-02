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
