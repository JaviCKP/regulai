"""Read old artifacts and run new offline checks against the fixed P02 snapshot."""
import contextlib
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import types
from unittest.mock import patch

sys.dont_write_bytecode = True
OWN = Path(__file__).resolve().parent
ROOT = OWN.parents[2]
SNAPSHOT = OWN / 'snapshot'
REVISION = '535eb9d8421006ea8476ea511427a7dcda9cee3b'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-name', default='run-02')
arguments = parser.parse_args()
if not arguments.output_name.startswith('run-') or not arguments.output_name[4:].isdigit():
    raise ValueError('Output must be a new run-N name inside the P02 directory')
OUT = OWN / arguments.output_name
OUT.mkdir(exist_ok=False)
for script in ('run_checks.py', 'p02_checks.py'):
    (OUT / script.replace('.py', '.executed.py')).write_bytes((OWN / script).read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def source_hashes():
    return {p.relative_to(SNAPSHOT).as_posix(): digest(p) for p in sorted((SNAPSHOT / 'regulai').rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.html')}


source_before = source_hashes()
old_reports = [ROOT / 'evals/reports/pilot-documents-20261003-01', ROOT / 'evals/reports/pilot-ui-followup-20261003-01']
input_paths = [ROOT / p for p in ['AGENTS.md', 'docs/agents/domain.md', 'docs/agents/issue-tracker.md',
    'docs/plan-blackhat/README.md', 'docs/plan-blackhat/documentos-y-ensayos-piloto.md',
    'docs/plan-blackhat/piloto-controlado.md', 'docs/plan-blackhat/operacion-y-recuperacion-piloto.md',
    'evals/documents/pilot-20261003/expectations.json', 'evals/documents/pilot-20261003/files/manifest.json',
    'evals/reports/pilot-operations-20261003-10/result.json',
    'evals/reports/pilot-operations-20261003-10/restart-result.json',
    'evals/reports/pilot-operations-20261003-10/snapshot-before.log',
    'evals/reports/pilot-operations-20261003-10/snapshot-restored.log',
    'evals/reports/pilot-operations-20261003-10/rollback-verified.log',
    'evals/reports/pilot-operations-20261003-10/commands.json',
    'evals/reports/pilot-operations-20261003-10/source-manifest.json']]
checks = []


def check(name, passed, detail):
    checks.append({'name': name, 'passed': bool(passed), 'detail': detail})


for report in old_reports:
    index = read(report / 'evidence-sha256.json')
    mismatches = []
    for record in index['files']:
        path = report / record['file']
        input_paths.append(path)
        if not path.is_file() or digest(path) != record['sha256'] or path.stat().st_size != record['bytes']:
            mismatches.append(record['file'])
    input_paths.append(report / 'evidence-sha256.json')
    check(report.name + ':recorded_hashes', not mismatches, {'files': len(index['files']), 'mismatches': mismatches})

docs = old_reports[0]
pending = read(docs / 'receipt-before-consent.json')
cancelled = read(docs / 'receipt-cancelled.json')
check('prior_pending_and_cancel_have_zero_calls', pending['status'] == 'pending_consent'
      and cancelled['status'] == 'cancelled' and not pending['receipt']['calls'] and not cancelled['receipt']['calls'],
      'Different historical requests; cancellation is not claimed to cancel the pending document record.')
states = [read(docs / ('state-postfix-' + name + '.json')) for name in ('pending', 'expired', 'completed')]
requests = [state['requests'][0] for state in states]
check('prior_expiry_preserves_request_file_message',
      all(len({row[key] for row in requests}) == 1 for key in ('request_id', 'file_sha256', 'user_message_id'))
      and requests[0]['calls'] == requests[1]['calls'] == 0 and requests[1]['status'] == 'pending_consent'
      and requests[1]['consent_reason'] == 'consent_expired' and requests[2]['status'] == 'completed'
      and states[2]['messages'] == {'assistant': 1, 'user': 1},
      {'request_id': requests[0]['request_id'], 'calls': [row['calls'] for row in requests],
       'historical_clock_wait_seconds': 316.599294, 'new_wait_performed': False})
receipt = read(docs / 'receipt-postfix-completed.json')['receipt']
generations = [call for call in receipt['calls'] if call['purpose'] == 'generation']
check('prior_receipt_retains_omission_and_two_distinct_attempts',
      receipt['coverage']['status'] == 'complete_text_only' and receipt['coverage']['warnings'] == ['images_unread']
      and receipt['coverage']['disclosures'][0]['locators'] == ['word/document.xml/paragraph:3']
      and [call['verification']['status'] for call in generations] == ['failed', 'passed']
      and len(receipt['calls']) == 8 and receipt['total']['attempts'] == 2,
      {'calls': len(receipt['calls']), 'generations': len(generations), 'estimated_fixture_cost': receipt['total']['cost']})
for label, path in [('reconstructed_ui', docs / 'receipt-outcome-unknown-reconstruction.json'),
                    ('historical_actual_process_kill', ROOT / 'evals/reports/pilot-operations-20261003-10/restart-result.json')]:
    item = read(path)
    calls = [call for call in item['receipt']['calls'] if call['purpose'] == 'generation']
    check(label + ':unknown_not_zero', item['status'] == 'outcome_unknown' and 'total' not in item['receipt']
          and all(call['status'] == 'started' and call['cost'] is None for call in calls)
          and bool(calls) and item.get('success', False) is False,
          {'new_interruption_performed': False, 'generations': len(calls)})
snapshot_text = (old_reports[1] / 'browser-completed-snapshot.yml').read_text(encoding='utf-8')
check('prior_completed_notice_is_historical', 'Previous confirmation notice: A previous confirmation expired.' in snapshot_text
      and 'Confirm sending' not in snapshot_text and 'Cancel request' not in snapshot_text,
      'Read historical snapshot; no browser opened by P02.')
snapshots = []
for name in ('snapshot-before.log', 'snapshot-restored.log', 'rollback-verified.log'):
    text = (ROOT / 'evals/reports/pilot-operations-20261003-10' / name).read_text(encoding='utf-8-sig')
    snapshots.append(json.loads(next(line for line in text.splitlines() if line.startswith('{'))))
check('prior_recovery_inventories_match', snapshots[0] == snapshots[1] == snapshots[2],
      {'tables': len(snapshots[0]['tables']), 'media_files': len(snapshots[0]['media']),
       'credentials_readable': all(item['credentials_readable'] for item in snapshots), 'new_restore_performed': False})
ops = ROOT / 'evals/reports/pilot-operations-20261003-10'
ops_commands = read(ops / 'commands.json')
bad_logs = [record['log'] for record in ops_commands if digest(ops / record['log']) != record['sha256']]
check('operations10_command_log_hashes', not bad_logs, {'logs': len(ops_commands), 'mismatches': bad_logs})
save('input-provenance.json', {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
    'files': [{'file': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)}
              for p in sorted(set(input_paths))], 'source_revision': REVISION,
    'snapshot_archive_sha256': digest(OWN / 'snapshot.zip'), 'snapshot_sources_before': source_before})

sys.path.insert(0, str(SNAPSHOT / 'regulai'))
sys.path.insert(0, str(OWN))
sys.modules['regulai.local_settings'] = types.ModuleType('regulai.local_settings')
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
temporary = OUT / 'temporary'
temporary.mkdir()
tempfile.tempdir = str(temporary)
blocked_network_attempts = []


def deny_network(*args, **kwargs):
    blocked_network_attempts.append('network_attempt_blocked')
    raise AssertionError('P02 offline guard blocked real network access')


import requests as http_requests
with patch.object(socket.socket, 'connect', side_effect=deny_network), \
     patch.object(socket, 'create_connection', side_effect=deny_network), \
     patch.object(http_requests.sessions.Session, 'request', side_effect=deny_network):
    import django
    django.setup()
    from django.conf import settings
    settings.MEDIA_ROOT = str(OUT / 'media')
    settings.PLATFORM_ADMIN_USER_IDS = []
    if settings.DATABASES['default']['NAME'] != ':memory:':
        raise RuntimeError('Only an in-memory database is allowed')
    module_path = SNAPSHOT / 'evals/documents/pilot-20261003/verify_corpus.py'
    spec = importlib.util.spec_from_file_location('p02_corpus_verifier', module_path)
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    corpus_exit = corpus.verify(OUT / 'extraction-results.json')
    check('new_frozen_corpus_extraction', corpus_exit == 0, {'report': 'extraction-results.json'})
    from django.core.files.uploadedfile import SimpleUploadedFile
    from front.documents import extract_document
    expectation = read(OWN / 'english-expectations.json')
    english = extract_document(SimpleUploadedFile('english-contract.txt', (OWN / 'english-contract.txt').read_bytes()))
    english_pass = english.status == expectation['status'] and english.units_total == expectation['units_total'] \
        and english.warnings == expectation['warnings'] and all(text in english.text for text in expectation['contains']) \
        and expectation['evidence_locator'] in [fragment['locator'] for fragment in english.fragments]
    save('english-extraction.json', {'passed': english_pass, 'expectations_sha256': digest(OWN / 'english-expectations.json'),
        'file_sha256': digest(OWN / 'english-contract.txt'), 'metadata': english.metadata(), 'fragments': english.fragments,
        'human_validation': False, 'model_answer_generated': False, 'browser_used': False})
    check('new_english_text_extraction', english_pass, {'report': 'english-extraction.json'})
    from django.test.runner import DiscoverRunner
    labels = ['p02_checks.BetaAdministratorIsolationTests', 'p02_checks.BetaDocumentCancellationTests',
        'front.test_chat_ui.ChatUITests',
        'front.test_chat_flow.ChatFlowTests',
        'front.test_state.RequestStateTests.test_confirmation_binds_actor_company_content_policy_and_endpoint',
        'front.test_state.RequestStateTests.test_foreign_conversation_and_credential_never_fall_back_to_own_destination',
        'front.test_state.RequestStateTests.test_cancelled_request_and_stale_processing_never_regenerate',
        'front.test_state.RequestStateTests.test_overlapping_confirmation_posts_generate_once_without_open_transaction',
        'front.test_review_regressions.ReviewRegressionTests.test_b09_expired_consent_issues_a_fresh_usable_token',
        'front.test_document_fidelity.DocumentHTTPTests.test_frozen_unreadable_and_partial_documents_block_all_send_entries',
        'front.test_document_fidelity.DocumentHTTPTests.test_frozen_final_page_clause_survives_all_send_entries_with_exact_citation',
        'front.test_document_fidelity.DocumentHTTPTests.test_inline_pdf_requires_coverage_consent_before_all_three_send_entries',
        'front.test_frontend_chat.ChatUiTests.test_finished_receipt_does_not_request_confirmation_for_historical_reason',
        'front.test_frontend_chat.ChatUiTests.test_unknown_outcome_without_total_never_renders_zero_cost_or_success']
    with (OUT / 'tests.log').open('x', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        runner = DiscoverRunner(verbosity=2, interactive=False)
        failures = runner.run_tests(labels)
    check('new_selected_django_tests', failures == 0, {'labels': labels, 'failures': failures, 'report': 'tests.log',
          'clock_expiry_in_new_test': 'mocked 301 seconds; not wall-clock waiting',
          'javascript': 'offline Node DOM harness, not browser actions'})

source_after = source_hashes()
check('snapshot_sources_unchanged', source_before == source_after, {'source_files': len(source_before)})
check('real_network_guard_unused', not blocked_network_attempts, {'blocked_attempts': len(blocked_network_attempts),
      'real_provider_calls': 0, 'database': 'SQLite in-memory test database', 'user_local_settings_imported': False})
save('checks.json', {'schema_version': 1, 'kind': 'new_agent_offline_checks_and_prior_artifact_review',
    'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'source_revision': REVISION,
    'human_trial': False, 'human_validation': False, 'browser_actions': 0, 'new_provider_calls': 0,
    'checks': checks, 'passed': sum(row['passed'] for row in checks), 'total': len(checks),
    'snapshot_sources_after': source_after})
result = {'passed': sum(row['passed'] for row in checks), 'total': len(checks), 'django_failures': failures,
          'human_trial': False, 'browser_actions': 0, 'new_provider_calls': 0}
print(json.dumps(result))
raise SystemExit(0 if all(row['passed'] for row in checks) else 1)
