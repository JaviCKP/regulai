from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'snapshot-manifest.json').read_text(encoding='utf-8'))
changed = [row['path'] for row in manifest['files']
    if hashlib.sha256((root / 'snapshot' / row['path']).read_bytes()).hexdigest() != row['sha256']]
red = json.loads((root / 'finding-S1-reservation-approval-race.json').read_text(encoding='utf-8'))
green = json.loads((root / 'control-S1-reservation-recheck.json').read_text(encoding='utf-8'))
result = {'commit': manifest['commit'], 'snapshot_files': len(manifest['files']), 'changed_files': changed,
    'red_events': red['events'], 'red_generation_count': len(red['generation_payloads']),
    'red_authorization_ready_after_reserve': red['authorization_ready_after_reserve'],
    'red_live_socket_calls': red['live_socket_calls'],
    'control_events': green['events'], 'control_generation_count': len(green['generation_payloads']),
    'control_generation_settlement': next(call for call in green['ledger']['calls'] if call['purpose'] == 'generation'),
    'control_live_socket_calls': green['live_socket_calls']}
(root / 'evidence-audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert not changed
