"""Export a separate fixed correction and copy independent review cases."""
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
target = HERE / ('followup-' + commit[:7])
if target.exists():
    raise SystemExit('Followup directory already exists')
names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit], cwd=ROOT, text=True).splitlines()
for name in names:
    leaf = Path(name).name
    if leaf == 'local_settings.py' or leaf == '.env' or leaf.startswith('.env.') or leaf.endswith(('.sqlite3', '.pem', '.key')):
        raise SystemExit('Rejected unsafe archive member: ' + name)
archive = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
snapshot = target / 'snapshot'
snapshot.mkdir(parents=True)
hashes = {}
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    for member in source.getmembers():
        destination = (snapshot / member.name).resolve()
        if not destination.is_relative_to(snapshot.resolve()):
            raise SystemExit('Unsafe archive path')
        if member.isdir():
            destination.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.extractfile(member).read()
            destination.write_bytes(data)
            hashes[member.name] = hashlib.sha256(data).hexdigest()
        else:
            raise SystemExit('Nonregular archive member')
manifest = {'commit': commit, 'base': 'c85d01963cc4e03a43162412f851e67139e602a6',
            'archive_sha256': hashlib.sha256(archive).hexdigest(), 'files': hashes}
(target / 'snapshot-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
for name in ('review_checks.py', 'supplemental_checks.py', 'bounded_workload.py', 'rollback_check.py', 'audit_snapshot.py'):
    (target / name).write_bytes((HERE / name).read_bytes())
runner = (HERE / 'run_review.py').read_text(encoding='utf-8').replace("'c85d01963cc4e03a43162412f851e67139e602a6'", repr(commit))
(target / 'run_review.py').write_text(runner, encoding='utf-8')
print(json.dumps({'commit': commit, 'files': len(hashes), 'archive_sha256': manifest['archive_sha256'], 'target': str(target)}))
