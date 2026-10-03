"""Launch probes with a constructed environment; never copies or inspects caller env."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OWN = Path(__file__).resolve().parent
(OWN / 'tmp').mkdir(exist_ok=True)
mode = sys.argv[1]
(OWN / ('followup' if mode == 'extension-fixed' else 'source') / 'regulai/regulai/local_settings.py').write_bytes(b'')
python = Path(sys.executable).resolve()
env = {
    'SystemRoot': r'C:\Windows', 'WINDIR': r'C:\Windows',
    'PATH': str(python.parent) + r';C:\Users\javi\.local\bin;C:\Windows\System32',
    'TEMP': str(OWN / 'tmp'), 'TMP': str(OWN / 'tmp'),
    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
    'DJANGO_SETTINGS_MODULE': 'regulai.test_settings',
    'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '',
    'REGULAI_EVAL_GENERATOR_KEY': '', 'REGULAI_EVAL_JEV_KEY': '',
    'GIT_CEILING_DIRECTORIES': str(OWN),
}
args = [str(python), '-B', str(OWN / 'driver.py'), mode]
started = time.monotonic()
process = subprocess.run(args, cwd=OWN, env=env, capture_output=True, text=True, encoding='utf-8')
log = process.stdout + process.stderr
(OWN / (mode + '.log')).write_text(log, encoding='utf-8')
record = {'command': 'rtk proxy .venv\\Scripts\\python.exe -B .claude\\adversarial-independent-review\\run.py ' + mode,
    'child_command': args, 'exit_code': process.returncode, 'seconds': round(time.monotonic() - started, 3),
    'source_commit': '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2' if mode == 'extension-fixed' else 'df91ea1dacbe1662d392bfd91417d32a0e46abe6',
    'log_sha256': hashlib.sha256((OWN / (mode + '.log')).read_bytes()).hexdigest(),
    'environment_constructed_without_reading_caller': True, 'private_settings_intercepted': True}
(OWN / (mode + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
print(log[-18000:])
raise SystemExit(process.returncode)
