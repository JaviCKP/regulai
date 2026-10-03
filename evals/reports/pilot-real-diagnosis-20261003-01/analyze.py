"""Read immutable pilot reports and replay local decisions; never open the live ledger."""
from collections import Counter
import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'evals/reports/pilot-real-vercel-20261003-01'
RUN = EVIDENCE / 'live-run-01'
OUTPUT = Path(__file__).resolve().parent / 'audit.json'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def total(values):
    return str(sum((Decimal(value) for value in values), Decimal(0)))


def exposure(call):
    cost, kind = call['cost'], call['metadata']['cost_kind']
    if cost is not None and kind in ('provider_reported', 'configured_zero', 'not_incurred'):
        return Decimal(cost)
    return max(Decimal(call['reserved']), Decimal(cost) if cost is not None else Decimal(0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    destination = parser.parse_args().output.resolve()
    if not destination.is_relative_to(Path(__file__).resolve().parent) or destination.exists():
        raise ValueError('Use a new report path inside .claude/real-run-diagnosis.')
    paths = [RUN / name for name in ('plan.json', 'manifest.json', 'results.jsonl', 'budget.json',
        'summary.json', 'completed-cases.jsonl', 'cases.executed.jsonl', 'human-review.pending.json')]
    paths += [EVIDENCE / name for name in ('live-result.json', 'live.stderr.log', 'live.stdout.log')]
    before = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    plan, final, budget = (read_json(RUN / name) for name in ('plan.json', 'manifest.json', 'budget.json'))
    rows = read_lines(RUN / 'results.jsonl')
    cases = {case['id']: case for case in read_lines(RUN / 'cases.executed.jsonl')}
    summaries = read_json(RUN / 'summary.json')
    pending = read_json(RUN / 'human-review.pending.json')
    calls = [call for row in rows for call in row['calls']]
    assert calls == budget['calls']
    assert len({call['id'] for call in calls}) == len(calls)
    order = [[row['case_id'], row['configuration']] for row in rows]
    assert order == plan['execution_order'][:len(rows)] == final['completed_order']
    assert read_lines(RUN / 'completed-cases.jsonl') == rows
    assert all(review['status'] == 'pending' and review['reviewer'] is None for review in pending)
    source_observed = {name: sha(ROOT / name) for name in plan['source_sha256']}
    assert plan['source_sha256'] == plan['source_sha256_observed']
    changed_sources = [name for name in source_observed if source_observed[name] != plan['source_sha256'][name]]
    replay_sources = ('classification.py', 'policy.py', 'verification.py', 'sources.py',
        'documents.py', 'masking.py', 'local_masking.py', 'management/commands/evaluate_ai.py')
    assert all('regulai/front/' + name not in changed_sources for name in replay_sources)
    source_equal = not changed_sources
    groups = []
    for configuration in plan['configurations']:
        selected = [row for row in rows if row['configuration'] == configuration]
        selected_calls = [call for row in selected for call in row['calls']]
        external = [call for call in selected_calls if call['metadata']['transport'] != 'local' and call['status'] != 'not_started']
        latencies = sorted(row['latency_ms'] for row in selected)
        group = {'configuration': configuration, 'n': len(selected),
            'delivered': sum(row['delivered'] for row in selected),
            'states': dict(Counter(row['execution_state'] for row in selected)),
            'external_calls': len(external), 'calls_by_purpose': dict(Counter(call['purpose'] for call in external)),
            'local_transformations': len(selected_calls) - len(external),
            'generation_attempts': sum(row['generation_calls'] for row in selected),
            'second_attempt_cases': sum(row['second_attempt'] for row in selected),
            'reported_usd': total(call['cost'] for call in selected_calls if call['metadata']['cost_kind'] == 'provider_reported'),
            'estimated_usd': total(call['cost'] for call in selected_calls if call['metadata']['cost_kind'] == 'tariff_estimate'),
            'unknown_reservations_usd': total(call['reserved'] for call in selected_calls if call['cost'] is None),
            'exposure_usd': str(sum((exposure(call) for call in selected_calls), Decimal(0))),
            'p50_ms': statistics.median(latencies), 'p95_ms': latencies[math.ceil(len(latencies) * .95) - 1]}
        stored = next(item for item in summaries if item['configuration'] == configuration and item['split'] == 'all')
        assert group['n'] == stored['n'] and group['external_calls'] == stored['provider_calls']
        assert group['local_transformations'] == stored['local_transformations']
        assert Decimal(group['reported_usd']) == Decimal(stored['provider_reported_usd'])
        assert Decimal(group['estimated_usd']) == Decimal(stored['tariff_estimated_usd'])
        assert group['p50_ms'] == stored['p50_latency_ms'] and group['p95_ms'] == stored['p95_latency_ms']
        assert stored['human_reviewed_n'] == 0 and stored['correct_answers'] is None
        assert stored['cost_per_correct_estimated_usd'] is None and stored['quality_claim'] is None and stored['savings_claim'] is None
        groups.append(group)
    reconstructed = {
        'known_cost_usd': total(call['cost'] for call in calls if call['cost'] is not None),
        'provider_reported_usd': total(call['cost'] for call in calls if call['metadata']['cost_kind'] == 'provider_reported'),
        'tariff_estimated_usd': total(call['cost'] for call in calls if call['metadata']['cost_kind'] == 'tariff_estimate'),
        'uncertain_reservations_usd': total(call['reserved'] for call in calls if call['cost'] is None),
        'budget_exposure_usd': str(sum((exposure(call) for call in calls), Decimal(0))),
    }
    for key, value in reconstructed.items():
        assert Decimal(value) == Decimal(budget[key]), key
    reconstructed['remaining_usd'] = str(Decimal(budget['cap_usd']) - Decimal(reconstructed['budget_exposure_usd']))
    assert Decimal(reconstructed['remaining_usd']) == Decimal(budget['remaining_usd'])
    reconstructed['estimated_generation_bounds_usd'] = total(call['reserved'] for call in calls if call['metadata']['cost_kind'] == 'tariff_estimate')
    reconstructed['extra_exposure_over_estimates_usd'] = str(Decimal(reconstructed['estimated_generation_bounds_usd']) - Decimal(reconstructed['tariff_estimated_usd']))

    sys.path.insert(0, str(ROOT / 'regulai'))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
    import django
    django.setup()
    from django.core.files.uploadedfile import SimpleUploadedFile
    from front.classification import decide
    from front.documents import extract_document
    from front.local_masking import mask_local_texts
    from front.management.commands.evaluate_ai import policy_config
    from front.policy import AIConfig
    from front.sources import build_sources
    from front.verification import verify_response

    replay = []
    with patch('socket.socket.connect', side_effect=AssertionError('Offline diagnosis forbids sockets')), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('Offline diagnosis forbids HTTP')), \
         patch('httpx.Client.send', side_effect=AssertionError('Offline diagnosis forbids SDK traffic')), \
         patch('django.db.backends.utils.CursorWrapper.execute', side_effect=AssertionError('Local replay needs no database')):
        for row in rows:
            case = cases[row['case_id']]
            cfg_dict = policy_config(case, row['configuration'], plan, SimpleNamespace(pk=1),
                {'economy': SimpleNamespace(pk=1), 'strong': SimpleNamespace(pk=2)}, SimpleNamespace(pk=1))
            cfg_dict['jev']['transport'] = plan['judge_transport']
            cfg = AIConfig.model_validate(cfg_dict)
            item = {'case_id': row['case_id'], 'configuration': row['configuration'],
                'signal_threshold': cfg.classification_policy.signal_threshold,
                'classification_confidence_threshold': cfg.jev.threshold,
                'verification_failure_cutoff_binary_float': 1 - cfg.verification.threshold}
            classification = next((call for call in row['receipt']['calls'] if call['purpose'] == 'classification'), None)
            if classification and 'signals' in classification:
                item['classification'] = asdict(decide(classification['signals'], cfg, cfg.local_sensitivity))
                item['manipulation_probability'] = classification['signals']['manipulation']['noul']
                if item['classification']['stop_code']:
                    assert item['classification']['stop_code'] == row['error_type']
            else:
                item['classification'] = None
            item['local_response_replays'] = []
            if row['generation_responses']:
                document = extract_document(SimpleUploadedFile('synthetic.txt', case['document'].encode('utf-8'))) if case.get('document') else None
                if document:
                    assert document.metadata() == row['coverage']
                    values = [case['input']] + [value for fragment in document.fragments for value in (fragment['text'], fragment['locator'])]
                    transformed = iter(mask_local_texts(values))
                    item['reconstructed_masked_request'] = next(transformed)
                    document.fragments = [{**fragment, 'text': next(transformed), 'locator': next(transformed)} for fragment in document.fragments]
                    sources = build_sources(document.fragments)
                    item['reconstructed_masked_sources'] = json.loads(sources.prompt_json)
                else:
                    sources = None
                generation_receipts = [call for call in row['receipt']['calls'] if call['purpose'] == 'generation']
                for response, receipt in zip(row['generation_responses'], generation_receipts, strict=True):
                    content = response['content']
                    content_hash = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
                    assert content_hash == response['content_sha256']
                    masked = mask_local_texts([content])[0]
                    checks = verify_response(masked, response['finish_reason'],
                        fragments=document.fragments if document else None,
                        alias_to_id=sources.alias_to_id if sources else None,
                        require_semantic=True, min_quote_chars=cfg.verification.min_quote_chars,
                        min_quote_words=cfg.verification.min_quote_words)
                    assert checks['local_status'] == receipt['verification']['local_status'] == 'passed'
                    item['local_response_replays'].append({'model': response['model'],
                        'content_sha256': response['content_sha256'], 'mask_changed_content': masked != content,
                        'local_status': checks['local_status'], 'checks': checks['checks'], 'evidence': checks['evidence']})
            item['semantic_replays'] = []
            for receipt in row['receipt']['calls']:
                if receipt['purpose'] == 'verification' and 'signals' in receipt:
                    failed = {key: answer['noul'] for key, answer in receipt['signals'].items()
                              if answer['noul'] > 1 - cfg.verification.threshold}
                    item['semantic_replays'].append({'signals': receipt['signals'], 'failed_signals': failed,
                        'status': 'failed' if failed else 'passed'})
            if item['semantic_replays']:
                assert item['semantic_replays'][-1]['status'] == row['verification']['status']
            replay.append(item)
    after = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    assert before == after
    result = {'basis_commit': plan['commit'], 'source_hashes_match': source_equal,
        'changed_sources_since_basis': changed_sources, 'replayed_source_hashes_match': True,
        'evidence_sha256': before, 'evidence_unchanged_after_replay': True,
        'planned_combinations': len(plan['execution_order']), 'recorded_combinations': len(rows),
        'unique_cases_started': len({row['case_id'] for row in rows}),
        'not_started_order': plan['execution_order'][len(rows):],
        'observed_order': order, 'stop_reason': final['stop_reason'],
        'accounting_entries': len(calls), 'external_calls': sum(group['external_calls'] for group in groups),
        'local_transformations': sum(group['local_transformations'] for group in groups),
        'states': dict(Counter(row['execution_state'] for row in rows)),
        'groups': groups, 'budget_recomputed': reconstructed,
        'local_replay': replay, 'human_reviewed_n': 0,
        'new_product_calls': 0, 'new_actual_spend_usd': '0',
        'limits': ['No live ledger or user database opened.', 'Full failed provider body and error code were not retained.',
            'Reconstructed masked state is a local replay, not a captured live outbound request.',
            'control_pass means control invariants only in real mode; expected_status applies to offline mode only.',
            'Known cost mixes reported and estimated amounts; it is not an invoice.',
            'A halted partial sample is not a balanced comparison of configurations.']}
    with destination.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(destination.relative_to(ROOT)), 'sha256': sha(destination),
        'recorded_combinations': len(rows), 'external_calls': result['external_calls'],
        'local_transformations': result['local_transformations'], 'replay_passed': True}, ensure_ascii=True))


if __name__ == '__main__':
    main()
