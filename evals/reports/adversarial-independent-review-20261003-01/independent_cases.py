from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from front import evaluation
from front.evaluation_budget import EvaluationBudget, BudgetExceeded
from front.test_smoke import SmokeHarness

OWN = Path(__file__).resolve().parent
RESULTS = {}


class IndependentExtensionTests(SmokeHarness, TestCase):
    def prepare(self):
        self.use_local_mask()
        old = EvaluationBudget(self.ledger_path, '1.00', authorization_id='prior', authorization_digest='b' * 64)
        estimate = old.reserve('generation', '.010858062')
        old.complete(estimate, cost='.0007', cost_kind='tariff_estimate')
        uncertain = old.reserve('classification', '.003')
        old.complete(uncertain, status='outcome_unknown')
        self.approval.update(approved=True, retain_existing_costs=True,
            extends={'authorization_id': 'prior', 'authorization_digest': 'b' * 64},
            execution_scope={'case_ids': [self.case['id']], 'configurations': ['economy', 'strong', 'router'],
                'max_runs': 1, 'max_combinations': 3, 'max_external_calls': 11, 'repeat_uncertain_calls': False})
        self.save_approval()
        return old, deepcopy(self.approval)

    def command(self, apply=False):
        out = StringIO()
        call_command('extend_pilot_authorization', manifest=str(self.manifest_path),
            authorization=str(self.approval_path), apply=apply, stdout=out)
        return json.loads(out.getvalue())

    def dump(self):
        (OWN / 'independent-observations.json').write_text(json.dumps(RESULTS, indent=2) + '\n', encoding='utf-8')

    def test_expiration_after_reservation_preserves_unknown_and_consumes_pass(self):
        old, frozen = self.prepare()
        before = old.snapshot()
        self.command(apply=True)
        reserve = EvaluationBudget.reserve
        def reserve_then_expire(ledger, *args, **kwargs):
            token = reserve(ledger, *args, **kwargs)
            self.approval['valid_until'] = '2000-01-01T00:00:00+00:00'
            self.approval_path.write_text(json.dumps(self.approval), encoding='utf-8')
            return token
        with patch.object(EvaluationBudget, 'reserve', reserve_then_expire), self.assertRaises(CommandError):
            self.run_smoke('expired-after-reserve')
        current = EvaluationBudget(self.ledger_path, '1.00', authorization_id=frozen['authorization_id'],
            authorization_digest=evaluation.digest(frozen))
        after = current.snapshot()
        self.assertEqual(after['calls'][:2], before['calls'])
        self.assertEqual(after['budget_exposure_usd'], '0.013858062')
        self.assertEqual(after['uncertain_reservations_usd'], '0.003')
        self.assertEqual(after['calls'][-1]['status'], 'not_started')
        self.assertEqual(after['calls'][-1]['metadata']['cost_kind'], 'not_incurred')
        with self.assertRaises(ValueError):
            current.claim_extension_run(frozen['manifest_sha256s'][0])
        self.assertFalse(self.events)
        RESULTS['expiry_after_reserve'] = {'exposure': after['budget_exposure_usd'],
            'uncertain': after['uncertain_reservations_usd'], 'transport_events': len(self.events),
            'nonstarted_status': after['calls'][-1]['status'], 'run_consumed': True}
        self.dump()

    def test_revocation_while_waiting_for_lock_never_registers(self):
        old, _ = self.prepare()
        before = self.ledger_path.read_bytes()
        @contextmanager
        def revoke_before_lock_body():
            self.approval['approved'] = False
            self.approval_path.write_text(json.dumps(self.approval), encoding='utf-8')
            yield
        with patch.object(evaluation, 'real_lock', revoke_before_lock_body), self.assertRaises(CommandError):
            self.command(apply=True)
        self.assertEqual(self.ledger_path.read_bytes(), before)
        RESULTS['revocation_during_lock_wait'] = {'ledger_byte_unchanged': True, 'events': len(self.events)}
        self.dump()

    def test_cli_report_identifies_exact_approval_registered_after_lock_wait(self):
        old, original = self.prepare()
        @contextmanager
        def replace_before_lock_body():
            # A distinct valid synthetic approval appears while the CLI waits.
            self.approval['approval_reference'] = 'SECOND synthetic human approval; never a live grant'
            self.approval_path.write_text(json.dumps(self.approval), encoding='utf-8')
            yield
        with patch.object(evaluation, 'real_lock', replace_before_lock_body):
            report = self.command(apply=True)
        actual_digest = evaluation.digest(self.approval)
        active = EvaluationBudget(self.ledger_path, '1.00', authorization_id=self.approval['authorization_id'],
            authorization_digest=actual_digest)
        self.assertEqual(active.snapshot(), old.snapshot())
        RESULTS['cli_report_race'] = {'reported_digest': report['authorization_digest'],
            'registered_digest': actual_digest, 'reported_mode': report['mode'],
            'head_checked_reported': report['ledger_head_checked'],
            'report_matches_registered': report['authorization_digest'] == actual_digest}
        self.dump()
        self.assertEqual(report['authorization_digest'], actual_digest,
            'The CLI must report the approval actually registered under the lock')
