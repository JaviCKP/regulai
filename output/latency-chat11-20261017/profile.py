"""Profile existing cached preparation, denying all data writes and API traffic."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
SCRIPT = '''import json,runpy,time,cProfile,pstats,collections,re
from unittest.mock import patch
runpy.run_path('/run/p1/p1_activation_remote.py')['_configure']()
from django.db import connection,transaction
from front.models import AgentExecution,PrivacyMessage
from front.agents import skill_context,professional
from front.agents.service import _context
from front.privacy import ProtectionContext,protect_tree
if AgentExecution.objects.filter(conversation_id=11,status__in=['queued','active','outcome_unknown']).exists():
 raise RuntimeError('conversation_busy')
run=AgentExecution.objects.filter(conversation_id=11).select_related('prompt','profile').latest('created_at')
fragments=[]
for r in AgentExecution.objects.filter(conversation_id=11).order_by('created_at'):
 rows=list(PrivacyMessage.objects.filter(turn__prompt=r.prompt_id).values('source_key','created_at','protected'))
 groups={}
 for row in rows:
  prefix=row['source_key'].split(':')[0]
  g=groups.setdefault(prefix,{'count':0,'short_fragments':0,'first_s':None,'last_s':None})
  elapsed=round((row['created_at']-r.created_at).total_seconds(),3)
  g['count']+=1;g['short_fragments']+=len(row['protected'])<80
  g['first_s']=min(g['first_s'] if g['first_s'] is not None else elapsed,elapsed)
  g['last_s']=max(g['last_s'] if g['last_s'] is not None else elapsed,elapsed)
 fragments.append({'execution':str(r.pk),'groups':groups})

measurements=[]
def measure(name,fn):
 stats=collections.Counter();tables=collections.Counter();sql_seconds=0
 def guard(execute,sql,params,many,context):
  nonlocal sql_seconds
  verb=sql.lstrip().split()[0].upper()
  if verb not in {'SELECT','SAVEPOINT','RELEASE','ROLLBACK'}:
   raise RuntimeError('diagnostic_data_write_denied:'+verb)
  stats[verb]+=1
  for table in set(re.findall(r'(?:FROM|JOIN) "(\\w+)"',sql)): tables[table]+=1
  start=time.perf_counter()
  try:return execute(sql,params,many,context)
  finally:sql_seconds+=time.perf_counter()-start
 profiler=cProfile.Profile()
 with transaction.atomic():
  with connection.cursor() as cursor:cursor.execute("SET LOCAL lock_timeout='100ms'")
  with connection.execute_wrapper(guard),patch('socket.create_connection',side_effect=RuntimeError('diagnostic_network_denied')):
   start=time.perf_counter();profiler.enable()
   try:result=fn()
   finally:profiler.disable()
   elapsed=time.perf_counter()-start
  transaction.set_rollback(True)
 top=[]
 for (file,line,func),(cc,nc,tt,ct,callers) in sorted(pstats.Stats(profiler).stats.items(),key=lambda item:item[1][3],reverse=True):
  if '/front/' in file:
   top.append({'file':file.split('/front/')[-1],'line':line,'function':func,'calls':nc,'self_s':round(tt,4),'cumulative_s':round(ct,4)})
 measurements.append({'phase':name,'seconds':round(elapsed,4),'sql_seconds':round(sql_seconds,4),
                      'sql_count':dict(stats),'tables':dict(tables),'functions':top[:14]})
 return result

context=measure('context',lambda:_context(run.prompt,run.profile_id))
measure('skill_catalog_first',lambda:skill_context.bootstrap(run))
result=measure('professional_bootstrap_cached',lambda:professional.bootstrap(run,context))
measure('bootstrap_full_tree_cached',lambda:protect_tree(ProtectionContext.from_prompt(run.prompt),result))
measure('skill_catalog_repeat',lambda:skill_context.bootstrap(run))
print(json.dumps({'execution':str(run.pk),'provider_calls':0,'data_writes':0,
 'measurement':'existing cached fragments; no mutations allowed; every transaction rolled back',
 'fragments':fragments,'measurements':measurements}))
'''
result = subprocess.run([*SSH,'sudo docker exec -i regulai-v2-web python -'],input=SCRIPT.encode(),capture_output=True)
if result.returncode:
    print(result.stderr.decode()[-2000:])
    raise SystemExit(result.returncode)
value = json.loads(result.stdout)
Path(__file__).with_name('profile.json').write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
print(json.dumps(value,indent=2))
