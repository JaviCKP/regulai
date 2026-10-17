"""Read chat 11 timing metadata only; never invoke a provider or mutate the app."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
SCRIPT = '''import json,runpy
runpy.run_path('/run/p1/p1_activation_remote.py')['_configure']()
from django.utils import timezone
from front.models import AgentExecution,AgentEvent,AgentInference,AgentOperation
safe={'category','phase','stage','duration_ms','started_at','completed_at','status','purpose',
      'operation','name','call_id','mode','reason','code','interval','sequence','provider_name',
      'model_requested','model_effective','cost','cost_kind','input_tokens','output_tokens',
      'usage','reasoning_tokens','cached_tokens','prompt_tokens','completion_tokens','total_tokens',
      'inference_options','requested','resolved','thinking','reasoning_effort','effort',
      'max_output_tokens','input_bytes','output_bytes','bytes','chunk_count','chunks','source'}
def clean(v):
 if isinstance(v,dict): return {k:clean(x) for k,x in v.items() if k in safe}
 if isinstance(v,list): return [clean(x) for x in v]
 return v
rows=[]
for run in AgentExecution.objects.filter(conversation_id=11).select_related('prompt').order_by('created_at')[:20]:
 events=list(AgentEvent.objects.filter(execution=run).order_by('id'))
 start=run.created_at
 event_rows=[{'id':e.pk,'kind':e.kind,'at':e.created_at.isoformat(),
              'elapsed_s':round((e.created_at-start).total_seconds(),3),'data':clean(e.data),
              'data_keys':sorted(e.data)} for e in events]
 rows.append({'id':str(run.pk),'status':run.status,'created_at':start.isoformat(),
   'prompt_created_at':str(getattr(run.prompt,'created_at',None)),
   'started_at':str(run.started_at),'finished_at':str(run.finished_at),
   'queue_s':round((run.started_at-start).total_seconds(),3) if run.started_at else None,
   'total_s':round(((run.finished_at or timezone.now())-start).total_seconds(),3),
   'prompt_characters':len(run.prompt.content),'source':bool(run.job.get('source')),
   'request_operation':run.job.get('request',{}).get('operation'),
   'inference_options':clean(run.job.get('inference',{})),
   'skills':{'catalog_count':len((run.job.get('skills') or {}).get('catalog',[])),
             'selected_count':len((run.job.get('skills') or {}).get('selected',[]))},
   'decision_keys':sorted(run.prompt.decision),'error_type':run.prompt.decision.get('error_type'),
   'calls':[clean(c) for c in run.prompt.decision.get('calls',[])],
   'inferences':[{'at':r.created_at.isoformat(),'elapsed_s':round((r.created_at-start).total_seconds(),3),
                  'status':r.status,'inference':clean(r.response.get('inference',{}))}
                 for r in AgentInference.objects.filter(execution=run).order_by('created_at')],
   'operations':list(AgentOperation.objects.filter(execution=run).values('name','status','created_at','completed_at')),
   'events':event_rows})
print(json.dumps({'observed_at':timezone.now().isoformat(),'conversation_id':11,'runs':rows},default=str))
'''
result = subprocess.run([*SSH,'sudo docker exec -i regulai-v2-web python -'],input=SCRIPT.encode(),capture_output=True)
if result.returncode:
    print(result.stderr.decode()[-2000:])
    raise SystemExit(result.returncode)
value = json.loads(result.stdout)
Path(__file__).with_name('timings.json').write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
print(json.dumps({'observed_at':value['observed_at'],'runs':[
    {key:row[key] for key in ('id','status','queue_s','total_s','prompt_characters','inferences')}
    for row in value['runs']]},indent=2))
