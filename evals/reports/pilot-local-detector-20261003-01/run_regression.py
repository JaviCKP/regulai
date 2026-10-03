"""Record local detector regression commands without changing previous evidence."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
name, *labels = sys.argv[1:]
log, metadata = HERE / (name + '.log'), HERE / (name + '.json')
if log.exists() or metadata.exists():
    raise SystemExit('Evidence already exists; choose a new execution name.')
command = ['rtk', 'proxy', sys.executable, 'regulai/manage.py', 'test', *labels,
           '--settings=regulai.test_settings']
started = time.monotonic()
result = subprocess.run(command, cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace')
log.write_text(result.stdout + result.stderr, encoding='utf-8')
metadata.write_text(json.dumps({'command': command, 'exit_code': result.returncode,
    'finished_utc': datetime.now(timezone.utc).isoformat(), 'seconds': round(time.monotonic() - started, 3),
    'log_sha256': sha256(log.read_bytes()).hexdigest(),
    'source_sha256': {rel: sha256((ROOT / rel).read_bytes()).hexdigest()
        for rel in ('regulai/front/local_masking.py', 'regulai/front/test_local_masking.py', 'requirements.txt')}}, indent=2), encoding='utf-8')
print(f'{name}: exit {result.returncode}; log: {log}')
raise SystemExit(result.returncode)
