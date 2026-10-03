"""Rollback authorization invariant, only on the isolated test database."""
import hashlib
import json
from pathlib import Path
import subprocess
import types
from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from front.forms import ObfuscationConfigForm
from front.models import Company, ObfuscationConfig
from front.test_chat_flow import mask_response

HERE = Path(__file__).resolve().parent
BASE = '700389c216592db1e0c8725749bb4fd02cf3fa10'


class RollbackAuthorizationTests(TransactionTestCase):
    def test_downgrade_does_not_turn_a_local_detector_into_original_http_egress(self):
        source = subprocess.check_output(['git', 'show', BASE + ':regulai/front/masking.py'], cwd=HERE.parents[1])
        (HERE / 'base-masking.py').write_bytes(source)
        baseline = types.ModuleType('front.review_baseline_masking')
        baseline.__package__ = 'front'
        exec(compile(source, str(HERE / 'base-masking.py'), 'exec'), baseline.__dict__)
        company = Company.objects.create(name='Rollback synthetic company')
        config = ObfuscationConfig.objects.create(company=company, name='Former remote mask', backend='http',
            api_url='https://former-mask.example.invalid', detect='both', active=True)
        company.ai_config = {'version': 1, 'local_sensitivity': 'internal', 'allow_empty_rules': True,
            'masking': {'max_call_cost': '0'}, 'destinations': {'internal': [f'obfuscation:{config.pk}']}}
        company.save()
        form = ObfuscationConfigForm({'name': config.name, 'backend': 'local', 'api_url': config.api_url,
            'detect': 'both', 'language': 'es', 'active': 'on'}, instance=config)
        self.assertTrue(form.is_valid(), form.errors)
        config = form.save()
        before = {'backend': config.backend, 'api_url': config.api_url, 'active': config.active}
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [('front', '0031_infer_historical_prompt_company')]
        sent = []
        try:
            executor.migrate(old_target)
            apps = executor.loader.project_state(old_target).apps
            downgraded = apps.get_model('front', 'ObfuscationConfig').objects.get(pk=config.pk)
            preserved_policy = apps.get_model('front', 'Company').objects.get(pk=company.pk).ai_config
            def transport(url, **kwargs):
                sent.append({'url': url, 'payload': kwargs['json']})
                return mask_response(url, **kwargs)
            accepted = baseline.valid_masks([downgraded])
            if accepted:
                with patch('requests.post', side_effect=transport):
                    baseline.mask_texts(['ana.rollback@example.invalid'], [downgraded])
            record = {'base': BASE, 'base_masking_sha256': hashlib.sha256(source).hexdigest(),
                'before_downgrade': before, 'after_downgrade': {'api_url': downgraded.api_url, 'active': downgraded.active},
                'baseline_accepts_mask': accepted, 'policy_unchanged': preserved_policy == company.ai_config,
                'captured_http': sent}
            (HERE / 'rollback-observations.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            self.assertEqual(sent, [], 'Rollback reactivates HTTP after the company selected local processing')
        finally:
            MigrationExecutor(connection).migrate(latest)
