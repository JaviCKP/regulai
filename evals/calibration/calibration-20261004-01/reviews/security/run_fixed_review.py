"""Independent fixed-commit security review; synthetic and network-disabled."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import types
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]


def prepare(commit):
    root = HERE / ('snapshot-' + commit)
    if root.exists():
        return root
    command = ['rtk', 'proxy', 'git', 'archive', commit, 'regulai/front', 'regulai/api',
        'regulai/regulai', 'regulai/manage.py', 'requirements.txt',
        'scripts/run_calibration_campaign.py',
        'evals/calibration/calibration-20261004-01/economics/decision.json']
    archived = subprocess.check_output(command, cwd=REPO)
    root.mkdir()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archived)) as archive:
        for item in archive.getmembers():
            if not item.isfile():
                continue
            path = (root / item.name).resolve()
            if not path.is_relative_to(root.resolve()) or path.name == 'local_settings.py' or path.suffix in {'.sqlite3', '.db'}:
                raise ValueError('Unexpected snapshot path')
            path.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(item).read()
            path.write_bytes(data)
            files[item.name] = hashlib.sha256(data).hexdigest()
    (HERE / ('snapshot-' + commit + '-hashes.json')).write_text(json.dumps(files, indent=2) + '\n', encoding='utf-8')
    return root


def setup(root):
    sys.path.insert(0, str(root / 'regulai'))
    sys.modules['regulai.local_settings'] = types.ModuleType('regulai.local_settings')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
    os.environ.pop('REGULAI_PRIVACY_CAPTURE', None)
    import django
    django.setup()
    from django.conf import settings
    assert settings.DATABASES['default']['NAME'] == ':memory:'
    return settings


def add_test_dependencies(root, commit):
    """Explicit public fixtures/scripts only; never corpus cases or builder literals."""
    hashes = {}
    for name in ('evals/adversarial-live/community-additional-20261003/manifest.json',
                 'scripts/calibration_local_checks.py'):
        path = root / name
        if path.exists():
            continue
        result = subprocess.run(['rtk', 'proxy', 'git', 'show', commit + ':' + name],
            cwd=REPO, capture_output=True)
        if result.returncode:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result.stdout)
        hashes[name] = hashlib.sha256(result.stdout).hexdigest()
    if hashes:
        with (HERE / ('snapshot-' + commit + '-extra-hashes.json')).open('x', encoding='utf-8') as output:
            output.write(json.dumps(hashes, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', default='4fdbe1a')
    parser.add_argument('--probes', action='store_true')
    parser.add_argument('--label', action='append')
    parser.add_argument('--run-name')
    options = parser.parse_args()
    root = prepare(options.commit)
    add_test_dependencies(root, options.commit)
    settings = setup(root)
    sys.path.insert(0, str(HERE))
    from django.test.utils import get_runner
    labels = options.label or (['security_probes'] if options.probes else [
        'front.test_calibration_budget', 'front.test_calibration_evaluation',
        'front.test_calibration_privacy', 'front.test_calibration_runner'])
    prefix = options.commit + ('-' + options.run_name if options.run_name else '-probes' if options.probes else '-existing')
    log = HERE / (prefix + '.log')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Review forbids sockets')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('Review forbids DNS')), \
         log.open('x', encoding='utf-8') as output, redirect_stdout(output), redirect_stderr(output):
        failures = get_runner(settings)(verbosity=2, interactive=False).run_tests(labels)
    record = {'commit': options.commit, 'labels': labels, 'failures': failures,
        'exit_code': int(bool(failures)), 'network_blocked': True,
        'user_database_opened': False, 'local_settings_loaded': False,
        'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    (HERE / (prefix + '-execution.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    print(log.read_text(encoding='utf-8')[-9000:])
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
