"""Private VM implementation; invoked with an explicit local request only."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import traceback

IDENTITY = 'privacy-20261017-a1'
STAGE = Path('/opt/regulai/updates')/IDENTITY
WEB, WORKER, PG = 'regulai-v2-web', 'regulai-v2-worker', 'regulai-v2-postgres'
CLONE = 'regulai_p1_privacy_20261017_a1'
helper = {'__name__': 'privacy_helper', '_ACTIVATION_SOURCE': REQUEST['helper']}
exec(compile(REQUEST['helper'],'helper.py','exec'),helper)
docker, inspect = helper['docker'], helper['inspect']
save = helper['private_json']


def app_script(action, database='regulai'):
    start = "import json,runpy,sys\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nh['_configure'](%r)\n" % database
    if action == 'migrate':
        return start+'''from django.db import connection
from django.db.migrations.executor import MigrationExecutor
executor=MigrationExecutor(connection)
target=[('front','0045_privacy_call_identity')]
plan=executor.migration_plan(target)
allowed={'0044_privacy_records','0045_privacy_call_identity'}
if any(backwards or m.app_label!='front' or m.name not in allowed for m,backwards in plan): raise RuntimeError('unexpected_migration_plan')
executor.migrate(target)
print(json.dumps({'applied':[m.name for m,_ in plan]}))
'''
    if action == 'configure':
        return start+"print(json.dumps(runpy.run_path('/app/ops/agent_chat/privacy_demo_account.py')['configure']()))\n"
    if action == 'validate':
        return start+'''from django.core.management import call_command
from django.contrib.auth import get_user_model
from front.models import Company,CompanyEngine,PrivacyRevision
from front.policy import AIConfig
from front.chat_assets import assets,react_enabled
from front.agents.capabilities import profile_for
from front.privacy_policy import PrivacyConfig,preview_text
from front.security_presets import PRIVACY_SAMPLE
call_command('check',verbosity=0)
c=Company.objects.get(pk=3)
AIConfig.model_validate(c.ai_config)
p=PrivacyConfig.model_validate_json(PrivacyRevision.objects.get(pk=c.ai_config['privacy']['revision_id']).configuration)
protected,ranges=preview_text(PRIVACY_SAMPLE,p,[])
assert len(ranges)==5 and 'lucia.romero@example.com' not in protected
assert react_enabled() and profile_for(get_user_model().objects.get(pk=1))
print(json.dumps({'react':True,'asset':assets()['script'],'privacy_matches':len(ranges),'agent_profile':1,'configured_connections':CompanyEngine.objects.filter(company=c,active=True).count()}))
'''
    if action == 'tests':
        return start+'''from django.core.management import call_command
from django.conf import settings
from django.db import connections
connections['default'].settings_dict['TEST']['NAME']='test_regulai_privacy_candidate_20261017'
call_command('test','front.test_security_presets','front.test_privacy_service','front.test_privacy_policy','front.test_privacy_presentation','front.test_privacy_views','front.test_privacy_vertical','front.test_privacy_boundaries','front.test_privacy_agent','front.test_privacy_http',interactive=False,verbosity=1)
'''
    raise RuntimeError('unknown_app_action')


def run_app(image, script):
    # Reuse the exact installed runtime and private config mounts; no export.
    original = helper['read_json'](STAGE/'original.json')[WEB]
    args=['run','--rm','-i','--network','host','--user','1000:1000','--read-only',
          '--cap-drop','ALL','--security-opt','no-new-privileges',
          '--tmpfs','/tmp:rw,nosuid,nodev,size=128m,uid=1000,gid=1000']
    for m in original['Mounts']:
        if m['Type']!='bind' or m['RW'] or m['Destination'] not in {'/run/private','/run/p1'}:
            raise RuntimeError('unexpected_installed_mount')
        args += ['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
    args += [image,'python','-']
    result=subprocess.run(['docker',*args],input=script.encode(),capture_output=True)
    if result.returncode:
        with (STAGE/'application-error.log').open('wb') as stream:
            os.chmod(stream.name,0o600)
            stream.write(result.stdout+result.stderr)
        raise RuntimeError('candidate_application_failed')
    return result.stdout.decode().strip()


def fingerprint(image, database, prior=None):
    script="import runpy,sys,io,json\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nsys.stdin=io.StringIO(%r)\nprint(json.dumps(h['inside_web']('fingerprint',%r)))" % (json.dumps(prior or {}),database)
    return json.loads(run_app(image,script))


def prepare():
    if (STAGE/'state.json').exists():
        raise RuntimeError('prepared_stage_exists')
    STAGE.mkdir(mode=0o700,exist_ok=True)
    rows={name:inspect(name) for name in (WEB,WORKER,PG)}
    if not rows[WEB]['State']['Running'] or not rows[PG]['State']['Running']:
        raise RuntimeError('existing_services_required')
    helper['require_idle'](current=True)
    if (STAGE/'original.json').exists():
        if helper['original_identity'](helper['read_json'](STAGE/'original.json'))!=helper['original_identity'](rows):
            raise RuntimeError('original_changed_during_prepare_retry')
    else:
        save(STAGE/'original.json',rows)
    save(STAGE/'configuration.json',{'digest':helper['private_configuration_digest']()})
    # Recheck every changed source against the observed installed version.
    check='import hashlib,json\nfrom pathlib import Path\nexpected=%r\nactual={p:hashlib.sha256((Path("/app")/p).read_bytes()).hexdigest() if (Path("/app")/p).is_file() else None for p in expected}\nassert actual==expected,"live_source_changed"\n' % REQUEST['baseline']
    docker('exec','-i',WEB,'python','-',data=check.encode())
    backup_file=STAGE/'before-prepare.dump'
    backup=({'file':backup_file.name,'bytes':backup_file.stat().st_size,
             'sha256':hashlib.sha256(backup_file.read_bytes()).hexdigest()} if backup_file.exists()
            else helper['snapshot_backup'](STAGE,'before-prepare'))
    before=fingerprint(rows[WEB]['Image'],'regulai')
    if (STAGE/'before.json').exists():
        helper['equal_fingerprints'](helper['read_json'](STAGE/'before.json'),before)
    else:
        save(STAGE/'before.json',before)
    for p, encoded in REQUEST['files'].items():
        path=PurePosixPath(p)
        if (path.is_absolute() or '..' in path.parts or '\\' in p or ':' in p
                or not p.startswith(('regulai/','ops/agent_chat/'))
                or path.name=='local_settings.py' or path.name.startswith('.env')
                or path.suffix in {'.sqlite3','.db','.pem','.key'}):
            raise RuntimeError('invalid_source_path')
        target=STAGE/'source'/p
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(base64.b64decode(encoded,validate=True))
    base_image='regulai-v2-web:'+IDENTITY+'-base'
    docker('tag',rows[WEB]['Image'],base_image)
    (STAGE/'Dockerfile').write_text('FROM '+base_image+'\nCOPY source/ /app/\n')
    image='regulai-v2-web:'+IDENTITY
    with (STAGE/'build.log').open('wb') as output:
        docker('build','--network=none','--pull=false','-t',image,str(STAGE),output=output)
    # A distinct new PostgreSQL database, never a replacement of an existing DB.
    if not (STAGE/'clone-created').exists():
        docker('exec',PG,'createdb','-U','regulai',CLONE)
        docker('exec','-i',PG,'pg_restore','-U','regulai','-d',CLONE,'--exit-on-error','--no-owner','--no-acl',data=(STAGE/'before-prepare.dump').read_bytes())
        (STAGE/'clone-created').write_text(CLONE)
    migrated=json.loads(run_app(image,app_script('migrate',CLONE)))
    helper['equal_fingerprints'](before,fingerprint(image,CLONE,before))
    with (STAGE/'tests.log').open('w') as output:
        output.write(run_app(image,app_script('tests',CLONE)))
    configured=json.loads(run_app(image,app_script('configure',CLONE)))
    validated=json.loads(run_app(image,app_script('validate',CLONE)).splitlines()[-1])
    helper['equal_fingerprints'](before,fingerprint(rows[WEB]['Image'],'regulai',before))
    state={'phase':'prepared','image':image,'image_id':json.loads(docker('image','inspect',image))[0]['Id'],
           'backup':backup,'clone':CLONE,'migration':migrated,'configuration':configured,
           'validation':validated,'existing_data_preserved':True,'provider_generation_calls':0}
    save(STAGE/'state.json',state)
    return state


def apply():
    state=helper['read_json'](STAGE/'state.json')
    if state['phase']!='prepared': raise RuntimeError('prepared_stage_required')
    original=helper['read_json'](STAGE/'original.json')
    if helper['original_identity']({n:inspect(n) for n in original})!=helper['original_identity'](original):
        raise RuntimeError('installed_container_changed')
    if helper['private_configuration_digest']()!=helper['read_json'](STAGE/'configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    if json.loads(docker('image','inspect',state['image']))[0]['Id']!=state['image_id']:
        raise RuntimeError('prepared_image_changed')
    helper['require_idle'](current=True)
    docker('stop',WORKER,WEB)
    script="import runpy,json\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nprint(json.dumps(h['inside_web']('metadata')))"
    idle=json.loads(run_app(original[WEB]['Image'],script))
    if any(idle[k] for k in ('live','active_calls','pending_inferences','provider_occupied','sandbox_occupied')):
        docker('start',WEB)
        raise RuntimeError('admission_not_idle')
    state['apply_backup']=helper['snapshot_backup'](STAGE,'before-apply')
    before=fingerprint(original[WEB]['Image'],'regulai')
    state['real_migration']=json.loads(run_app(state['image'],app_script('migrate')))
    helper['equal_fingerprints'](before,fingerprint(state['image'],'regulai',before))
    state['configuration']=json.loads(run_app(state['image'],app_script('configure')))
    state['validation']=json.loads(run_app(state['image'],app_script('validate')).splitlines()[-1])
    payload=copy.deepcopy(original[WEB]['Config'])
    payload.pop('Hostname',None); payload.pop('Domainname',None)
    payload.update(Image=state['image_id'],HostConfig=copy.deepcopy(original[WEB]['HostConfig']))
    payload['Labels']={**payload.get('Labels',{}),'regulai.privacy':IDENTITY}
    docker('rename',WEB,WEB+'-before-'+IDENTITY)
    connection=helper['DockerConnection']('localhost')
    try:
        connection.request('POST','/v1.47/containers/create?name='+WEB,body=json.dumps(payload),headers={'Content-Type':'application/json'})
        response=connection.getresponse(); response.read()
        if response.status!=201: raise RuntimeError('candidate_container_create_failed')
    finally:
        connection.close()
    docker('start',WEB)
    state['phase']='applied'
    state['previous_web']=WEB+'-before-'+IDENTITY
    save(STAGE/'state.json',state)
    return state


def sandbox():
    # Local infrastructure only. Never claim an agent request or call a model.
    row=inspect(WORKER)
    worker=next(m['Source'] for m in row['Mounts'] if m['Destination']=='/run/task50')
    script=Path('/opt/regulai/source/ops/setup/network.sh').read_bytes()
    helper['command'](['sysctl','-w','vm.nr_hugepages=1536'])
    helper['command'](['bash','-se'],data=script)
    docker('compose','--project-directory','/home/probe/e2b','run','--rm','--no-deps','host-setup')
    probe=Path('/opt/regulai/source/ops/setup/verify_sandbox.py')
    result=docker('run','--rm','--network','regulai-v2-exec','--user','1000:1000','--read-only',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--dns','127.0.0.1',
        '--memory','512m','--pids-limit','64','--tmpfs','/tmp:rw,nosuid,nodev,size=64m,uid=1000,gid=1000',
        '--mount',f'type=bind,src={worker},dst=/run/task50,readonly',
        '--mount',f'type=bind,src={probe},dst=/verify.py,readonly',row['Image'],'python','/verify.py')
    helper['require_idle'](current=True)
    docker('start',WORKER)
    return {'sandbox_render_and_isolation_verified':True,'worker_started':True,'provider_generation_calls':0}


def finish():
    state=helper['read_json'](STAGE/'state.json')
    if state['phase']!='applied': raise RuntimeError('applied_stage_required')
    before=helper['read_json'](STAGE/'before.json')
    after=fingerprint(state['image'],'regulai',before)
    changed={'front_company','front_rule','front_rulesgroup','front_agentmodelprofile','front_conversation','front_auditlog'}
    verified=[]
    for table, expected in before['tables'].items():
        if table not in changed:
            if after['tables'].get(table)!=expected: raise RuntimeError('unexpected_table_change:'+table)
            verified.append(table)
    if helper['private_configuration_digest']()!=helper['read_json'](STAGE/'configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    services={name:{'running':inspect(name)['State']['Running'],'restarts':inspect(name)['RestartCount']} for name in (WEB,WORKER,PG)}
    if not all(row['running'] and row['restarts']==0 for row in services.values()):
        raise RuntimeError('service_not_stable')
    metadata=helper['require_idle'](current=True)
    # Remove only the isolated database created by this exact operation.
    marker=STAGE/'clone-created'
    if marker.exists():
        if marker.read_text()!=CLONE or CLONE=='regulai': raise RuntimeError('clone_ownership_mismatch')
        docker('exec',PG,'dropdb','-U','regulai',CLONE)
        marker.rename(STAGE/'clone-removed')
    state['final']={'services':services,'metadata':metadata,'unchanged_tables':verified,
                    'private_configuration_unchanged':True,'clone_removed':True,'provider_generation_calls':0}
    save(STAGE/'state.json',state)
    return state['final']


try:
    if REQUEST['identity']!=IDENTITY: raise RuntimeError('unexpected_identity')
    value={'prepare':prepare,'apply':apply,'status':lambda:helper['read_json'](STAGE/'state.json'),'sandbox':sandbox,'finish':finish}[REQUEST['action']]()
    print(json.dumps(value))
except Exception as error:
    if STAGE.exists():
        with (STAGE/'error.log').open('w') as stream:
            os.chmod(stream.name,0o600)
            traceback.print_exc(file=stream)
    print(json.dumps({'error':type(error).__name__,'code':str(error) if isinstance(error,RuntimeError) else 'inspect_private_stage_log'}))
    sys.exit(1)
