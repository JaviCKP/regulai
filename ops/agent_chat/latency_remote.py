"""Private VM stages. Invoked only by latency_local.py, preserves live data/keys."""
import base64
import copy
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
import subprocess
import time
import traceback
import urllib.parse
import urllib.request
import uuid

STAGE = Path('/opt/regulai/updates') / 'latency-20261017-a1'
WEB, WORKER, PG = 'regulai-v2-web', 'regulai-v2-worker', 'regulai-v2-postgres'
WORKER_MODULES = {'regulai/front/agents/worker.py', 'regulai/front/agents/skill_backend.py'}
WORKER_TESTS = {'ops/agent_chat/test_queue_dispatch.py', 'ops/agent_chat/test_p1_skills_runtime.py',
                'ops/agent_chat/test_p1_skill_materialization.py'}
h = {'__name__': 'latency_helper', '_ACTIVATION_SOURCE': REQUEST['helper']}
exec(compile(REQUEST['helper'], 'helper.py', 'exec'), h)
docker, inspect, save = h['docker'], h['inspect'], h['private_json']


def app_args(image):
    original = h['read_json'](STAGE / 'original.json')[WEB]
    args = ['--network', 'host', '--user', '1000:1000', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=1000']
    for mount in original['Mounts']:
        if mount['Type'] != 'bind' or mount['RW'] or mount['Destination'] not in {'/run/private', '/run/p1'}:
            raise RuntimeError('unexpected_web_mount')
        args += ['--mount', f"type=bind,src={mount['Source']},dst={mount['Destination']},readonly"]
    return args


def fingerprint(image, prior=None):
    source = "import runpy,sys,io,json\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nsys.stdin=io.StringIO(%r)\nprint(json.dumps(h['inside_web']('fingerprint')))" % json.dumps(prior or {})
    return json.loads(docker('run', '--rm', '-i', *app_args(image), image, 'python', '-', data=source.encode()))



def mount_file_digest(path):
    """Hash regular files only, without following a final symlink or leaking bytes."""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError('mounted_file_not_regular')
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        after = os.fstat(stream.fileno())
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns)
    if identity(before) != identity(after):
        raise RuntimeError('mounted_file_changed_during_fingerprint')
    return {'sha256': digest.hexdigest(), 'bytes': before.st_size,
            'mode': stat.S_IMODE(before.st_mode), 'uid': before.st_uid, 'gid': before.st_gid}


def mounted_files(original, root=None):
    """Fingerprint actual readonly mounts and worker state; exclude special files."""
    allowed = Path('/opt/regulai') if root is None else Path(root)
    allowed = allowed.resolve(strict=True)
    result = {'readonly': [], 'state': []}
    for service, row in sorted(original.items()):
        for mount in sorted(row['Mounts'], key=lambda value: value['Destination']):
            is_state = service == WORKER and mount['Destination'] == '/state'
            if mount['RW'] and not is_state:
                continue  # PostgreSQL data has its own logical fingerprint.
            if mount['Type'] != 'bind':
                raise RuntimeError('unsupported_preserved_mount')
            source = Path(mount['Source'])
            resolved = source.resolve(strict=True)
            if source != resolved or not resolved.is_relative_to(allowed):
                raise RuntimeError('preserved_mount_path_denied')
            if is_state and not source.is_dir():
                raise RuntimeError('checkpoint_mount_not_directory')
            files, directories = {}, []
            entries = [source]
            while entries:
                path = entries.pop()
                mode = path.lstat().st_mode
                relative = path.relative_to(source).as_posix()
                if stat.S_ISLNK(mode):
                    raise RuntimeError('preserved_mount_symlink_denied')
                if stat.S_ISDIR(mode):
                    directories.append(relative)
                    entries.extend(sorted(path.iterdir(), reverse=True))
                elif stat.S_ISREG(mode):
                    files[relative] = mount_file_digest(path)
                # Sockets, devices, FIFOs and proc-like special entries are never read.
            result['state' if is_state else 'readonly'].append({
                'service': service, 'source': str(source), 'destination': mount['Destination'],
                'files': files, 'directories': sorted(directories)})
    if not result['readonly'] or len(result['state']) != 1:
        raise RuntimeError('required_preserved_mount_missing')
    return result


def equal_readonly_mounts(before, after):
    if before['readonly'] != after['readonly']:
        raise RuntimeError('mounted_readonly_configuration_changed')


def checkpoint_changed_count(before, after):
    def flattened(snapshot):
        return {(mount['service'], mount['destination'], path): value
                for mount in snapshot['state'] for path, value in mount['files'].items()}
    left, right = flattened(before), flattened(after)
    return sum(left.get(key) != right.get(key) for key in left.keys() | right.keys())


