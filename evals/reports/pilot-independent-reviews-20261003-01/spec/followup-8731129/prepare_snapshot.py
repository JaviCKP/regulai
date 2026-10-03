"""Pinned review copy; never copies private settings, environment files or databases."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tarfile

SHA = '87311294631d9ffdf6b76ccf3fcb9140018a0977'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'candidate'
OUT.mkdir(exist_ok=False)

def git(*arguments):
    return subprocess.check_output(['rtk', 'proxy', 'git', *arguments], cwd=ROOT, stderr=subprocess.DEVNULL)

names = git('ls-tree', '-r', '--name-only', SHA, '--', 'regulai', 'evals/pilot-real',
            'evals/pilot-human', 'requirements.txt', 'docs/plan-blackhat/README.md',
            'docs/plan-blackhat/arranque-y-demo.md', 'docs/plan-blackhat/estado-ejecucion.md',
            'docs/plan-blackhat/informe-correcciones-community.md').decode().splitlines()
names = [name for name in names if Path(name).name != 'local_settings.py'
         and not Path(name).name.startswith('.env')
         and Path(name).suffix in ('.py', '.html', '.json', '.jsonl', '.md', '.txt')]
hashes = {}
with tarfile.open(fileobj=BytesIO(git('archive', SHA, '--', *names))) as archive:
    for member in archive:
        if not member.isfile() or member.name not in names:
            continue
        target = OUT / member.name
        assert target.resolve().is_relative_to(OUT.resolve())
        data = archive.extractfile(member).read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[member.name] = sha256(data).hexdigest()
(HERE / 'snapshot.json').write_text(json.dumps({'commit': SHA, 'files': hashes}, indent=2), encoding='utf-8')
print(json.dumps({'commit': SHA, 'files': len(hashes), 'private_settings_copied': False}))
