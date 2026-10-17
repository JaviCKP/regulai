"""Read the provider's model catalogue using the existing in-place connection."""
import json
import runpy
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SSH=runpy.run_path(str(ROOT/'ops/agent_chat/p1_activate_local.py'))['SSH']
script='''import json,runpy,requests
from urllib.parse import urlsplit
runpy.run_path('/app/ops/setup/server.py',run_name='configure')
from front.models import CompanyEngine
e=CompanyEngine.objects.select_related('engine').get(pk=2,company_id=3,active=True)
url=(e.engine.base_url or '').rstrip('/')+'/models'
assert urlsplit(url).hostname=='api.deepseek.com' and urlsplit(url).scheme=='https'
try:
 r=requests.get(url,headers={'Authorization':'Bearer '+e.api_key},timeout=20,allow_redirects=False)
 result={'http_status':r.status_code,'generation_calls':0}
 if r.status_code==200:
  ids={item['id'] for item in r.json()['data']}
  result['configured_models']=[{'name':m.name,'model_id':m.model_id,'available':m.model_id in ids} for m in e.engine.models.filter(active=True)]
 print(json.dumps(result))
except requests.RequestException:
 print(json.dumps({'error':'model_catalogue_unavailable','generation_calls':0}))
'''
r=subprocess.run([*SSH,'sudo docker exec -i regulai-v2-web python -'],input=script.encode(),capture_output=True)
if r.returncode: raise SystemExit('Model catalogue check failed without exposing credentials.')
value=json.loads(r.stdout)
(ROOT/'output/privacy-20261017/real-models.json').write_text(json.dumps(value,indent=2))
print(json.dumps(value,indent=2))
