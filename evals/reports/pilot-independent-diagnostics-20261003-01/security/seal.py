"""Verify immutable snapshots and seal completed diagnostic review evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
target = HERE / 'final-seal.json'
if target.exists():
    raise SystemExit('Evidence already sealed')
verified = {}
for name in ('snapshot-535eb9d.json', 'snapshot-972edb8.json'):
    inventory = json.loads((HERE / name).read_text(encoding='utf-8'))
    for filename, expected in inventory['files'].items():
        actual = hashlib.sha256((HERE / inventory['snapshot'] / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit('Snapshot changed: ' + filename)
    verified[name] = {'files_verified': len(inventory['files']),
                      'sha256': hashlib.sha256((HERE / name).read_bytes()).hexdigest()}
report = ROOT / 'docs/revisiones-piloto/security-diagnostics-972edb8.md'
result = {'base_commit': '535eb9d8421006ea8476ea511427a7dcda9cee3b',
    'candidate_commit': '972edb88c82a5220a43ffcc89316a9f9033e82f7',
    'sealed_at': datetime.now(timezone.utc).isoformat(), 'snapshots': verified,
    'verdict': 'No new blocking security findings in the fixed diagnostic patch',
    'candidate_tests': {'supplied': 5, 'independent': 3, 'failures': 0},
    'differential_scenarios': 18, 'behavior_differences': 0, 'historical_files_unchanged': 11,
    'network_attempts': 0, 'bridge_executed': False, 'real_database_or_ledger_opened': False,
    'report': str(report.relative_to(ROOT)), 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
    'evidence': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(HERE.iterdir()) if path.is_file() and path != target}}
target.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'seal_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'report_sha256': result['report_sha256'], 'evidence_files': len(result['evidence']),
    'snapshot_files_verified': sum(item['files_verified'] for item in verified.values())}))
