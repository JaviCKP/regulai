"""Check the preserved live run, without importing Django or opening credentials/ledger."""
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
assert not (HERE / 'result-verification.json').exists(), 'Keep the original verification.'
run = HERE / 'live-run-01'
read = lambda name: json.loads((run / name).read_text(encoding='utf-8'))
rows = [json.loads(line) for line in (run / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
calls = [call for row in rows for call in row['calls']]
budget = read('budget.json')
plan = read('plan.json')
bridge = json.loads((HERE / 'live-result.json').read_text(encoding='utf-8'))
assert len({call['id'] for call in calls}) == len(calls)
assert {call['id'] for call in budget['calls']} == {call['id'] for call in calls}
assert rows == [json.loads(line) for line in (run / 'completed-cases.jsonl').read_text(encoding='utf-8').splitlines()]
assert plan['execution_mode'] == 'real' and len(plan['execution_order']) == 24
assert plan['completed_order'] == [[row['case_id'], row['configuration']] for row in rows]
assert all(row['control_pass'] for row in rows)
assert all(row['human_review'] is None for row in rows)
assert bridge['source_database_unchanged'] and not bridge['user_database_migrated']
assert not bridge['credential_values_redacted_from_unexpected_logs']
assert plan['stop_reason'] == 'failed_or_uncertain_provider_call' and bridge['exit_code'] == 1
external = [call for call in calls if call['metadata']['transport'] != 'local']
local = [call for call in calls if call['metadata']['transport'] == 'local']
assert all(Decimal(call['cost']) == Decimal(call['reserved']) == 0 for call in local)
reported = sum((Decimal(call['cost']) for call in external if call['metadata']['cost_kind'] == 'provider_reported'), Decimal(0))
estimated = sum((Decimal(call['cost']) for call in external if call['metadata']['cost_kind'] == 'tariff_estimate'), Decimal(0))
uncertain = [call for call in external if call['cost'] is None]
assert reported == Decimal(budget['provider_reported_usd'])
assert estimated == Decimal(budget['tariff_estimated_usd'])
assert reported + estimated == Decimal(budget['known_cost_usd'])
assert sum(Decimal(call['reserved']) for call in uncertain) == Decimal(budget['uncertain_reservations_usd'])
assert Decimal(budget['budget_exposure_usd']) + Decimal(budget['remaining_usd']) == Decimal('1.00')
assert len(uncertain) == 1 and uncertain[0]['purpose'] == 'classification'
assert uncertain[0]['status'] == 'outcome_unknown'
assert len(calls) == 29 and len(external) == 17 and len(local) == 12
record = {
    'passed': True, 'code_commit': plan['commit'], 'planned_combinations': len(plan['execution_order']),
    'observed_combinations': len(rows), 'distinct_case_ids': len({row['case_id'] for row in rows}),
    'states': dict(Counter(row['execution_state'] for row in rows)),
    'external_calls': len(external), 'local_transformations': len(local),
    'external_purposes': dict(Counter(call['purpose'] for call in external)),
    'provider_reported_usd': str(reported), 'tariff_estimated_usd': str(estimated),
    'uncertain_reservations_usd': budget['uncertain_reservations_usd'],
    'budget_exposure_usd': budget['budget_exposure_usd'], 'remaining_admission_usd': budget['remaining_usd'],
    'real_human_reviews': 0, 'stop_reason': plan['stop_reason'], 'new_product_calls_by_verifier': 0,
    'limitation': 'Checks preservation/accounting, not human semantic correctness or a final provider invoice.',
    'source_sha256': {p.relative_to(HERE).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in sorted(run.iterdir()) if p.is_file()},
}
(HERE / 'result-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in record.items() if k != 'source_sha256'}, indent=2))
