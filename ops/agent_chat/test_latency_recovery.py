"""Offline fault injection for the local latency installer; never touches Docker."""
import ast
import hashlib
from copy import deepcopy
import json
import os
import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]


class InstallerRecoveryTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / 'ops/agent_chat/latency_remote.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        # Deliberately load only definitions/imports, never REQUEST dispatch.
        definitions = ast.Module(body=[node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))], type_ignores=[])
        self.ns = {}
        exec(compile(definitions, str(source), 'exec'), self.ns)
        self.rows = {}
        for name in ('web', 'worker', 'pg'):
            self.rows['original-' + name] = self.row('original-' + name, name, 'image-' + name)
        self.original = {name: deepcopy(self.rows['original-' + name]) for name in ('web', 'worker', 'pg')}
        self.candidate = {'image_ids': {'web': 'new-web', 'worker': 'new-worker'},
                          'images': {'web': 'tag-web', 'worker': 'tag-worker'}}
        self.records = {'original.json': self.original, 'candidate.json': self.candidate,
                        'tests.json': {'exit_code': 0, 'image_ids': self.candidate['image_ids']},
                        'configuration.json': {'digest': 'unchanged'}}
        self.calls = []
        self.failure = None
        self.ns.update(WEB='web', WORKER='worker', PG='pg', STAGE=Path('/synthetic'),
                       REQUEST={'identity': 'synthetic'}, docker=self.docker,
                       container=self.lookup, inspect=lambda name: deepcopy(self.lookup(name)),
                       save=lambda path, value: self.records.__setitem__(path.name, deepcopy(value)),
                       create_candidate=self.create, fingerprint=lambda *args: {'unchanged': True},
                       require_no_work=Mock(), health_http=Mock(return_value={'status': 200}),
                       verify=Mock(return_value={'phase': 'verified'}),
                       mounted_files=Mock(return_value={'readonly': [], 'state': []}),
                       backup_checkpoints=Mock(return_value={'directory': '/private/synthetic', 'files': 0}),
                       time=SimpleNamespace(sleep=lambda _: None, time_ns=lambda: 1))
        self.ns['h'] = {'read_json': lambda path: deepcopy(self.records[path.name]),
            'private_configuration_digest': lambda: 'unchanged',
            'original_identity': lambda rows: {name: row['Id'] for name, row in rows.items()},
            'require_idle': Mock(), 'snapshot_backup': lambda *args: {'file': 'synthetic.dump'},
            'equal_fingerprints': lambda before, after: self.assertEqual(before, after)}

    @staticmethod
    def row(identifier, name, image):
        return {'Id': identifier, 'Name': '/' + name, 'Image': image,
                'Config': {'Labels': {'regulai.install': 'v2'}},
                'HostConfig': {'AutoRemove': False},
                'State': {'Running': True}, 'RestartCount': 0}

    def lookup(self, identifier):
        return next((deepcopy(row) for row in self.rows.values()
                     if row['Id'] == identifier or row['Name'].lstrip('/') == identifier), None)

    def create(self, name, original, image):
        identifier = 'candidate-' + original['Name'].lstrip('/')
        self.rows[identifier] = self.row(identifier, name, image)
        self.rows[identifier]['State']['Running'] = False
        return identifier

    def docker(self, action, *args, **kwargs):
        self.calls.append((action, args))
        if action == 'image':
            return json.dumps([{'Id': {'tag-web': 'new-web', 'tag-worker': 'new-worker'}[args[1]]}]).encode()
        if action in ('stop', 'start'):
            for identifier in args:
                row = self.lookup(identifier)
                if row is None:
                    raise RuntimeError('missing_container')
                self.rows[row['Id']]['State']['Running'] = action == 'start'
                self.fail_if(action, identifier)
            return b''
        if action == 'rename':
            identifier, new_name = args
            self.fail_if(action, identifier, new_name)
            if self.lookup(new_name) is not None:
                raise RuntimeError('name_collision')
            row = self.lookup(identifier)
            if row is None:
                raise RuntimeError('missing_container')
            self.rows[row['Id']]['Name'] = '/' + new_name
            return b''
        raise AssertionError('Unexpected Docker operation: ' + action)

    def fail_if(self, *operation):
        if self.failure == operation:
            self.failure = None
            raise RuntimeError('injected_failure')

    def assert_original_running(self):
        for name in ('web', 'worker'):
            row = self.lookup(name)
            self.assertEqual(row['Id'], 'original-' + name)
            self.assertTrue(row['State']['Running'])

    def test_apply_recovers_after_only_worker_was_stopped(self):
        self.failure = ('stop', 'worker')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assert_original_running()

    def test_apply_recovers_between_original_and_candidate_rename(self):
        self.failure = ('rename', 'candidate-web', 'web')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assert_original_running()
        self.assertIsNotNone(self.lookup('candidate-web'))

    def test_apply_recovers_when_worker_start_fails_after_web_started(self):
        self.failure = ('start', 'candidate-worker')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assert_original_running()

    def test_rollback_accepts_a_stopped_restarting_candidate(self):
        self.ns['apply']()
        self.rows['candidate-worker']['State']['Running'] = False
        self.rows['candidate-worker']['RestartCount'] = 5
        self.ns['verify'] = Mock(side_effect=AssertionError('Health cannot gate rollback'))
        self.assertEqual(self.ns['rollback']()['phase'], 'rolled_back')
        self.ns['verify'].assert_not_called()
        self.assert_original_running()

    def test_rollback_recovers_previous_names_when_original_rename_fails(self):
        self.ns['apply']()
        self.failure = ('rename', 'original-web', 'web')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['rollback']()
        for name in ('web', 'worker'):
            self.assertEqual(self.lookup(name)['Id'], 'candidate-' + name)
            self.assertTrue(self.lookup(name)['State']['Running'])
            self.assertIsNotNone(self.lookup('original-' + name))

    def test_recovery_never_stops_an_unexpected_service(self):
        self.rows['original-web']['Name'] = '/retained-web'
        self.rows['unrelated'] = self.row('unrelated', 'web', 'other')
        with self.assertRaisesRegex(RuntimeError, 'unexpected_container_at_service_name'):
            self.ns['restore_names']({'web': 'original-web', 'worker': 'original-worker'},
                                     {'original-web', 'original-worker'}, 'test')
        self.assertTrue(self.rows['unrelated']['State']['Running'])
        self.assertFalse(self.calls)


    def test_apply_rejects_readonly_change_during_stop_and_restores_originals(self):
        self.ns['mounted_files'].side_effect = [
            {'readonly': ['before'], 'state': []},
            {'readonly': ['changed'], 'state': []}]
        with self.assertRaisesRegex(RuntimeError, 'mounted_readonly_configuration_changed'):
            self.ns['apply']()
        self.ns['backup_checkpoints'].assert_not_called()
        self.assert_original_running()

    def test_apply_backs_up_state_with_both_services_stopped(self):
        def backup(snapshot, label):
            self.assertFalse(self.rows['original-web']['State']['Running'])
            self.assertFalse(self.rows['original-worker']['State']['Running'])
            self.assertFalse(self.rows['candidate-web']['State']['Running'])
            self.assertFalse(self.rows['candidate-worker']['State']['Running'])
            return {'directory': '/private/synthetic', 'files': 1}
        self.ns['backup_checkpoints'].side_effect = backup
        result = self.ns['apply']()
        self.ns['backup_checkpoints'].assert_called_once()
        self.assertEqual(result['checkpoint_backup']['files'], 1)
        self.assertTrue(result['checkpoint_files_unchanged_before_start'])


class MountedPreservationTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / 'ops/agent_chat/latency_remote.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        definitions = ast.Module(body=[node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))], type_ignores=[])
        self.ns = {}
        exec(compile(definitions, str(source), 'exec'), self.ns)
        self.temporary = tempfile.TemporaryDirectory(prefix='regulai-mount-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.config, self.state, self.stage = [self.root / name for name in ('config', 'state', 'stage')]
        for path in (self.config, self.state, self.stage):
            path.mkdir()
        (self.config / 'token').write_bytes(b'synthetic-never-print-this')
        (self.state / 'checkpoints.sqlite').write_bytes(b'synthetic-checkpoint')
        self.original = {
            'web': {'Mounts': [{'Type': 'bind', 'RW': False, 'Source': str(self.config), 'Destination': '/run/private'}]},
            'worker': {'Mounts': [{'Type': 'bind', 'RW': True, 'Source': str(self.state), 'Destination': '/state'}]}}
        self.saved = {}
        self.ns.update(WORKER='worker', STAGE=self.stage,
            save=lambda path, value: self.saved.__setitem__(path, value))

    def snapshot(self):
        return self.ns['mounted_files'](self.original, self.root)

    def test_changed_actual_mounted_key_is_detected_without_exposing_bytes(self):
        before = self.snapshot()
        self.assertNotIn('synthetic-never-print-this', json.dumps(before))
        (self.config / 'token').write_bytes(b'changed-synthetic-key')
        after = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'mounted_readonly_configuration_changed'):
            self.ns['equal_readonly_mounts'](before, after)
        self.assertEqual(self.ns['checkpoint_changed_count'](before, after), 0)

    def test_checkpoint_backup_survives_startup_changes_without_overwrite(self):
        before = self.snapshot()
        result = self.ns['backup_checkpoints'](before, 'before-switch-1')
        backup = Path(result['directory']) / '0' / 'checkpoints.sqlite'
        self.assertEqual(backup.read_bytes(), b'synthetic-checkpoint')
        if os.name != 'nt':
            self.assertEqual(Path(result['directory']).stat().st_mode & 0o777, 0o700)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        (self.state / 'checkpoints.sqlite').write_bytes(b'pruned-synthetic-checkpoint')
        after = self.snapshot()
        self.ns['equal_readonly_mounts'](before, after)
        self.assertEqual(self.ns['checkpoint_changed_count'](before, after), 1)
        self.assertEqual(backup.read_bytes(), b'synthetic-checkpoint')
        with self.assertRaises(FileExistsError):
            self.ns['backup_checkpoints'](after, 'before-switch-1')
        self.assertEqual((self.state / 'checkpoints.sqlite').read_bytes(), b'pruned-synthetic-checkpoint')

    def test_missing_checkpoint_mount_is_rejected(self):
        self.original['worker']['Mounts'].clear()
        with self.assertRaisesRegex(RuntimeError, 'required_preserved_mount_missing'):
            self.snapshot()

    def test_mount_outside_installation_root_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='regulai-unrelated-') as other:
            self.original['web']['Mounts'][0]['Source'] = str(Path(other).resolve())
            with self.assertRaisesRegex(RuntimeError, 'preserved_mount_path_denied'):
                self.snapshot()

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX'), 'Unix socket support required')
    def test_socket_is_never_read_or_copied(self):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.state / 'task.sock'))
            snapshot = self.snapshot()
            self.assertNotIn('task.sock', snapshot['state'][0]['files'])
            result = self.ns['backup_checkpoints'](snapshot, 'before-switch-2')
            self.assertFalse((Path(result['directory']) / '0' / 'task.sock').exists())
        finally:
            listener.close()


class BenchmarkCleanupTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / 'ops/agent_chat/latency_remote.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        definitions = ast.Module(body=[node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))], type_ignores=[])
        self.ns = {}
        exec(compile(definitions, str(source), 'exec'), self.ns)
        self.temporary = tempfile.TemporaryDirectory(prefix='regulai-cleanup-test-')
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name).resolve()
        (self.stage / 'bench-after-10').mkdir()
        self.original = {'web': {'Image': 'original-web', 'Mounts': []},
                         'worker': {'Image': 'original-worker', 'Mounts': []}}
        self.candidate = {'image_ids': {'web': 'new-web', 'worker': 'new-worker'},
                          'images': {'web': 'task-web-tag', 'worker': 'task-worker-tag'}}
        self.rows = {}
        for role in ('server', 'worker'):
            name = f'latency-{role}-after-10'
            folder = self.stage / 'bench-after-10'
            mount = {'Type': 'bind', 'RW': False, 'Source': str(folder), 'Destination': '/bench'}
            row = {'Id': 'id-' + role, 'Name': '/' + name, 'Image': 'new-web' if role == 'server' else 'new-worker',
                   'State': {'Running': False}, 'Mounts': [mount],
                   'Config': {'Cmd': ['python', f'/bench/latency_benchmark_{role}.py'],
                              'Env': ['BENCH_DATABASE=regulai_p1_latency_after_10']}}
            if role == 'server':
                row['Mounts'].append({'Type': 'bind', 'RW': True, 'Source': str(folder / 'results'),
                                      'Destination': '/results'})
            self.rows[row['Id']] = row
        self.calls, self.sessions, self.saved = [], b'', []
        self.database = 'regulai_p1_latency_after_10'
        self.records = {'applied.json': {'phase': 'applied'}, 'original.json': self.original,
                        'candidate.json': self.candidate}
        self.ns.update(STAGE=self.stage, WEB='web', WORKER='worker', PG='pg',
            REQUEST={'identity': 'latency-20261017-a1'},
            verify=Mock(), benchmark_container=self.lookup, docker=self.docker,
            time=SimpleNamespace(time_ns=lambda: 1),
            save=lambda path, value: self.saved.append(deepcopy(value)),
            h={'read_json': lambda path: deepcopy(self.records[path.name])})

    def lookup(self, identifier):
        return next((deepcopy(row) for row in self.rows.values()
                     if row['Id'] == identifier or row['Name'].lstrip('/') == identifier), None)

    def docker(self, action, *args, **kwargs):
        self.calls.append((action, args))
        if action == 'exec' and args[1] == 'psql':
            return self.sessions if 'pg_stat_activity' in args[-1] else (self.database + '\n').encode()
        if action == 'rm':
            self.rows.pop(args[0])
            return b''
        if action == 'exec' and args[1] == 'dropdb':
            return b''
        raise AssertionError('Unexpected operation: ' + action)

    def test_cleanup_removes_only_exact_stopped_fixtures_without_volumes(self):
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['phase'], 'benchmark_cleanup_complete')
        self.assertEqual(result['databases_removed'], ['regulai_p1_latency_after_10'])
        self.assertEqual([call for call in self.calls if call[0] == 'rm'],
                         [('rm', ('id-worker',)), ('rm', ('id-server',))])
        self.assertIn(('exec', ('pg', 'dropdb', '--if-exists', '-U', 'regulai', '--',
                               'regulai_p1_latency_after_10')), self.calls)
        self.assertTrue((self.stage / 'bench-after-10').exists())

    def test_running_fixture_is_retained_without_database_queries_or_removal(self):
        self.rows['id-worker']['State']['Running'] = True
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['phase'], 'benchmark_cleanup_partial')
        self.assertEqual(result['pending'][0]['reason'], 'benchmark_still_running')
        self.assertFalse(self.calls)

    def test_unexpected_mount_keeps_both_containers_and_database(self):
        self.rows['id-worker']['Mounts'][0]['Source'] = '/unrelated'
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['pending'][0]['reason'], 'benchmark_mount_mismatch')
        self.assertFalse(self.calls)
        self.assertEqual(len(self.rows), 2)

    def test_database_with_session_is_never_removed(self):
        self.sessions = b'regulai_p1_latency_after_10\n'
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['pending'][0]['reason'], 'benchmark_database_has_sessions')
        self.assertEqual(len(self.rows), 2)
        self.assertFalse(any(action == 'rm' or (action == 'exec' and args[1] == 'dropdb')
                             for action, args in self.calls))

    def test_unknown_image_is_retained(self):
        self.rows['id-worker']['Image'] = 'unrecognized-image'
        self.rows['id-worker']['Config']['Image'] = 'unrelated-tag'
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['pending'][0]['reason'], 'benchmark_image_unknown')
        self.assertFalse(self.calls)

    def test_legacy_fixture_without_results_mount_is_accepted(self):
        self.rows['id-server']['Mounts'].pop()
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['phase'], 'benchmark_cleanup_complete')


    def test_future_authorized_repeat_is_cleaned_with_same_strict_checks(self):
        (self.stage / 'bench-after-10').rename(self.stage / 'bench-after-13')
        self.database = 'regulai_p1_latency_after_13'
        for row in self.rows.values():
            row['Name'] = row['Name'].replace('after-10', 'after-13')
            row['Config']['Env'] = ['BENCH_DATABASE=' + self.database]
            for mount in row['Mounts']:
                mount['Source'] = mount['Source'].replace('after-10', 'after-13')
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['phase'], 'benchmark_cleanup_complete')
        self.assertEqual(result['databases_removed'], [self.database])
        self.assertEqual(len(result['containers_removed']), 2)

    def test_second_series_cannot_clean_first_series_containers(self):
        self.ns['REQUEST']['identity'] = 'latency-20261017-a2'
        self.ns['benchmark_container'] = Mock(return_value=None)
        self.database = 'regulai_p1_latency_v2_after_10'
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['databases_removed'], [self.database])
        self.assertEqual(len(self.rows), 2)
        self.assertFalse(any(action == 'rm' for action, _ in self.calls))
        self.assertEqual(self.ns['benchmark_names']('after', 10), (
            self.database, 'latency-v2-server-after-10', 'latency-v2-worker-after-10'))

    def historical_fixture(self):
        self.database = 'regulai_p1_latency_v2_after_10'
        ids = {'web': 'sha256:' + 'a' * 64, 'worker': 'sha256:' + 'b' * 64}
        manifest = {'phase': 'built', 'images': deepcopy(self.candidate['images']), 'image_ids': ids}
        self.ns['REQUEST'].update(identity='latency-20261017-a2', action='cleanup-benchmarks',
            historical_builds=[{'artifact': 'build-0.json', 'manifest': manifest}])
        for role, row in zip(('server', 'worker'), (self.rows['id-server'], self.rows['id-worker'])):
            kind = 'web' if role == 'server' else 'worker'
            row['Name'] = f'/latency-v2-{role}-after-10'
            row['Config']['Env'] = ['BENCH_DATABASE=' + self.database]
            row['Config']['Image'] = self.candidate['images'][kind]
            row['Image'] = ids[kind]
        return manifest

    def test_recorded_historical_images_need_no_missing_docker_image_metadata(self):
        self.historical_fixture()
        # docker() rejects any image inspection; the content-addressed IDs from
        # the recorded builds are sufficient even after Docker forgets metadata.
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['phase'], 'benchmark_cleanup_complete')
        self.assertEqual(result['databases_removed'], [self.database])
        self.assertEqual(len(result['containers_removed']), 2)
        self.assertFalse(any(action == 'image' for action, _ in self.calls))

    def test_historical_provenance_is_scoped_to_second_series_cleanup(self):
        manifest = self.historical_fixture()
        for key, value in (('identity', 'latency-20261017-a1'), ('action', 'verify')):
            with self.subTest(key=key):
                previous = self.ns['REQUEST'][key]
                self.ns['REQUEST'][key] = value
                self.assertFalse(self.ns['historical_benchmark_image'](
                    manifest['image_ids']['worker'], 'worker', self.candidate))
                self.ns['REQUEST'][key] = previous
        self.assertFalse(self.calls)

    def test_historical_image_requires_exact_role_and_digest(self):
        manifest = self.historical_fixture()
        for image in (manifest['image_ids']['web'], 'sha256:' + 'c' * 64):
            with self.subTest(image=image):
                self.assertFalse(self.ns['historical_benchmark_image'](image, 'worker', self.candidate))
        self.assertFalse(self.calls)

    def test_unknown_historical_image_with_missing_metadata_is_retained(self):
        self.historical_fixture()
        self.rows['id-worker']['Image'] = 'sha256:' + 'c' * 64
        def missing_metadata(action, *args, **kwargs):
            if action == 'image':
                self.calls.append((action, args))
                raise RuntimeError('synthetic_missing_image')
            return self.docker(action, *args, **kwargs)
        self.ns['docker'] = missing_metadata
        result = self.ns['cleanup_benchmarks']()
        self.assertEqual(result['pending'][0]['reason'], 'synthetic_missing_image')
        self.assertEqual(len(self.rows), 2)
        self.assertEqual([action for action, _ in self.calls], ['image'])

    def test_historical_images_do_not_bypass_tag_state_mount_or_database_checks(self):
        self.historical_fixture()
        checks = [
            ('worker', lambda row: row['Config'].update(Image='unrelated-tag'), 'benchmark_image_unknown'),
            ('worker', lambda row: row['State'].update(Running=True), 'benchmark_still_running'),
            ('worker', lambda row: row['Mounts'][0].update(Source='/unrelated'), 'benchmark_mount_mismatch'),
            ('server', lambda row: row['Config'].update(Env=['BENCH_DATABASE=live']), 'benchmark_database_mismatch'),
            ('worker', lambda row: row['Config'].update(Cmd=['python', 'other.py']), 'benchmark_command_mismatch'),
            ('worker', lambda row: row.update(Name='/unrelated'), 'benchmark_name_mismatch')]
        for role, mutate, reason in checks:
            with self.subTest(reason=reason):
                row = deepcopy(self.rows['id-' + role])
                mutate(row)
                with self.assertRaisesRegex(RuntimeError, reason):
                    self.ns['check_benchmark_container'](row, 'after', 10, role, self.original, self.candidate)
        self.assertFalse(self.calls)

    def test_malformed_or_foreign_build_manifest_is_rejected(self):
        manifest = self.historical_fixture()
        record = deepcopy(self.ns['REQUEST']['historical_builds'][0])
        mutations = [lambda value: value.update(artifact='build-999.json'),
            lambda value: value.update(artifact=[]),
            lambda value: value['manifest'].update(phase='other'),
            lambda value: value['manifest']['images'].update(worker='foreign-series-tag'),
            lambda value: value['manifest']['image_ids'].update(worker='sha256:short')]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                altered = deepcopy(record)
                mutate(altered)
                self.ns['REQUEST']['historical_builds'] = [altered]
                with self.assertRaisesRegex(RuntimeError, 'benchmark_history_invalid'):
                    self.ns['historical_benchmark_image'](manifest['image_ids']['worker'], 'worker', self.candidate)
        self.ns['REQUEST']['historical_builds'] = [record, record]
        with self.assertRaisesRegex(RuntimeError, 'benchmark_history_invalid'):
            self.ns['historical_benchmark_image'](manifest['image_ids']['worker'], 'worker', self.candidate)
        self.assertFalse(self.calls)


class CatalogIsolationTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / 'ops/agent_chat/latency_remote.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        definitions = ast.Module(body=[node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))], type_ignores=[])
        self.ns = {}
        exec(compile(definitions, str(source), 'exec'), self.ns)
        self.temporary = tempfile.TemporaryDirectory(prefix='regulai-catalog-test-')
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name).resolve()
        (self.stage / 'baseline.dump').write_bytes(b'synthetic-dump')
        self.calls = []
        self.failure = None
        records = {'original.json': {'web': {'Image': 'original-image'}},
                   'candidate.json': {'images': {'web': 'candidate-tag'}, 'image_ids': {'web': 'candidate-image'}}}
        self.ns.update(STAGE=self.stage, WEB='web', PG='pg', REQUEST={'action': 'catalog-after'},
            h={'read_json': lambda path: records[path.name]}, docker=self.docker,
            uuid=SimpleNamespace(uuid4=lambda: SimpleNamespace(hex='a'*32)),
            app_args=lambda image: [])
        self.database = 'regulai_p1_latency_catalog_after_' + 'a'*16

    def docker(self, action, *args, **kwargs):
        self.calls.append((action, args))
        operation = args[1] if action == 'exec' and args[0] != '-i' else action
        if self.failure == operation:
            raise RuntimeError('injected_failure')
        if action == 'run':
            script = kwargs['data'].decode()
            self.assertIn(repr(self.database), script)
            self.assertNotIn('regulai_p1_latency_baseline_3', script)
            return json.dumps({'rows': [{'seconds': 1, 'sql': {'SELECT': 1}}]*5,
                               'live_data_modified': False, 'provider_calls': 0}).encode()
        return b''

    def test_successful_catalog_removes_its_unique_clone_and_preserves_samples(self):
        result = self.ns['catalog']()
        self.assertEqual(result['database'], self.database)
        self.assertEqual(len(result['rows']), 5)
        self.assertEqual(result['image_id'], 'candidate-image')
        self.assertEqual(result['dataset_sha256'], hashlib.sha256(b'synthetic-dump').hexdigest())
        self.assertEqual(len(result['catalog_harness_sha256']), 64)
        self.assertEqual(self.calls[0], ('exec', ('pg', 'createdb', '-U', 'regulai', self.database)))
        self.assertEqual(self.calls[-1], ('exec', ('pg', 'dropdb', '--if-exists', '-U', 'regulai', '--', self.database)))

    def test_failed_measurement_still_removes_owned_clone_without_force(self):
        self.failure = 'run'
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['catalog']()
        self.assertEqual(self.calls[-1], ('exec', ('pg', 'dropdb', '--if-exists', '-U', 'regulai', '--', self.database)))

    def test_failed_creation_never_drops_an_existing_database(self):
        self.failure = 'createdb'
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['catalog']()
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    unittest.main()
