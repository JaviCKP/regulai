"""Compare observable states and hash the already recorded UTF-8 evidence only."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
base = json.loads((HERE / 'snapshot-535eb9d.json').read_text(encoding='utf-8'))
head = json.loads((HERE / 'snapshot-972edb8.json').read_text(encoding='utf-8'))
changed = [name for name in sorted(set(base['files']) | set(head['files']))
           if base['files'].get(name) != head['files'].get(name)]
assert changed == ['regulai/front/chat_service.py', 'regulai/front/evaluation.py', 'regulai/front/test_diagnostics.py'], changed
before = json.loads((HERE / 'baseline-matrix-isolated-http-matrix.json').read_text(encoding='utf-8'))
after = json.loads((HERE / 'candidate-matrix-isolated-http-matrix.json').read_text(encoding='utf-8'))
assert len(before) == len(after) == 18
expected = {'connect-timeout': 'timeout', 'read-timeout': 'timeout', 'http-403': 'http_403',
            'http-503': 'http_503', 'http-599': 'unknown_jev_error', 'malformed-json': 'invalid_response'}
for old, new in zip(before, after):
    assert old['provider_error_code'] is None
    assert new['provider_error_code'] == expected[new['fault']]
    assert {key: value for key, value in old.items() if key != 'provider_error_code'} == {
        key: value for key, value in new.items() if key != 'provider_error_code'}
prior = json.loads((ROOT / '.claude/real-run-diagnosis/audit-after-diagnostic-fix.json').read_text(encoding='utf-8'))
prefix = 'evals/reports/pilot-real-vercel-20261003-01/'
historical = {}
for name, expected_hash in prior['evidence_sha256'].items():
    relative = Path(name.replace('\\', '/'))
    if not relative.as_posix().startswith(prefix) or relative.suffix not in {'.json', '.jsonl', '.log'}:
        raise SystemExit('Unexpected evidence path')
    path = (ROOT / relative).resolve()
    assert path.is_relative_to((ROOT / prefix).resolve())
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    assert observed == expected_hash, name
    key = relative.as_posix()
    assert key in base['files'] and base['files'][key] == head['files'][key]
    historical[key] = {'recorded_sha256': expected_hash, 'observed_sha256': observed,
                       'unchanged_between_fixed_commits': True}
assert len(historical) == 11
result = {'base_commit': base['commit'], 'candidate_commit': head['commit'], 'changed_files': changed,
    'classification_scenarios_compared': 18, 'state_cost_bound_transport_replay_differences': [],
    'safe_diagnostics_added': expected, 'historical_evidence': historical,
    'historical_evidence_unchanged': True, 'database_or_persistent_ledger_opened': False,
    'contents_emitted': False}
with (HERE / 'differential-and-history-audit.json').open('x', encoding='utf-8') as handle:
    json.dump(result, handle, indent=2)
print(json.dumps({'changed_files': changed, 'compared_scenarios': 18, 'behavior_differences': 0,
    'historical_files_verified': 11,
    'audit_sha256': hashlib.sha256((HERE / 'differential-and-history-audit.json').read_bytes()).hexdigest()}))
