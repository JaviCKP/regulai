"""Verify final JSON evidence only. Never open SQLite, reserved cases, or the network."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import socket
from unittest.mock import patch

from check_pack import HERE, REPO, read, sha

CAMPAIGN = REPO / 'evals/calibration/calibration-20261004-01'
FINAL = CAMPAIGN / 'economics/final-reconciliation-01'
SHA = 'b3fea6a63761c06ef66695fee26377d23786c347'
PACKS = ('baseline-smoke-02', 'candidate-smoke-01', 'r4-smoke-01')
FIELDS = ('known_cost_usd', 'provider_reported_usd', 'tariff_estimated_usd',
          'budget_exposure_usd', 'uncertain_reservations_usd')


def canonical_sha(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def totals(calls):
    value = dict.fromkeys(FIELDS, Decimal(0))
    for call in calls:
        bound = Decimal(call['reserved'])
        cost = None if call['cost'] is None else Decimal(call['cost'])
        kind = call['metadata'].get('cost_kind', 'provider_reported')
        if cost is None:
            value['uncertain_reservations_usd'] += bound
        else:
            value['known_cost_usd'] += cost
            if kind in ('provider_reported', 'tariff_estimate'):
                key = 'provider_reported_usd' if kind == 'provider_reported' else 'tariff_estimated_usd'
                value[key] += cost
        value['budget_exposure_usd'] += (
            cost if cost is not None and kind in ('provider_reported', 'configured_zero', 'not_incurred')
            else max(bound, cost or Decimal(0)))
    return value


def equal_totals(left, right):
    return all(Decimal(left[key]) == Decimal(right[key]) for key in FIELDS)


def main():
    summary = read(FINAL / 'summary.json')
    snapshot = read(FINAL / 'ledger-snapshot.json')
    chain = read(FINAL / 'authorization-chain.json')
    historical = read(CAMPAIGN / 'batches/baseline-smoke-02/activation.json')['snapshot']
    last_runtime = read(CAMPAIGN / 'batches/r4-smoke-01/live-run-01/budget.json')
    selection = read(CAMPAIGN / 'final_selection.json')
    configuration = read(CAMPAIGN / selection['candidate_configuration'])
    old, calls = historical['calls'], snapshot['calls']
    current = calls[len(old):]
    external = [c for c in current if c['metadata'].get('scope_external_call') is True]
    local = [c for c in current if c['metadata'].get('transport') == 'local']
    unknown = [c for c in calls if c['cost'] is None]
    computed = totals(calls)
    increments = totals(current)
    terms = summary['campaign_terms']
    eur = computed['budget_exposure_usd'] * (1 + Decimal(terms['margin'])) / Decimal(terms['fx_provenance']['rate_usd_per_eur'])
    extensions = chain['extensions']
    by_auth = {item['id']: item for item in extensions}
    by_run = {item['authorization_id']: item for item in chain['runs']}
    checks = {
        'snapshot_equals_last_runtime': snapshot == last_runtime,
        'historical_prefix_unchanged': len(old) == 110 and calls[:len(old)] == old,
        'unique_ledger_call_ids': len(calls) == len({c['id'] for c in calls}),
        'entry_counts': len(calls) == summary['all_ledger_entries_n'] == 199 and len(current) == summary['campaign_entries_n'] == 89,
        'campaign_entry_status': dict(Counter(c['status'] for c in current)) == summary['campaign_entry_status'] == {'completed': 88, 'outcome_unknown': 1},
        'external_call_count_and_types': len(external) == summary['campaign_external_calls_n'] == 49 and all(c['metadata']['transport'] == 'http' for c in external),
        'external_purpose_counts': dict(Counter(c['purpose'] for c in external)) == summary['campaign_external_calls_by_purpose'] == {'classification': 29, 'generation': 11, 'verification': 9},
        'forty_local_zero_calls': len(local) == 40 and len(local) + len(external) == len(current) and all(Decimal(c['cost']) == Decimal(c['reserved']) == 0 and c['metadata']['cost_kind'] == 'configured_zero' and c['metadata']['scope_external_call'] is False for c in local),
        'all_totals_recompute': equal_totals(computed, summary['total']) and equal_totals(computed, snapshot),
        'historical_totals_recompute': equal_totals(totals(old), summary['historical']) and equal_totals(totals(old), historical),
        'increments_recompute': equal_totals(increments, summary['campaign_increment']) and all(computed[k] == totals(old)[k] + increments[k] for k in FIELDS),
        'known_reported_estimated_are_distinct': computed['known_cost_usd'] == computed['provider_reported_usd'] + computed['tariff_estimated_usd'],
        'uncertain_reservations_retained': unknown == summary['uncertain_calls'] and len(unknown) == 2 and all(c['status'] == 'outcome_unknown' and Decimal(c['reserved']) == Decimal('.003') and c['metadata']['cost_kind'] == 'unknown' for c in unknown) and computed['uncertain_reservations_usd'] == Decimal('.006'),
        'last_unknown_is_final_entry': calls[-1] == unknown[-1] and calls[-1]['id'] == 'fa61b595-536f-4eac-b455-7c5cdd40c19c' and calls[-1]['metadata']['provider_error_code'] == 'invalid_response' and max(datetime.fromisoformat(c['at']) for c in calls) == datetime.fromisoformat(calls[-1]['at']),
        'invalid_charge_not_settled': unknown[-1]['cost'] is None and summary['unvalidated_charge_in_invalid_response_usd'] == '0.000035742' and computed['provider_reported_usd'] == Decimal('.002794596'),
        'cap_and_margin': Decimal(summary['cap_usd']) == Decimal(terms['approved_ceiling_usd']) == Decimal('1.66') and Decimal(summary['cap_eur']) == Decimal(terms['approved_ceiling_eur']) == Decimal('2') and computed['budget_exposure_usd'] < Decimal('1.66') and eur == Decimal(summary['conservative_total_exposure_eur']) < Decimal('2'),
        'remaining_recomputes': Decimal(summary['remaining_usd']) == Decimal(snapshot['remaining_usd']) == Decimal('1.66') - computed['budget_exposure_usd'],
        'explicit_mandatory_stop': summary['stop_new_paid_calls'] is True and selection['stop_new_paid_calls'] is True and selection['post_holdout_tuning_permitted'] is False,
        'reconciliation_readonly_recorded': summary['database_open_mode'] == 'ro' and summary['query_only'] is True and summary['ledger_bytes_unchanged'] is True and summary['historical_calls_unchanged'] is True and summary['matches_final_runtime_snapshot'] is True,
        'reconciliation_source_hashes': all(sha(REPO / name.replace('\\', '/')) == expected for name, expected in summary['source_sha256'].items()),
        'extension_sequence_contiguous': [e['sequence'] for e in extensions] == list(range(1, len(extensions) + 1)) and all((next_item['previous_id'], next_item['previous_digest']) == (item['id'], item['digest']) for item, next_item in zip(extensions, extensions[1:])),
        'extension_identities_unique': len(by_auth) == len(extensions) == len({e['digest'] for e in extensions}) == 5,
        'authorization_head_is_final_extension': summary['authorization_head'] == [extensions[-1]['id'], extensions[-1]['digest']],
        'exactly_one_run_per_extension': len(by_run) == len(chain['runs']) == len(by_auth) and set(by_run) == set(by_auth) and len({r['run_id'] for r in chain['runs']}) == len(by_run) and all(r['manifest_sha256'] == by_auth[r['authorization_id']]['manifest_sha256'] for r in chain['runs']),
        'all_campaign_calls_match_chain': all(c['metadata']['authorization_digest'] == by_auth[c['metadata']['authorization_id']]['digest'] and c['metadata']['manifest_sha256'] == by_auth[c['metadata']['authorization_id']]['manifest_sha256'] and c['metadata']['run_id'] == by_run[c['metadata']['authorization_id']]['run_id'] for c in current),
        'calls_within_original_window': all(datetime.fromisoformat(terms['starts_at']) <= datetime.fromisoformat(c['at']) < datetime.fromisoformat(terms['expires_at']) for c in current),
        'run_and_authorization_precede_calls': all(datetime.fromisoformat(by_auth[c['metadata']['authorization_id']]['at']) <= datetime.fromisoformat(by_run[c['metadata']['authorization_id']]['at']) <= datetime.fromisoformat(c['at']) for c in current),
        'final_candidate_exact_hash': sha(CAMPAIGN / selection['candidate_configuration']) == selection['candidate_configuration_sha256'],
        'final_candidate_legacy_policy': selection['candidate_commit'] == configuration['candidate_commit'] == SHA and configuration['policy']['classification_policy']['manipulation_threshold'] is None and configuration['policy']['classification_policy']['signal_threshold'] == .2 and configuration['policy']['classification'] == 'required' and configuration['policy']['verification_mode'] == 'enforce',
        'final_selection_evidence_hashes': all(sha(CAMPAIGN / name) == expected for name, expected in selection['evidence_sha256'].items()),
    }
    for name in PACKS:
        pack = CAMPAIGN / 'batches' / name
        authorization = read(pack / 'authorization.json')
        manifest_hash = sha(pack / 'manifest.json')
        extension = by_auth[authorization['authorization_id']]
        scoped = [c for c in external if c['metadata']['authorization_id'] == extension['id']]
        checks[name + '_chain_digest_manifest_scope'] = (
            canonical_sha(authorization) == extension['digest']
            and manifest_hash == extension['manifest_sha256']
            and authorization['manifest_sha256s'] == [manifest_hash]
            and authorization['extends'] == {'authorization_id': extension['previous_id'], 'authorization_digest': extension['previous_digest']}
            and authorization['execution_scope']['max_runs'] == 1
            and authorization['execution_scope']['repeat_uncertain_calls'] is False
            and len(scoped) <= authorization['execution_scope']['max_external_calls'] == extension['max_external_calls'] == 44
            and authorization['campaign_budget'] == terms
            and all(c['metadata']['case_id'] in authorization['execution_scope']['case_ids'] and c['metadata']['configuration'] in authorization['execution_scope']['configurations'] for c in scoped))
    gates = read(CAMPAIGN / 'gates-02/manifest.json')
    r4 = read(CAMPAIGN / 'batches/r4-smoke-01/manifest.json')
    checks['gate_fixed_source'] = gates['revision'] == SHA and gates['source_unchanged'] is True and all(gates['source_sha256'][name] == expected == sha(REPO / name) for name, expected in r4['source_sha256'].items())
    checks['gate_logs_and_exit_codes'] = all(c['exit_code'] == 0 and sha(CAMPAIGN / 'gates-02' / c['log']) == c['sha256'] for c in gates['commands']) and {'check', 'front-api', 'migrations', 'offline', 'dependencies'} <= {c['gate'] for c in gates['commands']}
    reserve_summaries = {}
    for name in ('reserved-base-01', 'reserved-candidate-01'):
        directory = CAMPAIGN / 'evaluation' / name
        item, hashes = read(directory / 'summary.json'), read(directory / 'artifact-hashes.json')
        reserve_summaries[name] = item
        checks[name + '_summary_hash'] = sha(directory / 'summary.json') == hashes['summary.json']
        checks[name + '_local_only_integrity'] = item['cases_n'] == 571 and item['families_n'] == 372 and item['http_runs'] == 120 and item['http_controls_passed'] == 114 and item['local_errors'] == 0 and item['changed_sources_during_execution'] == [] and set(item['network_attempts'].values()) == {0} and Decimal(item['real_api_cost_usd']) == 0 and item['semantic_quality_measured'] is False and item['exit_code'] == 0
    checks['reserved_aggregate_tie'] = reserve_summaries['reserved-base-01'] == reserve_summaries['reserved-candidate-01']
    artifacts = [FINAL / name for name in ('summary.json', 'ledger-snapshot.json', 'authorization-chain.json')]
    artifacts += [CAMPAIGN / name for name in ('reconcile.py', 'final_selection.json', 'final-candidate-configuration.json', 'gates-02/manifest.json')]
    artifacts += [CAMPAIGN / 'evaluation' / name / 'summary.json' for name in reserve_summaries]
    result = {
        'reviewed_utc': datetime.now(timezone.utc).isoformat(), 'fixed_runtime_commit': SHA,
        'checks': checks, 'all_passed': all(checks.values()),
        'totals': {k: str(v) for k, v in computed.items()},
        'exposure_eur_with_margin': str(eur),
        'campaign_external_calls_per_scope': dict(Counter(c['metadata']['authorization_id'] for c in external)),
        'reserved_summary_limits': {'http_passed_per_arm': 114, 'http_total_per_arm': 120, 'local_annotation_passed_per_arm': 239, 'annotated_per_arm': 290, 'semantic_quality_measured': False, 'individual_reserved_cases_read': False},
        'evidence_sha256': {p.relative_to(CAMPAIGN).as_posix(): sha(p) for p in artifacts},
        'recorded_ledger_sha256': summary['ledger_sha256'],
        'ledger_or_user_database_opened': False, 'provider_calls': 0,
        'reconciliation_script_executed_by_reviewer': False,
        'new_payments_permitted': False, 'exit_code': int(not all(checks.values())),
    }
    with (HERE / 'final-reconciliation-independent-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return result['exit_code']


if __name__ == '__main__':
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('No review network')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('No review DNS')):
        raise SystemExit(main())
