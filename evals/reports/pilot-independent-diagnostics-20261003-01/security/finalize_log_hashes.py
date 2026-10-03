"""Record final file hashes separately from the preserved pre-close runner metadata."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
hashes = {}
for result_path in sorted(HERE.glob('*.json')):
    result = json.loads(result_path.read_text(encoding='utf-8'))
    log = result_path.with_suffix('.log')
    if not log.is_file() or 'log_sha256' not in result:
        continue
    data = log.read_bytes()
    final = hashlib.sha256(data).hexdigest()
    hashes[log.name] = {'runner_preclose_sha256': result['log_sha256'], 'finalized_sha256': final,
        'runner_hash_matches_final_file': result['log_sha256'] == final,
        'reported_test_failures': result['failures'], 'bytes': len(data)}
older = HERE.parent / 'review-vercel-security'
old_seal = json.loads((older / 'final-seal.json').read_text(encoding='utf-8'))
errata = {}
for name in ('supplied-focal', 'own-gateway', 'frozen-scope-approvedbytes', 'router-negative-verification-only'):
    metadata = json.loads((older / (name + '.json')).read_text(encoding='utf-8'))
    actual = hashlib.sha256((older / (name + '.log')).read_bytes()).hexdigest()
    assert actual == old_seal['evidence'][name + '.log']
    if actual != metadata['log_sha256']:
        errata[name + '.log'] = {'superseded_preclose_hash': metadata['log_sha256'],
                                'final_file_hash_already_in_original_seal': actual}
result = {'cause': 'Review runner hashed its log while the text output handle remained open; buffered final lines were flushed only after calculating that field.',
    'remediation': 'Preserve all original files. Treat finalized file hashes and final seals as canonical. Do not use early log_sha256 fields as complete-file digests.',
    'current_finalized_log_hashes': hashes, 'vercel_report_hash_table_errata': errata,
    'prior_evidence_modified': False, 'test_results_changed': False}
with (HERE / 'finalized-log-hashes.json').open('x', encoding='utf-8') as handle:
    json.dump(result, handle, indent=2)
print(json.dumps({'finalized_logs': len(hashes), 'prior_report_hash_errata': len(errata),
    'sha256': hashlib.sha256((HERE / 'finalized-log-hashes.json').read_bytes()).hexdigest()}))
