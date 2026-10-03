"""Independent closure cases: real clock expiry and persistently failed settlement."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3
from unittest.mock import patch

from django.core.management.base import CommandError
from front import evaluation
from front.evaluation_budget import EvaluationBudget
from front.test_smoke import SmokeIsolationTests

EVIDENCE = Path(__file__).resolve().parent


class AdditionalClosureCases(SmokeIsolationTests):
    def test_actual_clock_expiry_during_generation_reservation_blocks_transport(self):
        now = datetime.now(timezone.utc)
        self.approval.update(valid_from=(now - timedelta(minutes=1)).isoformat(),
            valid_until=(now + timedelta(seconds=1)).isoformat())
        self.save_approval()
        clock = [now]
        reserve = EvaluationBudget.reserve
        observed = {}

        def expire_clock(ledger, purpose, maximum, **kwargs):
            token = reserve(ledger, purpose, maximum, **kwargs)
            if purpose == 'generation':
                clock[0] = now + timedelta(seconds=2)
                check, _ = evaluation.preflight(self.manifest_path, self.approval_path)
                observed['blockers_after_reserve'] = check['blockers']
            return token

        with patch.object(evaluation, 'datetime', wraps=datetime) as virtual_time:
            virtual_time.now.side_effect = lambda tz: clock[0]
            with patch.object(EvaluationBudget, 'reserve', expire_clock):
                with self.assertRaises(CommandError):
                    self.run_smoke('clock-expiry')
        observed.update(events=self.events, ledger=self.ledger(), live_socket_calls=self.socket.call_count)
        (EVIDENCE / 'clock-expiry.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
        self.assertIn('authorization_expired_or_invalid_window', observed['blockers_after_reserve'])
        self.assertEqual(self.events, ['obfuscation', 'classification'])
        generation = next(call for call in observed['ledger']['calls'] if call['purpose'] == 'generation')
        self.assertEqual((generation['status'], generation['cost'], generation['metadata']['cost_kind']),
            ('not_started', '0', 'not_incurred'))
        self.assertEqual(self.generation_payloads, [])
        self.socket.assert_not_called()

    def test_persistent_settlement_failure_keeps_restart_exposure_and_no_transport(self):
        reserve = EvaluationBudget.reserve

        def revoke(ledger, purpose, maximum, **kwargs):
            token = reserve(ledger, purpose, maximum, **kwargs)
            self.approval_path.write_text(json.dumps({**self.approval, 'status': 'revoked'}), encoding='utf-8')
            return token

        with patch.object(EvaluationBudget, 'reserve', revoke), patch.object(EvaluationBudget, 'complete',
                side_effect=sqlite3.OperationalError('Synthetic persistent settlement failure')):
            with self.assertRaises(sqlite3.OperationalError):
                self.run_smoke('persistent-settlement-failure')
        ledger = self.ledger()  # A newly opened ledger retains the unresolved reserve.
        (EVIDENCE / 'persistent-settlement-failure.json').write_text(json.dumps({
            'events': self.events, 'ledger': ledger, 'live_socket_calls': self.socket.call_count}, indent=2), encoding='utf-8')
        self.assertEqual(self.events, [])
        self.assertEqual(len(ledger['calls']), 1)
        self.assertEqual(ledger['calls'][0]['status'], 'started')
        self.assertIsNone(ledger['calls'][0]['cost'])
        self.assertEqual(ledger['budget_exposure_usd'], '0.01')
        self.assertEqual(ledger['uncertain_reservations_usd'], '0.01')
        self.socket.assert_not_called()
