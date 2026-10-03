"""Extract the immutable reviewed code only; never copy local configuration or data."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
SHA = 'febc8aa9b303070e82e3f27626371d5b67cb73f7'
BASE = '6c78cd396eb72713e85b72d8592970e4b6b66585'
SNAPSHOT = EVIDENCE / 'snapshot'

def git(*args):
    return subprocess.check_output(['rtk', 'proxy', 'git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)

paths = git('ls-tree', '-r', '--name-only', SHA).decode().splitlines()
selected = [p for p in paths if (
    p.startswith(('regulai/front/', 'regulai/api/', 'regulai/regulai/', 'scripts/', 'ops/pilot/'))
    or p in {'regulai/manage.py', 'requirements.txt', 'regulai/requirements.txt'}
    or (p.startswith(('docs/evals/', 'evals/')) and '/reports/' not in p)
) and (Path(p).suffix in {'.py', '.html', '.txt', '.json', '.jsonl', '.ps1', '.conf', '.yaml', '.yml', '.md'} or Path(p).name == 'Dockerfile')
   and 'local_settings' not in p and '/migrations/__pycache__/' not in p]
records = []
for path in selected:
    dest = SNAPSHOT / path
    data = dest.read_bytes() if dest.exists() else git('show', SHA + ':' + path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    records.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
(EVIDENCE / 'snapshot-manifest.json').write_text(json.dumps({'commit': SHA, 'base': BASE, 'files': records}, indent=2), encoding='utf-8')
diff = git('diff', '--unified=6', BASE + '...' + SHA, '--', 'regulai', 'scripts', 'ops')
(EVIDENCE / 'reviewed.diff').write_bytes(diff)
print(f'Extracted {len(records)} tracked source/fixture files; no local settings or databases copied.')
print(f'Snapshot: {SNAPSHOT}')
