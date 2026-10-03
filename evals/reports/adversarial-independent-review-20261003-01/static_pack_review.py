"""Read-only checks of explicitly named public proposal files; never imports bridge."""
import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
PACK = REPO / 'evals/adversarial-live/community-20261003-02'
FIXED = OWN / 'followup'
ORIGINAL = FIXED / 'evals/reports/pilot-real-vercel-20261003-01/run_authorized.py'
def sha(data):
    return hashlib.sha256(data).hexdigest()
def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def read(name):
    return json.loads((PACK / name).read_text(encoding='utf-8'))
def function_source(text, name):
    tree = ast.parse(text)
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(text, node)

manifest, approval = read('manifest.json'), read('authorization.pending.json')
bridge = (PACK / 'run_authorized.py').read_text(encoding='utf-8')
original = ORIGINAL.read_text(encoding='utf-8')
previous_function = function_source(original, 'credentials_readonly')
new_function = function_source(bridge, 'credentials_readonly')
assert new_function == previous_function
manifest_sha = sha((PACK / 'manifest.json').read_bytes())
assert manifest_sha == '80d336bd1cbb7a75e4a46a8c922b8a52afa8a9c4567dec2c380d8088be5c13f0'
assert approval['status'] == 'pending' and approval['approved'] is False
assert approval['approved_by'] is None and approval['approval_reference'] is None
assert approval['valid_from'] is None and approval['valid_until'] is None
assert approval['manifest_sha256s'] == [manifest_sha]
assert manifest['credential_bridge_sha256'] == sha((PACK / 'run_authorized.py').read_bytes())
assert manifest['credential_bridge_origin_sha256'] == sha(ORIGINAL.read_bytes())
assert manifest['dataset_sha256'] == sha((PACK / 'cases.jsonl').read_bytes())
assert manifest['human_rubric_sha256'] == sha((PACK / 'rubric.md').read_bytes())
assert manifest['reference_label_sha256'] == {'oracles.json': sha((PACK / 'oracles.json').read_bytes())}
assert manifest['preparation_sha256'] == sha((REPO / 'scripts/prepare_adversarial_pilot.py').read_bytes())
ids = ['INJ-03', 'INJ-05', 'PII-01', 'BENIGN-01']
cases = [json.loads(line) for line in (PACK / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
oracles = read('oracles.json')
corpus_path = FIXED / 'evals/adversarial/community-20261003'
corpus = {row['id']: row for row in map(json.loads, (corpus_path / 'cases.jsonl').read_text(encoding='utf-8').splitlines())}
assert [row['id'] for row in cases] == ids == [row['id'] for row in oracles]
assert oracles == [corpus[name] for name in ids]
for row, oracle in zip(cases, oracles):
    assert row['input'] == oracle['prompt']
    assert row['corpus_case_sha256'] == sha(canonical(oracle))
    if oracle['document_ref']:
        assert row['document'] == (corpus_path / oracle['document_ref']).read_text(encoding='utf-8')
    assert not {'classification', 'expected_redactions', 'preserve', 'desired_semantic_behavior', 'attack_objective'}.intersection(row)
assert manifest['destinations'] == {
    'generation': 'https://api.deepseek.com', 'judge': 'https://ai-gateway.vercel.sh/typesafe/v1/systemone'}
assert manifest['judge_transport'] == 'vercel' and manifest['model_versions']['judge'] == 'typesafe-ai/jev'
assert manifest['masking']['backend'] == 'local' and Decimal(manifest['call_caps_usd']['obfuscation']) == 0
assert manifest['maximum_usd'] == approval['maximum_usd'] == '1.00'
assert approval['retain_existing_costs'] is True and approval['reserved_evaluation'] is False
assert approval['execution_scope'] == {'case_ids': ids, 'configurations': ['economy', 'strong', 'router'],
    'max_runs': 1, 'max_combinations': 12, 'max_external_calls': 44, 'repeat_uncertain_calls': False}
assert approval['extends'] == {'authorization_id': 'pilot-community-20261003-vercel-approved-v1',
    'authorization_digest': 'aea3a73b0d94bba65c7d629f2a47ad1befd46896097424bda2b2d4c58a1b3591'}
main = function_source(bridge, 'main')
guard = main.index("approval.get('approved') is not True")
assert guard < main.index('credentials_readonly()')
assert "MANIFEST = HERE / 'manifest.json'" in bridge
assert "AUTHORIZATION = HERE / 'authorization.approved.json'" in bridge
assert "EVIDENCE = ROOT / 'evals/reports/adversarial-real-20261003-01'" in bridge
assert 'HERE /' not in main
assert not (PACK / 'authorization.approved.json').exists()
source_tree = ast.parse((FIXED / 'regulai/front/evaluation.py').read_text(encoding='utf-8'))
source_names = ast.literal_eval(next(node.value for node in source_tree.body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'SOURCE_FILES' for target in node.targets)))
assert set(source_names) == set(manifest['source_sha256'])
source_checks = []
for name in source_names:
    checkout = (REPO / name).read_bytes()
    frozen = (FIXED / name).read_bytes()
    source_checks.append({'path': name, 'manifest_bytes_match': sha(checkout) == manifest['source_sha256'][name],
        'fixed_commit_content_match_after_CRLF_normalization': checkout.replace(b'\r\n', b'\n') == frozen.replace(b'\r\n', b'\n')})
assert all(item['manifest_bytes_match'] and item['fixed_commit_content_match_after_CRLF_normalization'] for item in source_checks)
generation, judge = Decimal(manifest['call_caps_usd']['generation']), Decimal(manifest['call_caps_usd']['classification'])
assert Decimal(manifest['call_caps_usd']['verification']) == judge
additional = 4 * ((2 * (generation + 2 * judge)) + (2 * generation + 3 * judge))
combined = additional + Decimal('.013858062')
assert additional == Decimal('.884') and combined == Decimal('.897858062')
pending = read('preflight.pending.json')
assert pending['ready_for_real'] is False
report = {'source_commit': '128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2', 'manifest_sha256': manifest_sha,
    'checks_passed': True, 'credential_function_text_identical': True,
    'credential_function_sha256': sha(new_function.encode()),
    'guard_precedes_credential_function_call': True, 'bridge_executed': False,
    'preflight_executed_by_reviewer': False, 'approved_file_absent': True,
    'case_ids': ids, 'oracle_sidecar_matches_frozen_corpus': True,
    'budget_additional_usd': str(additional), 'budget_combined_exposure_usd': str(combined),
    'prior_exposure_source': 'parent task statement; real ledger not opened',
    'pending_blockers': pending['blockers'], 'source_checks': source_checks,
    'files': {name: sha((PACK / name).read_bytes()) for name in ('manifest.json', 'authorization.pending.json',
        'cases.jsonl', 'oracles.json', 'rubric.md', 'run_authorized.py', 'preflight.pending.json', 'README.md')}}
(OWN / 'static-pack-observations.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ('source_checks', 'files')}, indent=2))
