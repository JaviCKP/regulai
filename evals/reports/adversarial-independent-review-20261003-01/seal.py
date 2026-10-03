"""Seal independent review evidence; all output stays in this owned directory."""
import hashlib
import json
from pathlib import Path
import subprocess

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    return json.loads((OWN / name).read_text(encoding='utf-8'))

commands = []
for filename, args in (
    ('reviewed.diff', ['git', 'diff', '21bdd9f...df91ea1dacbe1662d392bfd91417d32a0e46abe6']),
    ('followup.diff', ['git', 'diff', 'df91ea1dacbe1662d392bfd91417d32a0e46abe6', '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2']),
    ('commits.txt', ['git', 'log', '--oneline', '21bdd9f..128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2']),
):
    argv = ['rtk', 'proxy', *args]
    result = subprocess.run(argv, cwd=REPO, capture_output=True, check=True)
    (OWN / filename).write_bytes(result.stdout)
    commands.append({'argv': argv, 'exit_code': result.returncode, 'output': filename})
red, green, runner = read('extension.json'), read('extension-fixed.json'), read('runner.json')
measure = read('measurement-notes.json')
pack = read('static-pack-observations.json')
assert red['exit_code'] == 1 and green['exit_code'] == runner['exit_code'] == 0
assert read('followup-observations.json')['cli_report_race']['ledger_bytes_unchanged'] is True
assert measure['fresh_local_cases'] == 44 and measure['fresh_http_runs'] == 30
assert pack['checks_passed'] is True and pack['bridge_executed'] is False
names = ['Spec-review.md', 'Standards-review.md', 'driver.py', 'run.py', 'read_lines.py', 'independent_cases.py',
    'followup_cases.py', 'runner_probe.py', 'measurement_notes.py', 'static_pack_review.py', 'seal.py',
    'extension.log', 'extension.json', 'independent-observations.json', 'extension-fixed.log', 'extension-fixed.json',
    'followup-observations.json', 'runner.log', 'runner.json', 'runner-observations.json',
    'local-measurements.json', 'http-measurements.jsonl', 'measurement-notes.json', 'static-pack-observations.json',
    'reviewed.diff', 'followup.diff', 'commits.txt']
files = [{'path': name, 'bytes': (OWN / name).stat().st_size, 'sha256': sha(OWN / name)} for name in names]
evidence = {
    'base': '21bdd9f444024e2da76c826c0d0432090e555010',
    'reviewed': 'df91ea1dacbe1662d392bfd91417d32a0e46abe6',
    'followup': '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2',
    'findings': [{'id': 'SPEC-1', 'priority': 'P2', 'status': 'fixed_verified',
        'file': 'regulai/front/management/commands/extend_pilot_authorization.py',
        'lines_original': [25, 46], 'lines_fix': [35, 38],
        'summary': 'CLI reported an obsolete approval digest when a valid approval changed during lock wait.',
        'red_probe': 'independent_cases.py', 'green_probe': 'followup_cases.py'}],
    'open_spec_findings': 0, 'open_standards_findings': 0,
    'tests': {'original': {'repository_tests': 12, 'own_probes': 3, 'passed': 14, 'failed': 1, 'exit_code': 1},
        'followup': {'own_probes': 3, 'passed': 3, 'exit_code': 0},
        'detector': {'cases': 44, 'expectations_met': 37, 'redactions': '27/32', 'preservations': '61/66'},
        'http': {'runs': 30, 'cases': ['PII-03', 'INJ-05', 'DOC-04', 'DOC-08', 'PII-12'],
            'profiles': 2, 'endpoints': 3, 'controls_met': 27, 'integrity_exit_code': 0}},
    'execution_records': [red, green, runner], 'commands': commands,
    'snapshot_archives': {'source.zip': sha(OWN / 'source.zip'), 'followup.zip': sha(OWN / 'followup.zip')},
    'proposal_manifest_sha256': pack['manifest_sha256'], 'static_pack_check_exit_code': 0,
    'product_changes': [], 'index_changes': [], 'real_product_calls': 0,
    'bridge_executed': False, 'real_ledger_opened': False, 'user_keys_or_database_read': False,
    'private_settings': 'empty module installed before Django; empty snapshot file; memory DB enforced',
    'prior_review_evidence_modified': False,
    'web_sources': ['https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html'],
    'recommendation': 'Present exact pending four-case proposal for new human approval; do not treat review as execution authorization.',
    'limits': ['No live model semantic quality or injection resistance measured.',
        'Exact annotation disappearance is not anonymity or population recall.',
        'Full 264-run implementer suite and 400-test gates are not claimed as reviewer executions.',
        'Real ledger history/exposure was not read; arithmetic starts from parent-supplied exposure.',
        'Bridge checked statically only; no credential or provider access test.',
        'Historical uncertain call remains unattributed.'],
    'files': files,
}
(OWN / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
files.append({'path': 'evidence.json', 'bytes': (OWN / 'evidence.json').stat().st_size, 'sha256': sha(OWN / 'evidence.json')})
(OWN / 'package-files.json').write_text(json.dumps({'files': files}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'public_files': len(files), 'evidence_sha256': sha(OWN / 'evidence.json'),
    'package_list_sha256': sha(OWN / 'package-files.json'), 'exit_code': 0}, indent=2))
