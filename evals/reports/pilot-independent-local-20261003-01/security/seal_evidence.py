"""Record final review hashes and that original PoCs were replayed unchanged."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
result = {'snapshots': [], 'original_pocs_identical': {}, 'reports': {}}
for directory in (HERE, HERE / 'followup-be29b6f', HERE / 'followup-0957df4'):
    manifest = json.loads((directory / 'snapshot-manifest.json').read_text(encoding='utf-8'))
    mismatches = []
    for name, expected in manifest['files'].items():
        path = directory / 'snapshot' / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            mismatches.append(name)
    evidence = {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                for item in directory.iterdir() if item.is_file() and item.name != 'final-seal.json'}
    result['snapshots'].append({'commit': manifest['commit'], 'files': len(manifest['files']),
        'source_mismatches': mismatches, 'archive_sha256': manifest['archive_sha256'], 'evidence_sha256': evidence})
for name in ('review_checks.py', 'rollback_check.py'):
    original = (HERE / name).read_bytes()
    replayed = (HERE / 'followup-0957df4' / name).read_bytes()
    result['original_pocs_identical'][name] = original == replayed
for name in ('security-local-c85d019.md', 'security-local-0957df4.md'):
    path = ROOT / 'docs' / 'plan-blackhat' / 'revisiones-piloto' / name
    result['reports'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
(HERE / 'final-seal.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'sources_unchanged': all(not entry['source_mismatches'] for entry in result['snapshots']),
                  'original_pocs_identical': result['original_pocs_identical'], 'reports': result['reports']}))
raise SystemExit(not all(not entry['source_mismatches'] for entry in result['snapshots'])
                 or not all(result['original_pocs_identical'].values()))
