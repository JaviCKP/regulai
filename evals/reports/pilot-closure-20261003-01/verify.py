"""Read-only closure audit: sources, evidence, links, synthetic keys and owned resources."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert not (HERE / 'verification.json').exists(), 'Preserve earlier audit; use a new directory.'
failures = []
gates = ROOT / 'evals/reports/pilot-integrated-gates-20261003-03'
gate = json.loads((gates / 'manifest.json').read_text())
assert gate['passed'] and gate['source_unchanged']
for name, expected in gate['source_sha256'].items():
    if sha256((ROOT / name).read_bytes()).hexdigest() != expected:
        failures.append('source_changed:' + name)
for command in gate['commands']:
    if command['exit_code'] or sha256((gates / command['log']).read_bytes()).hexdigest() != command['sha256']:
        failures.append('gate_evidence_changed:' + command['gate'])

package = ROOT / 'evals/reports/pilot-independent-local-20261003-01'
packaged = json.loads((package / 'package-files.json').read_text())
for row in packaged:
    if sha256((package / row['file']).read_bytes()).hexdigest() != row['sha256']:
        failures.append('independent_evidence_changed:' + row['file'])

docs = [ROOT / 'README.md']
docs += [ROOT / 'docs/plan-blackhat' / name for name in (
    'README.md', 'arranque-y-demo.md', 'enmascarado-local.md', 'informe-correcciones-community.md',
    'informe-piloto-community-20261003.md', 'estado-ejecucion.md', 'piloto-checkpoint.md',
    'operacion-y-recuperacion-piloto.md', 'piloto-controlado.md', 'ejecucion-real-y-calibracion-piloto.md')]
docs += [p for p in (ROOT / 'docs/plan-blackhat/tareas').glob('*.md') if 20 <= int(p.name[:2]) <= 28]
docs += list((ROOT / 'docs/plan-blackhat/revisiones-piloto').glob('*local*.md'))
docs += list((ROOT / 'evals/reports').glob('pilot-*/README.md'))
links = []
for path in docs:
    content = path.read_text(encoding='utf-8')
    for match in re.finditer(r'\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', content):
        target = unquote(match.group(1).strip('<>'))
        if re.match(r'^(?:https?://|mailto:|#|data:)', target):
            continue
        target = target.split('#')[0]
        if not target:
            continue
        destination = (path.parent / target).resolve()
        exists = destination.exists()
        links.append({'file': path.relative_to(ROOT).as_posix(), 'target': target, 'exists': exists})
        if not exists:
            failures.append('missing_link:' + path.relative_to(ROOT).as_posix() + ':' + target)

# Compare only fresh laboratory secrets, never open user settings or credentials.
keys = []
for directory in sorted((ROOT / 'evals/reports').glob('pilot-operations-20261003-[0-9][0-9]')):
    result = json.loads((directory / 'result.json').read_text())
    private = Path(result['private_work']).resolve()
    assert private.is_relative_to((ROOT / '.claude').resolve()) and private.name.startswith('regulai-lab-')
    synthetic = json.loads((private / 'private/keys.json').read_text())
    keys.extend(synthetic[name] for name in ('signing', 'encryption', 'database'))
scanned = 0
matches = []
for directory in (ROOT / 'evals/reports').glob('pilot-*'):
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix in ('.log', '.txt', '.json', '.jsonl', '.md', '.py', '.csv'):
            data = path.read_bytes()
            scanned += 1
            if any(value.encode() in data or value.encode('utf-16-le') in data for value in keys):
                matches.append(path.relative_to(ROOT).as_posix())
if matches:
    failures.append('synthetic_key_exposure_in_artifact')

resources = []
for args in (
    ['docker', 'ps', '-a', '--filter', 'label=regulai.synthetic-lab', '--format', '{{.ID}} {{.Names}}'],
    ['docker', 'network', 'ls', '--filter', 'label=regulai.synthetic-lab', '--format', '{{.ID}} {{.Name}}'],
    ['docker', 'volume', 'ls', '--filter', 'label=regulai.synthetic-lab', '--format', '{{.Name}}'],
    ['docker', 'image', 'ls', '--filter', 'reference=regulai-lab-*', '--format', '{{.Repository}} {{.ID}}'],
):
    command = ['rtk', 'proxy', *args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    resources.append({'command': command, 'exit_code': result.returncode, 'resources': result.stdout.splitlines()})
    if result.returncode or result.stdout.strip():
        failures.append('owned_lab_resources_remaining:' + args[1])

untouched = ['MESAS_RETIRO.pdf', 'plantilla.pdf', 'plantillaInformeTecnica.pdf',
             'docs/brainstorming-regulae-vigia13-2026-10-02.md', 'docs/plan-blackhat/prompt-validacion-piloto-astra-max.md']
tracked = subprocess.run(['rtk', 'proxy', 'git', 'ls-files', '--', *untouched], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
if tracked.strip() or any(not (ROOT / p).is_file() for p in untouched):
    failures.append('unrelated_initial_files_not_preserved_untracked')
report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'runtime_matches_final_gate': not any(
    item.startswith('source_changed') for item in failures), 'gate_source_files': len(gate['source_sha256']),
    'independent_files_verified': len(packaged), 'links_checked': len(links), 'links': links,
    'synthetic_keys_compared_without_emitting_values': len(keys), 'artifact_text_files_scanned': scanned,
    'synthetic_key_matches': matches, 'resources': resources, 'initial_unrelated_files_untracked': untouched,
    'source_sha256': {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in docs},
    'failures': failures, 'passed': not failures, 'remote_ci_executed': False}
(HERE / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: report[key] for key in ('passed', 'gate_source_files', 'independent_files_verified',
    'links_checked', 'artifact_text_files_scanned', 'synthetic_key_matches', 'failures')}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
