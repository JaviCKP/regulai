"""Freeze the user's approved Gateway route; grants no scope beyond the explicit replies."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
import django
django.setup()
from front.evaluation import source_hashes, runtime_versions, local_masking_manifest
from front.jev import VERCEL_ENDPOINT, VERCEL_MODEL

assert not (HERE / 'authorization.json').exists(), 'Preserve earlier preparation.'
base = ROOT / 'evals/pilot-real'
manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
assert manifest['dataset_sha256'] == '63e1754f6f6c3fdedc859a16f428ff7e6a21737c1091c1e7553ecf1daa1015f1'
manifest['judge_transport'] = 'vercel'
manifest['destinations']['judge'] = VERCEL_ENDPOINT
manifest['model_versions']['judge'] = VERCEL_MODEL
manifest['published_versions']['judge'] = 'Gateway alias typesafe-ai/jev; underlying immutable Jev version not exposed'
manifest['allowed_effective_models'].pop('jev-1.13.0', None)
manifest['allowed_effective_models'][VERCEL_MODEL] = [VERCEL_MODEL]
manifest['mutable_model_aliases'] = list(dict.fromkeys([*manifest['mutable_model_aliases'], VERCEL_MODEL]))
manifest['pricing_sources'] = ['https://api-docs.deepseek.com/quick_start/pricing/',
                             'https://ai-gateway.vercel.sh/v1/models', 'https://vercel.com/ai-gateway/models/jev']
manifest['source_sha256'] = source_hashes()
manifest['runtime_versions'] = runtime_versions()
manifest['masking'] = local_masking_manifest()
manifest['authorization_id'] = 'pilot-community-20261003-vercel-approved-v1'
manifest['gateway_scope'] = {'only': ['typesafe-ai'], 'immutable_underlying_version_available': False,
    'user_instruction': 'Use Jev through Vercel with the already configured credential; same eight synthetic cases and USD1 total.'}
manifest_path = base / 'manifest-vercel.json'
with manifest_path.open('x', encoding='utf-8') as handle:
    handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
approval = json.loads((ROOT / 'evals/reports/pilot-real-authorized-20261003-01/authorization.json').read_text(encoding='utf-8'))
approval.update(authorization_id=manifest['authorization_id'],
    approval_reference='User explicitly approved USD1 for the eight cases in call_KWCsyBL4GgidolwelGqsmiC2, then instructed in call_pzrhNgSMpmgf2zyfFUV0iaM9: no tengo la clave typesafe, hazlo a traves de vercel coño',
    manifest_sha256s=[sha256(manifest_path.read_bytes()).hexdigest()], destinations=manifest['destinations'],
    notes='Explicit user-directed replacement of direct TypeSafe with Vercel Gateway, routed only to TypeSafe AI. The Gateway slug, like DeepSeek aliases, does not expose immutable weights. Same USD1 cap, same eight synthetic cases in three configurations. No human bank, invitations, publication, purchases or deployment. The earlier direct-route preparation made zero product calls and opened no ledger.')
with (HERE / 'authorization.json').open('x', encoding='utf-8') as handle:
    handle.write(json.dumps(approval, ensure_ascii=False, indent=2) + '\n')
(HERE / 'manifest.json').write_bytes(manifest_path.read_bytes())
(HERE / 'preparation.json').write_text(json.dumps({'prepared_utc': datetime.now(timezone.utc).isoformat(),
    'manifest_sha256': sha256(manifest_path.read_bytes()).hexdigest(),
    'authorization_sha256': sha256((HERE / 'authorization.json').read_bytes()).hexdigest(),
    'masking_backend': 'local', 'initial_cases': 8, 'configurations': manifest['configurations'],
    'maximum_usd': '1.00', 'dataset_and_rubric_unchanged': True, 'real_calls_at_preparation': 0}, indent=2) + '\n', encoding='utf-8')
print('Frozen user-approved Gateway scope. Product calls have not started.')
