"""Copy only reviewable tracked source from the pinned commit into this scratch."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

SHA = 'c1e3a360e7ba3051bb8f0bda487b005dd29834a0'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'candidate'
OUT.mkdir(exist_ok=False)

def git(*arguments):
    return subprocess.check_output(['rtk', 'proxy', 'git', *arguments], cwd=ROOT, stderr=subprocess.DEVNULL)

names = git('ls-tree', '-r', '--name-only', SHA, '--', 'regulai', 'evals/pilot-real',
            'evals/pilot-human', 'requirements.txt').decode().splitlines()
hashes = {}
for name in names:
    relative = Path(name)
    if (relative.name == 'local_settings.py' or relative.name.startswith('.env')
            or relative.suffix not in ('.py', '.html', '.json', '.jsonl', '.md', '.txt')):
        continue
    data = git('show', SHA + ':' + name)
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    hashes[name] = sha256(data).hexdigest()
(HERE / 'snapshot.json').write_text(json.dumps({'commit': SHA, 'files': hashes}, indent=2), encoding='utf-8')
print(json.dumps({'commit': SHA, 'files': len(hashes), 'private_settings_copied': False}))
