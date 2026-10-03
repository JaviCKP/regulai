"""Independent probes; expected assertions describe the reviewed bug, not desired behavior."""
import json
from unittest.mock import patch

import httpx

from front import test_pipeline
from front.chat_service import send_chat_message
from front.models import CompanyEngine, EngineModel
from front.test_chat_flow import ChatFixture


class ObserverDestinationRevocationProbe(ChatFixture):
    def test_revocation_during_external_reservation_reaches_sdk(self):
        for kind in ('engine_inactive', 'model_inactive', 'credential_changed'):
            with self.subTest(kind=kind):
                CompanyEngine.objects.filter(pk=self.credential.pk).update(active=True, api_key='synthetic-key')
                EngineModel.objects.filter(pk=self.model.pk).update(active=True)
                events = []
                settled = []
                fixture = self

                class Observer:
                    def before_call(self, call):
                        if call['purpose'] == 'generation':
                            if kind == 'engine_inactive':
                                CompanyEngine.objects.filter(pk=fixture.credential.pk).update(active=False)
                            elif kind == 'model_inactive':
                                EngineModel.objects.filter(pk=fixture.model.pk).update(active=False)
                            else:
                                CompanyEngine.objects.filter(pk=fixture.credential.pk).update(api_key='synthetic-new-key')
                        return 'synthetic-reserve'

                    def after_call(self, call, token):
                        settled.append(call)

                def transport(request):
                    credential = CompanyEngine.objects.get(pk=fixture.credential.pk)
                    model = EngineModel.objects.get(pk=fixture.model.pk)
                    events.append({'engine_active_at_transport': credential.active,
                                   'model_active_at_transport': model.active,
                                   'credential_matches_current': request.headers['Authorization'] == 'Bearer ' + credential.api_key})
                    return httpx.Response(200, json={'id': 'synthetic-review', 'object': 'chat.completion',
                        'created': 0, 'model': 'synthetic-v1',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Safe answer'},
                                     'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})

                with patch('front.connectors.OpenAIConnector.chat', test_pipeline.OPENAI_CHAT), \
                        patch('openai.DefaultHttpxClient', side_effect=lambda **kwargs:
                            httpx.Client(transport=httpx.MockTransport(transport), **kwargs)):
                    result = send_chat_message(self.user, {'content': 'Synthetic review request'}, call_observer=Observer())
                evidence = {'mutation': kind, 'status': result.data['status'], 'events': events,
                            'calls': [(call['purpose'], call['status']) for call in settled]}
                print('REVOCATION_PROBE ' + json.dumps(evidence, sort_keys=True))
                self.assertEqual(len(events), 1)
                self.assertEqual(result.data['status'], 'completed')
                field = {'engine_inactive': 'engine_active_at_transport', 'model_inactive': 'model_active_at_transport',
                         'credential_changed': 'credential_matches_current'}[kind]
                self.assertFalse(events[0][field])
