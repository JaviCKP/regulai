"""Collect immutable-source identities and independently observed review evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

snapshots = {}
for name, commit in [('source', 'da836e308daf7e518fa4f27a7c04e426f46dcd45'),
        ('closure', '0957df45362bc7cbf41c154bb13514d58901763a'),
        ('packaging', 'd63731a9c5dfda27c3dc504c295422502383d2f1')]:
    root = HERE / name
    files = [path for path in (root / 'regulai').rglob('*.py')]
    files += [root / 'requirements.txt', root / '.gitattributes']
    files += list((root / 'evals/pilot-real').glob('*'))
    files += list((root / 'evals/pilot-human').glob('*'))
    snapshots[name] = {'commit': commit, 'archive_sha256': sha(HERE / (name + '.zip')),
        'source_sha256': {path.relative_to(root).as_posix(): sha(path) for path in sorted(files) if path.is_file()}}

corpus = HERE / 'closure/evals/documents/pilot-20261003'
declared = read(corpus / 'files/manifest.json')
hashed_files = [('expectations.json', declared['expectations_sha256']),
    ('generate_corpus.py', declared['generator_sha256'])]
hashed_files += [('files/' + item['file'], item['sha256']) for item in declared['files']]
corpus_records = []
for relative, expected in hashed_files:
    content = (corpus / relative).read_bytes()
    corpus_records.append({'path': relative, 'bytes': len(content), 'expected_sha256': expected,
        'observed_sha256': hashlib.sha256(content).hexdigest(),
        'lf_only_sha256': hashlib.sha256(content.replace(b'\r\n', b'\n')).hexdigest(),
        'crlf_count': content.count(b'\r\n')})

bank_results = {}
for name in ('pilot-offline', 'human-offline'):
    rows = [json.loads(line) for line in (HERE / name / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
    calls = [call for row in rows for call in row['calls']]
    bank_results[name] = {'rows': len(rows), 'controls_passed': sum(row['control_pass'] for row in rows),
        'human_reviewed': sum(row['human_review'] is not None for row in rows),
        'modes': sorted({row['mode'] for row in rows}),
        'local_transformations': sum(call['metadata'].get('transport') == 'local' for call in calls),
        'nonzero_local_costs': sum(call['metadata'].get('transport') == 'local' and call['cost'] != '0' for call in calls),
        'results_sha256': sha(HERE / name / 'results.jsonl')}

commands = {name: read(HERE / (name + '.json')) for name in ('local-focused', 'corpus', 'pilot', 'human',
    'preflight', 'closure-independent', 'closure-migration', 'closure-corpus-red', 'packaging-corpus')}
evidence = {'review_axis': 'Spec', 'baseline_commit': '700389c216592db1e0c8725749bb4fd02cf3fa10',
    'snapshots': snapshots, 'commands': commands, 'bank_results': bank_results,
    'frozen_corpus_before_fix': corpus_records,
    'packaging_followup': read(HERE / 'packaging-verification.json'),
    'packaging_followup_sha256': sha(HERE / 'packaging-verification.json'),
    'finding': {'id': 'SPEC-LOCAL-1', 'priority': 'P2', 'scope': 'preexisting corpus packaging; outside new local runtime delta',
        'repro': 'core.autocrlf=true; git archive 0957df4; FrozenPilotCorpusTests rejects exported hashes',
        'status': 'closed_independently_verified', 'fixed_commit': 'd63731a9c5dfda27c3dc504c295422502383d2f1'},
    'execution_limits': {'real_product_calls': 0, 'human_participants': 0, 'human_reviews': 0,
        'database': 'isolated in-memory SQLite', 'postgres_rerun': False,
        'historical_302_tests_and_150_offline_reused': False},
    'review_harness_corrections': [
        'Initial history probe submitted conversation_id in POST to /chat/send/; web adapters take it from URL. Corrected probe to real conversation URLs; product unchanged.',
        'Initial mixed 23-test run had that harness failure and the corpus failure; other 21 passed. Focused final runs retain independent and migration outputs.',
        'Runner extension briefly reused name as environment variable loop iterator; three runner invocations failed before tests. Fixed local runner only.',
        'First 24/72 pilot reports can inherit the parent Git HEAD because archive remains under a Git worktree; authoritative source identity is this frozen archive/source manifest, not that incidental reported HEAD.'
    ],
    'evidence_sha256': {path.name: sha(path) for path in sorted(HERE.iterdir())
        if path.is_file() and path.suffix in {'.py', '.log', '.md'}},
}
(HERE / 'evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'evidence': str(HERE / 'evidence.json'), 'sha256': sha(HERE / 'evidence.json'),
    'corpus_mismatches': [item['path'] for item in corpus_records if item['expected_sha256'] != item['observed_sha256']]}, indent=2))
