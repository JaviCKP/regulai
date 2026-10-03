"""Capture read-only receipt state from a verified, synthetic B pilot workspace."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
if not workspace.is_relative_to((ROOT / '.claude').resolve()):
    parser.error('Only the isolated pilot workspace is permitted')
database = workspace / 'pilot.sqlite3'
metadata = json.loads((workspace / 'run.json').read_text(encoding='utf-8'))
if Path(metadata['database']).resolve() != database or not database.is_file() or database.is_symlink():
    parser.error('Pilot metadata/database mismatch')
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
    connection.row_factory = sqlite3.Row
    rows = []
    for record in connection.execute('SELECT request_id, status, created_at, updated_at, file_name, file_sha256, user_message_id, decision FROM front_prompt ORDER BY id'):
        row = dict(record)
        decision = json.loads(row.pop('decision'))
        row['request_id'] = str(uuid.UUID(row['request_id']))
        row['calls'] = len(decision.get('calls', []))
        row['consent_reason'] = decision.get('consent_reason')
        row['coverage_status'] = decision.get('coverage', {}).get('status')
        row['total'] = decision.get('total')
        row['total_present'] = 'total' in decision
        rows.append(row)
    messages = connection.execute('SELECT role, COUNT(*) AS n FROM front_message GROUP BY role').fetchall()
report = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
          'workspace': workspace.name, 'synthetic': True, 'read_only': True,
          'messages': {row['role']: row['n'] for row in messages}, 'requests': rows}
with args.output.open('x', encoding='utf-8') as output:
    output.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
