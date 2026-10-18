"""Private, current-image-bound, web-image Jev update with coordinated worker restart; no migrations or policy changes."""
import ast
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import traceback
import urllib.parse
import urllib.request
import uuid

if REQUEST['identity'] != 'jev-difficulty-20261018-a1':
    raise RuntimeError('invalid_jev_update_identity')
STAGE = Path('/opt/regulai/updates') / REQUEST['identity']
WEB, WORKER, PG = 'regulai-v2-web', 'regulai-v2-worker', 'regulai-v2-postgres'
SERVICE = 'regulai/front/agents/service.py'
TESTS = {'regulai/front/' + name + '.py' for name in (
    'test_agent_difficulty', 'test_agent_transparency', 'test_agent_inference', 'test_agent_state',
    'test_agent_context_performance', 'test_agent_message_batch', 'test_privacy_agent',
    'test_difficulty_routing', 'test_chat_flow', 'test_pipeline', 'test_chat_island',
    'test_local_masking')}
PRESERVED = ('regulai/front/agents/general_tools.py', 'regulai/front/agents/checkpoints.py',
             'regulai/front/agents/history.py', 'regulai/front/agents/continuation.py')
h = {'__name__': 'jev_update_helper', '_ACTIVATION_SOURCE': REQUEST['helper']}
exec(compile(REQUEST['helper'], 'helper.py', 'exec'), h)
docker, inspect, save = h['docker'], h['inspect'], h['private_json']
# Load the reviewed preservation primitives only, never the latency stage/dispatcher.
names = {'app_args', 'fingerprint', 'mount_file_digest', 'mounted_files', 'equal_readonly_mounts',
         'checkpoint_changed_count', 'backup_checkpoints', 'metadata', 'require_no_work',
         'container', 'health_http'}
tree = ast.parse(REQUEST['primitives'])
definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
if {node.name for node in definitions} != names:
    raise RuntimeError('preservation_primitives_missing')
exec(compile(ast.Module(body=definitions, type_ignores=[]), 'preservation_primitives.py', 'exec'))


def original():
    return h['read_json'](STAGE / 'original.json')


def require_original():
    rows = original()
    if h['original_identity']({name: inspect(name) for name in rows}) != h['original_identity'](rows):
        raise RuntimeError('current_installation_changed_since_init')
    return rows


def hashes(image=None, container_id=None):
    script = "import hashlib,json\nfrom pathlib import Path\npaths=%r\nprint(json.dumps({p:hashlib.sha256((Path('/app')/p).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() for p in paths}))" % ((SERVICE, *PRESERVED),)
    raw = (docker('exec', '-i', container_id, 'python', '-', data=script.encode()) if container_id else
           docker('run', '--rm', '-i', '--network', 'none', '--read-only', image, 'python', '-', data=script.encode()))
    return json.loads(raw)


def init():
    rows = {name: inspect(name) for name in (WEB, WORKER, PG)}
    if rows[WEB]['Image'] != REQUEST['expected_web']:
        raise RuntimeError('expected_current_chat12_image_required')
    h['require_idle'](current=True)
    if (STAGE / 'original.json').exists():
        require_original()
        return {'phase': 'already_initialized', 'base_image_id': rows[WEB]['Image']}
    observed = hashes(container_id=rows[WEB]['Id'])
    if observed[SERVICE] != REQUEST['baseline_service']:
        raise RuntimeError('current_service_source_changed')
    if rows[WEB]['HostConfig'].get('AutoRemove') or rows[WEB]['HostConfig']['NetworkMode'] != 'host':
        raise RuntimeError('unsupported_current_web_configuration')
    STAGE.mkdir(mode=0o700)
    save(STAGE / 'original.json', rows)
    save(STAGE / 'source-before.json', observed)
    save(STAGE / 'mounts-init.json', mounted_files(rows))
    backup = h['snapshot_backup'](STAGE, 'before-prepare')
    save(STAGE / 'database-init.json', fingerprint(rows[WEB]['Image']))
    return {'phase': 'initialized', 'base_image_id': rows[WEB]['Image'],
            'worker_image_id': rows[WORKER]['Image'], 'preserved_source_hashes': observed,
            'backup': backup, 'database_modified': False}


