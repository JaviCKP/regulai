"""Run immutable red/green evidence with synthetic SQLite and blocked networking."""
import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = ('regulai/front/chat_service.py', 'regulai/front/classification.py',
           'regulai/front/verification.py', 'regulai/front/test_semantic_threshold_boundary.py')
PROTECTED = ('evals/adversarial/community-20261003',
             'evals/adversarial-live/community-20261003-02',
             'evals/adversarial-live/community-additional-20261003',
             'evals/reports/adversarial-real-20261003-01/live-run-01',
             'evals/reports/adversarial-real-20261003-02/live-run-01')
GUARDS = ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
          'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyname_ex',
          'socket.gethostbyaddr', 'socket.socket.send', 'socket.socket.sendall',
          'socket.socket.sendto', 'requests.sessions.Session.request', 'httpx.Client.send')


def hashes(paths):
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('red', 'green', 'focused'))
    args = parser.parse_args()
    paths = [HERE / f'{args.phase}.{suffix}' for suffix in ('stdout.log', 'stderr.log', 'json')]
    if any(path.exists() for path in paths):
        raise FileExistsError('Evidence already exists; never overwrite a run.')
    protected = [path for relative in PROTECTED for path in (ROOT / relative).rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts]
    before = hashes(protected)
    source_hashes = hashes([ROOT / path for path in SOURCES])
    sys.path.insert(0, str(ROOT / 'regulai'))
    sys.modules['regulai.local_settings'] = ModuleType('regulai.local_settings')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
    os.environ['OPENAI_API_KEY'] = ''
    os.environ['ANTHROPIC_API_KEY'] = ''
    opened_databases = []
    original_connect = sqlite3.connect

    def memory_connect(database, *positional, **kwargs):
        name = str(database)
        if not (name == ':memory:' or name.startswith('file:memorydb_') and 'mode=memory' in name):
            raise AssertionError('Only synthetic in-memory SQLite is allowed: ' + name)
        opened_databases.append(name)
        return original_connect(database, *positional, **kwargs)

    stdout, stderr = io.StringIO(), io.StringIO()
    with ExitStack() as stack, TemporaryDirectory(prefix='semantic-threshold-') as media:
        guards = {name: stack.enter_context(patch(name, side_effect=AssertionError(
            'Real network is forbidden in this regression'))) for name in GUARDS}
        stack.enter_context(patch('sqlite3.connect', side_effect=memory_connect))
        stack.enter_context(patch('sqlite3.dbapi2.connect', side_effect=memory_connect))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            import django
            django.setup()
            from django.conf import settings
            from django.test import override_settings
            from django.test.runner import DiscoverRunner
            assert settings.DATABASES['default']['NAME'] == ':memory:'
            labels = ['front.test_semantic_threshold_boundary']
            if args.phase == 'focused':
                labels += ['front.test_classification', 'front.test_verification',
                           'front.test_verification_flow', 'front.test_verification_judge',
                           'front.test_pipeline', 'front.test_pipeline_privacy']
            with override_settings(MEDIA_ROOT=media):
                failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(labels)
        attempts = {name: guard.call_count for name, guard in guards.items()}
    assert before == hashes(protected), 'Frozen input/evidence changed during regression'
    assert not any(attempts.values()), attempts
    record = {'phase': args.phase, 'command': ['rtk', 'proxy', sys.executable, str(Path(__file__).resolve()), args.phase],
              'test_labels': labels, 'exit_code': int(bool(failures)), 'failures': failures,
              'source_sha256': source_hashes, 'protected_sha256': before,
              'frozen_inputs_unchanged': True, 'private_local_settings_intercepted': True,
              'database_connections': opened_databases, 'real_ledger_opened': False,
              'network_attempts': attempts, 'real_api_calls': 0,
              'scope': 'Synthetic boundary regression; no new model-quality measurement.'}
    for path, content in zip(paths[:2], (stdout.getvalue(), stderr.getvalue())):
        with path.open('xb') as stream:
            stream.write(content.encode('utf-8'))
    record['log_sha256'] = hashes(paths[:2])
    with paths[2].open('xb') as stream:
        stream.write((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: record[key] for key in ('phase', 'exit_code', 'failures',
        'frozen_inputs_unchanged', 'database_connections', 'network_attempts', 'real_api_calls')}))
    print(stderr.getvalue())
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
