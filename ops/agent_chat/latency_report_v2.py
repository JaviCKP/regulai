"""Validate and summarize second-pass latency evidence; no installation access.

Formal evidence is fixed to rounds 20..39, seven messages per fresh process.
Pilots, profiles, histories and concurrency have separate descriptive sections.
Exit 2 means incomplete/incomparable evidence; no performance goal is then scored.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
ROUNDS = tuple(range(20, 40))
ENTRIES = ('/chat/', '/chat/send/', '/api/chat/send/')
METRICS = ('queue_s', 'queue_admission_s', 'queue_dispatch_s', 'preparation_s',
    'first_inference_s', 'entry_to_provider_s', 'inference_http_to_provider_s')
HASH = re.compile(r'[0-9a-f]{64}')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}')
BENCHMARK = re.compile(r'bench-(baseline|after)-(\d+)(.*)\.json')
BUILD = re.compile(r'build-(\d+)\.json')


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'median': round(statistics.median(values), 6),
        'p95': round(values[math.ceil(.95 * len(values)) - 1], 6),
        'min': round(values[0], 6), 'max': round(values[-1], 6)}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def sql_counts(value):
    return isinstance(value, dict) and all(isinstance(key, str) and key.isalpha() and key.isupper()
        and type(count) is int and count >= 0 for key, count in value.items())


def read(path, issues):
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError):
        issues.append(path.name + ': falta JSON válido.')
        return None


def identities(report):
    images = report.get('image_ids', report.get('images'))
    if not isinstance(images, dict) or set(images) != {'web', 'worker'} or any(
            not isinstance(value, str) or not IMAGE.fullmatch(value) for value in images.values()):
        raise ValueError('faltan imágenes inmutables')
    harness = report.get('harness_sha256')
    if not isinstance(harness, dict) or not {'latency_benchmark_server.py', 'latency_benchmark_worker.py',
            'latency_profile.py'}.issubset(harness) or any(
            not isinstance(value, str) or not HASH.fullmatch(value) for value in harness.values()):
        raise ValueError('faltan hashes del banco')
    dataset = report.get('dataset_sha256')
    if not isinstance(dataset, str) or not HASH.fullmatch(dataset):
        raise ValueError('falta hash del backup de datos')
    return images, harness, dataset


def validate_rows(report, *, formal=False, round_number=0):
    issues, rows = [], report.get('rows')
    if not isinstance(rows, list) or (formal and len(rows) != 7):
        return [], ['se requieren siete muestras por proceso' if formal else 'faltan muestras']
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f'muestra {index}: no es un objeto')
            continue
        if any(not number(row.get(metric)) for metric in METRICS):
            issues.append(f'muestra {index}: tiempos ausentes o inválidos')
        elif (abs(row['queue_s'] + row['preparation_s'] - row['first_inference_s']) > .00001
                or abs(row['queue_admission_s'] + row['queue_dispatch_s'] - row['queue_s']) > .00001
                or row['first_inference_s'] > row['entry_to_provider_s'] + .00001
                or row['inference_http_to_provider_s'] > row['preparation_s'] + .00001):
            issues.append(f'muestra {index}: intervalos incompatibles')
        if row.get('status') != 'completed' or any(type(row.get(key)) is not int or row[key] != 1
                for key in ('provider_calls', 'inference_count', 'checkpoint_count')):
            issues.append(f'muestra {index}: ejecución/inferencia/checkpoint no completados exactamente una vez')
        if type(row.get('catalog_count')) is not int or row['catalog_count'] < 1:
            issues.append(f'muestra {index}: falta catálogo automático')
        if not sql_counts(row.get('sql_preparation')) or 'SELECT' not in row.get('sql_preparation', {}):
            issues.append(f'muestra {index}: SELECT inválidos')
        paths = row.get('sql_by_path')
        if not isinstance(paths, dict) or any(not isinstance(path, str) or not sql_counts(counts)
                for path, counts in paths.items()):
            issues.append(f'muestra {index}: desglose SQL inválido')
        else:
            counted = Counter()
            for path, counts in paths.items():
                if path.startswith('/internal/') and not path.endswith('/claim/'):
                    counted.update(counts)
            if dict(counted) != row.get('sql_preparation'):
                issues.append(f'muestra {index}: SQL no coincide con las rutas')
        if formal:
            expected = (index, 'process-cold' if index == 0 else 'warm',
                ENTRIES[(index + round_number) % 3], bool(index % 2), 'simple', 0, 'new')
            actual = tuple(row.get(key) for key in ('index', 'cache', 'entry', 'sensitive',
                'scenario', 'history_pairs', 'conversation_data'))
            if actual != expected or type(row.get('sensitive')) is not bool:
                issues.append(f'muestra {index}: contenido/entrada/orden/cohorte distintos del diseño')
            if row.get('sql_callers') or row.get('profile') or row.get('worker_profile'):
                issues.append(f'muestra {index}: contiene perfil diagnóstico')
    return (rows if not issues else []), issues


def summarize(rows):
    return {'n': len(rows), **{metric: distribution(row[metric] for row in rows) for metric in METRICS},
        'sql_selects': distribution(row['sql_preparation']['SELECT'] for row in rows),
        'sql_statements': distribution(sum(row['sql_preparation'].values()) for row in rows)}


def cohorts(rows):
    groups = {'all': rows, 'process-cold': [r for r in rows if r['cache'] == 'process-cold'],
        'warm': [r for r in rows if r['cache'] == 'warm'],
        'simple': [r for r in rows if not r['sensitive']], 'sensitive': [r for r in rows if r['sensitive']]}
    for cache in ('process-cold', 'warm'):
        for sensitive in (False, True):
            groups[cache + ('-sensitive' if sensitive else '-simple')] = [r for r in rows
                if r['cache'] == cache and r['sensitive'] == sensitive]
    return {name: summarize(values) for name, values in groups.items()}


def auxiliary(directory):
    pilots, scenarios, diagnostics = [], [], []
    reports = {}
    for path in sorted(directory.glob('bench-*.json')):
        match = BENCHMARK.fullmatch(path.name)
        if not match or int(match[2]) in ROUNDS:
            continue
        local = []
        report = read(path, local)
        if report is None:
            diagnostics.append({'file': path.name, 'issues': local})
            continue
        if report.get('instrumented') or report.get('profile') or '-profile' in match[3]:
            diagnostics.append({'file': path.name, 'n': len(report.get('rows', [])),
                'scope': 'perfil diagnóstico; excluido de percentiles formales'})
            continue
        rows, local = validate_rows(report)
        entry = {'file': path.name, 'variant': match[1], 'round': int(match[2]),
            'scenario': report.get('scenario', 'simple'), 'issues': local, 'formal': False}
        try:
            images, harness, dataset = identities(report)
            entry.update(images=images, harness_sha256=harness, dataset_sha256=dataset)
        except ValueError as error:
            entry['issues'].append(str(error))
        if rows:
            entry['summary'] = summarize(rows)
        if entry['scenario'] == 'concurrency' and rows:
            entry['capacity_configuration'] = report.get('capacity_configuration', {})
            entry['cohorts'] = {name: summarize([row for row in rows if
                (row.get('capacity_blocked') is True) == blocked])
                for name, blocked in (('free-capacity', False), ('capacity-blocked', True))}
            entry['groups'] = report.get('groups', [])
            entry['complete'] = report.get('complete') is True
            scenarios.append(entry)
        elif entry['scenario'] == 'history' and rows:
            entry['by_history_pairs'] = {str(size): summarize([r for r in rows if r.get('history_pairs') == size])
                for size in sorted({row.get('history_pairs', 0) for row in rows})}
            scenarios.append(entry)
        else:
            reports[match[1], int(match[2])] = entry
    for number_ in sorted({key[1] for key in reports}):
        before, after = (reports.get((variant, number_)) for variant in ('baseline', 'after'))
        comparable = bool(before and after and not before['issues'] and not after['issues']
            and before.get('harness_sha256') == after.get('harness_sha256')
            and before.get('dataset_sha256') == after.get('dataset_sha256'))
        pilots.append({'round': number_, 'formal': False, 'comparable_harness_and_dataset': comparable,
            'reason': 'Piloto excluido del diseño formal.' if comparable else
                'Pareja incompleta o hashes/muestras incompatibles; no atribuir una diferencia al producto.',
            'baseline': before, 'after': after})
    return {'pilots': pilots, 'scenarios': scenarios, 'diagnostics': diagnostics}


def select_build(directory, issues, build_number=None):
    if build_number is None:
        candidates = [(int(match[1]), path) for path in directory.glob('build-*.json')
            if (match := BUILD.fullmatch(path.name))]
        if not candidates:
            issues.append('Falta un artefacto build-N.json de la compilación final.')
            return None, None
        build_number, path = max(candidates, key=lambda value: value[0])
    else:
        path = directory / f'build-{build_number}.json'
    return path.name, read(path, issues)


def chronology(entries, issues):
    expected = [(number_, variant) for number_ in ROUNDS for variant in
        (('baseline', 'after') if number_ % 2 == 0 else ('after', 'baseline'))]
    ordered = sorted(entries, key=lambda row: row['started_at_unix'])
    actual = [(row['round'], row['variant']) for row in ordered]
    complete = len(ordered) == len(expected)
    alternating = complete and actual == expected
    nonoverlapping = all(left['finished_at_unix'] <= right['started_at_unix']
        for left, right in zip(ordered, ordered[1:]))
    if not complete:
        issues.append(f'Cronología formal incompleta: {len(ordered)}/40 intervalos válidos.')
    elif not alternating:
        issues.append('Los timestamps no demuestran el orden pareado alterno previsto para las rondas 20–39.')
    if not nonoverlapping:
        issues.append('Los intervalos medidos de rondas formales se solapan.')
    return {'verified': complete and alternating and nonoverlapping, 'n': len(ordered),
        'paired_alternating': alternating, 'nonoverlapping': nonoverlapping,
        'source': 'measured_started_at_unix/measured_finished_at_unix del orquestador en la misma VM; '
            'incluyen restauración y arranque, no sustituyen los tiempos individuales de inferencia.',
        'runs': ordered}


def build_report(directory, *, build_number=None):
    issues, accepted, observed, metadata, signatures, timings = [], {}, {}, {}, {}, []
    for variant in ('baseline', 'after'):
        accepted[variant], metadata[variant], observed[variant] = [], [], 0
        for round_number in ROUNDS:
            name = f'bench-{variant}-{round_number}.json'
            report = read(directory / name, issues)
            if report is None:
                continue
            observed[variant] += len(report.get('rows', [])) if isinstance(report.get('rows'), list) else 0
            local = []
            if (report.get('variant') != variant or report.get('round') != round_number
                    or report.get('round_offset') != round_number or report.get('scenario') != 'simple'
                    or report.get('instrumented') is not False or report.get('profile') is not False):
                local.append('identidad de ronda, escenario o instrumentación incorrecta')
            started, finished = report.get('measured_started_at_unix'), report.get('measured_finished_at_unix')
            if not number(started) or not number(finished) or started >= finished:
                local.append('timestamps de medición ausentes o inválidos')
            else:
                timings.append({'variant': variant, 'round': round_number,
                    'started_at_unix': started, 'finished_at_unix': finished})
            try:
                metadata[variant].append(identities(report))
            except ValueError as error:
                local.append(str(error))
            rows, invalid = validate_rows(report, formal=True, round_number=round_number)
            local.extend(invalid)
            signatures[variant, round_number] = [tuple(row.get(key) for key in
                ('index', 'cache', 'entry', 'sensitive', 'catalog_count', 'history_pairs')) for row in rows]
            if local:
                issues.extend(name + ': ' + error for error in local)
            else:
                accepted[variant].extend(rows)
        if len(accepted[variant]) != 140:
            issues.append(f'{variant}: se requieren 140 muestras válidas; disponibles {len(accepted[variant])}.')
        if len({json.dumps(item[0], sort_keys=True) for item in metadata[variant]}) > 1:
            issues.append(variant + ': cambian imágenes entre rondas formales.')
    all_metadata = metadata['baseline'] + metadata['after']
    same_harness = bool(all_metadata) and len({json.dumps(item[1], sort_keys=True) for item in all_metadata}) == 1
    same_dataset = bool(all_metadata) and len({item[2] for item in all_metadata}) == 1
    if not same_harness:
        issues.append('El banco de medición no tiene un único conjunto de hashes para todas las rondas.')
    if not same_dataset:
        issues.append('Las rondas no proceden de un único backup identificado.')
    for round_number in ROUNDS:
        if (('baseline', round_number) in signatures and ('after', round_number) in signatures
                and signatures['baseline', round_number] != signatures['after', round_number]):
            issues.append(f'Ronda {round_number}: entradas, tamaños o catálogos diferentes entre variantes.')
    build_name, build = select_build(directory, issues, build_number)
    final_images = build.get('image_ids', build.get('images')) if build else None
    matches_build = bool(metadata['after'] and final_images and all(item[0] == final_images for item in metadata['after']))
    if not matches_build:
        issues.append(f'Las imágenes después no coinciden con {build_name or "el artefacto de compilación final"}.')
    measured_order = chronology(timings, issues)
    result = {'status': 'complete' if not issues else 'incomplete', 'issues': issues,
        'formal_rounds': list(ROUNDS), 'expected_rows_per_variant': 140, 'observed_rows': observed,
        'accepted_rows': {key: len(rows) for key, rows in accepted.items()},
        'percentiles': 'p95 nearest-rank: ordered[ceil(0.95*n)-1]; mediana usual.',
        'identity_checks': {'same_harness': same_harness, 'same_dataset': same_dataset,
            'after_matches_final_build': matches_build, 'paired_alternating_verified': measured_order['verified']},
        'final_build': {'file': build_name, 'selection': 'explicit' if build_number is not None else 'highest_numeric_round',
            'images': final_images}, 'chronology': measured_order,
        'measurement': {'cold': 'Primer mensaje de cada proceso con Django/SDK importados y login fixture realizado; '
                '20 procesos independientes por variante. No incluye arranque de VM ni vaciado de caché PostgreSQL/SO.',
            'warm': '120 mensajes posteriores: 60 simples y 60 sensibles por variante, cada uno en conversación nueva.',
            'queue': 'Creación de ejecución → started_at; incluye admisión hasta commit y despacho después de commit.',
            'queue_commit': 'Timestamp de callback on_commit observado en aplicación, no timestamp interno de PostgreSQL.',
            'preparation': 'started_at → primera request al proveedor simulado.',
            'sql': 'Sentencias de rutas internas antes del proveedor, excluye admisión/claim/consultas del conductor.',
            'transport': 'Worker y servidor por HTTP loopback; admisión por Django TestClient; proveedor MockTransport.',
            'network': 'Sockets de cliente limitados a loopback en server/worker; claves sintéticas en proveedor.',
            'limitations': 'p95 descriptivo de la muestra local; 20 fríos dan p95 como segundo mayor. '
                'No estima tiempos del modelo real, red exterior ni caché de páginas fría. '
                'CPU/SQL/serialización se describen solo en perfiles separados, excluidos del p95.'},
        'variants': {variant: {'cohorts': cohorts(rows), 'entries': {entry: summarize(
            [row for row in rows if row['entry'] == entry]) for entry in ENTRIES}} for variant, rows in accepted.items()},
        **auxiliary(directory)}
    if not issues:
        after = result['variants']['after']['cohorts']
        result['goals'] = {'warm_simple_preparation_p95_under_700ms': after['warm-simple']['preparation_s']['p95'] < .7,
            'process_cold_preparation_p95_under_1500ms': after['process-cold']['preparation_s']['p95'] < 1.5,
            'free_capacity_queue_p95_under_100ms': after['all']['queue_s']['p95'] < .1}
    return result


def decimal(value, digits=3):
    return f'{value:.{digits}f}'.replace('.', ',')


def markdown(report):
    if report['status'] != 'complete':
        return '\n'.join(['**Comparación formal incompleta. No se evalúan las metas.**', '',
            f'Muestras válidas: antes {report["accepted_rows"]["baseline"]}/140; después {report["accepted_rows"]["after"]}/140.',
            '', *['- ' + issue for issue in report['issues']], '',
            'Pilotos, perfiles y escenarios auxiliares permanecen separados en summary.json.', ''])
    before, after = [report['variants'][key]['cohorts'] for key in ('baseline', 'after')]
    measures = [('Preparación simple caliente', 'warm-simple', 'preparation_s', 's'),
        ('Preparación sensible caliente', 'warm-sensitive', 'preparation_s', 's'),
        ('Preparación fría de proceso', 'process-cold', 'preparation_s', 's'),
        ('Cola con capacidad libre', 'all', 'queue_s', 's'),
        ('Cola: admisión hasta commit', 'all', 'queue_admission_s', 's'),
        ('Cola: despacho tras commit', 'all', 'queue_dispatch_s', 's'),
        ('Hasta primera inferencia, caliente', 'warm', 'first_inference_s', 's'),
        ('SELECT preparación simple caliente', 'warm-simple', 'sql_selects', '')]
    lines = ['**Comparación formal completa: 140 ejecuciones por variante.**', '',
        '20 procesos nuevos por variante; 20 primeras ejecuciones y 120 calientes. '
        'Mismo backup, banco e inputs, tres entradas HTTP y catálogo automático. '
        'Los timestamps verifican las parejas alternadas y la ausencia de solapamiento entre rondas. '
        'Cada ejecución completó exactamente una inferencia y un checkpoint.', '',
        '| Medida | n por variante | Antes mediana / p95 | Después mediana / p95 |',
        '| --- | ---: | ---: | ---: |']
    for label, cohort, metric, unit in measures:
        values = [data[cohort][metric] for data in (before, after)]
        formatted = [' / '.join(decimal(value[stat], 3 if unit else 0) for stat in ('median', 'p95')) + (' ' + unit if unit else '')
            for value in values]
        lines.append(f'| {label} | {values[1]["n"]} | {formatted[0]} | {formatted[1]} |')
    lines += ['', 'Metas comprobadas:', '']
    labels = {'warm_simple_preparation_p95_under_700ms': 'Preparación simple caliente p95 < 700 ms',
        'process_cold_preparation_p95_under_1500ms': 'Preparación fría p95 < 1,5 s',
        'free_capacity_queue_p95_under_100ms': 'Cola con capacidad libre p95 < 100 ms'}
    lines += ['- ' + labels[key] + ': ' + ('cumplida.' if value else '**no alcanzada**.') for key, value in report['goals'].items()]
    lines += ['', 'p95 usa rango más próximo. El frío es la primera ejecución tras inicialización de Django/SDK; '
        'la base se restaura desde el mismo backup y no se vacían las cachés de PostgreSQL/SO. '
        'El timestamp de commit corresponde al callback de aplicación. SQL excluye admisión, claim y conductor.', '',
        'El worker y servidor usan HTTP real por loopback; las tres admisiones usan Django TestClient. '
        'El proveedor está simulado y la red exterior bloqueada. Estos tiempos no predicen la latencia del modelo real.', '',
        f'Fuera de la comparación formal: {len(report["pilots"])} parejas piloto, '
        f'{len(report["diagnostics"])} perfiles y {len(report["scenarios"])} escenarios auxiliares. '
        'Los pilotos con distintos hashes no permiten atribuir sus diferencias al producto. '
        'El desglose completo, historiales y concurrencia están en summary.json.', '',
        '[Instalación y ensayos auxiliares](DELIVERY.md) · '
        '[Cambios, caché e invariantes](CHANGES-AND-SAFETY.md) · '
        '[Perfil CPU/SQL/HTTP](PROFILE-ANALYSIS.md) · [Cola](QUEUE-ANALYSIS.md) · '
        '[Verificar, reproducir y revertir](REPRODUCE.md).', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'output/latency-optimization-20261017-v2')
    parser.add_argument('--build', type=int, dest='build_number',
        help='Número explícito de build-N.json; por defecto se elige el mayor número presente.')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to((ROOT / 'output').resolve()):
        parser.error('--directory debe estar dentro de output del repositorio')
    if args.build_number is not None and args.build_number < 0:
        parser.error('--build debe ser no negativo')
    report = build_report(directory, build_number=args.build_number)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, content in (('summary.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n'),
            ('summary.md', markdown(report))):
        temporary = directory / (filename + '.tmp')
        temporary.write_text(content, encoding='utf-8', newline='\n')
        temporary.replace(directory / filename)
    print(json.dumps({'status': report['status'], 'accepted_rows': report['accepted_rows'],
        'issues': report['issues']}, ensure_ascii=False))
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