def build():
    rows = require_original()
    before = h['read_json'](STAGE / 'source-before.json')
    if hashes(container_id=rows[WEB]['Id']) != before:
        raise RuntimeError('live_source_changed')
    raw = base64.b64decode(REQUEST['service'], validate=True).replace(b'\r\n', b'\n')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REQUEST['target_sha256']:
        raise RuntimeError('candidate_source_hash_mismatch')
    compile(raw, SERVICE, 'exec')
    context = STAGE / ('context-' + digest[:16])
    context.mkdir(mode=0o700, exist_ok=True)
    (context / 'service.py').write_bytes(raw)
    base_tag = 'regulai-v2-web:' + REQUEST['identity'] + '-base'
    docker('tag', rows[WEB]['Image'], base_tag)
    definition = 'FROM ' + base_tag + '\nCOPY service.py /app/' + SERVICE + '\n'
    (context / 'Dockerfile').write_text(definition)
    if {path.name for path in context.iterdir()} != {'service.py', 'Dockerfile'}:
        raise RuntimeError('unexpected_build_context_file')
    image = 'regulai-v2-web:' + REQUEST['identity']
    with (STAGE / 'build.log').open('wb') as output:
        docker('build', '--network=none', '--pull=false', '-t', image, str(context), output=output)
    image_info = json.loads(docker('image', 'inspect', image))[0]
    base_info = json.loads(docker('image', 'inspect', rows[WEB]['Image']))[0]
    layers, base_layers = image_info['RootFS']['Layers'], base_info['RootFS']['Layers']
    if layers[:-1] != base_layers or len(layers) != len(base_layers) + 1:
        raise RuntimeError('candidate_not_based_on_current_image')
    expected = {**before, SERVICE: digest}
    if hashes(image=image_info['Id']) != expected:
        raise RuntimeError('candidate_source_preservation_failed')
    if set(REQUEST['tests']) != TESTS:
        raise RuntimeError('unexpected_test_source_paths')
    test_hashes = {}
    (STAGE / 'tests').mkdir(mode=0o700, exist_ok=True)
    for path, encoded in REQUEST['tests'].items():
        test = base64.b64decode(encoded, validate=True)
        compile(test, path, 'exec')
        target = STAGE / 'tests' / Path(path).name
        target.write_bytes(test)
        target.chmod(0o644)
        test_hashes[path] = hashlib.sha256(test).hexdigest()
    value = {'phase': 'built', 'image_id': image_info['Id'], 'image': image,
             'base_image_id': rows[WEB]['Image'], 'source_hashes': expected,
             'test_hashes': test_hashes, 'application_files_changed': [SERVICE],
             'worker_image_config_preserved': True}
    save(STAGE / 'candidate.json', value)
    return value


def clean_test_container(name, owner):
    response = subprocess.run(['docker', 'inspect', name], capture_output=True)
    if response.returncode:
        return
    row = json.loads(response.stdout)[0]
    if (row['Config'].get('Labels') or {}).get('regulai.jev_test') != owner:
        raise RuntimeError('unexpected_test_container_owner')
    docker('rm', '-f', row['Id'])  # No volumes; PG data lives only in tmpfs.


