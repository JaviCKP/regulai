"""Record the explicit user reply for the eight-case smoke, then perform read-only preflight."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'authorization.json').exists(), 'Never overwrite an approval record.'
manifest_path = ROOT / 'evals/pilot-real/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert sha256(manifest_path.read_bytes()).hexdigest() == '12aecafee1351be7584791db4f4e0d22d9f522abb7552bdce7af804e2525c1ed'
approval = json.loads((ROOT / 'evals/pilot-real/authorization.pending.json').read_text(encoding='utf-8'))
approval.update(status='approved', approved_by='Human user of the current Codex conversation',
    approval_reference='Explicit reply to request_user_input_async call_KWCsyBL4GgidolwelGqsmiC2: Autorizar hasta 1 USD para esos 8 casos',
    manifest_sha256s=[sha256(manifest_path.read_bytes()).hexdigest()],
    valid_from='2026-10-03T15:23:54+00:00', valid_until='2026-10-03T23:59:59+00:00',
    pricing_reviewed_on='2026-10-03', mutable_alias_acknowledged=True, reserved_evaluation=False,
    notes='New explicit approval for eight synthetic cases in three configurations only. Maximum USD1 includes failures and uncertain reservations. Human bank, participants, publication and deployment are excluded. The operational window ends with this UTC pricing-review day, within the approved 24-hour maximum. No October 2 approval is reused.')
with (HERE / 'authorization.json').open('x', encoding='utf-8') as handle:
    handle.write(json.dumps(approval, ensure_ascii=False, indent=2) + '\n')
command = ['rtk', 'proxy', sys.executable, 'regulai/manage.py', 'smoke_ai',
           '--settings=regulai.test_settings', '--preflight', '--authorization', str(HERE / 'authorization.json'),
           '--output', str(HERE / 'must-not-exist')]
result = subprocess.run(command, cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace')
(HERE / 'preflight.stdout.json').write_text(result.stdout, encoding='utf-8')
(HERE / 'preflight.stderr.log').write_text(result.stderr, encoding='utf-8')
preflight = json.loads(result.stdout)
assert result.returncode == 0 and preflight['blockers'] == ['isolated_credentials_required'], preflight['blockers']
assert preflight['network_calls'] == 0 and not (HERE / 'must-not-exist').exists()
record = {'command': command, 'exit_code': result.returncode, 'ready_for_real': preflight['ready_for_real'],
          'blockers': preflight['blockers'], 'network_calls': 0, 'actual_api_spend_usd': '0',
          'ledger_opened': (ROOT / '.claude/pilot-real-budget.sqlite3').exists(),
          'authorization_sha256': sha256((HERE / 'authorization.json').read_bytes()).hexdigest(),
          'logs': {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ('preflight.stdout.json', 'preflight.stderr.log')}}
with (HERE / 'result.json').open('x', encoding='utf-8') as handle:
    handle.write(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: record[key] for key in ('exit_code', 'ready_for_real', 'blockers', 'network_calls', 'actual_api_spend_usd', 'ledger_opened')}))
