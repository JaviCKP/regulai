"""Adversarial cases authored independently for the immutable security review."""
from pathlib import Path
import json
from unittest.mock import patch

from django.core.management.base import CommandError
from front import evaluation
from front.evaluation_budget import EvaluationBudget
from front.test_smoke import SmokeIsolationTests
from front.test_chat_flow import ChatFixture
from front.test_pipeline import OPENAI_CHAT
from front.models import ObfuscationConfig, Prompt
import httpx
from types import SimpleNamespace

EVIDENCE = Path(__file__).resolve().parent


class PilotApprovalRace(SmokeIsolationTests):
    def test_revocation_during_reservation_must_prevent_generation_transport(self):
        reserve = EvaluationBudget.reserve
        observed = {}

        def reserve_then_revoke(ledger, purpose, maximum, **kwargs):
            token = reserve(ledger, purpose, maximum, **kwargs)
            if purpose == 'generation':
                revoked = {**self.approval, 'status': 'revoked'}
                self.approval_path.write_text(json.dumps(revoked), encoding='utf-8')
                state, _ = evaluation.preflight(self.manifest_path, self.approval_path)
                observed.update(authorization_ready_after_reserve=state['ready_for_real'],
                    blockers_after_reserve=state['blockers'], reservation_id=token)
            return token

        with patch.object(EvaluationBudget, 'reserve', reserve_then_revoke):
            with self.assertRaises(CommandError):
                self.run_smoke('review-revoked-during-reservation')
        observed.update(events=self.events, generation_payloads=self.generation_payloads,
            ledger=self.ledger(), live_socket_calls=self.socket.call_count)
        evidence_name = 'control-S1-reservation-recheck.json' if getattr(self, 'control_recheck', False) else 'finding-S1-reservation-approval-race.json'
        (EVIDENCE / evidence_name).write_text(
            json.dumps(observed, indent=2), encoding='utf-8')
        self.assertFalse(observed['authorization_ready_after_reserve'])
        self.assertEqual(self.socket.call_count, 0)
        self.assertEqual(self.generation_payloads, [],
            'A generation crossed the actual SDK transport after the pilot approval was revoked during reservation')

    def test_control_recheck_after_reservation_prevents_the_same_transport(self):
        self.control_recheck = True
        original = evaluation.LedgerObserver.before_call

        def rechecked(observer, call):
            token = original(observer, call)
            try:
                if observer.authorize:
                    observer.authorize()
            except Exception:
                observer.ledger.complete(token, cost='0', status='not_started', cost_kind='not_incurred')
                raise
            return token

        # Experimental control only: no reviewed source file is changed.
        with patch.object(evaluation.LedgerObserver, 'before_call', rechecked):
            self.test_revocation_during_reservation_must_prevent_generation_transport()


class PrivacyTransportCapture(ChatFixture):
    def test_capture_mask_then_sdk_for_three_http_entries(self):
        captures = []
        self.company.system_prompt = 'Synthetic system ID 12345678Z'
        self.company.save()

        def mask(url, **kwargs):
            pending = Prompt.objects.latest('pk')
            self.assertEqual(pending.decision['calls'][-1]['status'], 'started')
            captures.append({'purpose': 'mask', 'url': url, 'payload': kwargs['json']})
            return SimpleNamespace(raise_for_status=lambda: None,
                json=lambda: {'masked': kwargs['json']['text'].replace('12345678Z', '[REVIEW_MASKED]')})

        def sdk(request):
            payload = json.loads(request.content)
            self.assertNotIn('12345678Z', request.content.decode())
            self.assertIn('[REVIEW_MASKED]', request.content.decode())
            self.assertEqual(Prompt.objects.latest('pk').decision['calls'][-1]['purpose'], 'generation')
            captures.append({'purpose': 'generation', 'url': str(request.url), 'payload': payload})
            return httpx.Response(200, json={'id': 'independent-review-synthetic', 'object': 'chat.completion',
                'created': 0, 'model': 'synthetic-v1', 'choices': [{'index': 0,
                'message': {'role': 'assistant', 'content': 'Synthetic answer 12345678Z'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25}})

        self.http.side_effect = mask
        with patch('front.connectors.OpenAIConnector.chat', OPENAI_CHAT), patch('openai.DefaultHttpxClient',
                side_effect=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(sdk), **kwargs)):
            for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
                result = self.send(path, 'Synthetic user ID 12345678Z')
                self.assertEqual(result.status_code, 302 if path == '/chat/' else 200)
                completed = Prompt.objects.latest('pk')
                self.assertEqual(completed.status, 'completed')
                self.assertNotIn('12345678Z', completed.response.content)
                self.assertNotIn('12345678Z', completed.user_message.content)
        self.assertEqual([item['purpose'] for item in captures], ['mask', 'generation', 'mask'] * 3)
        (EVIDENCE / 'privacy-transports.json').write_text(json.dumps(captures, indent=2), encoding='utf-8')

    def test_consent_does_not_override_deactivated_mandatory_mask(self):
        self.rule.action = 'consent'
        self.rule.save()
        pending = self.send('/api/chat/send/', 'SYNTHETIC_SECRET').json()
        self.assertEqual(pending['status'], 'pending_consent')
        ObfuscationConfig.objects.filter(pk=self.required_mask.pk).update(active=False)
        result = self.send('/api/chat/send/', 'SYNTHETIC_SECRET', request_id=pending['request_id'],
            consent_token=pending['consent_token']).json()
        self.assertEqual(result['error_type'], 'masking_required')
        self.assertEqual(result['receipt']['calls'], [])
        self.http.assert_not_called()
        self.provider.assert_not_called()
