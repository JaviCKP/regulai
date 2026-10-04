"""Reconcile immutable JSON artifacts after campaign stop; never settle a ledger."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json

from check_pack import HERE, REPO, read, sha, checked_bytes

CAMPAIGN = REPO / 'evals/calibration/calibration-20261004-01'
PACK = CAMPAIGN / 'batches/r4-smoke-01'
RUN = PACK / 'live-run-01'
PREVIOUS = CAMPAIGN / 'batches/candidate-smoke-01/live-run-01'


def main():
    budget, previous = read(RUN / 'budget.json'), read(PREVIOUS / 'budget.json')
    manifest, approval = read(PACK / 'manifest.json'), read(PACK / 'authorization.json')
    run, bridge = read(RUN / 'manifest.json'), read(PACK / 'live-bridge.json')
    events = read(RUN / 'synthetic-payloads.json')
    rows = [json.loads(line) for line in checked_bytes(RUN / 'results.jsonl').splitlines()]
    by_id = {row['id']: row for row in budget['calls']}
    current = [row for row in budget['calls'] if row['metadata'].get('authorization_id') == approval['authorization_id']]
    external = [row for row in current if row['metadata'].get('transport') != 'local']
    unknown = [row for row in external if row['cost'] is None]
    totals = {'known_cost_usd': Decimal(0), 'provider_reported_usd': Decimal(0), 'tariff_estimated_usd': Decimal(0), 'uncertain_reservations_usd': Decimal(0), 'budget_exposure_usd': Decimal(0)}
    for call in budget['calls']:
        bound = Decimal(call['reserved'])
        cost = None if call['cost'] is None else Decimal(call['cost'])
        kind = call['metadata'].get('cost_kind', 'provider_reported')
        if cost is None:
            totals['uncertain_reservations_usd'] += bound
        else:
            totals['known_cost_usd'] += cost
            if kind in ('provider_reported', 'tariff_estimate'):
                totals['provider_reported_usd' if kind == 'provider_reported' else 'tariff_estimated_usd'] += cost
        totals['budget_exposure_usd'] += cost if cost is not None and kind in ('provider_reported', 'configured_zero', 'not_incurred') else max(bound, cost or Decimal(0))
    checks = {
        'all_preceding_ledger_rows_preserved': all(by_id.get(call['id']) == call for call in previous['calls']),
        'totals_recompute_exactly': all(Decimal(budget[key]) == value for key, value in totals.items()),
        'known_separates_reported_estimated': totals['known_cost_usd'] == totals['provider_reported_usd'] + totals['tariff_estimated_usd'],
        'remaining_recomputes': Decimal(budget['remaining_usd']) == Decimal(budget['cap_usd']) - totals['budget_exposure_usd'],
        'under_global_cap': totals['budget_exposure_usd'] <= Decimal(budget['cap_usd']) == Decimal('1.66'),
        'bridge_failed_and_user_db_preserved': bridge['exit_code'] == 1 and bridge['source_database_unchanged'] and bridge['user_database_migrated'] is False,
        'exact_scope_identity': run['manifest_sha256'] == sha(PACK / 'manifest.json') == bridge['manifest_sha256'],
        'stopped_on_uncertainty': run['stop_reason'] == 'failed_or_uncertain_provider_call' and rows[-1]['execution_state'] == 'outcome_unknown',
        'five_prefix_combinations': len(rows) == 5 and run['completed_order'] == run['execution_order'][:5],
        'eleven_real_transports_and_ledger_calls': len(events) == len(external) == 11 and all(e['transport_started'] for e in events),
        'single_new_unknown_reservation_retained': len(unknown) == 1 and unknown[0]['status'] == 'outcome_unknown' and Decimal(unknown[0]['reserved']) == Decimal('.003') and unknown[0]['metadata']['cost_kind'] == 'unknown',
        'invalid_last_call': unknown[0]['metadata']['provider_error_code'] == 'invalid_response' and unknown[0]['id'] == budget['calls'][-1]['id'],
        'no_generation_after_unknown_classification': rows[-1]['generation_calls'] == 0 and rows[-1]['answer'] is None and events[-1]['purpose'] == 'classification' and (events[-1]['case_id'], events[-1]['configuration']) == ('P0619', 'router'),
        'unknown_total_includes_both_reservations': totals['uncertain_reservations_usd'] == Decimal('.006'),
        'per_call_caps_preserved': all(Decimal(call['reserved']) <= Decimal(manifest['call_caps_usd'][call['purpose']]) for call in current),
        'max_generation_attempts_preserved': all(row['generation_calls'] <= manifest['max_generation_attempts'][row['configuration']] for row in rows),
        'inside_original_window': all(datetime.fromisoformat(approval['valid_from']) <= datetime.fromisoformat(call['at']) < datetime.fromisoformat(approval['valid_until']) for call in current),
    }
    gates = read(CAMPAIGN / 'gates-02/manifest.json')
    checks['gates_fixed_revision'] = gates['revision'] == 'b3fea6a63761c06ef66695fee26377d23786c347' and gates['source_unchanged'] is True
    checks['gate_logs_and_exits'] = all(row['exit_code'] == 0 and sha(CAMPAIGN / 'gates-02' / row['log']) == row['sha256'] for row in gates['commands'])
    checks['gate_runtime_matches_pack'] = all(gates['source_sha256'][name] == expected for name, expected in manifest['source_sha256'].items())
    campaign_calls = [c for c in budget['calls'] if c['metadata'].get('authorization_id', '').startswith('calibration-20261004-01-') and c['metadata'].get('transport') != 'local']
    result = {'reviewed_at_utc': datetime.now(timezone.utc).isoformat(), 'commit': gates['revision'], 'checks': checks, 'all_passed': all(checks.values()), 'recomputed_totals': {k: str(v) for k, v in totals.items()}, 'campaign_external_calls_by_scope': dict(Counter(c['metadata']['authorization_id'] for c in campaign_calls)), 'r4_external_by_purpose': dict(Counter(c['purpose'] for c in external)), 'margin_adjusted_exposure_eur': str(totals['budget_exposure_usd'] * Decimal('1.35') / Decimal('1.1225')), 'new_unknown_reservation_usd': '.003', 'new_payments_permitted': False, 'budget_json_sha256': sha(RUN / 'budget.json'), 'gates_manifest_sha256': sha(CAMPAIGN / 'gates-02/manifest.json'), 'new_provider_calls': 0, 'ledger_opened_or_modified': False, 'exit_code': int(not all(checks.values()))}
    with (HERE / 'r4-final-stop-independent-check.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
