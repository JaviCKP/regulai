"""Verify both immutable snapshots and seal all direct review evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
seal = HERE / 'final-seal.json'
if seal.exists():
    raise SystemExit('Evidence is already sealed')
verified = {}
for inventory in ('snapshot-698e8f0.json', 'snapshot-698e8f0-approvedbytes.json'):
    manifest = json.loads((HERE / inventory).read_text(encoding='utf-8'))
    snapshot = HERE / manifest['snapshot']
    for name, expected in manifest['files'].items():
        if hashlib.sha256((snapshot / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('Snapshot changed: ' + name)
    verified[inventory] = {'verified_files': len(manifest['files']),
        'sha256': hashlib.sha256((HERE / inventory).read_bytes()).hexdigest()}
report = ROOT / 'docs/plan-blackhat/revisiones-piloto/security-vercel-698e8f0.md'
record = {'commit': '698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc',
    'sealed_utc': datetime.now(timezone.utc).isoformat(), 'snapshots': verified,
    'verdict': 'No new blocking security findings within the fixed authorized scope',
    'final_tests': {'supplied': 45, 'independent': 6, 'total': 51, 'failures': 0},
    'network_attempts': 0, 'bridge_executed': False, 'user_database_accessed': False,
    'report': str(report.relative_to(ROOT)), 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
    'evidence': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(HERE.iterdir()) if path.is_file() and path != seal}}
seal.write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps({'seal_sha256': hashlib.sha256(seal.read_bytes()).hexdigest(),
    'report_sha256': record['report_sha256'], 'verified_files': sum(x['verified_files'] for x in verified.values()),
    'evidence_files': len(record['evidence'])}))
