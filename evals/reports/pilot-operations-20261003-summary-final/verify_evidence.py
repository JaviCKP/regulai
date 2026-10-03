"""Recheck preserved synthetic lab evidence without printing secret values."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
reports = ROOT / 'evals/reports'
summary = []
for directory in sorted(reports.glob('pilot-operations-20261003-[0-9][0-9]')):
    result = json.loads((directory / 'result.json').read_text(encoding='utf-8'))
    private = Path(result['private_work']).resolve()
    if not private.is_relative_to((ROOT / '.claude').resolve()) or not private.name.startswith('regulai-lab-'):
        raise ValueError('Expected only synthetic private laboratory evidence.')
    # These are fresh synthetic secrets. Compare in memory; never emit their values.
    keys = json.loads((private / 'private/keys.json').read_text(encoding='utf-8'))
    prohibited = [keys[name] for name in ('signing', 'encryption', 'database')]
    prohibited += ['SYNTHETIC_PII_EMAIL', 'synthetic-jev-alpha', 'synthetic-engine-alpha']
    logs = list(directory.glob('*.log'))
    if any(value in log.read_text(encoding='utf-8') for value in prohibited for log in logs):
        raise AssertionError('A synthetic sensitive value appeared in a preserved command log.')
    commands = json.loads((directory / 'commands.json').read_text(encoding='utf-8'))
    for command in commands:
        assert sha256((directory / command['log']).read_bytes()).hexdigest() == command['sha256']
    summary.append({'directory': directory.name, 'checks': result['checks'],
        'has_failure_record': (directory / 'failure.txt').exists(), 'commands': len(commands),
        'logs_checked': len(logs), 'synthetic_secret_and_payload_matches': 0,
        'command_log_hashes_match': True,
        'files': {path.name: sha256(path.read_bytes()).hexdigest()
                  for path in sorted(directory.iterdir()) if path.is_file()}})
output = Path(__file__).with_name('verification.json')
if output.exists():
    raise FileExistsError('Keep previous verification; use a new evidence directory for another run.')
output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'executions': len(summary), 'all_command_hashes_match': True,
                  'synthetic_secret_and_payload_log_matches': 0}))
