from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
checks = []
for location in (root.parent, root):
    manifest = json.loads((location / 'snapshot-manifest.json').read_text(encoding='utf-8'))
    changed = [row['path'] for row in manifest['files']
        if hashlib.sha256((location / 'snapshot' / row['path']).read_bytes()).hexdigest() != row['sha256']]
    checks.append({'commit': manifest['commit'], 'source_files': len(manifest['files']), 'changed_files': changed})
result = json.loads((root / 'finding-S1-reservation-approval-race.json').read_text(encoding='utf-8'))
checks.append({'fixed_events': result['events'], 'generation_payload_count': len(result['generation_payloads']),
    'approval_ready_after_reserve': result['authorization_ready_after_reserve'],
    'live_socket_calls': result['live_socket_calls'],
    'generation_settlement': next(call for call in result['ledger']['calls'] if call['purpose'] == 'generation')})
(root / 'integrity.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
print(json.dumps(checks, indent=2))
assert not any(item.get('changed_files') for item in checks)
