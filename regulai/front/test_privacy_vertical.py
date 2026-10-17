"""E1: synthetic values, real provider SDK, captured HTTP with no external IO."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import OpenAI
from django.contrib.auth.models import User
from django.test import TestCase, SimpleTestCase

from front.agents.aliases import alias_text, preserve_aliases
from front.connectors import ChatMessage, OpenAIConnector
from front.local_masking import mask_local_texts
from front.models import Company, Conversation, ConversationAlias, Prompt
from front.privacy_projection import MAX_TOKEN, Projection, UNAVAILABLE, project


class ProjectionTests(SimpleTestCase):
    token = '[[R_PERSON_' + 'a' * 32 + ']]'

    def test_every_byte_and_character_split_and_atomic_original(self):
        aliases = {self.token: 'Ána 🦊 <img src="https://exfil.invalid">'}
        text = '¡Hola! ' + self.token + self.token + ' — fin 😊'
        expected = '¡Hola! ' + aliases[self.token] * 2 + ' — fin 😊'
        for value in (text, text.encode('utf-8')):
            for cut in range(len(value) + 1):
                parser = Projection(aliases)
                segments = parser.feed(value[:cut]) + parser.feed(value[cut:], final=True)
                self.assertEqual(''.join(s.text for s in segments), expected, cut)
                self.assertEqual([s.text for s in segments if s.kind == 'original'], [aliases[self.token]] * 2)
                self.assertEqual(segments[-1].end, len(text.encode('utf-8')))
            parser = Projection(aliases)
            segments = []
            for index in range(len(value)):
                segments += parser.feed(value[index:index + 1])
                self.assertLessEqual(len(parser.pending), MAX_TOKEN)
            segments += parser.feed(value[:0], final=True)
            self.assertEqual(''.join(s.text for s in segments), expected)

    def test_unknown_malformed_truncated_and_nonrecursive(self):
        for text in (self.token, '[[R_PERSON_bad]]', '[[R_PERSON_' + 'x' * 10000, '[[R_'):
            parser = Projection({})
            result = []
            for char in text:
                result += parser.feed(char)
                self.assertLessEqual(len(parser.pending), MAX_TOKEN)
            result += parser.feed('', final=True)
            self.assertEqual(''.join(s.text for s in result), UNAVAILABLE)
        self.assertEqual(project('[plain] [[ordinary]]', {} )[0].text, '[plain] [[ordinary]]')
        self.assertEqual(project(self.token, {self.token: self.token})[0].text, self.token)
        self.assertEqual(project(self.token, {self.token: self.token})[0].kind, 'original')

    def test_two_consumers_are_independent(self):
        a, b = Projection({self.token: 'Ana'}), Projection({})
        self.assertEqual(a.feed(self.token[:10]), [])
        self.assertEqual(b.feed(self.token, final=True)[0].text, UNAVAILABLE)
        self.assertEqual(a.feed(self.token[10:], final=True)[0].text, 'Ana')

    def test_discarded_token_does_not_advance_preceding_text_segment(self):
        parser = Projection({})
        ordinary = parser.feed('ok [[R_' + 'x' * 100)
        self.assertEqual((ordinary[0].start, ordinary[0].end, ordinary[0].text), (0, 3, 'ok '))
        unavailable = parser.feed(']]', final=True)[0]
        self.assertEqual((unavailable.start, unavailable.end), (3, 109))


class VerticalContractTests(TestCase):
    def test_protected_http_and_incremental_natural_response(self):
        user = User.objects.create_user('privacy-fixture')
        company = Company.objects.create(name='Synthetic privacy fixture')
        conversation = Conversation.objects.create(user=user)
        prompt = Prompt.objects.create(user=user, company=company, conversation=conversation, content='fixture')
        original = 'Nombre: Ana Torres; ana@example.invalid'
        protected = alias_text(SimpleNamespace(prompt=prompt), original)
        protected = preserve_aliases([protected], mask_local_texts)[0]
        aliases = dict(ConversationAlias.objects.filter(conversation=conversation).values_list('token', 'original'))
        capture = []

        def http(request):
            capture.append({'url': str(request.url), 'headers': dict(request.headers),
                            'body': json.loads(request.content)})
            return httpx.Response(200, json={'id': 'synthetic-e1', 'object': 'chat.completion',
                'created': 1, 'model': 'synthetic', 'choices': [{'index': 0,
                'message': {'role': 'assistant', 'content': protected}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})

        connector = OpenAIConnector('synthetic-only', 'https://provider.invalid/v1')
        connector.client.close()
        connector.client = OpenAI(api_key='synthetic-only', base_url='https://provider.invalid/v1',
            max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(http)))
        self.addCleanup(connector.client.close)
        response = connector.chat([ChatMessage('user', protected)], 'synthetic')
        serialized = json.dumps(capture, ensure_ascii=False)
        for value in ('Ana Torres', 'ana@example.invalid'):
            self.assertNotIn(value, serialized)
        self.assertEqual(len(capture), 1)
        if evidence := os.environ.get('REGULAI_PRIVACY_E1_EVIDENCE'):
            Path(evidence).write_text(json.dumps({'fixture': True, 'network': 'httpx.MockTransport',
                'capture': capture, 'canonical_response': response.content}, ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertEqual(response.tokens_used, 120)
        self.assertEqual((response.input_tokens, response.output_tokens), (100, 20))
        for value in (response.content, response.content.encode('utf-8')):
            for cut in range(len(value) + 1):
                parser = Projection(aliases)
                segments = parser.feed(value[:cut]) + parser.feed(value[cut:], final=True)
                self.assertEqual(''.join(s.text for s in segments), original)
        company.refresh_from_db()
        self.assertEqual(company.ai_config, {})
