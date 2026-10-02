"""Explicit real-provider smoke test using only the authorized synthetic account."""
from datetime import date, datetime, timezone
from decimal import Decimal
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from front import chat_service, jev
from front.connectors import get_connector
from front.evaluation_budget import EvaluationBudget
from front.models import Company, CompanyEngine, EngineModel, ObfuscationConfig, Rule, RulesGroup
from front.routing import actual_cost


class Command(BaseCommand):
    help = 'Real synthetic smoke test; explicit opt-in, persistent combined 1 USD ceiling.'

    def add_arguments(self, parser):
        parser.add_argument('--real', action='store_true')
        parser.add_argument('--max-usd', required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--case', choices=['blocked', 'arithmetic', 'document'], action='append')

    def handle(self, *args, **options):
        if not options['real'] or not settings.DEBUG:
            raise CommandError('Requires --real and an isolated local DEBUG installation.')
        if Path(settings.DATABASES['default']['NAME']).name != 'community-local.sqlite3':
            raise CommandError('Use the isolated community-local.sqlite3 database.')
        ledger_path = settings.BASE_DIR.parent / '.claude' / 'real-provider-budget.sqlite3'
        ledger_path.parent.mkdir(exist_ok=True)
        lock_path = ledger_path.with_name('real-provider-smoke.lock')
        try:
            lock = lock_path.open('x')
        except FileExistsError:
            raise CommandError('A smoke execution lock exists; inspect the prior run before removing it.') from None
        try:
            return self._run_smoke(options, ledger_path)
        finally:
            lock.close()
            lock_path.unlink()

    def _run_smoke(self, options, ledger_path):
        try:
            actor = User.objects.select_related('profile__company').get(username='community-local-demo')
            company = actor.profile.company
            credential = CompanyEngine.objects.select_related('engine').get(
                company=company, engine__name='DeepSeek authorized test')
        except (User.DoesNotExist, CompanyEngine.DoesNotExist):
            raise CommandError('Authorized synthetic account/credential is missing.') from None
        if (company.name != 'Community Local Synthetic Demo' or not credential.api_key
                or credential.engine.base_url.rstrip('/') != 'https://api.deepseek.com'
                or not company.jev_api_key):
            raise CommandError('Synthetic tenant or authorized destinations do not match.')
        if ObfuscationConfig.objects.filter(company=company, active=True).exists():
            raise CommandError('Real smoke requires no active external masking destinations.')
        if date.today() != date(2026, 10, 2):
            raise CommandError('Recheck the dated provider tariffs before authorizing a later real run.')
        output = Path(options['output']).resolve()
        if output.exists():
            raise CommandError('Choose a new output directory; earlier runs are retained.')
        output.mkdir(parents=True)
        ledger = EvaluationBudget(ledger_path, options['max_usd'])
        old_config = company.ai_config
        today = date.today()
        # Snapshot of official peak USD tariffs checked 2026-10-02. Peak tariffs
        # conservatively overestimate off-peak/cache charges; these are estimates.
        models = []
        for name, input_price, output_price in [('deepseek-flash', '.30', '1.20'), ('deepseek-v4-pro', '1.32', '3.96')]:
            model, _ = EngineModel.objects.get_or_create(engine=credential.engine, model_id=name,
                defaults={'name': name, 'context_window': 1_000_000, 'max_tokens': 512,
                    'supports_json': True, 'input_price': input_price, 'output_price': output_price,
                    'currency': 'USD', 'price_date': today})
            model.refresh_from_db()
            if (model.input_price != Decimal(input_price) or model.output_price != Decimal(output_price)
                    or model.currency != 'USD' or model.context_window != 1_000_000
                    or model.max_tokens != 512 or not model.supports_json or not model.active):
                raise CommandError('Existing synthetic model metadata differs; retained without making calls.')
            models.append(model)
        prices = {m.model_id: {'input_price': str(m.input_price), 'output_price': str(m.output_price),
            'currency': m.currency, 'price_date': str(m.price_date)} for m in models}
        run_id = str(uuid.uuid4())
        group = RulesGroup.objects.create(name='Real smoke ' + run_id, company=company)
        Rule.objects.create(rules_group=group, name='Synthetic credential block',
            yara_rule='rule synthetic_secret { strings: $s = "SYNTHETIC_SECRET_DO_NOT_SEND" condition: $s }',
            action='block', applies_to='both', active=True)
        config = {'version': 1, 'revision': old_config.get('revision', 0) + 1,
            'classification': 'local', 'local_sensitivity': 'internal', 'allow_empty_rules': False,
            'destinations': {'internal': [f'engine:{credential.pk}', 'jev']},
            'routing': {'mode': 'manual', 'max_output_tokens': 512,
                'candidates': [{'company_engine_id': credential.pk, 'model_id': m.pk,
                    'level': level, 'quality': {task: quality for task in ['general','extraction','summary','document_question']}}
                    for m, level, quality in [(models[0], 'economy', .5), (models[1], 'strong', 1.)]]},
            'verification': {'mode': 'local'}, 'limits': {'budget': '.15', 'deadline_seconds': 90},
            'jev': {'transport': 'vercel', 'model': 'typesafe-ai/jev', 'input_price': '.042',
                'output_price': '0', 'currency': 'USD', 'price_date': today.isoformat(), 'max_call_cost': '.01'}}
        real_jev = jev.evaluate

        def limited_connector(connector_type, api_key, base_url):
            if connector_type != 'openai_compatible' or base_url.rstrip('/') != 'https://api.deepseek.com':
                raise ValueError('Unexpected generator destination')
            client = get_connector(connector_type, api_key, base_url)
            original_chat = client.chat
            def chat(messages, **kwargs):
                if kwargs['model'] not in prices or not 0 < kwargs['max_tokens'] <= 512:
                    raise ValueError('Unexpected model/output limit')
                if sum(len(m.content.encode('utf-8')) for m in messages) > 16000:
                    raise ValueError('Synthetic request exceeded its input bound')
                call_id = ledger.reserve('generation', '.05')
                try:
                    result = original_chat(messages, **kwargs, extra_body={'thinking': {'type': 'disabled'}})
                except Exception:
                    ledger.complete(call_id, status='outcome_unknown')
                    raise
                cost = actual_cost(prices[kwargs['model']], result.input_tokens, result.output_tokens)
                ledger.complete(call_id, cost=cost, metadata={'kind': 'peak_tariff_upper_estimate',
                    'model': result.model, 'input_tokens': result.input_tokens, 'output_tokens': result.output_tokens})
                return result
            client.chat = chat
            return client

        def limited_jev(api_key, model, state, questions, **kwargs):
            if kwargs.get('transport') != 'vercel' or model != 'typesafe-ai/jev':
                raise ValueError('Unexpected evaluation destination')
            if len(json.dumps({'state': state, 'questions': questions}, ensure_ascii=False).encode('utf-8')) > 32000:
                raise ValueError('Synthetic evaluation exceeded its input bound')
            call_id = ledger.reserve('jev', '.01')
            try:
                result = real_jev(api_key, model, state, questions, **kwargs)
            except Exception as error:
                ledger.complete(call_id, status='outcome_unknown', metadata={
                    'error_code': error.code if isinstance(error, jev.JevError) else type(error).__name__})
                raise
            gateway = result.provider_metadata.get('gateway', {})
            cost = gateway.get('cost')
            kind = 'gateway_reported' if cost is not None else 'tariff_estimate'
            if cost is None:
                cost = actual_cost(config['jev'], result.input_tokens, result.output_tokens)
            ledger.complete(call_id, cost=cost, metadata={'kind': kind, 'model': result.effective_model,
                'input_tokens': result.input_tokens, 'output_tokens': result.output_tokens})
            return result

        results = []
        expected_config, installed = old_config, False
        configuration_restore = 'not_changed'
        try:
            with patch('front.chat_service.get_connector', side_effect=limited_connector), patch('front.jev.evaluate', side_effect=limited_jev):
                for name, content, document in [
                    ('blocked', 'SYNTHETIC_SECRET_DO_NOT_SEND', None),
                    ('arithmetic', 'Prueba sintética: responde solo con el número que resulta de 2 + 2.', None),
                    ('document', '¿Cuál es el plazo de entrega del contrato sintético? Cita su evidencia.', b'Contrato ficticio: el plazo de entrega es de 17 dias.'),
                ]:
                    if options['case'] and name not in options['case']:
                        continue
                    config['classification'] = 'required' if document else 'local'
                    config['verification'] = {'mode': 'enforce' if document else 'local'}
                    company.ai_config = config
                    company.full_clean()
                    if not Company.objects.filter(pk=company.pk, ai_config=expected_config).update(ai_config=config):
                        configuration_restore = 'external_change_preserved'
                        raise CommandError('Policy changed concurrently; no further smoke scenarios were started.')
                    expected_config, installed = deepcopy(config), True
                    command = {'content': content, 'request_id': str(uuid.uuid4()),
                        'engine_id': credential.pk, 'model_id': models[0].pk}
                    if document:
                        command['file'] = SimpleUploadedFile('synthetic-contract.txt', document)
                    result = chat_service.send_chat_message(actor, command)
                    data = result.data
                    actual = data.get('assistant_message', {}).get('content', '')
                    score = (data['status'] == 'blocked' and not data['receipt']['calls']) if name == 'blocked' else (
                        data['status'] == 'completed' and ('17' in actual if document else actual.strip().rstrip('.') == '4'))
                    results.append({'case': name, 'request_id': command['request_id'], 'status': data['status'],
                        'score_exact': bool(score), 'error': data.get('error_type'), 'synthetic_response': actual,
                        'receipt': data.get('receipt'), 'evidence': data.get('evidence')})
                    snapshot = ledger.snapshot()
                    if any(call['status'] == 'bound_exceeded' for call in snapshot['calls']):
                        break
        finally:
            if installed:
                restored = Company.objects.filter(pk=company.pk, ai_config=expected_config).update(ai_config=old_config)
                configuration_restore = 'restored' if restored else 'external_change_preserved'
            if configuration_restore == 'external_change_preserved':
                self.stderr.write('Policy changed concurrently; the newer configuration was preserved.')
            Rule.objects.filter(rules_group=group).update(active=False)
            report = {'at': datetime.now(timezone.utc).isoformat(), 'mode': 'real_synthetic_smoke',
                'configuration_restore': configuration_restore,
                'models_are_mutable_aliases': True, 'quality_values_are_fixture_not_calibration': True,
                'pricing_source': 'https://api-docs.deepseek.com/quick_start/pricing/',
                'results': results, 'budget': ledger.snapshot()}
            (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        if configuration_restore == 'external_change_preserved':
            raise CommandError('Policy changed concurrently; the newer configuration was preserved. See the report.')
        self.stdout.write(json.dumps({'cases': len(results), 'passed': sum(row['score_exact'] for row in results),
            'known_estimated_usd': ledger.snapshot()['known_cost_usd'],
            'uncertain_reserved_usd': ledger.snapshot()['uncertain_reservations_usd'], 'report': str(output / 'report.json')}))
