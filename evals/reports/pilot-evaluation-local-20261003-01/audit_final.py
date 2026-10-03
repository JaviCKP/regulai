"""Read-only audit of frozen pilot outputs; creates new inventory files, never replaces."""
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWNED = (
    'regulai/front/evaluation.py',
    'regulai/front/management/commands/evaluate_ai.py',
    'regulai/front/management/commands/run_demo.py',
    'regulai/front/test_smoke.py',
    'regulai/front/test_evaluation_pilot.py',
    'regulai/front/test_demo.py',
    'scripts/prepare_pilot_manifest.py',
    'evals/pilot-real/manifest.json',
    'evals/pilot-real/authorization.pending.json',
    'evals/pilot-real/README.md',
    'evals/pilot-human/manifest.json',
    'evals/pilot-human/README.md',
    'docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md',
    'docs/plan-blackhat/tareas/23-recorrido-real.md',
    'docs/plan-blackhat/tareas/24-calibracion-humana.md',
)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_new(name, value):
    with (HERE / name).open('x', encoding='utf-8') as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


reports = {}
for name, count in [('smoke-local-final', 24), ('human-local-final', 72)]:
    directory = HERE / name
    manifest = read(directory / 'manifest.json')
    rows = [json.loads(line) for line in (directory / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
    summary = [item for item in read(directory / 'summary.json') if item['split'] == 'all']
    budget = read(directory / 'budget.json')
    calls = [call for row in rows for call in row['calls']]
    local = [call for call in calls if call['metadata']['transport'] == 'local']
    external = [call for call in calls if call['metadata']['transport'] != 'local' and call['status'] != 'not_started']
    assert len(rows) == count and all(row['control_pass'] and row['mode'] == 'simulated' for row in rows)
    assert all(row['human_review'] is None for row in rows)
    assert all(call['purpose'] == 'obfuscation' and call['reserved'] == '0' and call['cost'] == '0'
               and call['metadata']['cost_kind'] == 'configured_zero' for call in local)
    assert sum(item['provider_calls'] for item in summary) == len(external)
    assert sum(item['local_transformations'] for item in summary) == len(local)
    assert all(item['calls_by_purpose']['obfuscation'] == 0 and item['real_provider_cases'] == 0
               and item['correct_answers'] is None and item['cost_per_correct_estimated_usd'] is None
               and item['cost_per_correct_reported_usd'] is None
               and item['quality_claim'] is None and item['savings_claim'] is None for item in summary)
    assert manifest['source_sha256'] == manifest['source_sha256_observed']
    assert all(digest(ROOT / filename) == expected for filename, expected in manifest['source_sha256'].items())
    assert manifest['runtime_versions'] == manifest['runtime_versions_observed']
    assert manifest['masking'] == manifest['masking_observed']
    assert len(read(directory / 'human-review.pending.json')) == count
    assert all(item['status'] == 'pending' and item['reviewer'] is None for item in read(directory / 'human-review.pending.json'))
    reports[name] = {'runs': count, 'controls_passed': count, 'local_transformations': len(local),
        'simulated_external_calls': len(external), 'human_reviews_completed': 0, 'real_provider_cases': 0,
        'actual_api_spend_usd': '0', 'budget_simulated': {key: value for key, value in budget.items() if key != 'calls'},
        'manifest_sha256': manifest['manifest_sha256'], 'report_manifest_sha256': digest(directory / 'manifest.json'),
        'results_sha256': digest(directory / 'results.jsonl'), 'declared_and_observed_sources_runtime_masking_match': True,
        'latencies': [{key: row[key] for key in ('configuration', 'n', 'p50_latency_ms', 'p95_latency_ms')} for row in summary]}

approval = read(ROOT / 'evals/pilot-real/authorization.pending.json')
assert approval['status'] == 'pending' and approval['approved_by'] is None and approval['maximum_usd'] == '1.00'
assert set(approval['destinations']) == {'generation', 'judge'}
assert set(approval['manifest_sha256s']) == {digest(ROOT / name) for name in ('evals/pilot-real/manifest.json', 'evals/pilot-human/manifest.json')}
for filename in ('preflight-final.json', 'human-preflight-final.json'):
    result = read(HERE / filename)
    assert not result['ready_for_real'] and result['network_calls'] == 0
    assert 'source_changed' not in result['blockers'] and 'runtime_changed' not in result['blockers']
assert not (HERE / 'preflight-must-not-exist').exists()
assert not (HERE / 'human-preflight-must-not-exist').exists()
write_new('owned-files.json', {name: digest(ROOT / name) for name in OWNED})
artifacts = {path.relative_to(HERE).as_posix(): digest(path) for path in sorted(HERE.rglob('*')) if path.is_file()}
write_new('audit.json', {'checks_passed': True, 'reports': reports, 'approval_status': 'pending',
    'approval_sha256': digest(ROOT / 'evals/pilot-real/authorization.pending.json'), 'artifacts_sha256': artifacts})
print(json.dumps({'checks_passed': True, 'reports': reports}, ensure_ascii=False, indent=2))