def backup_checkpoints(snapshot, label):
    """Private, verified copy while both services are stopped; never restores over data."""
    if not label.startswith(('before-switch-', 'before-rollback-')) or not label.rsplit('-', 1)[-1].isdigit():
        raise RuntimeError('invalid_checkpoint_backup_label')
    directory = STAGE / ('checkpoints-' + label)
    directory.mkdir(mode=0o700)  # A retry must not overwrite an existing backup.
    count = 0
    for index, mount in enumerate(snapshot['state']):
        source = Path(mount['source'])
        target = directory / str(index)
        target.mkdir(mode=0o700)
        for relative in mount['directories']:
            if relative != '.':
                (target / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
        for relative, expected in mount['files'].items():
            destination = target / relative
            with (source / relative).open('rb') as reader, destination.open('xb') as writer:
                os.chmod(destination, 0o600)
                shutil.copyfileobj(reader, writer)
            actual = mount_file_digest(destination)
            if any(actual[key] != expected[key] for key in ('sha256', 'bytes')):
                raise RuntimeError('checkpoint_backup_changed_during_copy')
            count += 1
    save(directory / 'manifest.json', snapshot['state'])
    return {'directory': str(directory), 'files': count,
            'manifest_sha256': hashlib.sha256(json.dumps(snapshot['state'], sort_keys=True).encode()).hexdigest()}

def init():
    if (STAGE / 'original.json').exists():
        if not all((STAGE / name).is_file() for name in ('configuration.json', 'baseline.dump', 'before.json')):
            raise RuntimeError('initialization_incomplete_inspect_private_stage')
        return {'phase': 'already_initialized'}
    h['require_idle'](current=True)
    STAGE.mkdir(mode=0o700)
    rows = {name: inspect(name) for name in (WEB, WORKER, PG)}
    save(STAGE / 'original.json', rows)
    save(STAGE / 'configuration.json', {'digest': h['private_configuration_digest']()})
    backup = h['snapshot_backup'](STAGE, 'baseline')
    save(STAGE / 'before.json', fingerprint(rows[WEB]['Image']))
    return {'phase': 'initialized', 'backup': backup,
        'images': {name: row['Image'] for name, row in rows.items()}, 'live_data_modified': False}


def benchmark():
    variant = 'baseline' if REQUEST['action'] == 'bench-baseline' else 'after'
    number, count = int(REQUEST['round']), int(REQUEST['count'])
    if not 0 <= number < 20 or not 1 <= count <= 30:
        raise RuntimeError('invalid_benchmark_size')
    database = f'regulai_p1_latency_{variant}_{number}'
    folder = STAGE / f'bench-{variant}-{number}'
    folder.mkdir(mode=0o755, exist_ok=True)
    for name, encoded in REQUEST['scripts'].items():
        if name not in {'latency_benchmark_server.py', 'latency_benchmark_worker.py'}:
            raise RuntimeError('invalid_script')
        (folder / name).write_bytes(base64.b64decode(encoded, validate=True))
    (folder / 'token').write_text('latency-fixture-worker-only-20261017')
    (folder / 'config.json').write_text(json.dumps({'internal_endpoint': 'http://127.0.0.1:31103/internal/agents/',
        'worker_token_file': '/bench/token', 'concurrency': 2}))
    for path in folder.iterdir():
        if path.is_file():
            path.chmod(0o644)
    results = folder / 'results'
    results.mkdir(mode=0o700)
    os.chown(results, 1000, 1000)
    # A new name is required. Never drop/overwrite a database to retry a run.
    docker('exec', PG, 'createdb', '-U', 'regulai', database)
    docker('exec', '-i', PG, 'pg_restore', '-U', 'regulai', '-d', database,
        '--exit-on-error', '--no-owner', '--no-acl', data=(STAGE / 'baseline.dump').read_bytes())
    original = h['read_json'](STAGE / 'original.json')
    images = ({'web': original[WEB]['Image'], 'worker': original[WORKER]['Image']} if variant == 'baseline'
        else h['read_json'](STAGE / 'candidate.json')['images'])
    server_name, worker_name = f'latency-server-{variant}-{number}', f'latency-worker-{variant}-{number}'
    mounted = ['--mount', f'type=bind,src={folder},dst=/bench,readonly']
    try:
        docker('run', '-d', '--name', server_name, *app_args(images['web']), *mounted,
            '--mount', f'type=bind,src={results},dst=/results',
            '-e', 'BENCH_DATABASE=' + database, '-e', 'BENCH_COUNT=' + str(count),
            images['web'], 'python', '/bench/latency_benchmark_server.py')
        for _ in range(150):
            ready = subprocess.run(['docker', 'exec', server_name, 'test', '-f', '/tmp/latency-ready'], capture_output=True)
            if ready.returncode == 0:
                break
            if not json.loads(docker('inspect', server_name))[0]['State']['Running']:
                raise RuntimeError('benchmark_server_failed_start')
            time.sleep(.2)
        else:
            raise RuntimeError('benchmark_server_not_ready')
        docker('run', '-d', '--name', worker_name, '--network', 'host', '--user', '1000:1000',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,uid=1000,gid=1000', *mounted,
            images['worker'], 'python', '/bench/latency_benchmark_worker.py')
        deadline = time.monotonic() + count * 180 + 60
        report = None
        while time.monotonic() < deadline:
            report_path = results / 'report.json'
            if report_path.is_file():
                try:
                    report = h['read_json'](report_path)
                except (ValueError, OSError):
                    report = None  # The producer may still be replacing/writing it.
                if report is not None and len(report.get('rows', [])) == count:
                    if any(row.get('status') != 'completed' for row in report['rows']):
                        raise RuntimeError('benchmark_execution_not_completed')
                    break
            if not json.loads(docker('inspect', server_name))[0]['State']['Running']:
                raise RuntimeError('benchmark_server_failed_before_complete_report')
            time.sleep(.5)
        else:
            raise RuntimeError('benchmark_report_timeout')
        # The persisted complete report is the result. A later 143 during the
        # bounded cleanup is not a failed benchmark or a reason to lose metrics.
        report.update(variant=variant, round=number, database=database, images=images,
            image_ids={kind: json.loads(docker('image', 'inspect', image))[0]['Id'] for kind, image in images.items()})
        return report
    finally:
        for name in (worker_name, server_name):
            result = subprocess.run(['docker', 'logs', name], capture_output=True)
            (folder / (name + '.log')).write_bytes(result.stdout + result.stderr)
            (folder / (name + '.log')).chmod(0o600)
            subprocess.run(['docker', 'stop', '-t', '8', name], capture_output=True)



def benchmark_container(identifier):
    """Read benchmark identity without assuming application ownership labels exist."""
    client = h['DockerConnection']('localhost')
    try:
        client.request('GET', '/v1.47/containers/' + urllib.parse.quote(identifier, safe='') + '/json')
        response = client.getresponse()
        raw = response.read()
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError('benchmark_container_inspection_failed')
        return json.loads(raw)
    finally:
        client.close()


def check_benchmark_container(row, variant, number, role, original, candidate):
    """All evidence must match this task's exact synthetic benchmark resource."""
    name = f'latency-{role}-{variant}-{number}'
    folder = STAGE / f'bench-{variant}-{number}'
    if row['Name'].lstrip('/') != name:
        raise RuntimeError('benchmark_name_mismatch')
    if row['State']['Running']:
        raise RuntimeError('benchmark_still_running')
    if row['Config']['Cmd'] != ['python', f'/bench/latency_benchmark_{role}.py']:
        raise RuntimeError('benchmark_command_mismatch')
    expected = {(str(folder), '/bench', False)}
    kind = 'web' if role == 'server' else 'worker'
    service = WEB if role == 'server' else WORKER
    if role == 'server':
        expected |= {(mount['Source'], mount['Destination'], mount['RW'])
                     for mount in original[WEB]['Mounts'] if mount['Type'] == 'bind'}
        expected.add((str(folder / 'results'), '/results', True))
        environment = dict(value.split('=', 1) for value in row['Config'].get('Env', []) if '=' in value)
        if environment.get('BENCH_DATABASE') != f'regulai_p1_latency_{variant}_{number}':
            raise RuntimeError('benchmark_database_mismatch')
    actual = {(mount['Source'], mount['Destination'], mount['RW'])
              for mount in row['Mounts'] if mount['Type'] == 'bind'}
    legacy = expected - {(str(folder / 'results'), '/results', True)}
    # Early failed fixture runs predate the persistent /results bind mount.
    if actual not in (expected, legacy) or any(mount['Type'] not in {'bind', 'tmpfs'}
                                or (mount['Type'] == 'tmpfs' and mount['Destination'] != '/tmp')
                                for mount in row['Mounts']):
        raise RuntimeError('benchmark_mount_mismatch')
    if row['Image'] in {original[service]['Image'], candidate['image_ids'][kind]}:
        return
    # Earlier measured candidates used the same task tag before later rebuilds.
    # Prove they inherit the exact original image with one COPY-only layer.
    if variant != 'after' or row['Config'].get('Image') != candidate['images'][kind]:
        raise RuntimeError('benchmark_image_unknown')
    image = json.loads(docker('image', 'inspect', row['Image']))[0]
    base = json.loads(docker('image', 'inspect', original[service]['Image']))[0]
    layers, base_layers = image['RootFS']['Layers'], base['RootFS']['Layers']
    if len(layers) != len(base_layers) + 1 or layers[:-1] != base_layers or image['Config'] != base['Config']:
        raise RuntimeError('benchmark_image_lineage_mismatch')


def cleanup_benchmarks():
    """Remove only the explicitly owned fixture resources after successful apply."""
    if h['read_json'](STAGE / 'applied.json').get('phase') != 'applied':
        raise RuntimeError('successful_local_apply_required')
    verify()
    original = h['read_json'](STAGE / 'original.json')
    candidate = h['read_json'](STAGE / 'candidate.json')
    # Explicit coordinator-approved runs. Never discover deletion targets by prefix.
    approved = {'baseline': (0, 1, 2, 3, 4, 7, 8, 9, *range(10, 20)),
                'after': (4, 5, 6, 7, 10, 11, 12, *range(13, 20))}
    plans, pending = [], []
    for variant, numbers in approved.items():
        for number in numbers:
            folder = STAGE / f'bench-{variant}-{number}'
            names = [f'latency-{role}-{variant}-{number}' for role in ('worker', 'server')]
            rows = [benchmark_container(name) for name in names]
            if not folder.is_dir():
                if any(row is not None for row in rows):
                    pending.append({'run': folder.name, 'reason': 'benchmark_folder_missing'})
                continue
            if folder.resolve(strict=True) != folder:
                pending.append({'run': folder.name, 'reason': 'benchmark_folder_symlink_denied'})
                continue
            try:
                for role, row in zip(('worker', 'server'), rows):
                    if row is not None:
                        check_benchmark_container(row, variant, number, role, original, candidate)
            except RuntimeError as error:
                pending.append({'run': folder.name, 'reason': str(error)})
                continue
            plans.append({'database': f'regulai_p1_latency_{variant}_{number}',
                          'containers': [(row['Id'], name) for name, row in zip(names, rows) if row is not None]})
    names = [plan['database'] for plan in plans]
    existing, sessions = set(), set()
    if names:
        literals = ','.join("'" + name + "'" for name in names)
        existing = set(docker('exec', PG, 'psql', '-U', 'regulai', '-d', 'postgres', '-At', '-c',
            'SELECT datname FROM pg_database WHERE datname IN (' + literals + ')').decode().splitlines())
        sessions = set(docker('exec', PG, 'psql', '-U', 'regulai', '-d', 'postgres', '-At', '-c',
            'SELECT DISTINCT datname FROM pg_stat_activity WHERE datname IN (' + literals + ')').decode().splitlines())
    result = {'phase': 'benchmark_cleanup_in_progress', 'containers_removed': [], 'databases_removed': [],
              'pending': pending, 'private_artifacts_preserved': True,
              'persistent_volumes_modified': False, 'original_containers_preserved': True}
    record = STAGE / ('cleanup-' + str(time.time_ns()) + '.json')
    # Complete preflight above; each subsequent irreversible removal is recorded.
    for plan in plans:
        if plan['database'] in sessions:
            pending.append({'database': plan['database'], 'reason': 'benchmark_database_has_sessions'})
            continue
        for identifier, name in plan['containers']:
            current = benchmark_container(identifier)
            if current is None:
                continue
            if current['State']['Running'] or current['Id'] != identifier or current['Name'].lstrip('/') != name:
                raise RuntimeError('benchmark_identity_or_state_changed_before_removal')
            docker('rm', identifier)  # No -v: volumes are never deletion targets.
            result['containers_removed'].append(name)
            save(record, result)
        if plan['database'] in existing:
            # No --force: a newly opened session makes dropdb fail safely.
            docker('exec', PG, 'dropdb', '--if-exists', '-U', 'regulai', '--', plan['database'])
            result['databases_removed'].append(plan['database'])
            save(record, result)
    result['phase'] = 'benchmark_cleanup_partial' if pending else 'benchmark_cleanup_complete'
    save(record, result)
    return result

def build():
    original = h['read_json'](STAGE / 'original.json')
    if h['original_identity']({name: inspect(name) for name in original}) != h['original_identity'](original):
        raise RuntimeError('live_installation_changed')
    files = {}
    for path, encoded in REQUEST['files'].items():
        if '..' in path or '\\' in path or not path.endswith('.py') or not path.startswith(('regulai/front/', 'ops/agent_chat/test_')):
            raise RuntimeError('candidate_path_denied')
        files[path] = base64.b64decode(encoded, validate=True)
    images, ids, changed_by_kind, files_by_kind = {}, {}, {}, {}
    for kind, container in (('web', WEB), ('worker', WORKER)):
        selected = files if kind == 'web' else {path: raw for path, raw in files.items()
            if path in WORKER_MODULES | WORKER_TESTS}
        changed = [path for path in REQUEST['changed'] if path in selected]
        expected = {path: REQUEST['baseline'][path] for path in changed}
        script = "import hashlib\nfrom pathlib import Path\nexpected=%r\nactual={p:hashlib.sha256((Path('/app')/p).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest() if (Path('/app')/p).is_file() else None for p in expected}\nassert actual==expected,'live_source_changed'\n" % expected
        # Validate the worker's own SDK files as well as the application's files.
        docker('exec', '-i', container, 'python', '-', data=script.encode())
        manifest = {path: hashlib.sha256(raw).hexdigest() for path, raw in selected.items()}
        content_id = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
        context = STAGE / ('context-' + kind + '-' + content_id)
        context.mkdir(mode=0o700, exist_ok=True)
        for path, raw in selected.items():
            target = context / 'source' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        actual_paths = {path.relative_to(context / 'source').as_posix()
                        for path in (context / 'source').rglob('*') if path.is_file()}
        if actual_paths != set(selected):
            raise RuntimeError('candidate_context_has_unexpected_files')
        images[kind] = 'regulai-v2-' + kind + ':' + REQUEST['identity']
        base = images[kind] + '-base'
        docker('tag', original[container]['Image'], base)
        definition = context / 'Dockerfile'
        definition.write_text('FROM ' + base + '\nCOPY source/ /app/\n')
        # Build context contains only source; never database dumps/configuration.
        with (STAGE / ('build-' + kind + '.log')).open('wb') as output:
            docker('build', '--network=none', '--pull=false', '-f', str(definition),
                   '-t', images[kind], str(context), output=output)
        ids[kind] = json.loads(docker('image', 'inspect', images[kind]))[0]['Id']
        changed_by_kind[kind], files_by_kind[kind] = changed, sorted(selected)
    value = {'phase': 'built', 'images': images, 'image_ids': ids,
        'source_hashes': {path: hashlib.sha256(raw).hexdigest() for path, raw in files.items()},
        'changed': REQUEST['changed'], 'changed_by_kind': changed_by_kind, 'files_by_kind': files_by_kind}
    save(STAGE / 'candidate.json', value)
    return value


def tests():
    candidate = h['read_json'](STAGE / 'candidate.json')
    source = """import runpy,json
h=runpy.run_path('/run/p1/p1_activation_remote.py'); h['_configure']()
from django.db import connections
from django.test.runner import DiscoverRunner
connections['default'].settings_dict['TEST']['NAME']='test_regulai_latency_20261017'
class Recorded(DiscoverRunner):
 def suite_result(self,suite,result,**kwargs):
  print(json.dumps({'tests':result.testsRun,'failures':[str(t) for t,_ in result.failures],
    'errors':[str(t) for t,_ in result.errors],'skipped':[(str(t),reason) for t,reason in result.skipped]}))
  return super().suite_result(suite,result,**kwargs)
labels=['front.test_agent_message_batch','front.test_privacy_batch','front.test_privacy_batch_revocation','front.test_agent_queue_wakeup','front.test_agent_skills_runtime',
 'front.test_privacy_service','front.test_privacy_policy','front.test_privacy_boundaries',
 'front.test_privacy_http','front.test_privacy_agent','front.test_privacy_vertical',
 'front.test_privacy_migrations','front.test_agent_inference.AgentInferenceTests',
 'front.test_agent_professional.ProfessionalTests.test_three_entries_real_account_free_text_and_http_idempotency']
raise SystemExit(Recorded(interactive=False,verbosity=1).run_tests(labels))
"""
    result = subprocess.run(['docker', 'run', '--rm', '-i', *app_args(candidate['images']['web']),
        candidate['images']['web'], 'python', '-'], input=source.encode(), capture_output=True)
    log = STAGE / 'candidate-tests.log'
    log.write_bytes(result.stdout + result.stderr)
    log.chmod(0o600)
    summaries = [json.loads(line) for line in result.stdout.decode().splitlines() if line.startswith('{')]
    value = {'exit_code': result.returncode, 'summary': summaries[-1] if summaries else None,
        'image_ids': candidate['image_ids']}
    save(STAGE / 'tests.json', value)
    return value


def metadata(image):
    script = "import runpy,json\nh=runpy.run_path('/run/p1/p1_activation_remote.py')\nprint(json.dumps(h['inside_web']('metadata')))"
    return json.loads(docker('run', '--rm', '-i', *app_args(image), image, 'python', '-', data=script.encode()))


def catalog():
    variant = 'baseline' if REQUEST['action'] == 'catalog-baseline' else 'after'
    original = h['read_json'](STAGE / 'original.json')
    image = original[WEB]['Image'] if variant == 'baseline' else h['read_json'](STAGE / 'candidate.json')['images']['web']
    database = 'regulai_p1_latency_catalog_' + variant + '_' + uuid.uuid4().hex[:16]
    created = False
    script = """import runpy,json,time,collections
from unittest.mock import patch
runpy.run_path('/run/p1/p1_activation_remote.py')['_configure'](%r)
from django.db import connection,transaction
from front.models import AgentExecution
from front.agents import skill_context
run=AgentExecution.objects.filter(conversation_id=11).select_related('prompt','profile').latest('created_at')
rows=[]
for index in range(5):
 counts=collections.Counter()
 def measure(execute,sql,params,many,context):
  counts[sql.lstrip().split()[0].upper()]+=1
  return execute(sql,params,many,context)
 with transaction.atomic(), connection.execute_wrapper(measure), patch('socket.create_connection',side_effect=AssertionError('benchmark_network_denied')):
  start=time.perf_counter(); result=skill_context.bootstrap(run); seconds=time.perf_counter()-start
  transaction.set_rollback(True)
 rows.append({'seconds':seconds,'sql':dict(counts),'catalog_count':len(result['catalog'])})
print(json.dumps({'rows':rows,'live_data_modified':False,'provider_calls':0}))
""" % database
    try:
        # A random task-owned name plus createdb's absence check cannot overwrite a database.
        docker('exec', PG, 'createdb', '-U', 'regulai', database)
        created = True
        docker('exec', '-i', PG, 'pg_restore', '-U', 'regulai', '-d', database,
            '--exit-on-error', '--no-owner', '--no-acl', data=(STAGE / 'baseline.dump').read_bytes())
        result = json.loads(docker('run', '--rm', '-i', *app_args(image), image,
                                  'python', '-', data=script.encode()))
        result['database'] = database
        return result
    finally:
        if created:
            # The synchronous --rm container has closed its connections. Do not force
            # termination if an unexpected session appeared; retain data and fail safely.
            docker('exec', PG, 'dropdb', '--if-exists', '-U', 'regulai', '--', database)


def require_no_work(image):
    value = metadata(image)
    if any(value[key] for key in ('live', 'active_calls', 'pending_inferences', 'provider_occupied', 'sandbox_occupied')):
        raise RuntimeError('installation_busy')


def container(identifier):
    """Inspect by immutable ID/name; 404 alone means missing, not daemon failure."""
    client = h['DockerConnection']('localhost')
    try:
        client.request('GET', '/v1.47/containers/' + urllib.parse.quote(identifier, safe='') + '/json')
        response = client.getresponse()
        raw = response.read()
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError('container_inspection_failed')
        row = json.loads(raw)
        if (row.get('Config', {}).get('Labels') or {}).get('regulai.install') != 'v2':
            raise RuntimeError('container_ownership_mismatch')
        return row
    finally:
        client.close()


def health_http(timeout=15):
    url = 'http://127.0.0.1:31058/static/js/skills.js'
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200 and response.geturl() == url:
                    return {'status': 200, 'path': '/static/js/skills.js'}
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('web_http_health_failed')
        time.sleep(.25)


def create_candidate(name, original, image):
    if original['HostConfig'].get('AutoRemove'):
        raise RuntimeError('original_container_must_survive_stop')
    networks = original.get('NetworkSettings', {}).get('Networks', {})
    if len(networks) != 1 or original['HostConfig']['NetworkMode'].startswith('container:'):
        raise RuntimeError('unsupported_original_network_topology')
    payload = copy.deepcopy(original['Config'])
    payload.pop('Hostname', None)
    payload.pop('Domainname', None)
    payload.update(Image=image, HostConfig=copy.deepcopy(original['HostConfig']))
    payload['Labels'] = {**(payload.get('Labels') or {}), 'regulai.latency_patch': REQUEST['identity']}
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


def restore_names(targets, known_ids, label):
    """Idempotent repair by immutable IDs, including half-finished renames."""
    for name in (WEB, WORKER):
        target = container(targets[name])
        if target is None:
            raise RuntimeError('retained_container_missing')
        current = container(name)
        if current is not None and current['Id'] != targets[name]:
            if current['Id'] not in known_ids:
                raise RuntimeError('unexpected_container_at_service_name')
            docker('stop', current['Id'])
            parked = name + '-' + label + '-' + current['Id'][:12]
            collision = container(parked)
            if collision is not None and collision['Id'] != current['Id']:
                raise RuntimeError('retained_name_collision')
            docker('rename', current['Id'], parked)
        target = container(targets[name])
        if target['Name'].lstrip('/') != name:
            docker('rename', targets[name], name)
    # Web becomes ready before either old or new worker can issue a claim.
    docker('start', targets[WEB])
    health_http()
    docker('start', targets[WORKER])


def verify():
    candidate = h['read_json'](STAGE / 'candidate.json')
    original = h['read_json'](STAGE / 'original.json')
    if h['private_configuration_digest']() != h['read_json'](STAGE / 'configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    rows = {name: inspect(name) for name in (WEB, WORKER)}
    for kind, name in (('web', WEB), ('worker', WORKER)):
        row = rows[name]
        if row['Image'] != candidate['image_ids'][kind] or not row['State']['Running'] or row['RestartCount']:
            raise RuntimeError('updated_service_unavailable')
        if row['HostConfig'] != original[name]['HostConfig']:
            raise RuntimeError('service_host_configuration_changed')
        if set(row.get('NetworkSettings', {}).get('Networks', {})) != set(original[name].get('NetworkSettings', {}).get('Networks', {})):
            raise RuntimeError('service_network_membership_changed')
        changed = candidate.get('changed_by_kind', {}).get(kind, candidate['changed'])
        expected = {path: candidate['source_hashes'][path] for path in changed}
        script = "import hashlib\nfrom pathlib import Path\nexpected=%r\nassert {p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in expected}==expected\n" % expected
        docker('exec', '-i', name, 'python', '-', data=script.encode())
    health = health_http()
    h['require_idle'](current=True)
    mounted_before = h['read_json'](STAGE / 'mounts-before-switch.json')
    mounted_after = mounted_files(original)
    equal_readonly_mounts(mounted_before, mounted_after)
    save(STAGE / 'mounts-after-switch.json', mounted_after)
    return {'phase': 'verified', 'services': {name: {'running': row['State']['Running'],
        'restarts': row['RestartCount'], 'image_id': row['Image']} for name, row in rows.items()},
        'private_configuration_unchanged': True, 'source_hashes_verified': True,
        'mounted_readonly_files_unchanged': True,
        'checkpoint_files_changed_since_switch': checkpoint_changed_count(mounted_before, mounted_after),
        'network_and_host_configuration_unchanged': True, 'http_health': health,
        'schema_changes': 0, 'provider_generation_calls': 0}


def apply():
    candidate = h['read_json'](STAGE / 'candidate.json')
    tested = h['read_json'](STAGE / 'tests.json')
    if tested['exit_code'] or tested.get('image_ids') != candidate['image_ids']:
        raise RuntimeError('current_candidate_tests_required')
    original = h['read_json'](STAGE / 'original.json')
    if h['original_identity']({name: inspect(name) for name in original}) != h['original_identity'](original):
        raise RuntimeError('original_services_changed')
    if h['private_configuration_digest']() != h['read_json'](STAGE / 'configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    for kind, image in candidate['images'].items():
        if json.loads(docker('image', 'inspect', image))[0]['Id'] != candidate['image_ids'][kind]:
            raise RuntimeError('candidate_image_changed')
    for name in (WEB, WORKER):
        if original[name]['HostConfig'].get('AutoRemove'):
            raise RuntimeError('original_container_must_survive_stop')
    h['require_idle'](current=True)
    replacements = {name: name + '-candidate-' + REQUEST['identity'] for name in (WEB, WORKER)}
    retained = {name: name + '-before-' + REQUEST['identity'] for name in (WEB, WORKER)}
    original_ids = {name: original[name]['Id'] for name in (WEB, WORKER)}
    replacement_ids = {}
    for name in (*replacements.values(), *retained.values()):
        if container(name) is not None:
            raise RuntimeError('switch_container_name_already_exists')
    try:
        for kind, name in (('web', WEB), ('worker', WORKER)):
            replacement_ids[name] = create_candidate(replacements[name], original[name], candidate['image_ids'][kind])
        save(STAGE / 'switch.json', {'original_ids': original_ids, 'replacement_ids': replacement_ids,
                                    'retained': retained})
        # Hash real mounted secrets/runtime, not only historical helper paths.
        mounted_before_stop = mounted_files(original)
        # Stop is inside the compensating block: even a partial stop is repaired.
        docker('stop', WORKER, WEB)
        require_no_work(original[WEB]['Image'])
        mounted_before = mounted_files(original)
        equal_readonly_mounts(mounted_before_stop, mounted_before)
        save(STAGE / 'mounts-before-switch.json', mounted_before)
        label = 'before-switch-' + str(time.time_ns())
        checkpoint_backup = backup_checkpoints(mounted_before, label)
        backup = h['snapshot_backup'](STAGE, label)
        before = fingerprint(original[WEB]['Image'])
        save(STAGE / 'before-switch.json', before)
        for name in (WEB, WORKER):
            docker('rename', original_ids[name], retained[name])
            docker('rename', replacement_ids[name], name)
        # Copies/renames must leave configuration and checkpoint bytes untouched.
        if mounted_files(original) != mounted_before:
            raise RuntimeError('mounted_files_changed_before_candidate_start')
        docker('start', replacement_ids[WEB])
        health_http()
        h['require_idle'](current=True)
        docker('start', replacement_ids[WORKER])
        time.sleep(10)
        result = verify()
        h['equal_fingerprints'](before, fingerprint(candidate['images']['web'], before))
        result.update(phase='applied', existing_data_unchanged=True, retained_containers=retained,
            backup=backup, checkpoint_backup=checkpoint_backup,
            checkpoint_files_unchanged_before_start=True)
        save(STAGE / 'applied.json', result)
        return result
    except Exception:
        # Restore by IDs, not a list appended after both renames. This covers a
        # failure between original->retained and candidate->canonical as well.
        restore_names(original_ids, set(original_ids.values()) | set(replacement_ids.values()),
                      'failed-' + REQUEST['identity'])
        raise


def rollback():
    candidate = h['read_json'](STAGE / 'candidate.json')
    original = h['read_json'](STAGE / 'original.json')
    switch = h['read_json'](STAGE / 'switch.json')
    if h['private_configuration_digest']() != h['read_json'](STAGE / 'configuration.json')['digest']:
        raise RuntimeError('private_configuration_changed')
    original_ids = {name: original[name]['Id'] for name in (WEB, WORKER)}
    known_ids = set(original_ids.values()) | set(switch['replacement_ids'].values())
    # Rollback must also work when the candidate is stopped or restarting.
    # Check identity, ownership and durable work, never candidate health.
    for name, identifier in original_ids.items():
        row = container(identifier)
        if row is None or row['Image'] != original[name]['Image']:
            raise RuntimeError('retained_original_changed')
    previous = {}
    for name in (WEB, WORKER):
        row = container(name)
        if row is not None and row['Id'] not in known_ids:
            raise RuntimeError('unexpected_service_identity')
        previous[name] = row['Id'] if row else original_ids[name]
    require_no_work(original[WEB]['Image'])
    mounted_before_stop = mounted_files(original)
    try:
        for name in (WORKER, WEB):
            row = container(name)
            if row is not None:
                docker('stop', row['Id'])
        require_no_work(original[WEB]['Image'])
        mounted_before = mounted_files(original)
        equal_readonly_mounts(mounted_before_stop, mounted_before)
        checkpoint_backup = backup_checkpoints(mounted_before, 'before-rollback-' + str(time.time_ns()))
        before = fingerprint(original[WEB]['Image'])
        if mounted_files(original) != mounted_before:
            raise RuntimeError('mounted_files_changed_before_original_start')
        restore_names(original_ids, known_ids, 'rolled-back-' + REQUEST['identity'])
        time.sleep(10)
        h['require_idle'](current=True)
        h['equal_fingerprints'](before, fingerprint(original[WEB]['Image'], before))
        if any(inspect(name)['Id'] != identifier for name, identifier in original_ids.items()):
            raise RuntimeError('rollback_identity_mismatch')
        mounted_after = mounted_files(original)
        equal_readonly_mounts(mounted_before, mounted_after)
        save(STAGE / 'mounts-after-rollback.json', mounted_after)
        return {'phase': 'rolled_back', 'data_and_keys_unchanged': True, 'database_restored': False,
                'http_health': health_http(), 'original_container_ids_verified': True,
                'mounted_readonly_files_unchanged': True, 'checkpoint_files_unchanged_before_start': True,
                'checkpoint_files_changed_after_start': checkpoint_changed_count(mounted_before, mounted_after),
                'checkpoint_backup': checkpoint_backup}
    except Exception:
        # If a Docker operation fails mid-rollback, restore the prior names by
        # immutable ID too; no database restore can overwrite intervening data.
        restore_names(previous, known_ids, 'rollback-failed-' + REQUEST['identity'])
        raise


try:
    print(json.dumps({'init': init, 'bench-baseline': benchmark, 'bench-after': benchmark,
        'build': build, 'tests': tests, 'apply': apply, 'verify': verify, 'rollback': rollback,
        'cleanup-benchmarks': cleanup_benchmarks,
        'catalog-baseline': catalog, 'catalog-after': catalog}[REQUEST['action']]()))
except Exception as error:
    if STAGE.exists():
        (STAGE / 'error.log').write_text(traceback.format_exc())
        (STAGE / 'error.log').chmod(0o600)
    print(json.dumps({'error': type(error).__name__, 'code': str(error) if isinstance(error, RuntimeError) else 'inspect_private_log'}))
    raise SystemExit(1)
