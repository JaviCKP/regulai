"""Exercise the frozen pre-local masking code after the real schema downgrade."""
import hashlib
import json
from pathlib import Path
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
LEGACY_SHA256 = '2508742be605a0c6f74d5c4a5a4fca7860667b9bbdc139ca3b16bb502835f697'
OBSERVATIONS = None


class LegacyRollbackTests(TransactionTestCase):
    def test_local_downgrade_never_sends_to_former_http_but_existing_http_still_works(self):
        source = (HERE / 'frozen_legacy_masking.py').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), LEGACY_SHA256)
        baseline = types.ModuleType('front.frozen_rollback_masking')
        baseline.__package__ = 'front'
        exec(compile(source, str(HERE / 'frozen_legacy_masking.py'), 'exec'), baseline.__dict__)
        company = Company.objects.create(name='Former HTTP isolated probe')
        config = ObfuscationConfig.objects.create(company=company, name='Former HTTP', backend='http',
            api_url='https://former-mask.example.invalid', detect='both', active=True)
        form = ObfuscationConfigForm({'name': config.name, 'backend': 'local', 'api_url': config.api_url,
            'detect': 'both', 'language': 'es', 'active': 'on'}, instance=config)
        self.assertTrue(form.is_valid(), form.errors)
        config = form.save()
        control_company = Company.objects.create(name='Remaining HTTP isolated probe')
        control = ObfuscationConfig.objects.create(company=control_company, name='Authorized HTTP', backend='http',
            api_url='https://authorized-mask.example.invalid', detect='both', active=True)
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [('front', '0031_infer_historical_prompt_company')]
        captured, control_captured = [], []
        def transport(url, **kwargs):
            destination = control_captured if url.startswith(control.api_url) else captured
            destination.append({'url': url, 'payload': kwargs['json']})
            return mask_response(url, **kwargs)
        try:
            executor.migrate(old_target)
            apps = executor.loader.project_state(old_target).apps
            model = apps.get_model('front', 'ObfuscationConfig')
            downgraded, remote = model.objects.get(pk=config.pk), model.objects.get(pk=control.pk)
            accepted = baseline.valid_masks([downgraded])
            with patch('requests.post', side_effect=transport):
                if accepted:
                    baseline.mask_texts(['ana.rollback@example.invalid'], [downgraded])
                baseline.mask_texts(['authorized synthetic control'], [remote])
            record = {'base': BASE, 'base_masking_sha256': LEGACY_SHA256,
                'before': {'backend': config.backend, 'active': config.active, 'api_url': config.api_url},
                'after': {'active': downgraded.active, 'api_url': downgraded.api_url},
                'baseline_accepts_former_http': accepted, 'captured_http_for_former_local': captured,
                'http_control_active': remote.active, 'http_control_captured': control_captured}
            with OBSERVATIONS.open('x', encoding='utf-8') as output:
                output.write(json.dumps(record, indent=2) + '\n')
            self.assertEqual(captured, [], 'Downgrade must not authorize the former HTTP endpoint')
            self.assertEqual(len(control_captured), 1, 'Existing HTTP authorization is preserved')
        finally:
            MigrationExecutor(connection).migrate(latest)
