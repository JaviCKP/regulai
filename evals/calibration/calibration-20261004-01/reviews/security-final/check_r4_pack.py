"""Read only public R4 artifacts. Never open a ledger, DB or credential bridge."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

from check_pack import HERE, REPO, checked_bytes, read, sha

COMMIT = 'b3fea6a63761c06ef66695fee26377d23786c347'
EXPECTED = '07c306ebf6e5ad258b3ad4a282cb34476e4d6f370d07d7a47fddb0fc19ed56d6'
CAMPAIGN = REPO / 'evals/calibration/calibration-20261004-01'
PACK = CAMPAIGN / 'batches/r4-smoke-01'
BASE = CAMPAIGN / 'batches/baseline-smoke-02'
PREVIOUS = CAMPAIGN / 'batches/candidate-smoke-01'


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    m, a, old = read(PACK / 'manifest.json'), read(PACK / 'authorization.json'), read(PREVIOUS / 'authorization.json')
    budget = read(PREVIOUS / 'live-run-01/budget.json')
    decision = read(CAMPAIGN / 'economics/decision.json')
    checks = {}
    checks['exact_manifest'] = sha(PACK / 'manifest.json') == EXPECTED and a['manifest_sha256s'] == [EXPECTED]
    checks['fixed_runtime_commit'] = m['source_runtime_commit'] == COMMIT
    checks['source_working_bytes'] = all(sha(REPO / p) == h for p, h in m['source_sha256'].items())
    checks['campaign_frozen_bytes'] = all(sha(REPO / p) == h for p, h in m['campaign_frozen_files'].items())
    changed = []
    eol_only = []
    for p in [*m['source_sha256'], 'scripts/run_calibration_campaign.py']:
        original = subprocess.check_output(['rtk', 'proxy', 'git', 'show', COMMIT + ':' + p], cwd=REPO)
        actual = checked_bytes(REPO / p)
        if actual != original:
            (eol_only if actual.replace(b'\r\n', b'\n') == original.replace(b'\r\n', b'\n') else changed).append(p)
    checks['fixed_commit_sources'] = not changed
    checks['same_frozen_sample'] = all(sha(PACK / p) == sha(BASE / p) for p in ('cases.jsonl', 'oracles.json', 'rubric.md'))
    checks['dataset_hash'] = sha(PACK / m['dataset']) == m['dataset_sha256']
    checks['rubric_hash'] = sha(PACK / m['human_rubric']) == m['human_rubric_sha256']
    checks['reference_hashes'] = all(sha(PACK / p) == h for p, h in m['reference_label_sha256'].items())
    checks['extends_latest_completed_pack'] = a['extends'] == {'authorization_id': old['authorization_id'], 'authorization_digest': canonical_hash(old)}
    checks['single_policy_change'] = m['policy_revision'] == 2 and m['classification_policy_override'] == {'manipulation_threshold': .4}
    checks['candidate_phase_only'] = m['campaign_variant'] == 'candidate' and m['campaign_phase'] == 'development'
    checks['masker_v5'] = m['masking']['backend'] == 'local' and m['masking']['detector_version'] == 'regulai-local-v5'
    checks['scope_and_bounds_unchanged'] = a['execution_scope'] == read(BASE / 'authorization.json')['execution_scope'] and m['call_caps_usd'] == read(BASE / 'manifest.json')['call_caps_usd']
    checks['controls_enforced'] = m['classification_mode'] == 'required' and m['verification_mode'] == 'enforce' and m['max_generation_attempts'] == {'economy': 1, 'strong': 1, 'router': 2}
    checks['same_aggregate_terms'] = m['campaign_budget'] == a['campaign_budget'] == read(BASE / 'manifest.json')['campaign_budget']
    checks['same_aggregate_cap'] = m['maximum_usd'] == a['maximum_usd'] == budget['cap_usd'] == '1.66'
    checks['same_destinations_models'] = m['destinations'] == read(BASE / 'manifest.json')['destinations'] and m['model_versions'] == read(BASE / 'manifest.json')['model_versions']
    additional = Decimal(m['maximum_additional_exposure_usd'])
    exposure = Decimal(budget['budget_exposure_usd'])
    limit = Decimal('1.66') - Decimal(decision['initial_phase_allocations_usd']['confirmation'])
    checks['maximum_additional'] = additional == Decimal('.308')
    checks['complete_phase_fits_latest_snapshot'] = exposure + additional <= limit
    checks['historical_uncertain_retained'] = Decimal(budget['uncertain_reservations_usd']) >= Decimal('.003')
    now = datetime.now(timezone.utc)
    checks['window_active'] = datetime.fromisoformat(a['valid_from']) <= now < datetime.fromisoformat(a['valid_until'])
    output = {'commit': COMMIT, 'compared_to': '3940fdc', 'reviewed_at_utc': now.isoformat(), 'manifest_sha256': sha(PACK / 'manifest.json'), 'authorization_sha256': sha(PACK / 'authorization.json'), 'latest_budget_artifact_sha256': sha(PREVIOUS / 'live-run-01/budget.json'), 'checks': checks, 'all_passed': all(checks.values()), 'source_changes': changed, 'git_crlf_checkout_only': eol_only, 'budget_snapshot_exposure_usd': str(exposure), 'worst_after_batch_usd': str(exposure + additional), 'development_phase_cap_usd': str(limit), 'confirmation_preserved_usd': decision['initial_phase_allocations_usd']['confirmation'], 'network_calls': 0, 'ledger_opened': False, 'user_database_opened': False, 'credentials_read': False, 'reserved_contents_read': False, 'exit_code': int(not all(checks.values()))}
    with (HERE / 'r4-smoke-01-independent-check.json').open('x', encoding='utf-8') as handle:
        json.dump(output, handle, indent=2)
        handle.write('\n')
    print(json.dumps(output, indent=2))
    return output['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
