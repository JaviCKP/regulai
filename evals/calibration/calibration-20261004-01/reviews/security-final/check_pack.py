"""Independent manifest checks; no credentials, sockets, ledger or user DB."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
COMMIT = '3940fdc698c34998b2541309b0b697b6c06c2287'
PACK = REPO / 'evals/calibration/calibration-20261004-01/batches/baseline-smoke-02'
CAMPAIGN = PACK.parent.parent


def checked_bytes(path):
    path = Path(path).resolve()
    relative = path.relative_to(REPO).as_posix()
    if '/reserved/' in relative or relative.endswith('scripts/build_calibration_corpus.py'):
        raise AssertionError('Reserved contents cannot enter this review.')
    return path.read_bytes()


def sha(path):
    return hashlib.sha256(checked_bytes(path)).hexdigest()


def read(path):
    return json.loads(checked_bytes(path))


def main():
    manifest = read(PACK / 'manifest.json')
    approval = read(PACK / 'authorization.json')
    cases = [json.loads(line) for line in checked_bytes(PACK / 'cases.jsonl').splitlines()]
    manifest_hash = sha(PACK / 'manifest.json')
    checks = {}
    checks['exact_manifest'] = manifest_hash == '140b78da56b9fccf0307fe6612a0d9b1ce2826fad6a65bd21ef9e900bafd1fe5'
    checks['fixed_runtime_commit'] = manifest['source_runtime_commit'] == COMMIT
    checks['approved_manifest'] = approval['manifest_sha256s'] == [manifest_hash]
    checks['dataset_hash'] = sha(PACK / manifest['dataset']) == manifest['dataset_sha256']
    checks['rubric_hash'] = sha(PACK / manifest['human_rubric']) == manifest['human_rubric_sha256']
    checks['references_hash'] = all(sha(PACK / name) == expected for name, expected in manifest['reference_label_sha256'].items())
    checks['frozen_files_hashes'] = all(sha(REPO / name) == expected for name, expected in manifest['campaign_frozen_files'].items())
    checks['runtime_working_files_match_manifest'] = all(sha(REPO / name) == expected for name, expected in manifest['source_sha256'].items())
    changed_sources = []
    eol_only_sources = []
    for name, expected in {**manifest['source_sha256'], 'scripts/run_calibration_campaign.py': manifest['campaign_frozen_files']['scripts/run_calibration_campaign.py']}.items():
        value = subprocess.check_output(['rtk', 'proxy', 'git', 'show', COMMIT + ':' + name], cwd=REPO)
        if hashlib.sha256(value).hexdigest() != expected:
            if checked_bytes(REPO / name).replace(b'\r\n', b'\n') == value.replace(b'\r\n', b'\n'):
                eol_only_sources.append(name)
            else:
                changed_sources.append(name)
    checks['runtime_fixed_commit_match_manifest'] = not changed_sources
    checks['scope_ids'] = approval['execution_scope']['case_ids'] == [row['id'] for row in cases]
    checks['development_only'] = all(row['split'] == 'development' for row in cases)
    checks['categories'] = set(row['group'] for row in cases) == {'legitimate', 'pii', 'documentary', 'injection'}
    development = [json.loads(line) for line in checked_bytes(CAMPAIGN / 'corpus/development/cases.jsonl').splitlines()]
    originals = {row['id']: row for row in development}
    checks['previously_reviewed_synthetic_cases'] = all(originals[row['id']]['provider_reviewed'] is True for row in cases)
    checks['same_frozen_prompts'] = all(originals[row['id']]['prompt'] == row['input'] for row in cases)
    checks['no_reference_fields_in_cases'] = all(not {'oracle', 'expected_answer', 'expected_classification', 'family_id', 'license'} & row.keys() for row in cases)
    checks['bounded_execution_scope'] = approval['execution_scope'] == {'case_ids': [row['id'] for row in cases], 'configurations': ['economy', 'strong', 'router'], 'max_runs': 1, 'max_combinations': 12, 'max_external_calls': 44, 'repeat_uncertain_calls': False}
    decision = read(CAMPAIGN / 'economics/decision.json')
    historical = Decimal(decision['historical_exposure_usd'])
    worst = 4 * (4 * Decimal('.014') + 7 * Decimal('.003'))
    cap = Decimal(manifest['maximum_usd'])
    terms = manifest['campaign_budget']
    checks['worst_additional'] = worst == Decimal(manifest['maximum_additional_exposure_usd']) == Decimal('.308')
    checks['baseline_phase_fits'] = worst <= Decimal(decision['initial_phase_allocations_usd']['baseline'])
    checks['aggregate_fits_after_history'] = historical + worst <= cap
    checks['eur_limit_with_margin'] = cap * (1 + Decimal(terms['margin'])) / Decimal(terms['fx_provenance']['rate_usd_per_eur']) <= Decimal('2')
    now = datetime.now(timezone.utc)
    checks['within_window'] = datetime.fromisoformat(terms['starts_at']) <= now < datetime.fromisoformat(terms['expires_at'])
    checks['same_campaign_terms'] = approval['campaign_budget'] == terms
    bridge = read(PACK / 'preflight-bridge.json')
    checks['central_bridge_evidence'] = bridge['exit_code'] == 0 and bridge['source_database_unchanged'] is True and bridge['source_database_open_mode'] == 'ro' and bridge['manifest_sha256'] == manifest_hash and bridge['authorization_sha256'] == sha(PACK / 'authorization.json')
    result = {'commit': COMMIT, 'compared_to': '9d7f942', 'reviewed_at_utc': now.isoformat(), 'manifest_sha256': manifest_hash, 'authorization_sha256': sha(PACK / 'authorization.json'), 'checks': checks, 'all_passed': all(checks.values()), 'changed_sources': changed_sources, 'git_crlf_checkout_only': eol_only_sources, 'source_comparison': 'Exact frozen working-byte hashes plus exact Git blob equality after CRLF-to-LF only', 'maximum_external_calls': 44, 'worst_additional_usd': str(worst), 'historical_exposure_from_frozen_decision_usd': str(historical), 'max_eur_including_margin': str(cap * (1 + Decimal(terms['margin'])) / Decimal(terms['fx_provenance']['rate_usd_per_eur'])), 'network_calls': 0, 'user_database_opened': False, 'ledger_opened': False, 'credentials_read': False, 'reserved_contents_read': False, 'exit_code': int(not all(checks.values()))}
    output = HERE / 'baseline-smoke-02-independent-check-eol.json'
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))
    return int(not result['all_passed'])


if __name__ == '__main__':
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('No review network')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('No review DNS')):
        raise SystemExit(main())
