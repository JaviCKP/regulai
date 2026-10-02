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
    def __init__(self, path, cap):
        self.path, self.cap = str(path), money(cap)
        if not 0 < self.cap <= 1:
            raise ValueError('This authorization is capped at 1 USD in total.')
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS authorization (cap TEXT NOT NULL)')
            previous = db.execute('SELECT cap FROM authorization').fetchone()
            if previous and money(previous[0]) != self.cap:
                raise ValueError('Existing authorization limit cannot be changed.')
            if not previous:
                db.execute('INSERT INTO authorization VALUES (?)', (str(self.cap),))
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, at TEXT, purpose TEXT, '
                       'reserved TEXT, status TEXT, cost TEXT, metadata TEXT)')

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

    def reserve(self, purpose, maximum):
        maximum = money(maximum)
        if maximum <= 0:
            raise ValueError('A positive reservation is required.')
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM calls WHERE status='bound_exceeded' LIMIT 1").fetchone():
                raise BudgetExceeded('An earlier provider charge exceeded its bound; review required.')
            used = sum((money(cost if cost is not None else bound)
                for bound, cost in db.execute('SELECT reserved,cost FROM calls')), Decimal(0))
            if used + maximum > self.cap:
                raise BudgetExceeded('Authorized total budget exhausted.')
            call_id = str(uuid.uuid4())
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)', (call_id,
                datetime.now(timezone.utc).isoformat(), purpose, str(maximum), 'started', None, '{}'))
        return call_id

    def complete(self, call_id, *, cost=None, metadata=None, status='completed'):
        with self.transaction() as db:
            row = db.execute('SELECT reserved,status FROM calls WHERE id=?', (call_id,)).fetchone()
            if not row or row[1] != 'started':
                raise ValueError('Call is missing or already settled.')
            cost = money(cost) if cost is not None else None
            # Record even a provider charge exceeding its advertised bound, then
            # stop further tests; never erase an observed expense.
            if cost is not None and cost > money(row[0]):
                status = 'bound_exceeded'
            db.execute('UPDATE calls SET status=?,cost=?,metadata=? WHERE id=?',
                (status, str(cost) if cost is not None else None, json.dumps(metadata or {}), call_id))
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
        return {'cap_usd': str(self.cap), 'known_cost_usd': str(known),
            'uncertain_reservations_usd': str(uncertain), 'calls': calls}
