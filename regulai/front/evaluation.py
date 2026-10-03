"""Small pilot harness around the application's chat service, never an alternate pipeline."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import csv
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from . import chat_service, jev
from .connectors import get_connector
from .evaluation_budget import BudgetExceeded, EvaluationBudget, money
from .models import Company, CompanyEngine, Engine, EngineModel, ObfuscationConfig, Profile, Rule, RulesGroup

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / '.claude' / 'pilot-real-budget.sqlite3'
PILOT_MANIFEST = ROOT / 'evals' / 'pilot-real' / 'manifest.json'
SOURCE_FILES = ('regulai/front/chat_service.py', 'regulai/front/policy.py', 'regulai/front/routing.py',
    'regulai/front/verification.py', 'regulai/front/jev.py', 'regulai/front/documents.py',
    'regulai/front/masking.py', 'regulai/front/local_masking.py', 'regulai/front/classification.py', 'regulai/front/sources.py',
    'regulai/front/connectors.py', 'regulai/front/views.py', 'regulai/front/models.py',
    'regulai/front/evaluation.py', 'regulai/front/evaluation_budget.py',
    'regulai/front/management/commands/evaluate_ai.py', 'regulai/front/management/commands/smoke_ai.py',
    'requirements.txt')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
    except (OSError, ValueError) as error:
        raise CommandError(f'Cannot read valid JSON from {Path(path).name}: {type(error).__name__}') from None


def load_pilot(path):
    path = Path(path).resolve()
    manifest = read_json(path)
    if manifest.get('bank_kind') != 'pilot' or manifest.get('configurations') != ['economy', 'strong', 'router']:
        raise CommandError('Use a versioned pilot manifest with all three configurations.')
    dataset = (path.parent / manifest['dataset']).resolve()
    if not dataset.is_relative_to(path.parent):
        raise CommandError('Pilot cases must stay in the manifest directory.')
    try:
        cases = [json.loads(line) for line in dataset.read_text(encoding='utf-8').splitlines() if line.strip()]
    except (OSError, ValueError):
        raise CommandError('Invalid pilot dataset.') from None
    if (not cases or len({case['id'] for case in cases}) != len(cases)
            or any(case['split'] not in ('development', 'reserved') or not case.get('input') for case in cases)):
        raise CommandError('Pilot cases require unique IDs, inputs and frozen splits.')
    if any(len((case['input'] + case.get('document', '')).encode('utf-8')) > manifest['input_limit_bytes'] for case in cases):
        raise CommandError('A synthetic case exceeds the frozen input byte limit.')
    if digest(dataset.read_bytes()) != manifest.get('dataset_sha256'):
        raise CommandError('Pilot dataset changed; prepare a new manifest and approval.')
    rubric = (path.parent / manifest['human_rubric']).resolve()
    if not rubric.is_relative_to(path.parent) or digest(rubric.read_bytes()) != manifest.get('human_rubric_sha256'):
        raise CommandError('Human rubric changed; prepare a new manifest and approval.')
    for name, expected_hash in manifest.get('reference_label_sha256', {}).items():
        label = (path.parent / name).resolve()
        # Only bytes are hashed. Reference labels never enter prompts or scores.
        if not label.is_relative_to(path.parent) or digest(label.read_bytes()) != expected_hash:
            raise CommandError('Frozen reference labels changed; reserved evaluation must be prepared again.')
    return manifest, cases


def source_hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def runtime_versions():
    versions = {'python': sys.version.split()[0]}
    for name in ('Django', 'djangorestframework', 'openai', 'pydantic', 'requests', 'pypdf', 'python-docx',
                 'spacy', 'xx-ent-wiki-sm'):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def local_masking_manifest():
    """Read the installed detector identity without loading NLP or accessing a network."""
    from .local_masking import detector_metadata
    return {**detector_metadata(), 'detect': 'both', 'language': ''}


def preflight(manifest_path, authorization_path=None, *, now=None, check_credentials=True):
    """Read-only. Never opens a provider or the ledger and never upgrades approval."""
    manifest, cases = load_pilot(manifest_path)
    now = now or datetime.now(timezone.utc)
    blockers = []
    manifest_hash = digest(Path(manifest_path).read_bytes())
    if manifest.get('source_sha256') != source_hashes():
        blockers.append('source_changed')
    if manifest.get('runtime_versions') != runtime_versions():
        blockers.append('runtime_changed')
    approval = read_json(authorization_path) if authorization_path else {}
    if approval.get('status') != 'approved' or not approval.get('approved_by') or not approval.get('approval_reference'):
        blockers.append('new_explicit_authorization_required')
    if manifest_hash not in approval.get('manifest_sha256s', []):
        blockers.append('authorization_manifest_mismatch')
    if approval.get('authorization_id') != manifest['authorization_id']:
        blockers.append('authorization_identity_mismatch')
    try:
        start = datetime.fromisoformat(approval['valid_from'])
        end = datetime.fromisoformat(approval['valid_until'])
        if start.tzinfo is None or end.tzinfo is None or not start <= now <= end or (end - start).total_seconds() > 86400:
            blockers.append('authorization_expired_or_invalid_window')
    except (KeyError, TypeError, ValueError):
        blockers.append('authorization_expired_or_invalid_window')
    try:
        cap = money(approval['maximum_usd'])
        if cap != money(manifest['maximum_usd']) or not 0 < cap <= 1:
            blockers.append('authorization_budget_mismatch')
    except (KeyError, TypeError, ValueError, ArithmeticError):
        blockers.append('authorization_budget_mismatch')
    if approval.get('destinations') != manifest['destinations']:
        blockers.append('authorization_destinations_mismatch')
    if approval.get('data_scope') != 'versioned_synthetic_cases_only':
        blockers.append('synthetic_data_scope_required')
    if approval.get('actions') != manifest.get('actions') or not manifest.get('actions'):
        blockers.append('explicit_actions_required')
    if approval.get('reserved_evaluation') is not True and any(case['split'] == 'reserved' for case in cases):
        blockers.append('reserved_evaluation_not_approved')
    if manifest.get('bank_purpose') == 'independent_human_calibration':
        review = manifest.get('reference_review', {})
        if (review.get('status') != 'reviewed' or len(set(review.get('reviewers', []))) < 2
                or not review.get('reviewed_at')):
            blockers.append('independent_reference_review_required')
    if approval.get('mutable_alias_acknowledged') is not True and manifest.get('mutable_model_aliases'):
        blockers.append('mutable_alias_acknowledgment_required')
    try:
        checked = date.fromisoformat(manifest['price_date'])
        if checked != now.date() or approval.get('pricing_reviewed_on') != checked.isoformat():
            blockers.append('same_day_official_pricing_review_required')
    except (KeyError, TypeError, ValueError):
        blockers.append('same_day_official_pricing_review_required')
    masking = manifest.get('masking', {'backend': 'http'})
    masking_observed = None
    if masking.get('backend') == 'local':
        if 'mask' in manifest['destinations'] or money(manifest['call_caps_usd']['obfuscation']) != 0:
            blockers.append('local_mask_must_have_no_endpoint_and_zero_api_bound')
        if approval.get('masking') != masking:
            blockers.append('authorization_local_mask_mismatch')
        try:
            masking_observed = local_masking_manifest()
        except (ImportError, RuntimeError, OSError):
            blockers.append('local_mask_runtime_unavailable')
        else:
            if masking != masking_observed:
                blockers.append('local_mask_detector_changed')
    elif masking.get('backend') == 'http':
        parsed = urlsplit(manifest['destinations'].get('mask') or '')
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.hostname.endswith('.invalid')
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            blockers.append('authorized_mask_destination_required')
        if not manifest.get('mask_contract_review') or approval.get('mask_contract_reviewed') is not True:
            blockers.append('mask_contract_and_price_review_required')
    else:
        blockers.append('unsupported_mask_backend')
    # No arbitrary new endpoint is inferred from a file or an environment variable.
    if manifest['destinations']['generation'] != 'https://api.deepseek.com':
        blockers.append('unsupported_generator_destination')
    judge_destination = (manifest['destinations']['judge'], manifest['judge_transport'], manifest['model_versions']['judge'])
    if judge_destination not in ((jev.ENDPOINT, 'typesafe', 'jev-1.13.0'),
                                 (jev.VERCEL_ENDPOINT, 'vercel', jev.VERCEL_MODEL)):
        blockers.append('pinned_judge_destination_required')
    if manifest.get('generation_options') != {'thinking': {'type': 'disabled'},
            'temperature': 0.6, 'document_temperature': 0.1}:
        blockers.append('unsupported_generation_options')
    if check_credentials and (not os.environ.get('REGULAI_EVAL_GENERATOR_KEY') or not os.environ.get('REGULAI_EVAL_JEV_KEY')):
        blockers.append('isolated_credentials_required')
    return {'ready_for_real': not blockers, 'blockers': blockers, 'manifest_sha256': manifest_hash,
            'source_sha256': source_hashes(), 'cases': len(cases), 'maximum_usd': manifest['maximum_usd'],
            'masking_observed': masking_observed, 'ledger': str(LEDGER_PATH), 'network_calls': 0}, approval


class LedgerObserver:
    """Every service boundary reserves; local transformations reserve zero API cost."""
    def __init__(self, ledger, manifest, destinations, *, case_id, configuration, authorize=None):
        self.ledger, self.manifest, self.destinations = ledger, manifest, destinations
        self.case_id, self.configuration, self.authorize = case_id, configuration, authorize
        self.tokens, self.stop_reason = [], None

    def before_call(self, call):
        if self.authorize:
            self.authorize()
        if self.stop_reason:
            raise BudgetExceeded(self.stop_reason)
        purpose = call['purpose']
        if purpose not in self.manifest['call_caps_usd'] or call['provider'] != self.destinations.get(purpose):
            raise BudgetExceeded('Unexpected pilot destination or purpose.')
        expected = (list(self.manifest['model_versions'][level] for level in ('economy', 'strong'))
                    if purpose == 'generation' else [None] if purpose == 'obfuscation' else [self.manifest['model_versions']['judge']])
        if call['model'] not in expected or call['cost_bound'] is None:
            raise BudgetExceeded('Unexpected pilot model or unknown call bound.')
        bound = money(call['cost_bound'])
        if bound > money(self.manifest['call_caps_usd'][purpose]):
            raise BudgetExceeded('The application call exceeds the approved per-call bound.')
        transport = call.get('transport', 'http')
        expected_transport = self.manifest.get('masking', {}).get('backend', 'http') if purpose == 'obfuscation' else 'http'
        if transport != expected_transport or transport == 'local' and bound != 0:
            raise BudgetExceeded('Unexpected pilot transport or nonzero local API bound.')
        token = self.ledger.reserve(purpose, bound, zero_cost=purpose == 'obfuscation' and bound == 0,
            metadata={'case_id': self.case_id, 'configuration': self.configuration,
                      'provider': call['provider'], 'model': call['model'], 'transport': transport,
                      'cost_scope': call.get('cost_scope', 'api')})
        self.tokens.append(token)
        try:
            if self.authorize:
                self.authorize()
        except Exception:
            self.stop_reason = 'authorization_changed_before_transport'
            # Reservation can wait for a writer while the approval is revoked or
            # expires. No transport has started, so this expense is provably zero.
            # Keep the token for conservative recovery if settlement itself fails.
            self.ledger.complete(token, cost='0', status='not_started', cost_kind='not_incurred')
            raise
        return token

    def after_call(self, call, token):
        effective = call.get('model_effective')
        if call['purpose'] != 'obfuscation' and call.get('status') == 'completed':
            expected = self.manifest['allowed_effective_models'].get(call['model'], [])
            if effective not in expected:
                self.stop_reason = 'effective_model_changed_or_missing'
        if call['status'] != 'completed':
            self.stop_reason = 'failed_or_uncertain_provider_call'
        self.ledger.complete(token, cost=call.get('cost'),
            cost_kind=call.get('cost_kind', 'unknown'), status=call['status'],
            metadata={key: call[key] for key in ('model_effective', 'input_tokens', 'output_tokens', 'provider_request_id', 'provider_error_code') if key in call})
        if self.stop_reason and call['status'] == 'completed':
            raise BudgetExceeded(self.stop_reason)

    def finish(self):
        for call in self.ledger.snapshot()['calls']:
            if call['id'] in self.tokens and call['status'] == 'started':
                local = call['metadata'].get('transport') == 'local'
                self.ledger.complete(call['id'], status='outcome_unknown',
                    cost='0' if local else None, cost_kind='configured_zero' if local else 'unknown')
                self.stop_reason = 'unsettled_provider_call'


def require_memory_database():
    database = connection.settings_dict
    name = str(database['NAME'])
    memory = name == ':memory:' or (name.startswith('file:') and parse_qs(urlsplit(name).query).get('mode') == ['memory'])
    if database['ENGINE'] != 'django.db.backends.sqlite3' or not memory:
        raise CommandError('Pilot requires isolated in-memory SQLite; no existing user database is accepted.')


@contextmanager
def real_lock():
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    path = LEDGER_PATH.with_suffix('.lock')
    try:
        handle = path.open('x', encoding='utf-8')
    except FileExistsError:
        raise CommandError('A pilot lock already exists. Inspect prior results and uncertain reservations; do not automatically retry.') from None
    try:
        handle.write(canonical({'pid': os.getpid(), 'created_at': datetime.now(timezone.utc).isoformat()}))
        handle.flush()
        yield
    finally:
        handle.close()
        path.unlink()


def configured_connector(*args, response_sink=None, **kwargs):
    """The existing connector, with the frozen DeepSeek non-thinking setting."""
    connector = get_connector(*args, **kwargs)
    original = connector.chat
    def chat(messages, **options):
        response = original(messages, **options, extra_body={'thinking': {'type': 'disabled'}})
        if response_sink:
            response_sink(response)
        return response
    connector.chat = chat
    return connector


def exercise_case(case, configuration, manifest, engine, models, ledger, *, real, authorize=None):
    from .management.commands.evaluate_ai import OfflineProviders, policy_config
    identity = uuid.uuid4().hex
    company = Company.objects.create(name='pilot-synthetic-' + identity,
        jev_api_key=os.environ['REGULAI_EVAL_JEV_KEY'] if real else 'synthetic-offline-credential')
    actor = User.objects.create(username='pilot-' + identity)
    actor.set_unusable_password()
    actor.save(update_fields=['password'])
    credential = CompanyEngine.objects.create(company=company, engine=engine,
        api_key=os.environ['REGULAI_EVAL_GENERATOR_KEY'] if real else 'synthetic-offline-credential')
    mask_backend = manifest.get('masking', {}).get('backend', 'http')
    mask = ObfuscationConfig.objects.create(company=company, name='Pilot authorized mask', backend=mask_backend,
        api_url='' if mask_backend == 'local' else manifest['destinations']['mask'] if real else 'https://mask.offline.invalid',
        active=True)
    Profile.objects.create(user=actor, company=company, default_engine=credential,
                           default_model=models['economy' if configuration == 'router' else configuration])
    config = policy_config(case, configuration, manifest, credential, models, mask)
    config['masking']['max_call_cost'] = manifest['call_caps_usd']['obfuscation'] if real else '0'
    config['jev']['transport'] = manifest['judge_transport']
    company.ai_config = config
    company.full_clean()
    company.save(update_fields=['ai_config'])
    group = RulesGroup.objects.create(company=company, name='Synthetic pilot rules')
    for marker, action in [('SYNTHETIC_SECRET', 'block'), ('SYNTHETIC_CONSENT', 'consent')]:
        Rule.objects.create(rules_group=group, name=action, action=action,
            yara_rule=f'rule synthetic_{action} {{ strings: $a = "{marker}" condition: $a }}')
    destinations = {'generation': f'engine:{credential.pk}', 'obfuscation': f'obfuscation:{mask.pk}',
                    'classification': 'jev', 'verification': 'jev'}
    observer = LedgerObserver(ledger, manifest, destinations, case_id=case['id'], configuration=configuration, authorize=authorize)
    fixture = OfflineProviders(case, manifest)
    generation_responses = []
    def retain_response(response):
        text = response.content if isinstance(response.content, str) else ''
        retained = len(text.encode('utf-8')) <= manifest['limits']['max_output_tokens'] * 8
        generation_responses.append({'model': response.model, 'content': text if retained else None,
            'content_sha256': digest(text), 'omitted_over_limit': not retained, 'finish_reason': response.finish_reason})
    def fixture_generate(*args, **kwargs):
        response = fixture.generate(*args, **kwargs)
        retain_response(response)
        return response
    command = {'content': case['input'], 'request_id': str(uuid.uuid4())}
    if case.get('document'):
        command['file'] = SimpleUploadedFile('synthetic.txt', case['document'].encode('utf-8'))
    started = time.monotonic()
    before_consent = None
    try:
        with ExitStack() as stack:
            if real:
                stack.enter_context(patch('front.chat_service.get_connector', side_effect=lambda *args, **kwargs:
                    configured_connector(*args, response_sink=retain_response, **kwargs)))
            else:
                stack.enter_context(patch('front.chat_service.get_connector', return_value=SimpleNamespace(chat=fixture_generate)))
                stack.enter_context(patch('front.jev.requests.post', side_effect=fixture.post))
                stack.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('Pilot offline forbids HTTP')))
                stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Pilot offline forbids sockets')))
            result = chat_service.send_chat_message(actor, command, call_observer=observer)
            if case.get('scenario') == 'consent_accept' and result.data['status'] == 'pending_consent':
                before_consent = len(observer.tokens)
                result = chat_service.send_chat_message(actor, {'request_id': command['request_id'],
                    'content': case['input'], 'consent_token': result.data['consent_token']}, call_observer=observer)
    finally:
        observer.finish()
    data = result.data
    receipt = data.get('receipt', {})
    calls = [call for call in ledger.snapshot()['calls'] if call['id'] in observer.tokens]
    delivered = bool(data.get('assistant_message'))
    generations = sum(call['purpose'] == 'generation' and call['status'] != 'not_started' for call in calls)
    control = (not case.get('must_block') or data['status'] == 'blocked' and not calls)
    control = control and (before_consent is None or before_consent == 0) and generations <= (2 if configuration == 'router' else 1)
    if not real and case.get('expected_status'):
        expected = case.get('expected_by_configuration', {}).get(configuration, case['expected_status'])
        from .management.commands.evaluate_ai import observed_outcome
        control = control and observed_outcome(data, receipt.get('calls', [])) == expected
    return {'case_id': case['id'], 'configuration': configuration, 'split': case['split'],
        'mode': 'real' if real else 'simulated', 'masking_backend': mask_backend,
        'masking_execution': 'local_detector' if mask_backend == 'local' else 'remote' if real else 'fixture',
        'group': case['group'], 'execution_state': data['status'],
        'error_type': data.get('error_type'), 'delivered': delivered, 'control_pass': bool(control),
        'answer': data.get('assistant_message', {}).get('content'), 'evidence': data.get('evidence', {}).get('items', []),
        'coverage': receipt.get('coverage'), 'sensitivity': receipt.get('policy', {}).get('sensitivity'),
        'verification': receipt.get('verification'), 'notices': receipt.get('notices', []),
        'generation_calls': generations, 'calls_before_consent': before_consent,
        'generation_responses': generation_responses,
        'second_attempt': generations > 1, 'receipt': receipt, 'calls': calls,
        'human_review': None, 'latency_ms': round((time.monotonic() - started) * 1000, 3),
        'stop_reason': observer.stop_reason or (data.get('error_type') if data.get('error_type') in {
            'external_budget_unavailable', 'external_accounting_failed', 'budget_bound_exceeded',
            'outcome_unknown', 'provider_failed', 'authorization_changed'} else None)}


REVIEW_FIELDS = ('correct', 'correct_abstention', 'requirements_met', 'sensitivity_correct',
                 'sensitivity_false_negative', 'sensitivity_false_positive',
                 'citations_supported', 'second_attempt_corrected', 'second_attempt_introduced')


def attach_reviews(rows, review_path):
    reviews = read_json(review_path)
    if not isinstance(reviews, list):
        raise CommandError('Human reviews must be a JSON list.')
    by_key = {(row['case_id'], row['configuration']): row for row in rows}
    seen = set()
    for review in reviews:
        key = (review.get('case_id'), review.get('configuration'))
        if key not in by_key or key in seen:
            raise CommandError('Unknown or duplicate human review row.')
        seen.add(key)
        if review.get('status') != 'reviewed':
            continue
        if (not review.get('reviewer') or not review.get('reviewed_at') or not review.get('rationale')
                or review.get('result_sha256') != digest(by_key[key])
                or any(type(review.get(field)) not in (bool, type(None)) for field in REVIEW_FIELDS)
                or review.get('correct') is None or review.get('correct_abstention') is None):
            raise CommandError('Review requires reviewer, timestamp, rationale, exact result hash and explicit boolean labels.')
        try:
            reviewed_at = datetime.fromisoformat(review['reviewed_at'])
            if reviewed_at.tzinfo is None:
                raise ValueError('Timezone required')
        except (ValueError, TypeError):
            raise CommandError('Human review timestamp must include an ISO-8601 timezone.') from None
        if review['correct'] and not by_key[key]['delivered']:
            raise CommandError('An undelivered answer cannot be counted as correct.')
        by_key[key]['human_review'] = review
    return rows


def is_external_call(call):
    # Historical records did not carry transport; do not silently recast them as local.
    return call.get('status') != 'not_started' and call.get('metadata', {}).get('transport') != 'local'


def summarize_pilot(rows):
    summaries = []
    for configuration in ('economy', 'strong', 'router'):
        for split in ('development', 'reserved', 'all'):
            selected = [row for row in rows if row['configuration'] == configuration and (split == 'all' or row['split'] == split)]
            if not selected:
                continue
            calls = [call for row in selected for call in row['calls']]
            reviewed = [row for row in selected if row.get('human_review')]
            complete = len(reviewed) == len(selected)
            reported = sum((money(call['cost']) for call in calls if call['cost'] is not None
                            and call['metadata'].get('cost_kind') == 'provider_reported'), Decimal(0))
            estimated = sum((money(call['cost']) for call in calls if call['cost'] is not None
                             and call['metadata'].get('cost_kind') == 'tariff_estimate'), Decimal(0))
            uncertain = sum((money(call['reserved']) for call in calls if call['cost'] is None), Decimal(0))
            unknown = sum(call['cost'] is None for call in calls)
            correct = sum(row['human_review']['correct'] is True and row['delivered'] for row in reviewed)
            latencies = sorted(row['latency_ms'] for row in selected)
            def labeled(field):
                values = [row['human_review'][field] for row in reviewed if row['human_review'].get(field) is not None]
                return {'positive': sum(values), 'negative': len(values) - sum(values), 'n': len(values)}
            summaries.append({'configuration': configuration, 'split': split, 'n': len(selected),
                'controls_passed': sum(row['control_pass'] for row in selected), 'delivered': sum(row['delivered'] for row in selected),
                'coverage': sum(row['delivered'] for row in selected) / len(selected),
                'human_reviewed_n': len(reviewed), 'human_review_complete': complete,
                'correct_answers': correct if reviewed else None,
                **{field: labeled(field) for field in REVIEW_FIELDS if field != 'correct'},
                'second_attempts': sum(row['second_attempt'] for row in selected),
                'accounting_entries': len(calls),
                'provider_calls': sum(is_external_call(call) for call in calls),
                'local_transformations': sum(call.get('status') != 'not_started' and call['metadata'].get('transport') == 'local' for call in calls),
                'local_api_cost_usd': str(sum((money(call['cost']) for call in calls
                    if call['metadata'].get('transport') == 'local' and call['cost'] is not None), Decimal(0))),
                'calls_by_purpose': {purpose: sum(call['purpose'] == purpose and is_external_call(call) for call in calls)
                    for purpose in ('obfuscation', 'classification', 'generation', 'verification')},
                'provider_reported_usd': str(reported), 'tariff_estimated_usd': str(estimated),
                'uncertain_reserved_usd': str(uncertain), 'unknown_cost_calls': unknown,
                'cost_per_correct_estimated_usd': str((reported + estimated) / correct) if complete and correct and not unknown else None,
                'cost_per_correct_reported_usd': str(reported / correct) if complete and correct and not unknown and estimated == 0 else None,
                'p50_latency_ms': statistics.median(latencies), 'p95_latency_ms': latencies[math.ceil(len(latencies) * .95) - 1],
                'real_provider_cases': sum(row['mode'] == 'real' and any(call['purpose'] == 'generation'
                    and call.get('status') != 'not_started' for call in row['calls']) for row in selected),
                'quality_claim': None, 'savings_claim': None})
    return summaries


def write_reports(output, manifest, rows, budget):
    summaries = summarize_pilot(rows)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'results.jsonl').write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
    if summaries:
        with (output / 'summary.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows({key: canonical(value) if isinstance(value, dict) else value for key, value in row.items()} for row in summaries)
    (output / 'budget.json').write_text(json.dumps(budget, indent=2) + '\n', encoding='utf-8')
    reviews = [{'case_id': row['case_id'], 'configuration': row['configuration'], 'result_sha256': digest(row),
        'status': 'pending', 'reviewer': None, 'reviewed_at': None, 'rationale': None,
        **{field: None for field in REVIEW_FIELDS}} for row in rows]
    (output / 'human-review.pending.json').write_text(json.dumps(reviews, indent=2) + '\n', encoding='utf-8')
    lines = ['# Pilot evaluation', '', f"Mode: **{manifest['execution_mode']}**. Runs: {len(rows)}. Human review is separate; no quality or savings claim.", '',
        '| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for item in summaries:
        lines.append('| ' + ' | '.join(str(item[key]) for key in ('configuration', 'split', 'n', 'delivered', 'human_reviewed_n',
            'provider_calls', 'local_transformations', 'tariff_estimated_usd', 'provider_reported_usd', 'uncertain_reserved_usd', 'p50_latency_ms', 'p95_latency_ms')) + ' |')
    provenance = ('Answers and judge results come from the configured live providers. Their outputs do not establish provider quality.'
                  if manifest['execution_mode'] == 'real' else
                  'Simulator answers and judges are fixtures. Their labels do not establish provider quality.')
    lines += ['', 'Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.',
        provenance + ' Cost per correct answer stays null until complete independent human review and complete cost information.',
        'When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.',
        'An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.',
        f"Stop reason: {manifest.get('stop_reason') or 'none'}."]
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run_pilot(options, stdout):
    manifest_path = options['manifest']
    manifest, cases = load_pilot(manifest_path)
    if options.get('preflight'):
        report, _ = preflight(manifest_path, options.get('authorization'))
        stdout.write(json.dumps(report, indent=2))
        return
    require_memory_database()
    real = bool(options.get('real'))
    if real:
        check, approval = preflight(manifest_path, options.get('authorization'))
        if not check['ready_for_real']:
            raise CommandError('Real pilot preflight blocked: ' + ', '.join(check['blockers']))
        if options.get('max_usd') != manifest['maximum_usd']:
            raise CommandError('Explicit --max-usd must exactly match the approved manifest.')
    selected = [case for case in cases if options.get('split', 'all') in ('all', case['split'])
                and (not options.get('case') or case['id'] in options['case'])]
    if not selected:
        raise CommandError('No pilot cases selected.')
    output = Path(options['output']).resolve()
    if output.exists():
        raise CommandError('Output directory already exists; previous results are immutable.')
    rows, order, stop = [], [], None
    sequence = [(case, configuration) for case in selected for configuration in manifest['configurations']]
    random.Random(manifest['seed']).shuffle(sequence)
    try:
        commit = subprocess.run(['rtk', 'git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = 'unavailable'
    frozen = {**manifest, 'source_sha256_observed': source_hashes(), 'manifest_sha256': digest(Path(manifest_path).read_bytes()),
        'runtime_versions_observed': runtime_versions(), 'commit': commit,
        'masking_observed': local_masking_manifest() if manifest.get('masking', {}).get('backend') == 'local' else None,
        'execution_mode': 'real' if real else 'simulated', 'started_at': datetime.now(timezone.utc).isoformat(),
        'selected_split': options.get('split', 'all'), 'execution_order': [[case['id'], configuration] for case, configuration in sequence]}
    with ExitStack() as stack:
        if real:
            stack.enter_context(real_lock())
        temporary = Path(stack.enter_context(TemporaryDirectory(prefix='regulai-pilot-')))
        stack.enter_context(override_settings(MEDIA_ROOT=str(temporary / 'media')))
        if 'front_company' not in connection.introspection.table_names():
            call_command('migrate', interactive=False, verbosity=0)
        ledger = EvaluationBudget(LEDGER_PATH if real else temporary / 'offline-budget.sqlite3', manifest['maximum_usd'],
            **({'authorization_id': approval['authorization_id'], 'authorization_digest': digest(approval)} if real else {}))
        output.mkdir(parents=True, exist_ok=False)
        (output / 'plan.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (output / 'cases.executed.jsonl').write_text(''.join(canonical(case) + '\n' for case in selected), encoding='utf-8')
        (output / 'rubric.md').write_bytes((Path(manifest_path).parent / manifest['human_rubric']).read_bytes())
        engine = Engine.objects.create(name='Synthetic pilot ' + uuid.uuid4().hex, connector_type='openai_compatible',
                                       base_url=manifest['destinations']['generation'])
        models = {level: EngineModel.objects.create(engine=engine, name=level, model_id=manifest['model_versions'][level],
            context_window=manifest['context_window'], max_tokens=manifest['limits']['max_output_tokens'], supports_json=True,
            input_price=Decimal(manifest['prices_per_million'][level]['input']), output_price=Decimal(manifest['prices_per_million'][level]['output']),
            price_date=date.fromisoformat(manifest['price_date'])) for level in ('economy', 'strong')}
        def authorize():
            check, current_approval = preflight(manifest_path, options.get('authorization'))
            if not check['ready_for_real'] or digest(current_approval) != digest(approval):
                raise BudgetExceeded('Authorization or frozen inputs changed during the run.')
        try:
            for case, configuration in sequence:
                row = exercise_case(case, configuration, manifest, engine, models, ledger, real=real, authorize=authorize if real else None)
                rows.append(row)
                order.append([case['id'], configuration])
                with (output / 'completed-cases.jsonl').open('a', encoding='utf-8') as progress:
                    progress.write(canonical(row) + '\n')
                    progress.flush()
                    os.fsync(progress.fileno())
                if row['stop_reason'] or not row['control_pass']:
                    stop = row['stop_reason'] or 'control_failed'
                    break
        except BaseException as error:
            stop = type(error).__name__
            raise
        finally:
            frozen.update(stop_reason=stop, completed_order=order, finished_at=datetime.now(timezone.utc).isoformat())
            write_reports(output, frozen, rows, ledger.snapshot())
    actual_calls = sum(is_external_call(call) for row in rows for call in row['calls']) if real else 0
    stdout.write(f'{len(rows)} pilot runs; real calls {actual_calls}; human review pending. Reports: {output}')
    if stop:
        raise CommandError('Pilot stopped: ' + stop + '. Retain the report and ledger; do not automatically retry.')
