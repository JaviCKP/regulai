"""Record one immutable synthetic probe; refuse result/log replacement."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
name = sys.argv[1]
assert name in {'red', 'green'}
assert not any((HERE / f'{name}-{suffix}').exists() for suffix in ('probe.log', 'result.json', 'observations.json'))
sys.path.insert(0, str(ROOT / 'regulai'))
sys.path.insert(0, str(HERE))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
started = time.monotonic()
guards = []
with ExitStack() as stack, (HERE / f'{name}-probe.log').open('x', encoding='utf-8') as log:
    for method in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                   'socket.getaddrinfo', 'socket.socket.sendto'):
        guards.append((method, stack.enter_context(patch(method, side_effect=AssertionError('Live network forbidden')))))
    with redirect_stdout(log), redirect_stderr(log):
        import django
        django.setup()
        from django.conf import settings
        from django.test.runner import DiscoverRunner
        assert settings.DATABASES['default']['NAME'] == ':memory:'
        import legacy_probe
        legacy_probe.OBSERVATIONS = HERE / f'{name}-observations.json'
        failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(['legacy_probe.LegacyRollbackTests'])
result = {'failures': failures, 'elapsed_seconds': round(time.monotonic() - started, 3),
    'database': 'isolated memory SQLite', 'network_attempts': {method: guard.call_count for method, guard in guards},
    'log_sha256': hashlib.sha256((HERE / f'{name}-probe.log').read_bytes()).hexdigest()}
with (HERE / f'{name}-result.json').open('x', encoding='utf-8') as output:
    output.write(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
sys.exit(bool(failures))
