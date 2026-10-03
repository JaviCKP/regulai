"""Synthetic tests only; never import the credential bridge or use its settings."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
short, name, *labels = sys.argv[1:]
manifest = json.loads((HERE / ('snapshot-' + short + '.json')).read_text(encoding='utf-8'))
snapshot = HERE / manifest['snapshot']
if (HERE / (name + '.json')).exists():
    raise SystemExit('Evidence name already exists')
sys.path.insert(0, str(snapshot / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.chdir(snapshot)
started = time.monotonic()
guards = []
with ExitStack() as stack, (HERE / (name + '.log')).open('w', encoding='utf-8') as output:
    for method in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection', 'socket.getaddrinfo', 'socket.socket.sendto'):
        guards.append((method, stack.enter_context(patch(method, side_effect=AssertionError('Review forbids live network')))))
    with redirect_stdout(output), redirect_stderr(output):
        import django
        django.setup()
        from django.conf import settings
        assert settings.DATABASES['default']['NAME'] == ':memory:'
        from django.test.runner import DiscoverRunner
        failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(labels)
    result = {'commit': manifest['commit'], 'labels': labels, 'failures': failures,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'network_attempts': {method: guard.call_count for method, guard in guards},
        'database': 'ephemeral synthetic SQLite', 'bridge_executed': False,
        'log_sha256': hashlib.sha256((HERE / (name + '.log')).read_bytes()).hexdigest()}
(HERE / (name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
raise SystemExit(bool(failures))
