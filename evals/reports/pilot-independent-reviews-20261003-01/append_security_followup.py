"""Append the separately closed Security follow-up; preserve the earlier capture."""
from datetime import datetime, timezone
import json
import shutil
import sys

sys.dont_write_bytecode = True

from preserve_evidence import HERE, ROOT, SECURITY, copy_one

SHA = '700389c216592db1e0c8725749bb4fd02cf3fa10'
manifest_path = HERE / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if any(row['destination'].startswith('security/followup-700389c/') for row in manifest['entries']):
    raise FileExistsError('Security follow-up is already captured; refusing to overwrite.')

source_root = ROOT / '.claude/review-security/followup-700389c'
for source in sorted(source_root.iterdir()):
    if source.is_file() and not source.is_symlink() and source.suffix not in ('.pyc', '.pyo'):
        manifest['entries'].append(copy_one(source, 'security/followup-700389c/' + source.name,
            [SECURITY, SHA], 'closed_review_evidence'))

report = ROOT / 'docs/plan-blackhat/revisiones-piloto/security-700389c.md'
if report.exists():
    raise FileExistsError('The destination review already exists; refusing to overwrite.')
shutil.copyfile(source_root / 'review.md', report)
manifest['entries'].append(copy_one(report, 'reports-at-capture/security-700389c.md',
    [SECURITY, SHA], 'report_before_evidence_link_update'))
manifest.update(scope='Closed initial reviews and fixed Standards, Spec and Security follow-ups; excludes the newly requested local detector.',
    security_followup_appended_utc=datetime.now(timezone.utc).isoformat(),
    security_directories=['.claude/review-security', '.claude/review-security/followup-700389c'])
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'captured_security_followup_files': 18, 'new_review': report.relative_to(ROOT).as_posix(),
    'total_copied_files': len(manifest['entries']), 'all_originals_preserved': True}))
