"""Copy independent review artifacts exactly; omit checkout copies, caches and archives."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'files.json').exists(), 'Use a new package; preserve previous hashes.'
rows = []
for role in ('security', 'spec'):
    source = ROOT / '.claude' / ('review-vercel-' + role)
    report = (ROOT / 'docs/plan-blackhat/revisiones-piloto/security-vercel-698e8f0.md'
              if role == 'security' else source / 'Spec-review.md')
    assert report.exists(), 'Independent written verdict must be ready.'
    target = HERE / role
    target.mkdir(exist_ok=False)
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.suffix not in ('.py', '.json', '.log', '.md', '.diff'):
            continue
        data = path.read_bytes()
        (target / path.name).write_bytes(data)
        rows.append({'source': path.relative_to(ROOT).as_posix(),
            'file': (target / path.name).relative_to(HERE).as_posix(),
            'bytes': len(data), 'sha256': sha256(data).hexdigest()})
    if role == 'security':
        data = report.read_bytes()
        (target / report.name).write_bytes(data)
        rows.append({'source': report.relative_to(ROOT).as_posix(),
            'file': (target / report.name).relative_to(HERE).as_posix(),
            'bytes': len(data), 'sha256': sha256(data).hexdigest()})
(HERE / 'files.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files_preserved': len(rows), 'all_copies_byte_identical': True}))
