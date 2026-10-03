"""Freeze approved byte representations only after matching the fixed archive content."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
original = json.loads((HERE / 'snapshot-698e8f0.json').read_text(encoding='utf-8'))
source = HERE / original['snapshot']
destination = HERE / 'snapshot-698e8f0-approvedbytes'
if destination.exists():
    raise SystemExit('Refusing to overwrite immutable evidence')
pilot = json.loads((source / 'evals/pilot-real/manifest-vercel.json').read_text(encoding='utf-8'))
approved, comparisons = {}, {}
for name, expected in pilot['source_sha256'].items():
    archived = (source / name).read_bytes()
    current = (ROOT / name).read_bytes()
    observed = hashlib.sha256(current).hexdigest()
    if observed != expected:
        raise SystemExit('Worktree bytes are not approved: ' + name)
    if current.replace(b'\r\n', b'\n') != archived.replace(b'\r\n', b'\n'):
        raise SystemExit('Content differs from fixed archive: ' + name)
    approved[name] = current
    comparisons[name] = {'approved_sha256': observed,
        'archive_sha256': hashlib.sha256(archived).hexdigest(),
        'normalized_sha256': hashlib.sha256(current.replace(b'\r\n', b'\n')).hexdigest(),
        'normalized_equal_to_fixed_archive': True,
        'archive_crlf': archived.count(b'\r\n'), 'approved_crlf': current.count(b'\r\n'),
        'approved_lf_only': current.count(b'\n') - current.count(b'\r\n')}
hashes = {}
for name, expected in original['files'].items():
    data = (source / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit('Original archive was altered: ' + name)
    data = approved.get(name, data)
    path = destination / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    hashes[name] = hashlib.sha256(data).hexdigest()
record = {**original, 'snapshot': destination.name, 'files': hashes,
    'derived_from': original['snapshot'], 'approved_byte_overrides': comparisons,
    'archive_sha256': original['archive_sha256'],
    'note': 'Original immutable archive retained. Only EOL representations whose bytes match the approved manifest and whose normalized content matches that archive were replaced in this separate derived snapshot.'}
(HERE / (destination.name + '.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
(HERE / 'eol-approved-byte-audit.json').write_text(json.dumps(comparisons, indent=2), encoding='utf-8')
print(json.dumps({'commit': original['commit'], 'files': len(hashes),
    'all_approved_source_hashes_match': True, 'all_source_normalized_content_matches_fixed_archive': True,
    'different_raw_representations': sum(value['archive_sha256'] != value['approved_sha256'] for value in comparisons.values())}))
