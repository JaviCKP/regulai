"""Read only account metadata; never emit credential values or prompt text."""
import json
import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
SCRIPT = '''
import json, runpy
runpy.run_path('/app/ops/setup/server.py', run_name='inspect_configuration')
from django.contrib.auth import get_user_model
from django.db import connection
from front.models import Company, CompanyEngine, AgentModelProfile, Rule, ObfuscationConfig
result = {'accounts': [], 'companies': []}
for u in get_user_model().objects.select_related('profile__company'):
 result['accounts'].append({'id': u.pk, 'username': u.username, 'company': u.profile.company.name, 'company_id': u.profile.company_id, 'active': u.is_active})
for c in Company.objects.all():
 row = {'id': c.pk, 'name': c.name, 'policy_configured': bool(c.ai_config), 'connections': [], 'rules': [], 'masking': []}
 for e in CompanyEngine.objects.filter(company=c).select_related('engine'):
  row['connections'].append({'id': e.pk, 'name': e.display_name, 'provider': e.engine.name, 'active': e.active, 'key_configured': bool(e.api_key), 'models': list(e.engine.models.filter(active=True).values('id','name','model_id'))})
 row['rules'] = list(Rule.objects.filter(rules_group__company=c).values('id','name','action','applies_to','active'))
 row['masking'] = list(ObfuscationConfig.objects.filter(company=c).values('id','name','backend','detect','active'))
 result['companies'].append(row)
result['agents'] = list(AgentModelProfile.objects.values('id','name','connection_id','model_id','enabled','professional'))
with connection.cursor() as cur:
 cur.execute("SELECT name FROM django_migrations WHERE app='front' ORDER BY name DESC LIMIT 4")
 result['migrations'] = [r[0] for r in cur.fetchall()]
 cur.execute("SELECT status,count(*) FROM front_agentexecution WHERE status IN ('queued','active','outcome_unknown') GROUP BY status")
 result['pending'] = dict(cur.fetchall())
print(json.dumps(result, ensure_ascii=False))
'''
result = subprocess.run([*SSH, 'sudo docker exec -i regulai-v2-web python -'],
                        input=SCRIPT.encode(), capture_output=True)
if result.returncode:
    # Only code/schema errors, no private settings or database objects.
    print(result.stderr.decode(errors='replace')[-2000:])
    raise SystemExit(result.returncode)
value = json.loads(result.stdout)
print(json.dumps(value, ensure_ascii=True, indent=2))
