"""Independent spec-review execution on an immutable archive, without credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
name = sys.argv[1]
snapshot = 'packaging' if name.startswith('packaging') else 'closure' if name.startswith('closure') else 'source'
ROOT = HERE / snapshot
COMMIT = {'packaging': 'd63731a9c5dfda27c3dc504c295422502383d2f1',
    'closure': '0957df45362bc7cbf41c154bb13514d58901763a',
    'source': 'da836e308daf7e518fa4f27a7c04e426f46dcd45'}[snapshot]
PYTHON = HERE.parents[1] / '.venv' / 'Scripts' / 'python.exe'
ENV = os.environ.copy()
for environment_name in ('REGULAI_EVAL_GENERATOR_KEY', 'REGULAI_EVAL_JEV_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
    ENV.pop(environment_name, None)
ENV['PYTHONDONTWRITEBYTECODE'] = '1'
ENV['PYTHONIOENCODING'] = 'utf-8'
ENV['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
ENV['GIT_CEILING_DIRECTORIES'] = str(HERE)

commands = {
    'packaging-corpus': ['regulai/manage.py', 'test', 'front.test_document_fidelity.FrozenPilotCorpusTests',
        '--settings=regulai.test_settings', '--verbosity=2'],
    'closure-independent': [str(HERE / 'probe_driver.py'), 'closure', 'independent'],
    'closure-corpus-red': ['regulai/manage.py', 'test', 'front.test_document_fidelity.FrozenPilotCorpusTests',
        '--settings=regulai.test_settings', '--verbosity=2'],
    'closure-migration': ['regulai/manage.py', 'test', 'front.test_local_masking_integration.LocalMaskingMigrationTests',
        'front.test_onboarding_migrations', 'front.test_access', '--settings=regulai.test_settings', '--verbosity=2'],
    'focused': ['regulai/manage.py', 'test', 'front.test_local_masking', 'front.test_local_masking_integration',
        'front.test_evaluation_pilot', 'front.test_smoke', 'front.test_history_invariants',
        '--settings=regulai.test_settings', '--verbosity=2'],
    'local-focused': ['regulai/manage.py', 'test', 'front.test_local_masking', 'front.test_local_masking_integration',
        'front.test_evaluation_pilot', 'front.test_smoke', '--settings=regulai.test_settings', '--verbosity=2'],
    'corpus': ['scripts/evaluate_local_mask.py', '--output', str(HERE / 'detector-corpus')],
    'pilot': ['regulai/manage.py', 'smoke_ai', '--settings=regulai.test_settings', '--output', str(HERE / 'pilot-offline')],
    'human': ['regulai/manage.py', 'evaluate_ai', '--settings=regulai.test_settings', '--manifest',
        'evals/pilot-human/manifest.json', '--output', str(HERE / 'human-offline')],
    'preflight': ['regulai/manage.py', 'smoke_ai', '--settings=regulai.test_settings', '--preflight',
        '--authorization', 'evals/pilot-real/authorization.pending.json', '--output', str(HERE / 'unused-preflight')],
}
command = ['rtk', 'proxy', str(PYTHON), *commands[name]]
start = time.monotonic()
result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
log = HERE / f'{name}.log'
log.write_bytes(result.stdout)
record = {'commit': COMMIT,
    'baseline': '700389c216592db1e0c8725749bb4fd02cf3fa10', 'command': command,
    'cwd': str(ROOT), 'exit_code': result.returncode, 'duration_seconds': round(time.monotonic() - start, 3),
    'log': str(log), 'log_sha256': hashlib.sha256(result.stdout).hexdigest(),
    'archive_sha256': hashlib.sha256((HERE / f'{snapshot}.zip').read_bytes()).hexdigest()}
(HERE / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
print(result.stdout.decode('utf-8', errors='replace')[-4000:])
raise SystemExit(result.returncode)
