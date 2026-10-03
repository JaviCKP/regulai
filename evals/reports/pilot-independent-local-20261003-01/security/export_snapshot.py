import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COMMIT = 'c85d01963cc4e03a43162412f851e67139e602a6'
SNAPSHOT = HERE / 'snapshot'
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', COMMIT], cwd=ROOT, text=True).splitlines()
for name in paths:
    leaf = Path(name).name
    if leaf == 'local_settings.py' or leaf == '.env' or leaf.startswith('.env.') or leaf.endswith(('.sqlite3', '.pem', '.key')):
        raise SystemExit('Unsafe tracked archive member rejected: ' + name)
if SNAPSHOT.exists():
    raise SystemExit('Snapshot already exists; refusing overwrite')
archive = subprocess.check_output(['git', 'archive', '--format=tar', COMMIT], cwd=ROOT)
SNAPSHOT.mkdir(parents=True)
hashes = {}
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    for member in source.getmembers():
        target = (SNAPSHOT / member.name).resolve()
        if not target.is_relative_to(SNAPSHOT.resolve()):
            raise SystemExit('Unsafe archive path')
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.extractfile(member).read()
            target.write_bytes(data)
            hashes[member.name] = hashlib.sha256(data).hexdigest()
        else:
            raise SystemExit('Nonregular archive member rejected: ' + member.name)
manifest = {'commit': COMMIT, 'base': '700389c216592db1e0c8725749bb4fd02cf3fa10', 'archive_sha256': hashlib.sha256(archive).hexdigest(), 'files': hashes}
(HERE / 'snapshot-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'commit': COMMIT, 'file_count': len(hashes), 'archive_sha256': manifest['archive_sha256']}))
