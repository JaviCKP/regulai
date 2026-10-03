"""Record the explicit 2026-10-03 user approval and extend the existing ledger once.

No provider or credential access. The user approved these four cases and additional
cases from the same synthetic bank within the unchanged 1 USD combined cap.
This activation registers ONLY four additional cases explicitly allowed by the same user reply.
"""
from contextlib import closing
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import sys
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACK = ROOT / 'evals/adversarial-live/community-additional-20261003'
sys.path.insert(0, str(ROOT / 'regulai'))
sys.modules['regulai.local_settings'] = types.ModuleType('regulai.local_settings')
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
import django
django.setup()
from django.core.management import call_command
from front.evaluation import LEDGER_PATH, canonical, digest, preflight


def state():
    with closing(sqlite3.connect(LEDGER_PATH.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        calls = db.execute('SELECT * FROM calls ORDER BY rowid').fetchall()
        return {'ledger_sha256': digest(LEDGER_PATH.read_bytes()), 'calls_sha256': digest(calls),
            'calls_n': len(calls), 'cap': db.execute('SELECT cap FROM authorization').fetchall(),
            'original_approval': db.execute('SELECT id,digest FROM approval').fetchall()}


def main():
    manifest = PACK / 'manifest.json'
    expected = 'b4730105fd1f74bfbd3baf0d6757cd9bfd6484b1170b61517944ad721e058b30'
    if digest(manifest.read_bytes()) != expected or not LEDGER_PATH.is_file():
        raise RuntimeError('Frozen scope or existing ledger is missing/changed.')
    authorization = PACK / 'authorization.approved.json'
    approval = json.loads((PACK / 'authorization.pending.json').read_text(encoding='utf-8'))
    approval.update(status='approved', approved=True, approved_by='Repository owner in this Codex conversation',
        approval_reference='2026-10-03 user reply to call_3bb9a7ecc55448f6afbf14dc542141c7: '
            'autorizo esos 4 casos y autorizo que hagas mas. This record registers BENIGN-02, PII-03, DOC-01 and INJ-07 under the explicit additional-cases permission; '
            'the combined 1 USD cap, destinations, synthetic-only data and stop conditions remain unchanged.',
        valid_from='2026-10-03T17:09:37+00:00', valid_until='2026-10-04T17:09:37+00:00',
        mutable_alias_acknowledged=True)
    with authorization.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(approval, ensure_ascii=False, indent=2) + '\n')
    check, _ = preflight(manifest, authorization, check_credentials=False)
    if not check['ready_for_real']:
        raise RuntimeError('Approved four-case preparation is not ready: ' + ', '.join(check['blockers']))
    before = state()
    backup = ROOT / '.claude/adversarial-ledger-backups/before-additional-case-extension.sqlite3'
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open('xb') as handle:
        handle.write(LEDGER_PATH.read_bytes())
    console = StringIO()
    call_command('extend_pilot_authorization', manifest=str(manifest), authorization=str(authorization),
                 apply=True, stdout=console)
    after = state()
    unchanged = all(before[key] == after[key] for key in ('calls_sha256', 'calls_n', 'cap', 'original_approval'))
    record = {'at': datetime.now(timezone.utc).isoformat(), 'manifest_sha256': expected,
        'authorization_canonical_digest': digest(approval), 'before': before, 'after': after,
        'historical_calls_anchor_and_cap_unchanged': unchanged, 'backup_sha256': digest(backup.read_bytes()),
        'registration': json.loads(console.getvalue()), 'credentials_accessed': False, 'network_calls': 0}
    with (HERE / 'activation.json').open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(record, indent=2) + '\n')
    print(canonical({'registered': True, 'historical_calls_anchor_and_cap_unchanged': unchanged,
        'historical_calls': before['calls_n'], 'network_calls': 0}))
    if not unchanged:
        raise RuntimeError('Historical ledger changed unexpectedly; stop before any provider call.')


if __name__ == '__main__':
    main()

