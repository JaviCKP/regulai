"""Inspect only run structure and error codes for the reported greeting."""
import json, runpy, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SSH=runpy.run_path(str(ROOT/'ops/agent_chat/p1_activate_local.py'))['SSH']
script='''import json,runpy,hashlib
from pathlib import Path
runpy.run_path('/app/ops/setup/server.py',run_name='configure')
from front.models import AgentExecution,AgentEvent,AgentInput,AgentInference
run=AgentExecution.objects.select_related('prompt').filter(conversation_id=9).latest('created_at')
job=run.job
print(json.dumps({'id':str(run.pk),'status':run.status,'prompt_status':run.prompt.status,
 'greeting_matches':run.prompt.content=='hola', 'job_keys':sorted(job),
 'source':bool(job.get('source')),'base':bool(job.get('base')), 'restore_checkpoint':bool(job.get('restore_checkpoint')),
 'skills':{'catalog_count':len((job.get('skills') or {}).get('catalog',[])), 'selected_count':len((job.get('skills') or {}).get('selected',[])), 'auto':(job.get('skills') or {}).get('auto')},
 'request':job.get('request'), 'error_type':run.prompt.decision.get('error_type'),
 'calls':[{'kind':c.get('kind'),'status':c.get('status'),'code':c.get('code')} for c in run.prompt.decision.get('calls',[])],
 'inputs':list(AgentInput.objects.filter(execution=run).values('kind','path')),
 'inferences':list(AgentInference.objects.filter(execution=run).values('status')),
 'events':[{'kind':e.kind,'data':{k:v for k,v in e.data.items() if k in {'code','status','phase','stage','duration_ms','operation'}}} for e in AgentEvent.objects.filter(execution=run)],
 'hashes':{p:hashlib.sha256((Path('/app/regulai/front/agents')/p).read_bytes()).hexdigest() for p in ['professional.py','skill_context.py','checkpoints.py','service.py']}
}))
'''
r=subprocess.run([*SSH,'sudo docker exec -i regulai-v2-web python -'],input=script.encode(),capture_output=True)
if r.returncode:
 print(r.stderr.decode()[-1600:]); raise SystemExit(1)
value=json.loads(r.stdout)
(ROOT/'output/privacy-20261017/greeting-before.json').write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
print(json.dumps(value,indent=2))
