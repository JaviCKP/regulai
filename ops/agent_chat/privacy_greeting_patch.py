"""Prepare/apply the narrow greeting fix to the owned local privacy installation."""
import argparse
import base64
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SSH=runpy.run_path(str(ROOT/'ops/agent_chat/p1_activate_local.py'))['SSH']
IDENTITY='privacy-greeting-20261017-a1'


REMOTE=r'''
import base64,copy,hashlib,json,os,subprocess,traceback
from pathlib import Path
STAGE=Path('/opt/regulai/updates')/REQUEST['identity']
WEB,WORKER='regulai-v2-web','regulai-v2-worker'
h={'__name__':'patch_helper','_ACTIVATION_SOURCE':REQUEST['helper']}
exec(compile(REQUEST['helper'],'helper.py','exec'),h)
docker,inspect,save=h['docker'],h['inspect'],h['private_json']

def app(image,script,log=None):
    original=h['read_json'](STAGE/'original.json')[WEB]
    args=['run','--rm','-i','--network','host','--user','1000:1000','--read-only',
          '--cap-drop','ALL','--security-opt','no-new-privileges',
          '--tmpfs','/tmp:rw,nosuid,nodev,size=128m,uid=1000,gid=1000']
    for m in original['Mounts']:
        if m['Type']!='bind' or m['RW'] or m['Destination'] not in {'/run/private','/run/p1'}:
            raise RuntimeError('unexpected_mount')
        args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
    result=subprocess.run(['docker',*args,image,'python','-'],input=script.encode(),capture_output=True)
    if log or result.returncode:
        target=STAGE/(log or 'app-error.log')
        target.write_bytes(result.stdout+result.stderr); os.chmod(target,0o600)
    if result.returncode: raise RuntimeError('patch_app_check_failed')
    return result.stdout.decode().strip()

def call(image,action,payload=None):
    return json.loads(app(image,"import runpy,sys,io,json\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nsys.stdin=io.StringIO(%r)\nprint(json.dumps(h['inside_web'](%r)))"%(json.dumps(payload or {}),action)))

def prepare():
    if STAGE.exists(): raise RuntimeError('patch_stage_exists')
    STAGE.mkdir(mode=0o700)
    rows={n:inspect(n) for n in (WEB,WORKER)}
    if rows[WEB]['Image']!='sha256:39599fadcc74d9819c29e2a31cc00366f04cec2694e5a1a68842941019077385':
        raise RuntimeError('expected_privacy_image_required')
    h['require_idle'](current=True)
    save(STAGE/'original.json',rows)
    save(STAGE/'private-configuration.json',{'digest':h['private_configuration_digest']()})
    before=call(rows[WEB]['Image'],'fingerprint')
    save(STAGE/'before.json',before)
    image='regulai-v2-web:'+REQUEST['identity']
    base=image+'-base'
    docker('tag',rows[WEB]['Image'],base)
    for p,raw in REQUEST['files'].items():
        if not (p in REQUEST['allowed'] or p.startswith('regulai/static/chat-app/')) or '..' in p or '\\' in p:
            raise RuntimeError('patch_path_denied')
        target=STAGE/'source'/p; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(base64.b64decode(raw,validate=True))
    (STAGE/'Dockerfile').write_text('FROM '+base+'\nCOPY source/ /app/\n')
    with (STAGE/'build.log').open('wb') as out:
        docker('build','--network=none','--pull=false','-t',image,str(STAGE),output=out)
    return validate()

def validate():
    rows=h['read_json'](STAGE/'original.json')
    h['require_idle'](current=True)
    image='regulai-v2-web:'+REQUEST['identity']
    before=h['read_json'](STAGE/'before.json')
    # Compare the five legacy failures with the installed base image, using
    # identical runtime settings. Two require PDF evidence absent from the image.
    baseline_script="""import runpy,json
h=runpy.run_path('/run/p1/p1_activation_remote.py'); h['_configure']()
from django.db import connections
from django.test.runner import DiscoverRunner
connections['default'].settings_dict['TEST']['NAME']='test_regulai_greeting_baseline_20261017'
names=['checkpoint_resume_keeps_usage_and_rejects_later_operations',
       'private_results_seal_all_outbound_channels_and_keep_logs_encrypted',
       'published_document_records_visual_dispatch_only_after_all_pages',
       'repaired_document_delivers_only_latest_revision_and_preserves_history',
       'tool_state_injection_is_data_and_diagnostics_are_paginated']
failures=DiscoverRunner(interactive=False,verbosity=2).run_tests(['front.test_agent_professional.ProfessionalTests.test_'+n for n in names])
print(json.dumps({'baseline_failures':failures,'tests':len(names)}))
"""
    baseline=json.loads(app(rows[WEB]['Image'],baseline_script,'baseline-tests.log').splitlines()[-1])
    script="""import runpy,json
h=runpy.run_path('/run/p1/p1_activation_remote.py'); h['_configure']()
from django.core.management import call_command
from django.db import connections
connections['default'].settings_dict['TEST']['NAME']='test_regulai_greeting_patch_20261017'
call_command('test','front.test_privacy_agent','front.test_privacy_boundaries','front.test_agent_inference.AgentInferenceTests','front.test_agent_skills_runtime','front.test_agent_professional.ProfessionalTests.test_plain_request_is_told_to_answer_in_chat_without_research','front.test_agent_professional.ProfessionalTests.test_actual_image_bytes_use_vision_gateway_and_record_exact_hash','front.test_agent_professional.ProfessionalTests.test_three_entries_real_account_free_text_and_http_idempotency',interactive=False,verbosity=1)
from front.chat_assets import assets,react_enabled
assert react_enabled()
print(json.dumps({'asset':assets()['script']}))
"""
    checked=app(image,script,'targeted-tests.log')
    h['equal_fingerprints'](before,call(rows[WEB]['Image'],'fingerprint',before))
    state={'phase':'prepared','image':image,'image_id':json.loads(docker('image','inspect',image))[0]['Id'],
           'validation':json.loads(checked.splitlines()[-1]),'test_summary':checked.splitlines()[0],
           'legacy_baseline':baseline,
           'provider_generation_calls':0,'schema_changes':0,'account_changes':0}
    save(STAGE/'state.json',state)
    return state

def apply():
    state=h['read_json'](STAGE/'state.json')
    if state['phase']!='prepared': raise RuntimeError('prepared_patch_required')
    rows=h['read_json'](STAGE/'original.json')
    if h['original_identity']({n:inspect(n) for n in rows})!=h['original_identity'](rows):
        raise RuntimeError('installed_services_changed')
    if h['private_configuration_digest']()!=h['read_json'](STAGE/'private-configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    if json.loads(docker('image','inspect',state['image']))[0]['Id']!=state['image_id']:
        raise RuntimeError('patch_image_changed')
    h['require_idle'](current=True)
    payload=copy.deepcopy(rows[WEB]['Config']); payload.pop('Hostname',None); payload.pop('Domainname',None)
    payload.update(Image=state['image_id'],HostConfig=copy.deepcopy(rows[WEB]['HostConfig']))
    payload['Labels']={**payload.get('Labels',{}),'regulai.greeting_patch':REQUEST['identity']}
    candidate=WEB+'-candidate-'+REQUEST['identity']
    conn=h['DockerConnection']('localhost')
    try:
        conn.request('POST','/v1.47/containers/create?name='+candidate,body=json.dumps(payload),headers={'Content-Type':'application/json'})
        response=conn.getresponse(); response.read()
        if response.status!=201: raise RuntimeError('candidate_create_failed')
    finally: conn.close()
    docker('stop',WORKER,WEB)
    meta=call(rows[WEB]['Image'],'metadata')
    if any(meta[k] for k in ('live','active_calls','pending_inferences','provider_occupied','sandbox_occupied')):
        docker('start',WEB,WORKER)
        raise RuntimeError('new_work_arrived_before_switch')
    before=call(rows[WEB]['Image'],'fingerprint')
    save(STAGE/'before-switch.json',before)
    original_name=WEB+'-before-'+REQUEST['identity']
    docker('rename',WEB,original_name); docker('rename',candidate,WEB)
    try:
        docker('start',WEB)
        h['require_idle'](current=True)
        docker('start',WORKER)
        h['equal_fingerprints'](before,call(state['image'],'fingerprint',before))
    except Exception:
        # No migrations or configuration writes: the previous image is compatible.
        docker('stop',WORKER,WEB); docker('rename',WEB,WEB+'-failed-'+REQUEST['identity'])
        docker('rename',original_name,WEB); docker('start',WEB,WORKER)
        raise
    state.update(phase='applied',all_existing_data_unchanged=True,previous_web=original_name)
    save(STAGE/'state.json',state)
    return state

def finish():
    state=h['read_json'](STAGE/'state.json')
    if state['phase']!='applied': raise RuntimeError('applied_patch_required')
    rows={n:inspect(n) for n in (WEB,WORKER)}
    original=h['read_json'](STAGE/'original.json')
    if rows[WEB]['Image']!=state['image_id'] or rows[WORKER]['Id']!=original[WORKER]['Id']:
        raise RuntimeError('unexpected_service_identity')
    if h['private_configuration_digest']()!=h['read_json'](STAGE/'private-configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    for row in rows.values():
        if not row['State']['Running'] or row['RestartCount']:
            raise RuntimeError('service_not_stable')
    expected={p:hashlib.sha256((STAGE/'source'/p).read_bytes()).hexdigest()
              for p in REQUEST['allowed']+['regulai/static/chat-app/manifest.json']}
    script="import json,hashlib\nfrom pathlib import Path\nexpected=%r\nactual={p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in expected}\nassert actual==expected\nprint(json.dumps(actual))"%expected
    actual=json.loads(docker('exec','-i',WEB,'python','-',data=script.encode()))
    return {'phase':'verified','image_id':state['image_id'],'installed_hashes':actual,
            'services':{n:{'running':r['State']['Running'],'restarts':r['RestartCount']} for n,r in rows.items()},
            'private_configuration_unchanged':True,'provider_generation_calls':0}

try:
    print(json.dumps({'prepare':prepare,'validate':validate,'apply':apply,'finish':finish}[REQUEST['action']]()))
except Exception as error:
    if STAGE.exists():
        (STAGE/'error.log').write_text(traceback.format_exc()); os.chmod(STAGE/'error.log',0o600)
    print(json.dumps({'error':type(error).__name__,'code':str(error) if isinstance(error,RuntimeError) else 'inspect_private_log'}))
    raise SystemExit(1)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','validate','apply','finish'])
    args=parser.parse_args()
    allowed=['regulai/front/agents/service.py','regulai/front/agents/delivery.py',
             'regulai/front/test_privacy_agent.py','regulai/front/test_privacy_boundaries.py',
             'regulai/static/js/agent-chat.js']
    request={'action':args.action,'identity':IDENTITY,'allowed':allowed,
             'helper':(ROOT/'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8')}
    if args.action=='prepare':
        paths=allowed+[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'regulai/static/chat-app').rglob('*') if p.is_file()]
        request['files']={p:base64.b64encode((ROOT/p).read_bytes()).decode() for p in paths}
    loader='import sys,json; REQUEST=json.loads(sys.stdin.buffer.readline()); exec(compile(sys.stdin.buffer.read(),"greeting_patch.py","exec"))'
    result=subprocess.run([*SSH,'sudo python3 -c '+shlex.quote(loader)],input=json.dumps(request).encode()+b'\n'+REMOTE.encode(),capture_output=True)
    if result.returncode: raise SystemExit(result.stdout.decode()[-1200:] or 'Private patch stage failed.')
    value=json.loads(result.stdout)
    (ROOT/'output/privacy-20261017'/('greeting-'+args.action+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(value,indent=2))


if __name__=='__main__':
    main()
