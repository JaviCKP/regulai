"""Durable, single-host reservation ledger for explicitly authorized real tests."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3
import uuid


class BudgetExceeded(ValueError):
    pass


def money(value):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError('Invalid nonnegative amount')
    return value


class EvaluationBudget:
    """All test invocations share one file. Uncertain outcomes retain reservation."""
    def __init__(self, path, cap, *, authorization_id=None, authorization_digest=None):
        self.path, self.cap = str(path), money(cap)
        if not 0 < self.cap <= 1:
            raise ValueError('The pilot is capped at 1 USD in total.')
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS authorization (cap TEXT NOT NULL)')
            previous = db.execute('SELECT cap FROM authorization').fetchone()
            if previous and money(previous[0]) != self.cap:
                raise ValueError('Existing authorization limit cannot be changed.')
            if not previous:
                db.execute('INSERT INTO authorization VALUES (?)', (str(self.cap),))
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, at TEXT, purpose TEXT, '
                       'reserved TEXT, status TEXT, cost TEXT, metadata TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS approval (id TEXT NOT NULL, digest TEXT NOT NULL)')
            approval = db.execute('SELECT id,digest FROM approval').fetchone()
            if authorization_id is not None:
                if not authorization_id or not authorization_digest:
                    raise ValueError('An explicit authorization identity and digest are required.')
                if approval and approval != (authorization_id, authorization_digest):
                    raise ValueError('The existing authorization cannot be replaced or renewed implicitly.')
                if not approval:
                    if db.execute('SELECT 1 FROM calls LIMIT 1').fetchone():
                        raise ValueError('Historical calls cannot acquire a new authorization.')
                    db.execute('INSERT INTO approval VALUES (?,?)', (authorization_id, authorization_digest))
            elif approval:
                raise ValueError('This ledger requires its explicit authorization.')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, purpose, maximum, *, metadata=None, zero_cost=False):
        maximum = money(maximum)
        if maximum == 0 and not zero_cost:
            raise ValueError('A positive reservation is required.')
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM calls WHERE status='bound_exceeded' LIMIT 1").fetchone():
                raise BudgetExceeded('An earlier provider charge exceeded its bound; review required.')
            used = sum((self.exposure(bound, cost, json.loads(meta))
                for bound, cost, meta in db.execute('SELECT reserved,cost,metadata FROM calls')), Decimal(0))
            if used + maximum > self.cap:
                raise BudgetExceeded('Authorized total budget exhausted.')
            call_id = str(uuid.uuid4())
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)', (call_id,
                datetime.now(timezone.utc).isoformat(), purpose, str(maximum), 'started', None, json.dumps(metadata or {})))
        return call_id

    @staticmethod
    def exposure(bound, cost, metadata):
        # A tariff calculation is an estimate, not a communicated charge. It
        # never releases the reservation merely because it happens to be lower.
        if cost is not None and metadata.get('cost_kind', 'provider_reported') in ('provider_reported', 'configured_zero', 'not_incurred'):
            return money(cost)
        return max(money(bound), money(cost) if cost is not None else Decimal(0))

    def complete(self, call_id, *, cost=None, metadata=None, status='completed', cost_kind='provider_reported'):
        if status not in {'completed', 'failed', 'outcome_unknown', 'not_started'} or cost_kind not in {
                'provider_reported', 'tariff_estimate', 'configured_zero', 'not_incurred', 'unknown'}:
            raise ValueError('Invalid settlement status or cost provenance.')
        with self.transaction() as db:
            row = db.execute('SELECT reserved,status,metadata FROM calls WHERE id=?', (call_id,)).fetchone()
            if not row or row[1] != 'started':
                raise ValueError('Call is missing or already settled.')
            cost = money(cost) if cost is not None else None
            if (status == 'not_started' or cost_kind == 'not_incurred') and not (
                    status == 'not_started' and cost_kind == 'not_incurred' and cost == 0):
                raise ValueError('A non-started call must have a proven zero expense.')
            if cost_kind == 'configured_zero' and (cost != 0 or money(row[0]) != 0):
                raise ValueError('Configured zero requires a zero bound and zero cost.')
            if status != 'completed':
                cost_kind = 'unknown' if cost is None else cost_kind
            # Record even a provider charge exceeding its advertised bound, then
            # stop further tests; never erase an observed expense.
            if cost is not None and cost > money(row[0]):
                status = 'bound_exceeded'
            db.execute('UPDATE calls SET status=?,cost=?,metadata=? WHERE id=?',
                (status, str(cost) if cost is not None else None,
                 json.dumps({**json.loads(row[2]), **(metadata or {}), 'cost_kind': cost_kind}), call_id))
        if status == 'bound_exceeded':
            raise BudgetExceeded('Provider charge exceeded the reserved bound.')

    def snapshot(self):
        with self.transaction() as db:
            rows = db.execute('SELECT id,at,purpose,reserved,status,cost,metadata FROM calls ORDER BY rowid').fetchall()
        calls = [dict(zip(('id','at','purpose','reserved','status','cost','metadata'), row)) for row in rows]
        for call in calls:
            call['metadata'] = json.loads(call['metadata'])
        known = sum((money(call['cost']) for call in calls if call['cost'] is not None), Decimal(0))
        uncertain = sum((money(call['reserved']) for call in calls if call['cost'] is None), Decimal(0))
        exposure = sum((self.exposure(call['reserved'], call['cost'], call['metadata']) for call in calls), Decimal(0))
        reported = sum((money(call['cost']) for call in calls if call['cost'] is not None
                        and call['metadata'].get('cost_kind') == 'provider_reported'), Decimal(0))
        estimated = sum((money(call['cost']) for call in calls if call['cost'] is not None
                         and call['metadata'].get('cost_kind') == 'tariff_estimate'), Decimal(0))
        return {'cap_usd': str(self.cap), 'known_cost_usd': str(known),
            'provider_reported_usd': str(reported), 'tariff_estimated_usd': str(estimated),
            'budget_exposure_usd': str(exposure), 'remaining_usd': str(max(Decimal(0), self.cap - exposure)),
            'uncertain_reservations_usd': str(uncertain), 'calls': calls}
