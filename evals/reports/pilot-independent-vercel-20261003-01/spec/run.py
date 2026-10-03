import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'source'
PYTHON = HERE.parents[1] / '.venv/Scripts/python.exe'
env = os.environ.copy()
for key in ('REGULAI_EVAL_GENERATOR_KEY', 'REGULAI_EVAL_JEV_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
    env.pop(key, None)
env.update(DJANGO_SETTINGS_MODULE='regulai.test_settings', PYTHONDONTWRITEBYTECODE='1',
    PYTHONIOENCODING='utf-8', GIT_CEILING_DIRECTORIES=str(HERE))
name = sys.argv[1]
commands = {'independent': [str(HERE / 'probe_driver.py')],
    'regression': ['regulai/manage.py', 'test', 'front.test_smoke', 'front.test_evaluation_budget',
        '--settings=regulai.test_settings', '--verbosity=2']}
command = ['rtk', 'proxy', str(PYTHON), *commands[name]]
started = time.monotonic()
result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(HERE / (name + '.log')).write_bytes(result.stdout)
record = {'commit': '698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc', 'baseline': '6668db4',
    'command': command, 'cwd': str(ROOT), 'exit_code': result.returncode,
    'duration_seconds': round(time.monotonic() - started, 3),
    'archive_sha256': hashlib.sha256((HERE / 'source.zip').read_bytes()).hexdigest(),
    'log_sha256': hashlib.sha256(result.stdout).hexdigest()}
(HERE / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
print(result.stdout.decode('utf-8', errors='replace')[-5000:])
raise SystemExit(result.returncode)