def tests():
    rows = require_original()
    candidate = h['read_json'](STAGE / 'candidate.json')
    if candidate['source_hashes'][SERVICE] != REQUEST['target_sha256']:
        raise RuntimeError('rebuild_required_for_current_source')
    if set(candidate['test_hashes']) != TESTS or any(
            hashlib.sha256((STAGE / 'tests' / Path(path).name).read_bytes()).hexdigest() != expected
            for path, expected in candidate['test_hashes'].items()):
        raise RuntimeError('test_source_changed')
    suffix = uuid.uuid4().hex[:10]
    network = 'jev-test-net-' + suffix
    pg_name, app_name = 'jev-test-pg-' + suffix, 'jev-test-app-' + suffix
    created_network = False
    try:
        docker('network', 'create', '--internal', '--label', 'regulai.jev_test=' + suffix, network)
        created_network = True
        docker('run', '-d', '--rm', '--pull', 'never', '--name', pg_name,
               '--label', 'regulai.jev_test=' + suffix, '--network', network,
               '--tmpfs', '/var/lib/postgresql/data:rw,nosuid,nodev,size=768m',
               '-e', 'POSTGRES_USER=jev_test', '-e', 'POSTGRES_PASSWORD=synthetic-test-only',
               '-e', 'POSTGRES_DB=postgres', rows[PG]['Image'])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready = subprocess.run(['docker', 'exec', pg_name, 'pg_isready', '-U', 'jev_test'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('isolated_postgres_not_ready')
        script = """import runpy,json
runpy.run_path('/app/ops/setup/server.py',run_name='setupserver_config')
from django.db import connections
from django.conf import settings
from django.test.runner import DiscoverRunner
connections.close_all()
settings.DATABASES['default'].update(NAME='postgres',USER='jev_test',PASSWORD='synthetic-test-only',HOST=%r,PORT='5432')
connections['default'].settings_dict.update(settings.DATABASES['default'])
connections['default'].settings_dict['TEST']['NAME']='test_jev'
class Recorded(DiscoverRunner):
 def suite_result(self,suite,result,**kwargs):
  print(json.dumps({'tests':result.testsRun,'failures':[str(t) for t,_ in result.failures],
   'errors':[str(t) for t,_ in result.errors],'skipped':[(str(t),reason) for t,reason in result.skipped]}))
  return super().suite_result(suite,result,**kwargs)
labels=['front.test_agent_difficulty','front.test_agent_transparency','front.test_agent_inference.AgentInferenceTests','front.test_agent_state.AgentStateTests','front.test_agent_context_performance','front.test_agent_message_batch','front.test_privacy_agent','front.test_difficulty_routing']
raise SystemExit(Recorded(interactive=False,verbosity=1).run_tests(labels))
""" % pg_name
        args = app_args(candidate['image_id'])
        args[args.index('host')] = network
        args += ['--name', app_name, '--label', 'regulai.jev_test=' + suffix]
        for path in sorted(candidate['test_hashes']):
            args += ['--mount', 'type=bind,src=' + str(STAGE / 'tests' / Path(path).name) +
                     ',dst=/app/' + path + ',readonly']
        result = subprocess.run(['docker', 'run', '--rm', '-i', *args, candidate['image_id'], 'python', '-'],
                                input=script.encode(), capture_output=True, timeout=900)
        (STAGE / 'tests.log').write_bytes(result.stdout + result.stderr)
        (STAGE / 'tests.log').chmod(0o600)
        summaries = [json.loads(line) for line in result.stdout.decode().splitlines() if line.startswith('{')]
        value = {'phase': 'tested', 'exit_code': result.returncode, 'image_id': candidate['image_id'],
                 'summary': summaries[-1] if summaries else None, 'network': 'internal',
                 'postgres': 'isolated_tmpfs', 'live_database_used': False, 'external_provider_calls': 0,
                 'isolated_resources_removed': False, 'test_hashes': candidate['test_hashes']}
        save(STAGE / 'tests.json', value)
        return value
    finally:
        if created_network:
            clean_test_container(app_name, suffix)
            clean_test_container(pg_name, suffix)
            docker('network', 'rm', network)
            if 'value' in locals():
                value['isolated_resources_removed'] = True
                save(STAGE / 'tests.json', value)


def create_web(original_row, image_id, name):
    payload = copy.deepcopy(original_row['Config'])
    payload.update(Image=image_id, HostConfig=copy.deepcopy(original_row['HostConfig']))
    client = h['DockerConnection']('localhost')
    try:
        client.request('POST', '/v1.47/containers/create?name=' + urllib.parse.quote(name, safe=''),
                       body=json.dumps(payload), headers={'Content-Type': 'application/json'})
        response = client.getresponse()
        raw = response.read()
        if response.status != 201:
            raise RuntimeError('candidate_create_failed')
        return json.loads(raw)['Id']
    finally:
        client.close()


def restore_web(identifier, known):
    current = container(WEB)
    if current is not None and current['Id'] != identifier:
        if current['Id'] not in known:
            raise RuntimeError('unknown_current_web')
        docker('stop', current['Id'])
        docker('rename', current['Id'], WEB + '-jev-parked-' + current['Id'][:12])
    row = container(identifier)
    if row is None:
        raise RuntimeError('retained_web_missing')
    if row['Name'].lstrip('/') != WEB:
        docker('rename', identifier, WEB)
    docker('start', identifier)
    health_http()


def require_companions(rows, worker_running=True):
    others = {name: inspect(name) for name in (WORKER, PG)}
    if h['original_identity'](others) != h['original_identity']({name: rows[name] for name in others}):
        raise RuntimeError('worker_or_postgres_changed')
    if any(row['RestartCount'] != rows[name]['RestartCount']
           or ((name == PG or worker_running) and not row['State']['Running'])
           for name, row in others.items()):
        raise RuntimeError('worker_or_postgres_runtime_changed')
    return others


def start_worker(rows):
    others = require_companions(rows, worker_running=False)
    if not others[WORKER]['State']['Running']:
        docker('start', rows[WORKER]['Id'])
    require_companions(rows)


def restore_services(identifier, known, rows):
    current = container(WEB)
    if current is not None and current['Id'] not in known:
        raise RuntimeError('unknown_current_web')
    require_companions(rows, worker_running=False)
    try:
        try:
            if current is not None:
                docker('stop', current['Id'])
        finally:
            docker('stop', rows[WORKER]['Id'])
    finally:
        try:
            restore_web(identifier, known)
        finally:
            start_worker(rows)


def verify():
    rows = original()
    candidate = h['read_json'](STAGE / 'candidate.json')
    current = inspect(WEB)
    if current['Image'] != candidate['image_id'] or not current['State']['Running'] or current['RestartCount']:
        raise RuntimeError('candidate_not_running')
    expected_config = {**rows[WEB]['Config'], 'Image': candidate['image_id']}
    if current['Config'] != expected_config or current['HostConfig'] != rows[WEB]['HostConfig']:
        raise RuntimeError('web_configuration_changed')
    mounts = lambda row: sorted(row['Mounts'], key=lambda item: item['Destination'])
    if mounts(current) != mounts(rows[WEB]) or set(current['NetworkSettings']['Networks']) != set(rows[WEB]['NetworkSettings']['Networks']):
        raise RuntimeError('web_mounts_or_networks_changed')
    others = require_companions(rows)
    if hashes(container_id=current['Id']) != candidate['source_hashes']:
        raise RuntimeError('candidate_sources_changed')
    equal_readonly_mounts(h['read_json'](STAGE / 'mounts-before-switch.json'), mounted_files(rows))
    health_http()
    h['require_idle'](current=True)
    return {'phase': 'verified', 'image_id': current['Image'], 'base_image_id': rows[WEB]['Image'],
            'source_hashes_verified': True, 'chat12_sources_preserved': True,
            'env_mounts_networks_preserved': True, 'mounted_config_and_keys_unchanged': True,
            'worker_image_config_preserved': True,
            'worker_restarted': others[WORKER]['State'].get('StartedAt') != rows[WORKER]['State'].get('StartedAt'),
            'postgres_unchanged': True, 'schema_changes': 0, 'provider_calls': 0}


def apply():
    rows = require_original()
    require_companions(rows)
    candidate, tested = h['read_json'](STAGE / 'candidate.json'), h['read_json'](STAGE / 'tests.json')
    summary = tested.get('summary') or {}
    if (tested['exit_code'] or not tested.get('isolated_resources_removed')
            or tested['image_id'] != candidate['image_id']
            or tested.get('test_hashes') != candidate['test_hashes']
            or not isinstance(summary.get('tests'), int) or summary['tests'] <= 0
            or summary.get('failures') != [] or summary.get('errors') != []
            or candidate['source_hashes'][SERVICE] != REQUEST['target_sha256']):
        raise RuntimeError('current_candidate_tests_required')
    h['require_idle'](current=True)
    before_mounts = mounted_files(rows)
    equal_readonly_mounts(h['read_json'](STAGE / 'mounts-init.json'), before_mounts)
    name, retained = WEB + '-candidate-' + REQUEST['identity'], WEB + '-before-' + REQUEST['identity']
    if container(name) is not None or container(retained) is not None:
        raise RuntimeError('switch_name_already_exists')
    replacement = None
    try:
        replacement = create_web(rows[WEB], candidate['image_id'], name)
        save(STAGE / 'switch.json', {'original_web_id': rows[WEB]['Id'], 'candidate_web_id': replacement,
                                    'retained_name': retained})
        h['require_idle'](current=True)
        docker('stop', rows[WEB]['Id'])
        docker('stop', rows[WORKER]['Id'])
        require_no_work(rows[WEB]['Image'])
        stable_mounts = mounted_files(rows)
        equal_readonly_mounts(before_mounts, stable_mounts)
        save(STAGE / 'mounts-before-switch.json', stable_mounts)
        label = 'before-switch-' + str(time.time_ns())
        checkpoints = backup_checkpoints(stable_mounts, label)
        backup = h['snapshot_backup'](STAGE, label)
        before = fingerprint(rows[WEB]['Image'])
        save(STAGE / 'database-before-switch.json', before)
        docker('rename', rows[WEB]['Id'], retained)
        docker('rename', replacement, WEB)
        if mounted_files(rows) != stable_mounts:
            raise RuntimeError('mounted_files_changed_before_start')
        docker('start', replacement)
        health_http()
        start_worker(rows)
        result = verify()
        h['equal_fingerprints'](before, fingerprint(candidate['image_id'], before))
        final_mounts = mounted_files(rows)
        if final_mounts != stable_mounts:
            raise RuntimeError('mounted_files_changed_after_switch')
        result.update(phase='applied', existing_data_unchanged=True, checkpoints_unchanged=True,
                      worker_image_config_preserved=True, worker_restarted=True,
                      backup=backup, checkpoint_backup=checkpoints, retained_web_id=rows[WEB]['Id'])
        save(STAGE / 'applied.json', result)
        return result
    except Exception:
        restore_services(rows[WEB]['Id'], {rows[WEB]['Id'], replacement} - {None}, rows)
        raise


def rollback():
    rows = original()
    require_companions(rows, worker_running=False)
    switch = h['read_json'](STAGE / 'switch.json')
    known = {switch['original_web_id'], switch['candidate_web_id']}
    current = container(WEB)
    if current is None or current['Id'] not in known:
        raise RuntimeError('current_web_identity_changed')
    retained = container(rows[WEB]['Id'])
    if retained is None or retained['Image'] != rows[WEB]['Image']:
        raise RuntimeError('retained_current_base_missing')
    require_no_work(rows[WEB]['Image'])
    before_mounts = mounted_files(rows)
    try:
        docker('stop', current['Id'])
        docker('stop', rows[WORKER]['Id'])
        require_no_work(rows[WEB]['Image'])
        stable_mounts = mounted_files(rows)
        equal_readonly_mounts(before_mounts, stable_mounts)
        before = fingerprint(rows[WEB]['Image'])
        restore_services(rows[WEB]['Id'], known, rows)
        h['equal_fingerprints'](before, fingerprint(rows[WEB]['Image'], before))
        if mounted_files(rows) != stable_mounts:
            raise RuntimeError('mounted_files_changed_during_rollback')
        if any(inspect(name)['Id'] != rows[name]['Id'] for name in (WEB, WORKER, PG)):
            raise RuntimeError('rollback_did_not_restore_initialized_identities')
        result = {'phase': 'rolled_back', 'restored_image_id': rows[WEB]['Image'],
                  'data_keys_checkpoints_unchanged': True, 'database_restored': False,
                  'worker_image_config_preserved': True, 'worker_restarted': True}
        save(STAGE / 'rollback.json', result)
        return result
    except Exception:
        restore_services(current['Id'], known, rows)
        raise


try:
    print(json.dumps({'init': init, 'build': build, 'tests': tests, 'apply': apply,
                      'verify': verify, 'rollback': rollback}[REQUEST['action']]()))
except Exception as error:
    if STAGE.exists():
        (STAGE / 'error.log').write_text(traceback.format_exc())
        (STAGE / 'error.log').chmod(0o600)
    print(json.dumps({'error': str(error) if isinstance(error, RuntimeError) else type(error).__name__}))
    raise SystemExit(1)
