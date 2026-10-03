import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
local = json.loads((OWN / 'local-measurements.json').read_text(encoding='utf-8'))
http = [json.loads(line) for line in (OWN / 'http-measurements.jsonl').read_text(encoding='utf-8').splitlines()]
summary = json.loads((OWN / 'runner-observations.json').read_text(encoding='utf-8'))['summary']
failures = []
for row in local:
    if row['measurement']['passed'] is not True:
        failures.append({'case_id': row['case_id'],
            'remaining': [item['remaining_representations'] for item in row['measurement']['redactions'] if not item['passed']],
            'lost': [item['value'] for item in row['measurement']['preservations'] if not item['passed']]})
examples = []
for name in ('INJ-05', 'PII-03', 'PII-12', 'DOC-08'):
    row = next(row for row in http if row['case_id'] == name and row['endpoint'] == '/api/chat/send/' and row['provider_profile'] == 'neutral')
    examples.append({'case_id': name, 'observed_control': row['observed_control'],
        'verification': row['decision'].get('verification'),
        'missing_in_boundary_content': [{'purpose': event['purpose'],
            'values': [item['value'] for item in event['bytes_measurement']['preservations'] if not item['passed']],
            'input_content': event['delivered_input_content']} for event in row['boundary_events']
            if any(not item['passed'] for item in event['bytes_measurement']['preservations'])],
        'remaining_sensitive': [item['remaining_representations'] for item in row['bytes_measurement']['redactions'] if item['remaining_representations']]})
result = {'fresh_local_cases': len(local), 'fresh_http_runs': len(http),
    'local_expectations_met': summary['local_expectations_met'],
    'local_redactions': [summary['local_redaction_annotations_removed'], summary['local_redaction_annotations']],
    'local_preservations': [summary['local_preservation_annotations_retained'], summary['local_preservation_annotations']],
    'http_controls_met': summary['control_runs_passed'], 'local_failures': failures,
    'examples': examples, 'all_metrics_are_exact_annotation_or_pipeline_controls': True,
    'llm_semantics_measured': False}
(OWN / 'measurement-notes.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=True, indent=2))
