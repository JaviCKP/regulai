"""Independent final-export byte checks. Never regenerates or changes fixtures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
root = HERE / 'packaging'
corpus = root / 'evals/documents/pilot-20261003'
manifest = json.loads((corpus / 'files/manifest.json').read_text(encoding='utf-8'))
checks = [('expectations.json', manifest['expectations_sha256']),
    ('generate_corpus.py', manifest['generator_sha256'])]
checks.extend(('files/' + item['file'], item['sha256']) for item in manifest['files'])
results = []
for name, expected in checks:
    actual = hashlib.sha256((corpus / name).read_bytes()).hexdigest()
    results.append({'path': name, 'sha256': actual, 'expected': expected, 'equal': actual == expected})

approval = json.loads((root / 'evals/pilot-real/authorization.pending.json').read_text(encoding='utf-8'))
approval_checks = []
for name in ('pilot-real', 'pilot-human'):
    source = root / 'evals' / name / 'manifest.json'
    value = json.loads(source.read_text(encoding='utf-8'))
    observed_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    approval_checks.append({'bank': name, 'sha256': observed_hash,
        'bound_to_pending_approval': observed_hash in approval['manifest_sha256s'],
        'detector_version': value['masking']['detector_version']})

runtime_drift = []
for source in sorted((HERE / 'closure/regulai').rglob('*.py')):
    relative = source.relative_to(HERE / 'closure')
    if source.read_bytes() != (root / relative).read_bytes():
        runtime_drift.append(relative.as_posix())

record = {'commit': 'd63731a9c5dfda27c3dc504c295422502383d2f1',
    'runtime_baseline': '0957df45362bc7cbf41c154bb13514d58901763a',
    'core_autocrlf': True, 'corpus_hash_checks': results, 'approval_status': approval['status'],
    'approval_checks': approval_checks, 'runtime_drift': runtime_drift,
    'network_calls': 0, 'api_spend_usd': '0', 'human_participants': 0,
}
record['passed'] = (all(item['equal'] for item in results) and approval['status'] == 'pending'
    and all(item['bound_to_pending_approval'] and item['detector_version'] == 'regulai-local-v2' for item in approval_checks)
    and not runtime_drift)
target = HERE / 'packaging-verification.json'
target.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': record['passed'], 'corpus_hashes': len(results),
    'approval_checks': approval_checks, 'runtime_drift': runtime_drift,
    'evidence': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}, indent=2))
raise SystemExit(0 if record['passed'] else 1)
