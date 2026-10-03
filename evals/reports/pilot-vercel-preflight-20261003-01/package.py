"""Preserve the implementer's exact red/green evidence without modifying its source."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'files.json').exists(), 'Use a new evidence directory.'
rows = []
for name in ('checkpoint.json', 'manifest-delta.json', 'tdd-results.json', 'focal-results.json'):
    source = ROOT / '.claude/vercel-preflight' / name
    data = source.read_bytes()
    (HERE / name).write_bytes(data)
    rows.append({'source': source.relative_to(ROOT).as_posix(), 'file': name,
                 'sha256': sha256(data).hexdigest(), 'bytes': len(data)})
(HERE / 'files.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
print('Preserved four original C artifacts with SHA256; no product calls.')
