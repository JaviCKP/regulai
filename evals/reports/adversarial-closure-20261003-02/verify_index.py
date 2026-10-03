"""Confirm Git will preserve the exact bytes of the sealed evidence directories."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
folders = ('adversarial-real-20261003-01', 'adversarial-real-20261003-02',
           'adversarial-live-response-review-20261003-01', 'adversarial-second-response-review-20261003-01',
           'adversarial-consolidated-20261003-01', 'adversarial-gates-20261003-02',
           'semantic-threshold-boundary-20261003-01', 'semantic-threshold-independent-20261003-01',
           'adversarial-closure-20261003-02')
command = ['rtk', 'proxy', 'git', 'ls-files', '--stage', '--',
           *['evals/reports/' + folder for folder in folders]]
raw = subprocess.check_output(command, cwd=ROOT, encoding='utf-8')
bad, count = [], 0
for line in raw.splitlines():
    metadata, name = line.split('\t', 1)
    data = (ROOT / name).read_bytes()
    object_id = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()
    count += 1
    if object_id != metadata.split()[1]:
        bad.append(name)
result = {'command': command, 'tracked_evidence_files': count,
          'index_bytes_equal_working_tree': not bad, 'mismatches': bad, 'new_calls': 0}
with (ROOT / sys.argv[1]).open('x', encoding='utf-8') as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
raise SystemExit(bool(bad))
