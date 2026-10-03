"""Verify the honest P02 report and enumerate only shareable synthetic artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import re

base = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, data):
    (base / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


walkthrough = (base / 'p02-simulated-walkthrough.md').read_text(encoding='utf-8')
steps = re.findall(r'^## ((?:P02|H1|H2)-\S+)', walkthrough, re.M)
assert len(steps) == len(set(steps)) == 19
for label in ('Objetivo/entrada', 'Evidencia previa examinada', 'Acción nueva real',
              'Observable', 'Reacción hipotética, simulada', 'Duda/incidencia y severidad'):
    assert walkthrough.count('**' + label + ':**') == 19, label
form = read(base / 'p02-simulated-form.json')
assert form['human_trial'] is False and form['human_validation'] is False
for key in ('human_participant_alias', 'human_observer', 'human_session_date', 'human_start_time',
            'human_finish_time', 'human_duration_seconds', 'human_clock_wait_seconds',
            'human_help_required', 'human_comprehension_score', 'global_human_result'):
    assert form[key] is None, key
assert form['human_literal_comments'] == []
assert form['H1']['human_status'] == form['H2']['human_status'] == 'not_performed'
assert form['H1']['human_step_times'] == [None] * 7
assert form['H2']['human_step_times'] == [None] * 6
for name in ('run_checks.py', 'p02_checks.py', 'finalize.py'):
    ast.parse((base / name).read_text(encoding='utf-8'))
first, second = [read(base / run / 'checks.json') for run in ('run-01', 'run-02')]
assert (first['passed'], first['total']) == (15, 15)
assert (second['passed'], second['total']) == (14, 15)
assert 'Ran 22 tests in 8.460s' in (base / 'run-01/tests.log').read_text(encoding='utf-8')
assert 'FAILED (failures=3)' in (base / 'run-02/tests.log').read_text(encoding='utf-8')
for name, expected in second['snapshot_sources_after'].items():
    assert hashlib.sha256((base / 'snapshot' / name).read_bytes()).hexdigest() == expected, name
provenance = read(base / 'run-02/input-provenance.json')
human_form = next(row for row in provenance['files'] if row['file'].endswith('/human-rehearsal-form.md'))
assert hashlib.sha256((base.parents[2] / human_form['file']).read_bytes()).hexdigest() == human_form['sha256']
commands = read(base / 'commands.json')
commands['finalization'] = {'command': 'rtk proxy .venv/Scripts/python.exe -B .claude/pilot-personas/p02/finalize.py',
    'exit_code': 0, 'result': '19 complete simulated step records; human fields empty; failed supplemental run preserved; Python AST and JSON valid; fixed sources and original human form unchanged'}
write('commands.json', commands)
write('final-verification.json', {'passed': True, 'steps': steps, 'human_fields_empty': True,
    'original_human_form_unchanged': True, 'source_files_unchanged': 171,
    'run_01': '22 tests OK; 15/15 checks', 'run_02': '23 tests; 3 failed supplemental subtests; 14/15 checks',
    'runtime_modified': False, 'git_index_modified': False, 'public_manifest_excludes_private_work': True})
files = [p for p in base.iterdir() if p.is_file() and p.name not in ('snapshot.zip', 'public-files.json', 'evidence-sha256.json')]
for run in ('run-01', 'run-02'):
    files.extend(p for p in (base / run).iterdir() if p.is_file())
public = sorted(p.relative_to(base).as_posix() for p in files) + ['public-files.json', 'evidence-sha256.json']
write('public-files.json', {'schema_version': 1, 'copy_only_these_relative_files': public,
    'excluded': ['snapshot/', 'snapshot.zip', 'run-01/media/', 'run-02/media/', 'run-01/temporary/', 'run-02/temporary/'],
    'contains_no_database_or_keys_or_cookies': True,
    'note': 'Keep relative subdirectories. Do not copy the whole P02 directory. Git snapshot bytes are identified by revision and SHA but not included in the public list.'})
files.append(base / 'public-files.json')
for path in files:
    if path.suffix == '.json':
        read(path)
write('evidence-sha256.json', {'schema_version': 1,
    'scope': 'All public-files entries except this self-referential manifest',
    'files': [{'file': p.relative_to(base).as_posix(), 'bytes': p.stat().st_size,
               'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]})
print(json.dumps({'verified': True, 'simulated_steps': 19, 'public_files': len(public),
    'run_01_checks': '15/15', 'run_02_checks': '14/15 with preserved failed supplemental setup',
    'manifest_sha256': hashlib.sha256((base / 'evidence-sha256.json').read_bytes()).hexdigest()}))
