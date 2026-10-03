"""Reproduce frozen-data drift in an immutable Git export, then verify its repair."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
label, revision = sys.argv[1:]
assert label in ('red', 'green', 'green-02', 'green-03')
work = ROOT / '.claude' / ('pilot-corpus-export-' + label)
work.mkdir(exist_ok=False)
archive = work / 'source.zip'
args = ['rtk', 'proxy', 'git', 'archive', '--format=zip', '--output=' + str(archive), revision,
        '.gitattributes', 'regulai', 'evals/documents/pilot-20261003', 'evals/pilot-real', 'evals/pilot-human']
result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
source = work / 'source'
with zipfile.ZipFile(archive) as handle:
    handle.extractall(source)
base = source / 'evals/documents/pilot-20261003'
manifest = json.loads((base / 'files/manifest.json').read_text(encoding='utf-8'))
checks = []
for name, expected in [('expectations.json', manifest['expectations_sha256']),
                       ('generate_corpus.py', manifest['generator_sha256'])] + [
                       ('files/' + row['file'], row['sha256']) for row in manifest['files']]:
    data = (base / name).read_bytes()
    checks.append({'path': name, 'expected': expected, 'observed': sha256(data).hexdigest(),
                   'bytes': len(data), 'matches': sha256(data).hexdigest() == expected})
approval = json.loads((source / 'evals/pilot-real/authorization.pending.json').read_text())
manifest_hashes = [sha256((source / 'evals' / bank / 'manifest.json').read_bytes()).hexdigest()
                   for bank in ('pilot-real', 'pilot-human')]
command = ['rtk', 'proxy', sys.executable, str(source / 'regulai/manage.py'), 'test',
           'front.test_document_fidelity.FrozenPilotCorpusTests', '--settings=regulai.test_settings', '--noinput']
started = time.monotonic()
test = subprocess.run(command, cwd=source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                      encoding='utf-8', errors='replace')
log = HERE / (label + '.log')
with log.open('x', encoding='utf-8') as handle:
    handle.write(test.stdout)
resolved = subprocess.run(['rtk', 'proxy', 'git', 'rev-parse', revision], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
report = {'revision': revision, 'resolved_revision': resolved, 'archive_command': args, 'archive_sha256': sha256(archive.read_bytes()).hexdigest(),
          'checks': checks, 'authorization_manifest_hashes_match': manifest_hashes == approval['manifest_sha256s'],
          'command': command, 'exit_code': test.returncode, 'seconds': round(time.monotonic() - started, 3),
          'log_sha256': sha256(log.read_bytes()).hexdigest(), 'real_calls': 0}
with (HERE / (label + '.json')).open('x', encoding='utf-8') as handle:
    handle.write(json.dumps(report, indent=2) + '\n')
passed = test.returncode == 0 and all(row['matches'] for row in checks) and report['authorization_manifest_hashes_match']
print(json.dumps({'test_exit': test.returncode, 'drifted': [row['path'] for row in checks if not row['matches']],
                  'authorization_manifest_hashes_match': report['authorization_manifest_hashes_match'], 'passed': passed}))
raise SystemExit(0 if passed else 1)
