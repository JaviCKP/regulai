from pathlib import Path
import hashlib
import json
import subprocess

EVIDENCE = Path(__file__).resolve().parent
INITIAL = EVIDENCE.parent
ROOT = INITIAL.parents[1]
BASE = 'febc8aa9b303070e82e3f27626371d5b67cb73f7'
SHA = '700389c216592db1e0c8725749bb4fd02cf3fa10'

def git(*args):
    return subprocess.check_output(['rtk', 'proxy', 'git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)

changed = set(git('diff', '--name-only', BASE + '...' + SHA).decode().splitlines())
paths = git('ls-tree', '-r', '--name-only', SHA).decode().splitlines()
selected = [p for p in paths if (
    p.startswith(('regulai/front/', 'regulai/api/', 'regulai/regulai/', 'scripts/', 'ops/pilot/'))
    or p in {'regulai/manage.py', 'requirements.txt', 'regulai/requirements.txt'}
    or (p.startswith(('docs/evals/', 'evals/')) and '/reports/' not in p)
) and (Path(p).suffix in {'.py', '.html', '.txt', '.json', '.jsonl', '.ps1', '.conf', '.yaml', '.yml', '.md'}
       or Path(p).name == 'Dockerfile') and 'local_settings' not in p]
original = {row['path']: row['sha256'] for row in json.loads((INITIAL / 'snapshot-manifest.json').read_text(encoding='utf-8'))['files']}
records = []
for path in selected:
    if path not in changed and path in original:
        data = (INITIAL / 'snapshot' / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == original[path]
    else:
        data = git('show', SHA + ':' + path)
    dest = EVIDENCE / 'snapshot' / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    records.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
(EVIDENCE / 'snapshot-manifest.json').write_text(json.dumps({'commit': SHA, 'base': BASE, 'files': records}, indent=2), encoding='utf-8')
(EVIDENCE / 'reviewed.diff').write_bytes(git('diff', '--unified=6', BASE + '...' + SHA, '--', 'regulai', 'scripts', 'ops'))
for script in ('run_tests.py', 'review_cases.py'):
    source = (INITIAL / script).read_text(encoding='utf-8')
    if script == 'run_tests.py':
        source = source.replace(BASE, SHA)
    (EVIDENCE / script).write_text(source, encoding='utf-8')
print(json.dumps({'commit': SHA, 'snapshot_files': len(records), 'changed_runtime': sorted(p for p in changed if p.startswith(('regulai/', 'scripts/', 'ops/')))}, indent=2))
