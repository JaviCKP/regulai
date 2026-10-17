"""Summarize the formal baseline rounds 7/8/9 and final after rounds 10/11/12; no runtime access.

Usage: rtk proxy python ops/agent_chat/latency_report.py
Writes summary.json and summary.md below output/latency-optimization-20261017.
Exit 0 means a complete comparable dataset; exit 2 means missing/invalid evidence.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
ROUNDS = {'baseline': (7, 8, 9), 'after': (10, 11, 12)}
ENTRIES = ('/chat/', '/chat/send/', '/api/chat/send/')
METRICS = ('queue_s', 'preparation_s', 'first_inference_s', 'entry_to_provider_s',
           'inference_http_to_provider_s')
IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}')


def distribution(values):
    """Median plus nearest-rank p95: ordered[ceil(0.95*n)-1], no interpolation."""
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'min': round(values[0], 6),
            'median': round(statistics.median(values), 6),
            'p95': round(values[math.ceil(.95 * len(values)) - 1], 6),
            'max': round(values[-1], 6)}


def read_json(path, issues, *, optional=False):
    if not path.exists():
        if not optional:
            issues.append(f'Falta {path.name}.')
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError):
        issues.append(f'{path.name}: JSON inválido o ilegible.')
        return None


def immutable_images(report):
    result = report.get('image_ids', report.get('images', {}))
    if (not isinstance(result, dict) or set(result) != {'web', 'worker'}
            or not all(isinstance(value, str) and IMAGE_ID.fullmatch(value) for value in result.values())):
        return None
    return result


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def valid_sql(value, *, require_select=True):
    return (isinstance(value, dict) and (not require_select or 'SELECT' in value)
            and all(isinstance(key, str) and key.isalpha() and key.isupper()
                    and type(count) is int and count >= 0 for key, count in value.items()))


def validate_round(report, variant, number, issues):
    name = f'bench-{variant}-{number}.json'
    local = []
    if report.get('variant') != variant or report.get('round') != number:
        local.append('variante o ronda incorrecta')
    rows = report.get('rows')
    if not isinstance(rows, list) or len(rows) != 7:
        local.append('se requieren exactamente 7 muestras')
        rows = rows if isinstance(rows, list) else []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            local.append(f'muestra {index}: formato inválido')
            continue
        expected = (index, 'process-cold' if index == 0 else 'warm', ENTRIES[index % 3], bool(index % 2))
        actual = tuple(row.get(key) for key in ('index', 'cache', 'entry', 'sensitive'))
        if actual != expected or type(row.get('sensitive')) is not bool:
            local.append(f'muestra {index}: entrada, contenido sintético u orden incorrectos')
        if any(not valid_number(row.get(key)) for key in METRICS):
            local.append(f'muestra {index}: tiempos inválidos')
        elif (abs(row['queue_s'] + row['preparation_s'] - row['first_inference_s']) > .00001
              or row['entry_to_provider_s'] + .00001 < row['first_inference_s']
              or row['inference_http_to_provider_s'] > row['preparation_s'] + .00001):
            local.append(f'muestra {index}: intervalos temporales inconsistentes')
        if not valid_sql(row.get('sql_preparation')):
            local.append(f'muestra {index}: contadores SQL inválidos')
        if (row.get('status') != 'completed' or row.get('provider_calls') != 1
                or row.get('inference_count') != 1 or row.get('checkpoint_count') != 1
                or any(type(row.get(key)) is not int for key in ('provider_calls', 'inference_count', 'checkpoint_count'))
                or type(row.get('catalog_count')) is not int or row['catalog_count'] < 1):
            local.append(f'muestra {index}: ejecución, catálogo, checkpoint o número de llamadas inválidos')
        if row.get('sql_callers'):
            local.append(f'muestra {index}: contiene instrumentación de stacks de diagnóstico')
        by_path = row.get('sql_by_path')
        if (isinstance(by_path, dict) and all(isinstance(path, str) and valid_sql(counts, require_select=False)
                                            for path, counts in by_path.items())):
            counted = Counter()
            for path, counts in by_path.items():
                if path.startswith('/internal/') and not path.endswith('/claim/'):
                    counted.update(counts)
            if dict(counted) != row.get('sql_preparation'):
                local.append(f'muestra {index}: SQL preparación no coincide con sus rutas HTTP')
        else:
            local.append(f'muestra {index}: falta desglose SQL por ruta')
    images = immutable_images(report)
    if images is None:
        local.append('faltan hashes de imágenes inmutables')
    issues.extend(f'{name}: {issue}.' for issue in local)
    return (rows if not local else []), images


def summarize(rows):
    return {'n': len(rows), **{metric: distribution(row[metric] for row in rows) for metric in METRICS},
            'sql_selects': distribution(row['sql_preparation']['SELECT'] for row in rows),
            'sql_statements': distribution(sum(row['sql_preparation'].values()) for row in rows),
            'sql_totals_by_verb': dict(sum((Counter(row['sql_preparation']) for row in rows), Counter()))}


def cohorts(rows):
    selections = {'all': rows,
        'process-cold': [row for row in rows if row['cache'] == 'process-cold'],
        'warm': [row for row in rows if row['cache'] == 'warm'],
        'simple': [row for row in rows if not row['sensitive']],
        'sensitive': [row for row in rows if row['sensitive']]}
    for cache in ('process-cold', 'warm'):
        for sensitive in (False, True):
            selections[f'{cache}-{"sensitive" if sensitive else "simple"}'] = [
                row for row in rows if row['cache'] == cache and row['sensitive'] == sensitive]
    return {name: summarize(selected) for name, selected in selections.items()}


def queue_summary(directory):
    issues = []
    report = read_json(directory / 'queue-comparison.json', issues, optional=True)
    if report is None:
        return {'status': 'unavailable' if not issues else 'invalid', 'issues': issues}
    groups, signatures = [], {}
    try:
        for group in report['groups']:
            mode, capacity = group['mode'], group['concurrent_jobs']
            if (mode not in ('poll_500ms', 'notification') or type(capacity) is not int
                    or capacity not in (1, 2) or len(group['samples']) != 21):
                raise ValueError()
            signature = []
            for index, sample in enumerate(group['samples']):
                if sample.get('warmth') != ('cold_connection' if index == 0 else 'warm_connection'):
                    raise ValueError()
                if (sample['warmth'] not in ('cold_connection', 'warm_connection')
                        or len(sample['jobs']) != capacity
                        or not valid_number(sample['phase_seconds'])):
                    raise ValueError()
                signature.append((sample['warmth'], sample['phase_seconds'], len(sample['jobs'])))
                for job in sample['jobs']:
                    if not valid_number(job['queue_ms']) or not valid_number(job['claim_selects']):
                        raise ValueError()
            signatures[mode, capacity] = signature
            for warmth in ('cold_connection', 'warm_connection'):
                jobs = [job for sample in group['samples'] if sample['warmth'] == warmth for job in sample['jobs']]
                groups.append({'mode': mode, 'concurrent_jobs': capacity, 'warmth': warmth,
                               'queue_ms': distribution(job['queue_ms'] for job in jobs),
                               'claim_selects': distribution(job['claim_selects'] for job in jobs)})
        if set(signatures) != {(mode, capacity) for mode in ('poll_500ms', 'notification') for capacity in (1, 2)}:
            raise ValueError()
        if any(signatures['poll_500ms', capacity] != signatures['notification', capacity] for capacity in (1, 2)):
            raise ValueError()
    except (AttributeError, KeyError, TypeError, ValueError):
        return {'status': 'invalid', 'issues': ['queue-comparison.json: muestras no comparables.']}
    return {'status': 'complete', 'groups': groups,
            'scope': 'Cola sintética PostgreSQL, capacidad libre; excluye SDK/proveedor y transporte HTTP del claim.',
            'cold_scope': 'Primera conexión de hilo; no equivale al frío del proceso de la comparación principal.'}


def catalog_summary(directory):
    results, issues = {}, []
    for variant in ('baseline', 'after'):
        name = f'catalog-{variant}-0.json'
        report = read_json(directory / name, issues, optional=True)
        if report is None:
            continue
        rows = report.get('rows', [])
        if (not isinstance(rows, list) or len(rows) != 5 or report.get('provider_calls') != 0 or report.get('live_data_modified') is not False
                or any(not isinstance(row, dict) or not valid_number(row.get('seconds')) or not valid_sql(row.get('sql'))
                       or type(row.get('catalog_count')) is not int for row in rows)):
            issues.append(f'{name}: se requieren 5 medidas válidas sin proveedor ni cambios persistentes.')
            continue
        results[variant] = {'n': len(rows), 'seconds': distribution(row['seconds'] for row in rows),
            'sql_selects': distribution(row['sql']['SELECT'] for row in rows),
            'sql_statements': distribution(sum(row['sql'].values()) for row in rows),
            'first_iteration_seconds': rows[0]['seconds'],
            'later_iterations_seconds': distribution(row['seconds'] for row in rows[1:])}
        results[variant]['catalog_counts'] = sorted({row['catalog_count'] for row in rows})
    if len(results) == 2 and results['baseline']['catalog_counts'] != results['after']['catalog_counts']:
        issues.append('Catálogo: número de entradas diferente entre variantes.')
    return {'status': 'complete' if len(results) == 2 and not issues else 'incomplete',
            'issues': issues, 'variants': results,
            'scope': 'Lectura directa del catálogo instalado, 5 repeticiones con rollback; no es latencia completa.'}


def build_report(directory):
    issues, rows_by_variant, images_by_variant, signatures = [], {}, {}, {}
    observed = {}
    for variant in ('baseline', 'after'):
        rows_by_variant[variant], images_by_variant[variant] = [], []
        observed[variant] = 0
        for number in ROUNDS[variant]:
            report = read_json(directory / f'bench-{variant}-{number}.json', issues)
            if report is None:
                continue
            observed[variant] += len(report.get('rows', [])) if isinstance(report.get('rows'), list) else 0
            rows, images = validate_round(report, variant, number, issues)
            rows_by_variant[variant].extend(rows)
            if images is not None:
                images_by_variant[variant].append(images)
            signatures[variant, number] = [
                tuple(row[key] for key in ('index', 'cache', 'entry', 'sensitive', 'catalog_count')) for row in rows]
        if len(rows_by_variant[variant]) != 21:
            issues.append(f'{variant}: se requieren 21 muestras válidas; disponibles {len(rows_by_variant[variant])}.')
        if len({json.dumps(item, sort_keys=True) for item in images_by_variant[variant]}) > 1:
            issues.append(f'{variant}: las imágenes cambiaron entre las rondas formales.')
    for baseline_round, after_round in zip(ROUNDS['baseline'], ROUNDS['after'], strict=True):
        left, right = signatures.get(('baseline', baseline_round)), signatures.get(('after', after_round))
        if left is not None and right is not None and left != right:
            issues.append(f'Rondas baseline-{baseline_round}/after-{after_round}: entradas, muestras o catálogo distintos.')
    build = read_json(directory / 'build-0.json', issues, optional=True)
    final_images = immutable_images(build) if build else None
    matches_build = (bool(final_images and len(images_by_variant['after']) == 3)
                     and all(item == final_images for item in images_by_variant['after']))
    if final_images is None:
        issues.append('Falta build-0.json con hashes inmutables de la versión final.')
    elif images_by_variant['after'] and not all(item == final_images for item in images_by_variant['after']):
        issues.append('La imagen medida después no coincide con la compilación final build-0.json.')
    complete = not issues
    result = {'status': 'complete' if complete else 'incomplete',
        'formal_rounds': {variant: list(numbers) for variant, numbers in ROUNDS.items()}, 'expected_rows_per_variant': 21, 'observed_rows': observed,
        'issues': issues, 'percentiles': 'p95 nearest-rank ceil(0.95*n); median usual, no interpolated p95',
        'image_checks': {'immutable_and_stable': complete, 'after_matches_final_build': matches_build},
        'measurement': {
            'preparation_s': 'Asignación del worker hasta primera request al proveedor simulado.',
            'queue_s': 'Creación de ejecución hasta asignación del worker.',
            'first_inference_s': 'Creación de ejecución hasta primera request al proveedor simulado (cola + preparación).',
            'entry_to_provider_s': 'Inicio del POST de admisión hasta primera request al proveedor simulado.',
            'sql_preparation': 'Sentencias capturadas antes del proveedor en rutas /internal/ salvo claim; excluye admisión y driver.',
            'cold': 'Primer mensaje de un proceso nuevo; Django ya inicializado. No mide arranque del SO ni caché fría de PostgreSQL.',
            'inputs': 'Mismas dos entradas sintéticas (simple/con datos sensibles), mismo orden y tres entradas HTTP por ronda.',
            'limitations': '3 muestras frías y 18 calientes por variante; p95 es descriptivo de esta muestra. Proveedor simulado, sin nuevas llamadas de pago.'},
        'variants': {variant: {'cohorts': cohorts(rows), 'entries': {
            entry: summarize([row for row in rows if row['entry'] == entry]) for entry in ENTRIES}}
            for variant, rows in rows_by_variant.items()},
        'queue_experiment': queue_summary(directory), 'catalog_experiment': catalog_summary(directory)}
    if complete:
        after = result['variants']['after']['cohorts']
        result['goals'] = {
            'simple_preparation_p95_under_3s': after['simple']['preparation_s']['p95'] < 3,
            'queue_p95_under_500ms': after['all']['queue_s']['p95'] < .5}
    return result


def decimal(value, places=3):
    return f'{value:.{places}f}'.replace('.', ',')


def markdown(report):
    if report['status'] != 'complete':
        return '\n'.join(['**Medición formal incompleta: no se evalúan los objetivos.**', '',
            f'Muestras recibidas: antes {report["observed_rows"]["baseline"]}/21; después {report["observed_rows"]["after"]}/21.',
            '', *['- ' + issue for issue in report['issues']], '',
            'Solo se aceptan baseline 7/8/9 y after 10/11/12. Las rondas piloto y las trazas instrumentadas quedan excluidas.', ''])
    before, after = [report['variants'][variant]['cohorts'] for variant in ('baseline', 'after')]
    table = [
        ('Preparación p95, simple', 'simple', 'preparation_s', 'p95', 's'),
        ('Preparación p95, sensible', 'sensitive', 'preparation_s', 'p95', 's'),
        ('Preparación p95, caliente', 'warm', 'preparation_s', 'p95', 's'),
        ('Preparación p95, frío de proceso', 'process-cold', 'preparation_s', 'p95', 's'),
        ('Cola p95', 'all', 'queue_s', 'p95', 's'),
        ('Hasta primera inferencia p95, desde creación', 'all', 'first_inference_s', 'p95', 's'),
        ('Hasta primera inferencia p95, desde POST', 'all', 'entry_to_provider_s', 'p95', 's'),
        ('SELECT de preparación, mediana', 'all', 'sql_selects', 'median', ''),
        ('Sentencias SQL de preparación, mediana', 'all', 'sql_statements', 'median', '')]
    lines = ['**Comparación formal completa: 21 ejecuciones por variante.**',
        '', 'Tres procesos por variante: 3 primeras peticiones y 18 calientes. Mismos mensajes sintéticos, catálogo y tres entradas HTTP. Imágenes inmutables verificadas; la versión medida coincide con la compilación final.',
        '', '| Medida | n por variante | Antes | Después |', '| --- | ---: | ---: | ---: |']
    for label, cohort, metric, statistic, unit in table:
        places = 3 if unit else 0
        left, right = (decimal(data[cohort][metric][statistic], places) for data in (before, after))
        lines.append(f'| {label} | {after[cohort]["n"]} | {left} {unit} | {right} {unit} |')
    goals = report['goals']
    lines += ['', 'Objetivos para esta muestra: preparación simple p95 < 3 s '
              + ('cumplido' if goals['simple_preparation_p95_under_3s'] else '**no cumplido**')
              + '; cola p95 < 500 ms '
              + ('cumplido' if goals['queue_p95_under_500ms'] else '**no cumplido**') + '.',
        '', 'p95 usa rango más próximo: posición ceil(0,95 × n). Con 3 muestras frías o 18 calientes coincide con el máximo. El frío corresponde al primer mensaje del proceso, con Django ya inicializado. El desglose por frío/caliente, simple/sensible y entrada HTTP figura en summary.json.',
        '', 'SQL incluye todas las sentencias capturadas antes del proveedor en las rutas internas de preparación; excluye admisión, claim y sondeo del banco. El tiempo hasta primera inferencia no incluye la respuesta del modelo. Proveedor simulado y sockets externos bloqueados.']
    queue = report['queue_experiment']
    if queue['status'] == 'complete':
        lines += ['', 'Cola aislada PostgreSQL, conexión caliente y capacidad libre (sin transporte HTTP del claim):',
                  '', '| Trabajos concurrentes | p95 anterior | p95 notificación |', '| --- | ---: | ---: |']
        for capacity in (1, 2):
            values = {group['mode']: group['queue_ms']['p95'] for group in queue['groups']
                      if group['concurrent_jobs'] == capacity and group['warmth'] == 'warm_connection'}
            lines.append(f'| {capacity} | {decimal(values["poll_500ms"], 1)} ms | {decimal(values["notification"], 1)} ms |')
    catalog = report['catalog_experiment']
    if catalog['status'] == 'complete':
        left, right = (catalog['variants'][key] for key in ('baseline', 'after'))
        lines += ['', 'Catálogo, lectura directa con rollback (5 repeticiones): '
                  + f'mediana {decimal(left["seconds"]["median"])} → {decimal(right["seconds"]["median"])} s; '
                  + f'SELECT {decimal(left["sql_selects"]["median"], 0)} → {decimal(right["sql_selects"]["median"], 0)}.']
    else:
        lines += ['', 'Medición auxiliar del catálogo pendiente o incompleta; no se mezcla con la latencia completa.']
    return '\n'.join([*lines, ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'output/latency-optimization-20261017')
    args = parser.parse_args()
    directory = args.directory.resolve()
    output_root = (ROOT / 'output').resolve()
    if not directory.is_relative_to(output_root):
        parser.error('--directory debe estar dentro de output del repositorio')
    report = build_report(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in (('summary.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n'),
                          ('summary.md', markdown(report))):
        temporary = directory / (name + '.tmp')
        temporary.write_text(content, encoding='utf-8', newline='\n')
        temporary.replace(directory / name)
    print(json.dumps({'status': report['status'], 'observed_rows': report['observed_rows'],
                      'issues': report['issues']}, ensure_ascii=False))
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
