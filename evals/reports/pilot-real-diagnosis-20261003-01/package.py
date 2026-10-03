"""Preserve the offline diagnosis and regression evidence exactly."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'files.json').exists(), 'Preserve earlier evidence.'
source = ROOT / '.claude/real-run-diagnosis'
assert (source / 'diagnosis.md').exists() and (source / 'inventory.json').exists()
rows = []
for path in sorted(source.iterdir()):
    if path.is_file() and path.suffix in ('.py', '.json', '.log', '.md'):
        data = path.read_bytes()
        (HERE / path.name).write_bytes(data)
        rows.append({'source': path.relative_to(ROOT).as_posix(), 'file': path.name,
                     'sha256': sha256(data).hexdigest(), 'bytes': len(data)})
(HERE / 'files.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files_preserved': len(rows), 'product_calls': 0}))
