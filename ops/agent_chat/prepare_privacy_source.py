"""Build a narrow candidate atop the running image, preserving unrelated code."""
import base64
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/privacy-20261017/real-source'
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
BASE = '2bfb930'
def git(*args):
    return subprocess.check_output(['rtk', 'proxy', 'git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)
def sources(ref):
    with tarfile.open(fileobj=io.BytesIO(git('archive',ref,'regulai'))) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()
                and Path(m.name).suffix not in {'.sqlite3','.db','.pem','.key'}
                and Path(m.name).name != 'local_settings.py' and not Path(m.name).name.startswith('.env')}
head, base = sources('HEAD'), sources(BASE)
paths = [p for p in head if '/test_' not in p and not p.endswith('privacy_test_settings.py')]
script = '''import base64,json
from pathlib import Path
paths = %r
print(json.dumps({p:base64.b64encode((Path('/app')/p).read_bytes()).decode() if (Path('/app')/p).is_file() else None for p in paths}))
''' % paths
r = subprocess.run([*SSH, 'sudo docker exec -i regulai-v2-web python -'], input=script.encode(), capture_output=True, check=True)
live = json.loads(r.stdout)
OUT.mkdir(exist_ok=True)
report = {'paths': {}, 'conflicts': [], 'merged': []}
for p in paths:
    candidate = head[p]
    baseline = base.get(p)
    current = base64.b64decode(live[p]) if live[p] is not None else None
    norm = lambda raw: raw.replace(b'\r\n', b'\n') if raw is not None else None
    if norm(current) == norm(candidate):
        continue
    if norm(candidate) == norm(baseline) and current is not None:
        continue
    if current is not None and norm(current) not in (norm(baseline), norm(candidate)):
        if baseline is None:
            raise RuntimeError('new_path_already_exists:' + p)
        scratch = OUT / 'merge'
        scratch.mkdir(exist_ok=True)
        for name, data in [('current',current),('base',baseline),('candidate',candidate)]:
            (scratch/name).write_bytes(norm(data))
        merged = subprocess.run(['rtk','proxy','git','merge-file','-p',str(scratch/'current'),str(scratch/'base'),str(scratch/'candidate')], capture_output=True)
        candidate = merged.stdout
        report['merged'].append(p)
        if merged.returncode:
            report['conflicts'].append(p)
    target = OUT / 'source' / p
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(candidate)
    report['paths'][p] = {'sha256':hashlib.sha256(candidate).hexdigest(), 'live_sha256':hashlib.sha256(current).hexdigest() if current is not None else None}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'files':len(paths),'merged':report['merged'],'conflicts':report['conflicts']},indent=2))
