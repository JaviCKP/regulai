"""Independent focused use of the frozen offline transport harness."""
import hashlib
import importlib.util
import json
from pathlib import Path
import requests
import subprocess

from django.conf import settings

OWN = Path(__file__).resolve().parent
SOURCE = OWN / 'source'
spec = importlib.util.spec_from_file_location('frozen_adversarial_runner', SOURCE / 'scripts/run_adversarial_community.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def run():
    dataset = SOURCE / 'evals/adversarial/community-20261003/cases.jsonl'
    cases = runner.load_cases(dataset)
    manifest = json.loads((dataset.parent / 'manifest.json').read_text(encoding='utf-8'))
    filechecks = []
    for item in manifest['files']:
        source = dataset.parent / item['path']
        observed = hashlib.sha256(source.read_bytes()).hexdigest()
        filechecks.append({'path': item['path'], 'sha256': observed,
            'passed': observed == item['sha256'] and source.stat().st_size == item['bytes']})
    assert all(item['passed'] for item in filechecks)
    assert len(cases) == 44
    settings.MEDIA_ROOT = OWN / 'synthetic-media'
    settings.MEDIA_ROOT.mkdir(exist_ok=True)
    selected = ['PII-03', 'INJ-05', 'DOC-04', 'DOC-08', 'PII-12']
    local_rows, http_rows, parser_records = [], [], []
    post, run_process = requests.post, subprocess.run
    with runner.deny_network() as guards:
        for case in cases:
            local_rows.append(runner.local_measurement(case, dataset))
        for case in cases:
            if case['id'] not in selected:
                continue
            for profile in runner.PROFILES:
                for endpoint in runner.ENDPOINTS:
                    http_rows.append(runner.run_http(case, dataset, endpoint, profile, post, run_process, parser_records))
        summary = runner.build_summary(local_rows, http_rows, guards, parser_records)
    # This probe demands truthful harness execution, not all product measurements green.
    assert summary['harness_integrity_passed'], summary
    assert summary['classification_accuracy'] is None and summary['llm_prompt_injection_resistance'] is None
    assert len(http_rows) == 30
    assert {row['endpoint'] for row in http_rows} == set(runner.ENDPOINTS)
    compact = []
    for row in http_rows:
        compact.append({key: row.get(key) for key in ('case_id', 'endpoint', 'provider_profile',
            'expected_control', 'observed_control', 'control_passed', 'classification_oracle',
            'classification_measurement', 'bytes_measurement', 'harness_error')})
        compact[-1]['boundary_count'] = len(row.get('boundary_events', []))
        compact[-1]['verification'] = row.get('decision', {}).get('verification')
        compact[-1]['parsers'] = row.get('isolated_parser_calls', [])
        compact[-1]['false_assertions'] = [item for item in row['assertions'] if not item['passed']]
    evidence = {'source_commit': 'df91ea1dacbe1662d392bfd91417d32a0e46abe6',
        'cases_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(),
        'manifest_sha256': hashlib.sha256((dataset.parent / 'manifest.json').read_bytes()).hexdigest(),
        'corpus_checks': filechecks, 'selected_http_cases': selected,
        'summary': summary, 'http_compact': compact}
    (OWN / 'runner-observations.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OWN / 'local-measurements.json').write_text(json.dumps(local_rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OWN / 'http-measurements.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in http_rows), encoding='utf-8')
    print(json.dumps({'corpus_files': len(filechecks), 'corpus_valid': True, **summary}, ensure_ascii=False, indent=2))
