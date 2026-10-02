from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from .evaluation_budget import BudgetExceeded, EvaluationBudget


class BudgetTests(SimpleTestCase):
    def test_concurrent_reservation_and_restart_never_release_unknown_expense(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'budget.sqlite3'
            ledger = EvaluationBudget(path, '1')
            def reserve(_):
                try:
                    return ledger.reserve('synthetic', '.3')
                except BudgetExceeded:
                    return None
            with ThreadPoolExecutor(max_workers=4) as executor:
                ids = [value for value in executor.map(reserve, range(4)) if value]
            self.assertEqual(len(ids), 3)
            ledger.complete(ids[0], cost='.01')
            ledger.complete(ids[1], status='outcome_unknown')
            fresh = EvaluationBudget(path, '1')
            self.assertEqual(fresh.snapshot()['uncertain_reservations_usd'], '0.6')
            with self.assertRaises(BudgetExceeded):
                fresh.reserve('too much', '.4')
            fresh.reserve('last permitted', '.39')
            with self.assertRaises(BudgetExceeded):
                fresh.reserve('over cap', '.00001')
            with self.assertRaises(ValueError):
                fresh.complete(ids[0], cost='0')
            with self.assertRaises(ValueError):
                EvaluationBudget(path, '2')
