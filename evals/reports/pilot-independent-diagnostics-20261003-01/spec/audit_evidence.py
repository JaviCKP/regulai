import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

base = subprocess.run(['rtk', 'proxy', 'git', 'rev-parse', '535eb9d'], cwd=REPO,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode().strip()
fixed = '972edb88c82a5220a43ffcc89316a9f9033e82f7'
command = ['rtk', 'proxy', 'git', 'diff', '--no-ext-diff', base, fixed]
diff = subprocess.run(command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
(HERE / 'reviewed.diff').write_bytes(diff.stdout)
unchanged_command = ['rtk', 'proxy', 'git', 'diff', '--exit-code', base, fixed, '--', 'evals', 'docs',
    'regulai/front/jev.py', 'regulai/front/evaluation_budget.py', 'regulai/front/policy.py',
    'regulai/front/routing.py', 'regulai/front/classification.py', 'regulai/front/verification.py']
unchanged = subprocess.run(unchanged_command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assert unchanged.returncode == 0 and not unchanged.stdout
before, after = read(HERE / 'base-behavior.json'), read(HERE / 'source-behavior.json')
assert before == after and len(before) == 11
record = {'axis': 'Spec', 'fixed_commit': fixed, 'baseline_commit': base,
    'findings': [], 'product_changes_by_reviewer': [],
    'diff': {'command': command, 'exit_code': diff.returncode, 'sha256': sha(HERE / 'reviewed.diff')},
    'unchanged_controls_and_historical_evidence': {'command': unchanged_command, 'exit_code': unchanged.returncode},
    'fresh_runs': [read(HERE / 'base.json'), read(HERE / 'source.json')],
    'behavior_comparison': {'cases': 11, 'equal': before == after,
        'excluded_receipt_keys': ['duration_ms', 'provider_error_code'],
        'public_error_text': 'Expected intentional correction; reviewed statically, excluded from behavioral projection.',
        'base_sha256': sha(HERE / 'base-behavior.json'), 'source_sha256': sha(HERE / 'source-behavior.json')},
    'source_sha256': {snapshot: {name: sha(HERE / snapshot / name) for name in
        ('regulai/front/chat_service.py', 'regulai/front/evaluation.py', 'regulai/front/evaluation_budget.py',
         'regulai/front/jev.py', 'regulai/front/policy.py', 'regulai/front/routing.py')}
        for snapshot in ('base', 'source')},
    'limits': {'bridge_executed': False, 'user_database_or_credentials_read': False,
        'persistent_ledger_opened': False, 'ledger_observer': 'in-memory mock only',
        'real_product_calls': 0, 'api_spend_usd': '0', 'historical_failure_cause': 'unknown, not inferred',
        'historical_evidence_changed': False, 'tests_reported_by_other_agents_repeated': False},
    'evidence_sha256': {path.name: sha(path) for path in sorted(HERE.iterdir())
        if path.is_file() and path.suffix != '.zip' and path.name not in {'evidence.json', 'package-files.json'}},
}
(HERE / 'evidence.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
package = [path.name for path in sorted(HERE.iterdir()) if path.is_file() and path.suffix != '.zip'
    and path.name != 'package-files.json']
(HERE / 'package-files.json').write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'report': str(HERE / 'Spec-review.md'), 'evidence': str(HERE / 'evidence.json'),
    'sha256': sha(HERE / 'evidence.json'), 'findings': 0, 'compared_cases': len(before),
    'public_package_files': len(package)}, indent=2))
