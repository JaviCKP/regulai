"""Independent review runner: immutable snapshot, in-memory DB and no real sockets."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
import json
import os
import sys
import tempfile
import time
from unittest.mock import patch

EVIDENCE = Path(__file__).resolve().parent
SNAPSHOT = EVIDENCE / 'snapshot'
os.chdir(SNAPSHOT / 'regulai')
sys.path.insert(0, str(SNAPSHOT / 'regulai'))
sys.dont_write_bytecode = True
(EVIDENCE / 'tmp').mkdir(exist_ok=True)
tempfile.tempdir = str(EVIDENCE / 'tmp')
os.environ.update(DJANGO_SETTINGS_MODULE='regulai.test_settings',
    OPENAI_API_KEY='synthetic-review-only', REGULAI_EVAL_GENERATOR_KEY='synthetic-review-only',
    REGULAI_EVAL_JEV_KEY='synthetic-review-only', PYTHONDONTWRITEBYTECODE='1')

run_name = sys.argv[1]
labels = sys.argv[2:]
log = EVIDENCE / (run_name + '.log')
started = time.monotonic()
with log.open('w', encoding='utf-8') as stream, redirect_stdout(stream), redirect_stderr(stream), ExitStack() as stack:
    stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Independent security review forbids live sockets')))
    stack.enter_context(patch('socket.socket.connect_ex', side_effect=AssertionError('Independent security review forbids live sockets')))
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    assert settings.SETTINGS_MODULE == 'regulai.test_settings'
    assert connection.settings_dict['NAME'] == ':memory:'
    assert not (SNAPSHOT / 'regulai/regulai/local_settings.py').exists()
    settings.STATICFILES_DIRS = []
    from django.test.runner import DiscoverRunner
    failed = DiscoverRunner(verbosity=2, interactive=False).run_tests(labels)
result = {'commit': '700389c216592db1e0c8725749bb4fd02cf3fa10', 'labels': labels,
    'exit_code': bool(failed), 'failure_count': failed, 'elapsed_seconds': round(time.monotonic() - started, 3),
    'database': 'isolated in-memory SQLite', 'sockets': 'blocked', 'log': str(log)}
(EVIDENCE / (run_name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-7:]))
sys.exit(bool(failed))
