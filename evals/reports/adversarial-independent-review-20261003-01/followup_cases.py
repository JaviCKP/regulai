from contextlib import contextmanager
import json
from unittest.mock import patch

from django.core.management.base import CommandError
from front import evaluation
import independent_cases


class FollowupExtensionTests(independent_cases.IndependentExtensionTests):
    def dump(self):
        (independent_cases.OWN / 'followup-observations.json').write_text(
            json.dumps(independent_cases.RESULTS, indent=2) + '\n', encoding='utf-8')

    def test_cli_report_identifies_exact_approval_registered_after_lock_wait(self):
        old, original = self.prepare()
        before = self.ledger_path.read_bytes()
        @contextmanager
        def replace_before_lock_body():
            self.approval['approval_reference'] = 'SECOND synthetic human approval; never a live grant'
            self.approval_path.write_text(json.dumps(self.approval), encoding='utf-8')
            yield
        with patch.object(evaluation, 'real_lock', replace_before_lock_body), self.assertRaisesMessage(
                CommandError, 'Authorization changed while waiting'):
            self.command(apply=True)
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.http.assert_not_called()
        self.sdk.assert_not_called()
        self.socket.assert_not_called()
        independent_cases.RESULTS['cli_report_race'] = {
            'rejected_changed_approval_before_registration': True,
            'ledger_bytes_unchanged': True, 'transport_events': len(self.events)}
        self.dump()
