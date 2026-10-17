"""Bounded agent request batching through the real local mask and call ledger."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from front.agents.protocol import WireMessage
from front.agents.service import _context, _government
from front.test_agent_inference import AgentFixture


@override_settings(REGULAY_AGENT_ENABLED=True)
class AgentMessageBatchTests(AgentFixture, TestCase):
    def test_system_fragments_and_duplicate_messages_share_one_mask_call(self):
        messages = [{"role": "system", "content": "Instruction " + str(i)} for i in range(6)]
        messages += [{"role": "user", "content": "Contact ana@example.invalid"}] * 2
        request = self.request(messages=messages)
        self.assertEqual(self.infer(request)["status"], "completed")
        self.assertEqual(len(self.requests[0]["messages"]), len(messages))
        self.assertEqual(self.requests[0]["messages"][-1], self.requests[0]["messages"][-2])
        self.assertNotIn("ana@example.invalid", json.dumps(self.requests))
        self.prompt.refresh_from_db()
        masks = [c for c in self.prompt.decision["calls"] if c["purpose"] == "obfuscation"]
        self.assertEqual(len(masks), 2)  # One request batch and the response.
        generation = next(c for c in self.prompt.decision["calls"] if c["purpose"] == "generation")
        self.assertEqual(generation["protection"], {"protected": 7, "reused": 1})

    def test_mask_revocation_after_batch_prevents_provider_dispatch(self):
        from front.masking import mask_local_texts
        calls = []

        def revoke_after_real_mask(values, **kwargs):
            result = mask_local_texts(values, **kwargs)
            self.mask.active = False
            self.mask.save(update_fields=["active"])
            calls.append(True)
            return result

        request = self.request(messages=[{"role": "system", "content": "Give a concise answer"},
            {"role": "user", "content": "Contact ana@example.invalid"}])
        with patch("front.masking.mask_local_texts", side_effect=revoke_after_real_mask):
            result = self.infer(request)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["code"], "masking_required")
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.requests)

    def test_near_limit_alias_messages_split_without_truncating_or_changing_tokens(self):
        from front.agents.aliases import alias_value
        from front.agents import service
        from front.masking import mask_local_texts
        token = alias_value(self.execution, "EMAIL", "near-limit@example.invalid")
        text = "x" * (256000 - len(token)) + token
        messages = [WireMessage(role="user", content=text), WireMessage(role="assistant", content=text)]
        context = _context(self.prompt, self.agent.pk)
        government = _government(self.execution, context, self.token, self.execution.attempt, "batch-limits")
        observed = []

        def mask(values, **kwargs):
            observed.append((len(values), sum(len(value.encode()) for value in values)))
            return mask_local_texts(values, **kwargs)

        with patch("front.masking.mask_local_texts", side_effect=mask):
            result = service._protect_messages(self.execution, government, messages, context[8])
        self.assertEqual([message.content for message in result], [text, text])
        self.assertEqual(len(observed), 2)
        self.assertTrue(all(count <= 4096 and size <= 512000 for count, size in observed))


class AgentMessageBatchLimitTests(SimpleTestCase):
    def test_segment_limit_keeps_each_message_parts_together(self):
        from front.agents.service import _mask_message_groups
        parts = [["first"] * 4095, ["content", "tool arguments"]]
        groups = list(_mask_message_groups(parts))
        self.assertEqual([[index for index, _ in group] for group in groups], [[0], [1]])
        self.assertEqual([part for group in groups for _, segment in group for part in segment],
                         parts[0] + parts[1])
