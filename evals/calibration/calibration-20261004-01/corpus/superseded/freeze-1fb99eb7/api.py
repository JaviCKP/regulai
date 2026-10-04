"""Frozen calibration data access. Reserved contents are custodian-only until release."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def canonical(value):
    result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    # Keep one physical record even for adversarial Unicode line separators.
    return result.replace('\u0085', '\\u0085').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def provider_input(case):
    """An explicit allowlist: no labels, case IDs, evidence or benchmark metadata."""
    return {'prompt': case['prompt'], 'instructions': case.get('instructions', ''),
            'history': [{'role': item['role'], 'content': item['content']} for item in case.get('history', [])],
            'documents': [{'text': item['text']} for item in case.get('documents', [])]}


def _safe_path(ref):
    path = (ROOT / ref).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError('Corpus reference escapes its root')
    return path


def _manifest():
    return json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))


def load_partition(partition):
    if partition not in {'development', 'validation'}:
        raise ValueError('Reserved cases are sealed; only the custodian may release them after final selection')
    manifest = _manifest()
    entry = manifest['partitions'][partition]
    data = _safe_path(entry['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Frozen corpus partition hash mismatch')
    return [json.loads(line) for line in data.decode('utf-8').splitlines() if line]


def verify_integrity():
    """Hash bytes only. Does not parse, return, or log reserved labels or cases."""
    manifest = _manifest()
    failures = []
    for ref, expected in manifest['files'].items():
        path = _safe_path(ref)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(ref)
    return {'ok': not failures, 'failures': failures, 'corpus_id': manifest['corpus_id'],
            'cases': manifest['counts']['cases'], 'families': manifest['counts']['families'],
            'partitions': {name: {'cases': entry['cases'], 'sha256': entry['sha256']}
                           for name, entry in manifest['partitions'].items()}}
