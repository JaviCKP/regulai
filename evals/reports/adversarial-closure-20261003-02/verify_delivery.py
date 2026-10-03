"""Read-only integrity, links and shared-budget checks; never loads product credentials."""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / 'evals/reports'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    output = (ROOT / sys.argv[1]).resolve()
    if not output.is_relative_to(REPORTS.resolve()):
        raise ValueError('Evidence output must stay inside reports')
    output.mkdir(parents=True, exist_ok=False)
    checks, bad, count = {}, [], 0

    def verify(path, expected):
        nonlocal count
        count += 1
        if not path.is_file() or digest(path) != expected:
            bad.append(str(path.relative_to(ROOT)))

    corpus = ROOT / 'evals/adversarial/community-20261003'
    for item in read(corpus / 'manifest.json')['files']:
        verify(corpus / item['path'], item['sha256'])
    for folder_name in ('adversarial-community-20261003-02', 'semantic-threshold-boundary-20261003-01'):
        folder = REPORTS / folder_name
        base = ROOT if folder_name == 'semantic-threshold-boundary-20261003-01' else folder
        for name, expected in read(folder / 'artifact-hashes.json').items():
            verify(base / name, expected)
    for folder_name in ('adversarial-independent-review-20261003-01',
                        'adversarial-live-response-review-20261003-01',
                        'adversarial-second-response-review-20261003-01',
                        'semantic-threshold-independent-20261003-01'):
        folder = REPORTS / folder_name
        items = read(folder / 'package-files.json')
        for item in items if isinstance(items, list) else items['files']:
            verify(folder / item['path'], item['sha256'])
    review_folder = REPORTS / 'semantic-threshold-independent-20261003-01'
    seal = read(review_folder / 'seal.json')
    for name, key in (('package-files.json', 'package_files_sha256'), ('evidence.json', 'evidence_sha256'),
                      ('Spec-review.md', 'spec_review_sha256'), ('Standards-review.md', 'standards_review_sha256')):
        verify(review_folder / name, seal[key])
    checks['independent_fix_review_closed'] = (seal['reviewed_commit'] == '1af809fd209c4260d5314ff55fa090147515b8d0'
                                              and seal['own_command_exit_code'] == 0 and seal['open_findings'] == 0)
    gate_manifests = []
    for suffix in ('01', '02'):
        folder = REPORTS / ('adversarial-gates-20261003-' + suffix)
        gate = read(folder / 'manifest.json')
        gate_manifests.append(gate)
        checks['gates_' + suffix] = gate['passed'] and gate['source_unchanged']
        for command in gate['commands']:
            checks[f"gate_{suffix}_{command['gate']}"] = command['exit_code'] == 0
            verify(folder / command['log'], command['sha256'])
    for path, expected in gate_manifests[-1]['source_sha256'].items():
        verify(ROOT / path, expected)
    checks['final_gate_commit'] = gate_manifests[-1]['revision'] == '1af809fd209c4260d5314ff55fa090147515b8d0'
    changed = sorted(path for path, expected in gate_manifests[0]['source_sha256'].items()
                     if path in gate_manifests[1]['source_sha256']
                     and expected != gate_manifests[1]['source_sha256'][path])
    checks['runtime_delta_only_numeric_fix'] = changed == ['regulai/front/chat_service.py', 'regulai/front/classification.py']
    for path, expected in read(REPORTS / 'adversarial-real-20261003-02/prepared-files.json').items():
        verify(ROOT / path, expected)
    for suffix, pack in (('01', 'community-20261003-02'), ('02', 'community-additional-20261003')):
        folder = REPORTS / ('adversarial-real-20261003-' + suffix)
        packed = ROOT / 'evals/adversarial-live' / pack
        live = read(folder / 'live-result.json')
        verify(packed / 'manifest.json', live['manifest_sha256'])
        verify(packed / 'authorization.approved.json', live['authorization_sha256'])
        verify(packed / 'run_authorized.py', live['script_sha256'])
        for path, expected in live['logs'].items():
            verify(folder / path, expected)
        checks['live_' + suffix] = live['exit_code'] == 0 and live['source_database_unchanged'] and (
            live['source_database_sha256_before'] == live['source_database_sha256_after'])
        manifest = read(folder / 'live-run-01/manifest.json')
        checks['live_sources_' + suffix] = all(gate_manifests[0]['source_sha256'][path] == expected
                                               for path, expected in manifest['source_sha256'].items())
    calculation = REPORTS / 'adversarial-consolidated-20261003-01/calculation-03'
    for path, expected in read(calculation / 'artifact-hashes.json').items():
        verify(calculation / path, expected)
    for path, expected in read(calculation / 'summary.json')['input_sha256'].items():
        verify(ROOT / path, expected)

    docs = list((ROOT / 'evals/adversarial-live').rglob('README.md'))
    docs += list((ROOT / 'evals/adversarial-live').rglob('STATUS.md'))
    docs += list((ROOT / 'docs/plan-blackhat/tareas').glob('3[2345]-*.md'))
    docs += [ROOT / 'docs/plan-blackhat/estado-ejecucion.md',
             ROOT / 'docs/plan-blackhat/informe-adversarial-community-20261003.md']
    docs += [folder / 'README.md' for folder in REPORTS.glob('adversarial-*') if (folder / 'README.md').exists()]
    docs += [REPORTS / 'semantic-threshold-boundary-20261003-01/README.md']
    broken, links = [], 0
    for path in docs:
        content = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)', content):
            href = match.group(1).strip('<>')
            if urlsplit(href).scheme or href.startswith('#'):
                continue
            relative = unquote(href.split('#', 1)[0])
            links += 1
            if not (path.parent / relative).resolve().exists():
                broken.append({'file': str(path.relative_to(ROOT)), 'target': href})
    snapshot = read(REPORTS / 'adversarial-real-20261003-02/live-run-01/budget.json')
    with closing(sqlite3.connect((ROOT / '.claude/pilot-real-budget.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        for suffix in ('01', '02'):
            before = read(REPORTS / ('adversarial-real-20261003-' + suffix) / 'activation.json')['before']
            historical = db.execute('SELECT * FROM calls ORDER BY rowid LIMIT ?', (before['calls_n'],)).fetchall()
            encoded = json.dumps(historical, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            checks['preserved_first_' + str(before['calls_n']) + '_entries'] = sha256(encoded).hexdigest() == before['calls_sha256']
        rows = db.execute('SELECT id,reserved,cost,metadata FROM calls ORDER BY rowid').fetchall()
        scopes = db.execute('SELECT id,digest FROM approval_extensions ORDER BY sequence').fetchall()
        cap = db.execute('SELECT cap FROM authorization').fetchall()
    observed = {row[0]: (row[1], row[2], json.loads(row[3])) for row in rows}
    checks['live_ledger_equals_last_snapshot'] = len(observed) == len(snapshot['calls']) and all(
        observed[call['id']] == (call['reserved'], call['cost'], call['metadata']) for call in snapshot['calls'])
    uncertain = [(row[0], row[1]) for row in rows if row[2] is None]
    checks['old_uncertainty_retained'] = len(uncertain) == 1 and Decimal(uncertain[0][1]) == Decimal('.003')
    checks['two_scopes_shared_original_cap'] = len(scopes) == 2 and cap == [('1.00',)]
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'hashes_checked': count,
        'hash_mismatches': bad, 'markdown_links_checked': links, 'broken_links': broken,
        'runtime_changed_paths': changed, 'ledger_entries': len(rows), 'scope_count': len(scopes),
        'unknown_reservations_usd': str(sum((Decimal(row[1]) for row in uncertain), Decimal(0))),
        'new_paid_calls': 0, 'user_database_opened': False,
        'passed': all(checks.values()) and not bad and not broken}
    (output / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
