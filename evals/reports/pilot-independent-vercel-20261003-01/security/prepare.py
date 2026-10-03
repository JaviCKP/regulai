"""Export a fixed source candidate; refuse private configuration and DB files."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
commit = subprocess.check_output(['git', 'rev-parse', '--verify', sys.argv[1] + '^{commit}'], cwd=ROOT, text=True).strip()
names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit], cwd=ROOT, text=True).splitlines()
for name in names:
    leaf = Path(name).name
    if leaf == 'local_settings.py' or leaf == '.env' or leaf.startswith('.env.') or leaf.endswith(('.sqlite3', '.pem', '.key')):
        raise SystemExit('Rejected private archive member: ' + name)
snapshot = HERE / ('snapshot-' + commit[:7])
if snapshot.exists():
    raise SystemExit('Refusing to overwrite a snapshot')
archive = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
snapshot.mkdir()
hashes = {}
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    for member in source.getmembers():
        path = (snapshot / member.name).resolve()
        if not path.is_relative_to(snapshot.resolve()):
            raise SystemExit('Invalid archive path')
        if member.isdir():
            path.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            path.parent.mkdir(parents=True, exist_ok=True)
            value = source.extractfile(member).read()
            path.write_bytes(value)
            hashes[member.name] = hashlib.sha256(value).hexdigest()
        else:
            raise SystemExit('Invalid archive member')
manifest = {'commit': commit, 'snapshot': snapshot.name, 'files': hashes,
            'archive_sha256': hashlib.sha256(archive).hexdigest()}
(HERE / ('snapshot-' + commit[:7] + '.json')).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'commit': commit, 'files': len(hashes), 'archive_sha256': manifest['archive_sha256']}))
