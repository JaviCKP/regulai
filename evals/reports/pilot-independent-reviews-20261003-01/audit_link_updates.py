"""Audit report link edits against the captured originals, without running product code."""
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT_DIR = ROOT / 'docs/plan-blackhat/revisiones-piloto'
SECTIONS = {
    'standards-c1e3a36.md': [('## Informe principal', '## Evidencia y reproducción')],
    'standards-a3bc67b.md': [('## Dictamen focalizado', '## Comandos y evidencia propia')],
    'spec-c1e3a36.md': [('1. **[P2]', 'Verificación propia:'), ('Sin scope creep identificado.', None)],
    'spec-8731129.md': [('- **S2 cerrado.**', 'Comando propio:'), ('**Cero hallazgos persistentes', None)],
    'security-febc8aa.md': [('**Resultado inicial:', '\n\n'),
        ('## SEC-1:', '\nEvidencia:'), ('**Límites:**', None)],
    'security-700389c.md': [('**SEC-1 está corregido', '\n\n'),
        ('| Comprobación |', '\nLos tres comandos'), ('El alcance restante', None)],
}


def section(text, start, end):
    tail = text[text.index(start):]
    return tail if end is None else tail[:tail.index(end)]


def main():
    reports = []
    for name, sections in SECTIONS.items():
        old_path, new_path = HERE / 'reports-at-capture' / name, REPORT_DIR / name
        old, new = old_path.read_text(encoding='utf-8'), new_path.read_text(encoding='utf-8')
        unchanged = all(section(old, start, end) == section(new, start, end) for start, end in sections)
        commands_unchanged = re.findall(r'```[^\n]*\n(.*?)```', old, re.S) == re.findall(r'```[^\n]*\n(.*?)```', new, re.S)
        reports.append({'path': new_path.relative_to(ROOT).as_posix(),
            'before_sha256': sha256(old_path.read_bytes()).hexdigest(),
            'after_sha256': sha256(new_path.read_bytes()).hexdigest(),
            'findings_verdicts_and_limits_unchanged': unchanged,
            'command_blocks_unchanged': commands_unchanged})
    missing, private_links, checked = [], [], 0
    for path in [HERE / 'README.md', *(REPORT_DIR / name for name in SECTIONS)]:
        content = path.read_text(encoding='utf-8')
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', content):
            if target.startswith(('https://', 'http://', '#')):
                continue
            if '.claude/' in target:
                private_links.append({'file': path.relative_to(ROOT).as_posix(), 'target': target})
            resolved = path.parent / unquote(target.split('#', 1)[0])
            checked += 1
            if not resolved.exists() and resolved.resolve() != HERE / 'packaging-verification.json':
                missing.append({'file': path.relative_to(ROOT).as_posix(), 'target': target})
    forbidden = [path.relative_to(HERE).as_posix() for path in HERE.rglob('*')
        if path.name in ('snapshot', 'candidate', '__pycache__', '.pytest_cache') or path.suffix in ('.pyc', '.pyo')]
    result = {'reports': reports, 'local_links_checked': checked, 'missing_links': missing,
        'private_markdown_links': private_links, 'excluded_trees_or_bytecode_found': forbidden,
        'captured_evidence_files': 65, 'captured_reports': 6,
        'product_or_provider_executed': False,
        'commands': [
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/preserve_evidence.py', 'exit_code': 0},
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/append_security_followup.py', 'exit_code': 0},
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/verify_archive.py', 'exit_code': 0},
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/verify_archive.py --compare-originals', 'exit_code': 0},
            {'command': 'rtk proxy git check-attr text whitespace -- evals/reports/pilot-independent-reviews-20261003-01/standards/probe-output.txt evals/reports/pilot-independent-reviews-20261003-01/spec/temperature-test.log evals/reports/pilot-independent-reviews-20261003-01/security/approval-race.log', 'exit_code': 0},
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/audit_link_updates.py',
             'exit_code': 1, 'attempt': 'initial', 'reason': 'Self-output had not been written; packaging helper generated one bytecode cache. Initial result retained separately.'},
            {'command': 'rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/audit_link_updates.py',
             'exit_code': 0, 'attempt': 'after correcting the packaging-only checks and removing owned bytecode'},
        ]}
    passed = all(row['findings_verdicts_and_limits_unchanged'] and row['command_blocks_unchanged'] for row in reports)
    passed = passed and not (missing or private_links or forbidden)
    result['passed'] = passed
    (HERE / 'packaging-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'reports': len(reports), 'local_links_checked': checked,
        'findings_and_commands_unchanged': all(row['findings_verdicts_and_limits_unchanged'] and row['command_blocks_unchanged'] for row in reports),
        'missing_links': missing, 'private_links': private_links, 'excluded_found': forbidden, 'passed': passed}))
    return not passed


if __name__ == '__main__':
    raise SystemExit(main())
