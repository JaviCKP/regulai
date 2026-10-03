"""Preserve only the explicit public artifacts of the two simulated profiles."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'files.json').exists(), 'Use a new report directory; never overwrite evidence.'
records = []
for persona, manifest, field, expected_count in (
    ('p01', 'public-artifacts.json', 'files_relative_to_p01', 24),
    ('p02', 'public-files.json', 'copy_only_these_relative_files', 26),
):
    source = ROOT / '.claude/pilot-personas' / persona
    destination = HERE.parent / f'pilot-persona-{persona}-simulated-20261003-01'
    assert not destination.exists()
    names = json.loads((source / manifest).read_text(encoding='utf-8'))[field]
    assert len(names) == expected_count and len(set(names)) == expected_count
    for name in names:
        original = (source / name).resolve()
        copied = (destination / name).resolve()
        assert original.is_relative_to(source.resolve()) and copied.is_relative_to(destination.resolve())
        assert original.is_file() and original.suffix.lower() not in {'.sqlite3', '.db', '.zip'}
        data = original.read_bytes()
        copied.parent.mkdir(parents=True, exist_ok=True)
        with copied.open('xb') as output:
            output.write(data)
        assert copied.read_bytes() == data
        records.append({'source': original.relative_to(ROOT).as_posix(),
                        'file': '../' + copied.relative_to(HERE.parent).as_posix(),
                        'bytes': len(data), 'sha256': sha256(data).hexdigest()})
with (HERE / 'files.json').open('x', encoding='utf-8') as output:
    json.dump(records, output, indent=2)
    output.write('\n')
print(json.dumps({'public_files_copied': len(records), 'human_participants': 0,
                  'real_provider_calls': 0, 'original_bytes_preserved': True}))
