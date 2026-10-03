"""Durable, single-host reservation ledger for explicitly authorized real tests."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
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
        self.authorization = (authorization_id, authorization_digest) if authorization_id is not None else None
        self.run_id = None
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
            approval = self.head(db)
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

    @staticmethod
    def head(db):
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='approval_extensions'").fetchone():
            latest = db.execute('SELECT id,digest FROM approval_extensions ORDER BY sequence DESC LIMIT 1').fetchone()
            if latest:
                return latest
        anchors = db.execute('SELECT id,digest FROM approval').fetchall()
        if len(anchors) > 1:
            raise ValueError('The ledger has an ambiguous approval anchor.')
        return anchors[0] if anchors else None

    @classmethod
    def extend_authorization(cls, path, cap, *, previous_id, previous_digest, authorization_id,
                             authorization_digest, manifest_sha256, approval_reference, max_external_calls):
        """Append an explicitly validated scope. Never create/reset a missing ledger.

        The management command validates the human approval and frozen manifest;
        this transaction enforces the immutable chain, cap and existing history.
        """
        values = (previous_id, previous_digest, authorization_id, authorization_digest,
                  manifest_sha256, approval_reference)
        if (any(not isinstance(value, str) or not value for value in values)
                or len(manifest_sha256) != 64 or any(char not in '0123456789abcdef' for char in manifest_sha256)
                or previous_id == authorization_id or previous_digest == authorization_digest
                or type(max_external_calls) is not int or max_external_calls < 1):
            raise ValueError('Invalid explicit scope extension.')
        ledger = cls.__new__(cls)
        ledger.path, ledger.cap = str(path), money(cap)
        try:
            with ledger.transaction(existing_only=True) as db:
                caps = db.execute('SELECT cap FROM authorization').fetchall()
                if len(caps) != 1 or money(caps[0][0]) != ledger.cap or not 0 < ledger.cap <= 1:
                    raise ValueError('The shared authorization cap cannot change.')
                head = cls.head(db)
                if not head:
                    raise ValueError('An explicit existing approval is required.')
                db.execute('CREATE TABLE IF NOT EXISTS approval_extensions ('
                    'sequence INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, digest TEXT NOT NULL UNIQUE, '
                    'previous_id TEXT NOT NULL, previous_digest TEXT NOT NULL, at TEXT NOT NULL, '
                    'manifest_sha256 TEXT NOT NULL, approval_reference TEXT NOT NULL, max_external_calls INTEGER NOT NULL, '
                    'UNIQUE(previous_id, previous_digest))')
                expected = (authorization_id, authorization_digest, previous_id, previous_digest,
                            manifest_sha256, approval_reference, max_external_calls)
                duplicate = db.execute('SELECT id,digest,previous_id,previous_digest,manifest_sha256,'
                    'approval_reference,max_external_calls FROM approval_extensions WHERE id=? OR digest=?',
                    (authorization_id, authorization_digest)).fetchone()
                if duplicate:
                    if duplicate == expected and head == (authorization_id, authorization_digest):
                        return False
                    raise ValueError('A scope identity cannot be reused or replaced.')
                if head != (previous_id, previous_digest):
                    raise ValueError('The previous approval is not the current ledger head.')
                anchors = db.execute('SELECT id,digest FROM approval').fetchall()
                if any(authorization_id == pair[0] or authorization_digest == pair[1] for pair in anchors):
                    raise ValueError('The original approval cannot be reused.')
                db.execute('INSERT INTO approval_extensions (id,digest,previous_id,previous_digest,manifest_sha256,'
                    'approval_reference,max_external_calls,at) VALUES (?,?,?,?,?,?,?,?)',
                    (*expected, datetime.now(timezone.utc).isoformat()))
                db.execute('CREATE TABLE IF NOT EXISTS extension_runs (authorization_id TEXT PRIMARY KEY, '
                    'run_id TEXT NOT NULL UNIQUE, manifest_sha256 TEXT NOT NULL, at TEXT NOT NULL)')
        except sqlite3.Error as error:
            raise ValueError('The existing ledger cannot accept this scope extension.') from error
        return True

    def claim_extension_run(self, manifest_sha256):
        """A claimed extension cannot resume/replay, even after a crash or new output directory."""
        with self.transaction() as db:
            if self.head(db) != self.authorization:
                raise ValueError('The approval is no longer the current ledger head.')
            extension = db.execute('SELECT manifest_sha256 FROM approval_extensions WHERE id=? AND digest=?',
                                   self.authorization).fetchone()
            if not extension or extension[0] != manifest_sha256:
                raise ValueError('The run must use the registered extension manifest.')
            if db.execute('SELECT 1 FROM extension_runs WHERE authorization_id=?', (self.authorization[0],)).fetchone():
                raise ValueError('This extension run was already claimed; automatic replay is prohibited.')
            run_id = str(uuid.uuid4())
            db.execute('INSERT INTO extension_runs VALUES (?,?,?,?)',
                       (self.authorization[0], run_id, manifest_sha256, datetime.now(timezone.utc).isoformat()))
        self.run_id = run_id
        return run_id

    @contextmanager
    def transaction(self, *, existing_only=False):
        location = Path(self.path).resolve().as_uri() + '?mode=rw' if existing_only else self.path
        db = sqlite3.connect(location, timeout=10, uri=existing_only)
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
            if self.head(db) != self.authorization:
                raise ValueError('The approval is no longer the current ledger head.')
            metadata = dict(metadata or {})
            if self.authorization:
                metadata.update(authorization_id=self.authorization[0], authorization_digest=self.authorization[1])
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='approval_extensions'").fetchone():
                extension = db.execute('SELECT manifest_sha256,max_external_calls FROM approval_extensions WHERE id=? AND digest=?',
                                       self.authorization or (None, None)).fetchone()
                if extension:
                    claimed = db.execute('SELECT run_id FROM extension_runs WHERE authorization_id=?',
                                         (self.authorization[0],)).fetchone()
                    if not self.run_id or claimed != (self.run_id,):
                        raise ValueError('Reserve calls only in the process that claimed this extension run.')
                    metadata.update(manifest_sha256=extension[0], run_id=self.run_id)
                    external = not (purpose == 'obfuscation' and zero_cost and metadata.get('transport') == 'local')
                    metadata['scope_external_call'] = external
                    previous_calls = [json.loads(row[0]) for row in db.execute('SELECT metadata FROM calls')]
                    count = sum(row.get('authorization_id') == self.authorization[0]
                                and row.get('scope_external_call') is True for row in previous_calls)
                    if external and count >= extension[1]:
                        raise BudgetExceeded('The approved external call count is exhausted.')
            if db.execute("SELECT 1 FROM calls WHERE status='bound_exceeded' LIMIT 1").fetchone():
                raise BudgetExceeded('An earlier provider charge exceeded its bound; review required.')
            used = sum((self.exposure(bound, cost, json.loads(meta))
                for bound, cost, meta in db.execute('SELECT reserved,cost,metadata FROM calls')), Decimal(0))
            if used + maximum > self.cap:
                raise BudgetExceeded('Authorized total budget exhausted.')
            call_id = str(uuid.uuid4())
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)', (call_id,
                datetime.now(timezone.utc).isoformat(), purpose, str(maximum), 'started', None, json.dumps(metadata)))
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
            original_metadata = json.loads(row[2])
            settled_metadata = {**original_metadata, **(metadata or {}), 'cost_kind': cost_kind}
            for field in ('authorization_id', 'authorization_digest', 'manifest_sha256', 'run_id', 'transport', 'scope_external_call'):
                if field in original_metadata:
                    settled_metadata[field] = original_metadata[field]
            db.execute('UPDATE calls SET status=?,cost=?,metadata=? WHERE id=?',
                (status, str(cost) if cost is not None else None,
                 json.dumps(settled_metadata), call_id))
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
