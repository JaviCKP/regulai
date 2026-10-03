"""Summarize two immutable live runs without importing the product or using a network."""
import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / 'evals/reports'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def total_cost(calls):
    reported = estimated = uncertain = exposure = Decimal(0)
    for call in calls:
        cost = Decimal(call['cost']) if call['cost'] is not None else None
        bound = Decimal(call['reserved'])
        kind = call['metadata'].get('cost_kind', 'provider_reported')
        if cost is None:
            uncertain += bound
        elif kind == 'provider_reported':
            reported += cost
        elif kind == 'tariff_estimate':
            estimated += cost
        exposure += (cost if cost is not None and kind in
                     {'provider_reported', 'configured_zero', 'not_incurred'}
                     else max(bound, cost or Decimal(0)))
    return {key: str(value) for key, value in {
        'provider_reported_usd': reported, 'tariff_estimated_usd': estimated,
        'uncertain_reservations_usd': uncertain, 'budget_exposure_usd': exposure}.items()}


def summarize(rows):
    calls = [call for row in rows for call in row['calls']]
    assert len({call['id'] for call in calls}) == len(calls)
    latency = sorted(row['latency_ms'] for row in rows)
    external = [call for call in calls if call['metadata']['transport'] == 'http']
    return {
        'n': len(rows), 'distinct_cases': len({row['case_id'] for row in rows}),
        'delivered': sum(row['delivered'] for row in rows),
        'states': dict(Counter(row['execution_state'] for row in rows)),
        'errors': dict(Counter(row['error_type'] or 'none' for row in rows)),
        'second_attempts': sum(row['second_attempt'] for row in rows),
        'external_calls': len(external), 'local_transformations': len(calls) - len(external),
        'external_calls_by_purpose': dict(Counter(call['purpose'] for call in external)),
        'p50_latency_ms': statistics.median(latency),
        'p95_latency_ms': latency[math.ceil(0.95 * len(latency)) - 1],
        'p95_method': 'nearest_rank', 'latency_includes_blocks': True,
        'costs': total_cost(calls), 'human_reviewed_n': 0,
        'quality_accuracy': None, 'cost_per_correct_answer': None, 'savings_claim': None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(REPORTS.resolve()):
        raise ValueError('Output must be a new directory inside evals/reports')
    output.mkdir(parents=True, exist_ok=False)
    corpus_path = ROOT / 'evals/adversarial/community-20261003/cases.jsonl'
    corpus = {row['id']: row for row in read_rows(corpus_path)}
    reference_manifest = read_json(ROOT / 'evals/adversarial-live/community-additional-20261003/manifest.json')
    assert reference_manifest['source_runtime_commit'] == '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2'
    inputs = {str(corpus_path.relative_to(ROOT)): sha256(corpus_path.read_bytes()).hexdigest()}
    rows, run_summaries, budgets = [], [], []
    for suffix in ('01', '02'):
        folder = REPORTS / ('adversarial-real-20261003-' + suffix)
        source = folder / 'live-run-01'
        for path in (source / 'results.jsonl', source / 'budget.json', source / 'manifest.json',
                     folder / 'live-result.json'):
            inputs[str(path.relative_to(ROOT))] = sha256(path.read_bytes()).hexdigest()
        batch = read_rows(source / 'results.jsonl')
        manifest, result = read_json(source / 'manifest.json'), read_json(folder / 'live-result.json')
        assert len(batch) == 12 and result['exit_code'] == 0 and result['source_database_unchanged']
        assert manifest['source_sha256'] == reference_manifest['source_sha256']
        assert manifest['corpus_dataset_sha256'] == inputs[str(corpus_path.relative_to(ROOT))]
        for row in batch:
            assert row['mode'] == 'real' and row['human_review'] is None
            for generation in row['generation_responses']:
                assert not generation['omitted_over_limit']
                # evaluation.digest hashes the canonical JSON string, including its quotes.
                encoded = json.dumps(generation['content'], ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()
                assert sha256(encoded).hexdigest() == generation['content_sha256']
        run_summaries.append({'run': suffix, **summarize(batch),
            'started_utc': result['started_utc'], 'finished_utc': result['finished_utc']})
        budgets.append(read_json(source / 'budget.json'))
        rows.extend(batch)
    assert len({(row['case_id'], row['configuration']) for row in rows}) == 24
    assert budgets[1]['calls'][:len(budgets[0]['calls'])] == budgets[0]['calls']
    all_new = [call for row in rows for call in row['calls']]
    new_ids = {call['id'] for call in all_new}
    assert {call['id'] for call in budgets[1]['calls'] if call['id'] in new_ids} == new_ids
    assert len(all_new) == 81
    for key, value in total_cost(budgets[1]['calls']).items():
        assert Decimal(value) == Decimal(budgets[1][key])
    summary = {
        'runtime_of_observed_calls': '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2',
        'input_sha256': inputs, 'runs': run_summaries, 'combined': summarize(rows),
        'configurations': {config: summarize([row for row in rows if row['configuration'] == config])
                           for config in ('economy', 'strong', 'router')},
        'budget_cumulative_including_earlier_trial': {key: value for key, value in budgets[-1].items()
                                                   if key != 'calls'},
        'prior_ledger_entries_preserved_in_second_snapshot': len(budgets[0]['calls']),
        'generation_response_hashes_verified': sum(len(row['generation_responses']) for row in rows),
        'new_network_calls_by_this_script': 0, 'database_opened': False,
        'human_review_complete': False,
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Las 24 respuestas observadas', '',
        'Dos pasadas reales del 3 de octubre de 2026 sobre `128d66a`. Las generaciones son el texto conservado antes de la máscara de salida; solo **Entregada: sí** llegó al usuario del ensayo. El estado exacto enviado al juez no se conservó. Revisión técnica por agentes; revisión humana pendiente.', '']
    normalized = []
    for row in sorted(rows, key=lambda item: (item['case_id'], item['configuration'])):
        oracle = corpus[row['case_id']]
        signals = [{'purpose': call['purpose'], 'threshold': call.get('threshold'), 'signals': call['signals']}
                   for call in row['receipt']['calls'] if call.get('signals')]
        normalized.append({'case_id': row['case_id'], 'configuration': row['configuration'],
            'expected_category': oracle['classification'], 'prompt': oracle['prompt'],
            'document_ref': oracle['document_ref'], 'desired_semantic_behavior': oracle['desired_semantic_behavior'],
            'observed_state': row['execution_state'], 'error_type': row['error_type'],
            'delivered': row['delivered'], 'delivered_answer': row['answer'],
            'generation_responses_before_output_mask': row['generation_responses'], 'signals': signals,
            'local_and_semantic_checks': row['verification'], 'evidence': row['evidence'],
            'latency_ms': row['latency_ms'], 'costs': total_cost(row['calls']), 'human_review': None})
        lines += [f"## {row['case_id']} / {row['configuration']} — {oracle['title']}", '',
            '**Prompt:** ' + oracle['prompt'], '',
            '**Esperado:** ' + oracle['desired_semantic_behavior'], '',
            f"**Estado:** {row['execution_state']}; error: {row['error_type'] or 'ninguno'}; **entregada: {'sí' if row['delivered'] else 'no'}**.", '']
        if row['answer']:
            lines += ['**Texto entregado:**', '', '```text', row['answer'], '```', '']
        if not row['generation_responses']:
            lines += ['El bloqueo ocurrió antes de generar; no hay respuesta de DeepSeek para valorar.', '']
        for index, generation in enumerate(row['generation_responses'], 1):
            lines += [f"**Generación {index} ({generation['model']}), previa a máscara de salida:**", '',
                      '```text', generation['content'], '```', '']
        lines += ['**Señales registradas:**', '', '```json',
                  json.dumps(signals, ensure_ascii=False, indent=2), '```', '']
    (output / 'cases.json').write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'responses.md').write_text('\n'.join(lines), encoding='utf-8')
    hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir()) if path.is_file()}
    (output / 'artifact-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    (output / '.gitattributes').write_text('* -text\n', encoding='utf-8')
    print(json.dumps({'output': str(output.relative_to(ROOT)), **summary['combined']}, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
