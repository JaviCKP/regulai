"""Reopen only B's known synthetic browser04 database for a visual followup.

No migrate, seed or reset. The historical completed request is preserved.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT / '.claude' / 'pilot-document-browser-20261003-04'
database = WORKSPACE / 'pilot.sqlite3'
metadata = json.loads((WORKSPACE / 'run.json').read_text(encoding='utf-8'))
assert database.is_file() and not database.is_symlink()
assert Path(metadata['database']).resolve() == database.resolve()
assert WORKSPACE.resolve().is_relative_to((ROOT / '.claude').resolve())
sys.path.insert(0, str(ROOT / 'regulai'))
from django.conf import settings
from regulai import test_settings
values = {key: getattr(test_settings, key) for key in dir(test_settings) if key.isupper()}
values.update(DEBUG=True, DEMO_MODE=True,
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': database}},
    MEDIA_ROOT=WORKSPACE / 'media', ALLOW_REGISTRATION=False,
    SESSION_COOKIE_NAME='pilot_ui_followup_session', CSRF_COOKIE_NAME='pilot_ui_followup_csrf',
    SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, SECURE_SSL_REDIRECT=False,
    CORS_ALLOW_ALL_ORIGINS=False, CORS_ALLOWED_ORIGINS=['http://127.0.0.1:8769'])
values['TEMPLATES'] = deepcopy(values['TEMPLATES'])
values['TEMPLATES'][0]['OPTIONS']['context_processors'].append('regulai.demo_settings.demo_context')
settings.configure(**values)
import django
django.setup()
from django.core.management import call_command
from front.models import Prompt
from front.management.commands import run_demo
request = Prompt.objects.get(request_id='e7c85964-6e98-4fcd-86dc-daa86d669dc0',
    status='completed', user__username='community-demo', company__name='Community offline demo')
assert request.decision['consent_reason'] == 'consent_expired'
assert request.file_sha256 == '38c43302be0249621eea168e77532edd326d9d8ae8e70e3bfd7a3fd9bd1ed315'
report = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
    'database': str(database), 'listen': '127.0.0.1:8769',
    'source_state': 'working tree after a3bc67b25b341cb28172bebd5001ef48c5b8d34f',
    'reconstruction': False, 'historical_request_id': str(request.request_id),
    'migrate_seed_or_reset': False,
    'sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in [
        'regulai/front/templates/chat/chat.html', 'regulai/front/test_frontend_chat.py',
        'regulai/front/chat_service.py', 'regulai/front/management/commands/run_demo.py',
        'regulai/front/management/commands/evaluate_ai.py',
        'evals/reports/pilot-ui-followup-20261003-01/browser-runner.py']}}
output = Path(__file__).with_name('browser-environment.json')
with output.open('x', encoding='utf-8') as stream:
    stream.write(json.dumps(report, indent=2) + '\n')
with patch.object(run_demo, 'DEMO_DATABASE', database), run_demo.offline_demo():
    print('Offline visual followup: http://127.0.0.1:8769/login/', flush=True)
    call_command('runserver', addrport='127.0.0.1:8769', use_reloader=False, use_threading=True)
