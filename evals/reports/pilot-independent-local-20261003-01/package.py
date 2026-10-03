"""Preserve independent review evidence byte for byte, excluding full checkouts."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'package-files.json').exists(), 'Use a new evidence package.'
copied = []


def preserve(source, relative):
    target = HERE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), target
    shutil.copyfile(source, target)
    original, saved = sha256(source.read_bytes()).hexdigest(), sha256(target.read_bytes()).hexdigest()
    assert original == saved
    copied.append({'origin': source.relative_to(ROOT).as_posix(), 'file': target.relative_to(HERE).as_posix(),
                   'bytes': source.stat().st_size, 'sha256': original})


for team in ('security', 'spec'):
    source = ROOT / '.claude' / ('review-local-' + team)
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.json', '.log', '.md'):
            preserve(path, Path(team) / path.name)
    directories = ('followup-be29b6f', 'followup-0957df4') if team == 'security' else (
        'detector-corpus', 'pilot-offline', 'human-offline')
    for name in directories:
        for path in sorted((source / name).iterdir()):
            if path.is_file() and path.suffix in ('.py', '.json', '.jsonl', '.log', '.md', '.csv'):
                preserve(path, Path(team) / name / path.name)

reports = ROOT / 'docs/plan-blackhat/revisiones-piloto'
for name in ('security-local-c85d019.md', 'security-local-0957df4.md'):
    preserve(reports / name, Path('original-reports') / name)
    content = (reports / name).read_text(encoding='utf-8').replace(
        '../../../.claude/review-local-security/',
        '../../../evals/reports/pilot-independent-local-20261003-01/security/')
    (reports / name).write_text(content, encoding='utf-8')
spec = ROOT / '.claude/review-local-spec/Spec-review.md'
preserve(spec, Path('original-reports/spec-local-d63731a.md'))
target = reports / 'spec-local-d63731a.md'
assert not target.exists()
target.write_text(spec.read_text(encoding='utf-8').replace('en `evidence.json`.',
    'en [evidence.json](../../../evals/reports/pilot-independent-local-20261003-01/spec/evidence.json).'), encoding='utf-8')
(HERE / 'package-files.json').write_text(json.dumps(copied, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files': len(copied), 'bytes': sum(row['bytes'] for row in copied), 'hashes_match': True}))
