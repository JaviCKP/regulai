"""Run only on the exported candidate and memory SQLite; block real network."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'snapshot'
sys.path.insert(0, str(SNAPSHOT / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.chdir(SNAPSHOT)
arguments = sys.argv[1:]
explicit_name = None
if arguments and arguments[0] == '--run-name':
    explicit_name = arguments[1]
    arguments = arguments[2:]
labels = arguments or ['review_checks']
name = explicit_name or ('independent' if labels == ['review_checks'] else 'candidate-tests')
assert name.replace('-', '').replace('_', '').isalnum()
if (HERE / f'{name}-result.json').exists():
    raise SystemExit('Refusing to overwrite an existing run result: ' + name)
started = time.monotonic()
guards = []
with ExitStack() as stack, (HERE / f'{name}.log').open('w', encoding='utf-8') as output:
    for method in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection', 'socket.getaddrinfo', 'socket.socket.sendto'):
        guards.append((method, stack.enter_context(patch(method, side_effect=AssertionError('Real network forbidden in security review')))))
    with redirect_stdout(output), redirect_stderr(output):
        import django
        django.setup()
        from django.conf import settings
        assert settings.DATABASES['default']['NAME'] == ':memory:'
        from front.local_masking import detector_metadata
        identity = detector_metadata()
        from django.test.runner import DiscoverRunner
        failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(labels)
    result = {'commit': 'be29b6fd084159dd93e88d835e67438cd8a5ab7a', 'labels': labels,
              'failures': failures, 'elapsed_seconds': round(time.monotonic() - started, 3),
              'model': identity, 'network_attempts': {method: guard.call_count for method, guard in guards},
              'database': 'isolated memory SQLite', 'log_sha256': hashlib.sha256((HERE / f'{name}.log').read_bytes()).hexdigest()}
(HERE / f'{name}-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
sys.exit(bool(failures))
