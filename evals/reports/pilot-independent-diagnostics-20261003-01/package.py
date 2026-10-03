"""Copy sealed public security/spec evidence without altering original bytes."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'files.json').exists(), 'Preserve previous evidence; use a new directory.'
records = []

def copy(source, destination, expected=None):
    data = source.read_bytes()
    digest = sha256(data).hexdigest()
    if expected is not None:
        assert digest == expected, source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        output.write(data)
    assert destination.read_bytes() == data
    records.append({'source': source.relative_to(ROOT).as_posix(),
                    'file': destination.relative_to(HERE).as_posix(),
                    'bytes': len(data), 'sha256': digest})

security = ROOT / '.claude/review-diagnostics-security'
seal = json.loads((security / 'final-seal.json').read_text(encoding='utf-8'))
assert seal['candidate_commit'] == '972edb88c82a5220a43ffcc89316a9f9033e82f7'
for name, digest in seal['evidence'].items():
    source = (security / name).resolve()
    assert source.is_relative_to(security.resolve()) and source.suffix not in {'.zip', '.db', '.sqlite3'}
    copy(source, HERE / 'security' / name, digest)
copy(security / 'final-seal.json', HERE / 'security/final-seal.json',
     '28330861efbf7998de1b77eddda44d63a3a5a8db8b110be25d198fbde552331f')
copy(ROOT / seal['report'], HERE / 'security/Security-review.md', seal['report_sha256'])

spec = ROOT / '.claude/review-diagnostics-spec'
names = json.loads((spec / 'package-files.json').read_text(encoding='utf-8'))
assert len(names) == 13 and len(set(names)) == 13
assert sha256((spec / 'evidence.json').read_bytes()).hexdigest() == 'ef7d9743eca15748e0ecc12a5e3fc7f3cd7dc9eb451b29e6cf7b056d93615e6b'
for name in names + ['package-files.json']:
    source = (spec / name).resolve()
    assert source.is_relative_to(spec.resolve()) and source.suffix not in {'.zip', '.db', '.sqlite3'}
    copy(source, HERE / 'spec' / name)
with (HERE / 'files.json').open('x', encoding='utf-8') as output:
    json.dump(records, output, indent=2)
    output.write('\n')
print(json.dumps({'public_files_copied': len(records), 'original_bytes_preserved': True,
                  'real_provider_calls': 0}))
