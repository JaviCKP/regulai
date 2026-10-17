"""Capture the installed SDK's greeting envelope with network and models offline."""
import base64
import json
import runpy
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SSH=runpy.run_path(str(ROOT/'ops/agent_chat/p1_activate_local.py'))['SSH']
modules={name:base64.b64encode((ROOT/'ops/agent_chat'/(name+'.py')).read_bytes()).decode()
         for name in ('test_p0_runtime','test_p1_skills_runtime')}
script='''import base64,json,sys,types
modules=%r
for name,source in modules.items():
 full='ops.agent_chat.'+name
 module=types.ModuleType(full)
 module.__file__='/app/ops/agent_chat/'+name+'.py'
 sys.modules[full]=module
 exec(compile(base64.b64decode(source),module.__file__,'exec'),module.__dict__)
from ops.agent_chat.test_p1_skills_runtime import SkillsBoundary,SkillsRuntimeTests
import httpx
class Greeting(SkillsBoundary):
 def respond(self,request):
  response=super().respond(request)
  if request.url.path.endswith('/run/bootstrap/'):
   value=response.json(); value['message']='hola'; return httpx.Response(200,json=value)
  return response
boundary=Greeting()
result=SkillsRuntimeTests().invoke(boundary)
assert result['status']=='completed' and len(boundary.inferences)==1
print(json.dumps({'request':boundary.inferences[0], 'model_calls_simulated':1,
                 'network':'none','sdk_completed':True,'sandbox_allocations':0}))
''' % modules
image=subprocess.check_output([*SSH,"sudo docker inspect --format '{{.Image}}' regulai-v2-worker"],stderr=subprocess.DEVNULL).decode().strip()
if not image.startswith('sha256:') or len(image)!=71: raise RuntimeError('worker_image_required')
result=subprocess.run([*SSH,'sudo docker run --rm -i --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m '+image+' python -'],
                      input=script.encode(),capture_output=True)
if result.returncode:
 print(result.stderr.decode()[-2000:]); raise SystemExit(result.returncode)
value=json.loads(result.stdout)
out=ROOT/'output/privacy-20261017/greeting-sdk.json'
out.write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
print(json.dumps({'sdk_completed':value['sdk_completed'],'image':image,'network':'none',
 'messages':[{'role':m['role'],'content_type':type(m['content']).__name__,
              'block_types':[p['type'] for p in m['content']] if isinstance(m['content'],list) else []}
             for m in value['request']['messages']], 'provider_generation_calls':0},indent=2))
