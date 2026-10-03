import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PYTHON = HERE.parents[1] / '.venv/Scripts/python.exe'
snapshot = sys.argv[1]
env = os.environ.copy()
for key in ('REGULAI_EVAL_GENERATOR_KEY', 'REGULAI_EVAL_JEV_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
    env.pop(key, None)
env.update(DJANGO_SETTINGS_MODULE='regulai.test_settings', PYTHONDONTWRITEBYTECODE='1',
    PYTHONIOENCODING='utf-8', GIT_CEILING_DIRECTORIES=str(HERE))
command = ['rtk', 'proxy', str(PYTHON), str(HERE / 'probe_driver.py'), snapshot]
started = time.monotonic()
result = subprocess.run(command, cwd=HERE / snapshot, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(HERE / (snapshot + '.log')).write_bytes(result.stdout)
record = {'snapshot': snapshot, 'commit': '972edb88c82a5220a43ffcc89316a9f9033e82f7' if snapshot == 'source' else '535eb9d',
    'command': command, 'cwd': str(HERE / snapshot), 'exit_code': result.returncode,
    'duration_seconds': round(time.monotonic() - started, 3),
    'archive_sha256': hashlib.sha256((HERE / (snapshot + '.zip')).read_bytes()).hexdigest(),
    'log_sha256': hashlib.sha256(result.stdout).hexdigest()}
(HERE / (snapshot + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
print(result.stdout.decode('utf-8', errors='replace')[-5000:])
raise SystemExit(result.returncode)
