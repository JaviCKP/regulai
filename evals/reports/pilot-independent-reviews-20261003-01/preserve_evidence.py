"""Copy closed review evidence byte for byte; never import or execute the product."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = '6c78cd396eb72713e85b72d8592970e4b6b66585'
C1 = 'c1e3a360e7ba3051bb8f0bda487b005dd29834a0'
A3 = 'a3bc67b25b341cb28172bebd5001ef48c5b8d34f'
SPEC_CLOSE = '87311294631d9ffdf6b76ccf3fcb9140018a0977'
SECURITY = 'febc8aa9b303070e82e3f27626371d5b67cb73f7'
EXCLUDED_DIRECTORIES = {'candidate', 'snapshot', 'snapshots', '__pycache__',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', 'cache', '.git', '.venv', 'node_modules'}
REPORTS = {
    'standards-c1e3a36.md': [BASE, C1],
    'standards-a3bc67b.md': [C1, A3],
    'spec-c1e3a36.md': [BASE, C1],
    'spec-8731129.md': [SPEC_CLOSE],
    'security-febc8aa.md': [BASE, SECURITY],
}


def copy_one(source, relative, refs, kind):
    target = HERE / relative
    if target.exists():
        raise FileExistsError(f'Evidence is immutable; already exists: {target}')
    before = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    after, copied = source.read_bytes(), target.read_bytes()
    if before != after or before != copied:
        raise RuntimeError(f'Source changed or copy differs: {source}')
    return {'source': source.relative_to(ROOT).as_posix(),
        'destination': target.relative_to(HERE).as_posix(), 'kind': kind,
        'fixed_refs': refs, 'bytes': len(before), 'source_sha256': sha256(before).hexdigest(),
        'copy_sha256': sha256(copied).hexdigest(), 'source_equals_copy': True}


def main():
    manifest = HERE / 'manifest.json'
    if manifest.exists():
        raise FileExistsError('The evidence capture already exists; do not overwrite it.')
    entries = []
    for group in ('standards', 'spec', 'security'):
        source_root = ROOT / '.claude' / ('review-' + group)
        paths = source_root.iterdir() if group == 'security' else source_root.rglob('*')
        for source in sorted(paths):
            relative = source.relative_to(source_root)
            if (not source.is_file() or source.is_symlink()
                    or any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1])
                    or source.suffix in ('.pyc', '.pyo')):
                continue
            if group == 'standards':
                refs = [C1, A3] if relative.parts[0] == 'followup-a3bc67b' else [BASE, C1]
            elif group == 'spec':
                refs = [SPEC_CLOSE] if relative.parts[0] == 'followup-8731129' else [BASE, C1]
            else:
                refs = [BASE, SECURITY]
            entries.append(copy_one(source, Path(group) / relative, refs, 'closed_review_evidence'))
    for report, refs in REPORTS.items():
        entries.append(copy_one(ROOT / 'docs/plan-blackhat/revisiones-piloto' / report,
            Path('reports-at-capture') / report, refs, 'report_before_evidence_link_update'))
    payload = {'schema_version': 1, 'captured_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Closed initial reviews and Standards/Spec follow-ups only; no later Security follow-up.',
        'copy_mode': 'binary read/copy; no encoding or newline normalization',
        'excluded_directories': sorted(EXCLUDED_DIRECTORIES),
        'excluded_suffixes': ['.pyc', '.pyo'], 'security_top_level_only': True,
        'snapshots_represented_by_manifests_and_fixed_refs': True,
        'source_files_removed_or_changed': False, 'product_or_provider_executed': False,
        'entries': entries}
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'copied_evidence': sum(row['kind'] == 'closed_review_evidence' for row in entries),
        'original_reports': len(REPORTS), 'total_bytes': sum(row['bytes'] for row in entries),
        'all_source_equals_copy': all(row['source_equals_copy'] for row in entries)}))


if __name__ == '__main__':
    main()
