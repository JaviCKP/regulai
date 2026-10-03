import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'source'
REPO = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

fixed = '698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc'
base = subprocess.run(['rtk', 'proxy', 'git', 'rev-parse', '6668db4'], cwd=REPO,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode().strip()
diff_command = ['rtk', 'proxy', 'git', 'diff', '--no-ext-diff', base, fixed]
diff = subprocess.run(diff_command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
(HERE / 'reviewed.diff').write_bytes(diff.stdout)
unchanged_paths = ['evals/pilot-real/cases.jsonl', 'evals/pilot-real/rubric.md', 'evals/pilot-human',
    'regulai/front/chat_service.py', 'regulai/front/evaluation_budget.py', 'regulai/front/jev.py',
    'regulai/front/classification.py', 'regulai/front/verification.py']
unchanged_command = ['rtk', 'proxy', 'git', 'diff', '--exit-code', base, fixed, '--', *unchanged_paths]
unchanged = subprocess.run(unchanged_command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assert unchanged.returncode == 0 and not unchanged.stdout
manifest_paths = ['evals/pilot-real/manifest-vercel.json',
    'evals/reports/pilot-real-vercel-20261003-01/manifest.json',
    'evals/reports/pilot-real-vercel-20261003-01/authorization.json',
    'evals/reports/pilot-real-vercel-20261003-01/preparation.json',
    'evals/reports/pilot-real-vercel-20261003-01/run_authorized.py',
    'evals/reports/pilot-real-vercel-20261003-01/prepare.py',
    'evals/pilot-real/cases.jsonl', 'evals/pilot-real/rubric.md']
matrix = read(HERE / 'tuple-matrix.json')
evidence = {'axis': 'Spec', 'fixed_commit': fixed, 'baseline_commit': base,
    'product_changes_by_reviewer': [], 'findings': [],
    'archive_sha256': sha(HERE / 'source.zip'),
    'diff_command': diff_command, 'diff_exit_code': diff.returncode, 'diff_sha256': sha(HERE / 'reviewed.diff'),
    'unchanged_control_files': {'command': unchanged_command, 'exit_code': unchanged.returncode},
    'manifest_and_bridge_sha256': {name: sha(ROOT / name) for name in manifest_paths},
    'source_sha256': {path.relative_to(ROOT).as_posix(): sha(path)
        for path in sorted((ROOT / 'regulai/front').rglob('*.py'))},
    'executions': [read(HERE / 'independent.json'), read(HERE / 'regression.json')],
    'fresh_test_counts': {'independent_suite': 10, 'own_probes': 6, 'repository_new_tests': 4, 'regression_suite': 21},
    'tuple_matrix': {'cases': len(matrix), 'accepted': sum(row['ready'] for row in matrix),
        'rejected': sum(not row['ready'] for row in matrix)},
    'human_bank_blockers': read(HERE / 'human-bank-denied.json')['blockers'],
    'timeout_exposure_usd': read(HERE / 'timeout-ledger.json')['budget_exposure_usd'],
    'limits': {'bridge_executed': False, 'user_database_or_keys_read': False, 'real_product_calls': 0,
        'api_spend_usd': '0', 'human_participants': 0, 'database': 'isolated SQLite test databases only',
        'live_provider_quality_or_availability_validated': False},
    'evidence_sha256': {path.name: sha(path) for path in sorted(HERE.iterdir())
        if path.is_file() and path.name not in {'evidence.json', 'package-files.json'} and path.suffix != '.zip'},
}
output = HERE / 'evidence.json'
output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
package = [path.name for path in sorted(HERE.iterdir()) if path.is_file() and path.suffix != '.zip'
    and path.name != 'package-files.json']
(HERE / 'package-files.json').write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'report': str(HERE / 'Spec-review.md'), 'evidence': str(output), 'sha256': sha(output),
    'findings': 0, 'fresh_tests': 31, 'package_files': len(package)}, indent=2))
