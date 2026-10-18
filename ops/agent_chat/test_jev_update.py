"""Offline fault checks for the current-image-bound Jev installer. No Docker/network."""
import ast
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]


class JevUpdateTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'ops/agent_chat/jev_remote.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        definitions = ast.Module(body=[node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef))], type_ignores=[])
        self.ns = {}
        exec(compile(definitions, str(path), 'exec'), self.ns)
        self.temporary = tempfile.TemporaryDirectory(prefix='jev-update-offline-')
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name).resolve()
        self.rows = {name + '-old': self.row(name + '-old', name, 'image-' + name)
                     for name in ('web', 'worker', 'pg')}
        self.original = {name: deepcopy(self.rows[name + '-old']) for name in ('web', 'worker', 'pg')}
        self.candidate = {'image_id': 'image-new', 'source_hashes': {'service.py': 'newhash'},
                          'test_hashes': {'test.py': 'testhash'}}
        self.records = {'original.json': self.original, 'candidate.json': self.candidate,
                        'tests.json': {'exit_code': 0, 'image_id': 'image-new', 'isolated_resources_removed': True,
                                       'test_hashes': {'test.py': 'testhash'},
                                       'summary': {'tests': 1, 'failures': [], 'errors': []}},
                        'mounts-init.json': {'readonly': [], 'state': []}}
        self.calls = []
        self.failure = None
        self.ns.update(WEB='web', WORKER='worker', PG='pg', SERVICE='service.py', PRESERVED=(),
            STAGE=self.stage, REQUEST={'identity': 'synthetic', 'target_sha256': 'newhash'},
            docker=self.docker, inspect=lambda name: self.lookup(name), container=self.lookup,
            require_original=lambda: deepcopy(self.original), mounted_files=Mock(return_value={'readonly': [], 'state': []}),
            equal_readonly_mounts=lambda before, after: self.assertEqual(before['readonly'], after['readonly']),
            backup_checkpoints=Mock(return_value={'files': 0}), fingerprint=Mock(return_value={'unchanged': True}),
            require_no_work=Mock(), health_http=Mock(side_effect=lambda: self.calls.append(('health', ()))), verify=Mock(return_value={'phase': 'verified'}),
            create_web=self.create, time=SimpleNamespace(time_ns=lambda: 1),
            save=lambda path, value: self.records.__setitem__(path.name, deepcopy(value)))
        self.ns['h'] = {'original_identity': lambda rows: {name: {key: row[key] for key in
                ('Id', 'Image', 'Config', 'HostConfig')} for name, row in rows.items()}, 'read_json': lambda path: deepcopy(self.records[path.name]),
            'require_idle': Mock(), 'snapshot_backup': Mock(return_value={'file': 'synthetic.dump'}),
            'equal_fingerprints': lambda before, after: self.assertEqual(before, after)}

    @staticmethod
    def row(identifier, name, image):
        return {'Id': identifier, 'Name': '/' + name, 'Image': image, 'State': {'Running': True},
            'RestartCount': 0, 'Config': {'Image': image, 'Env': ['KEEP=synthetic'],
                'User': '1000:1000', 'Labels': {'regulai.install': 'v2'}, 'Cmd': ['python', 'serve.py']},
            'HostConfig': {'NetworkMode': 'host', 'AutoRemove': False}, 'Mounts': [],
            'NetworkSettings': {'Networks': {'host': {}}}}

    def lookup(self, identifier):
        return next((deepcopy(row) for row in self.rows.values()
                     if row['Id'] == identifier or row['Name'].lstrip('/') == identifier), None)

    def create(self, original, image, name):
        row = deepcopy(original)
        row.update(Id='web-new', Name='/' + name, Image=image, State={'Running': False})
        row['Config']['Image'] = image
        self.rows[row['Id']] = row
        return row['Id']

    def docker(self, action, *args, **kwargs):
        self.calls.append((action, args))
        if action in ('stop', 'start'):
            for identifier in args:
                row = self.lookup(identifier)
                self.rows[row['Id']]['State']['Running'] = action == 'start'
                self.fail_if(action, identifier)
            return b''
        if action == 'rename':
            identifier, name = args
            self.fail_if(action, identifier, name)
            if self.lookup(name):
                raise RuntimeError('name_collision')
            self.rows[identifier]['Name'] = '/' + name
            return b''
        raise AssertionError('Unexpected Docker operation')

    def fail_if(self, *operation):
        if self.failure == operation:
            self.failure = None
            raise RuntimeError('injected_failure')

    def assert_worker_restored(self):
        self.assertEqual(self.rows['worker-old'], self.original['worker'])
        self.assertEqual(self.rows['pg-old'], self.original['pg'])
        self.assertFalse(any('pg-old' in str(args) for action, args in self.calls))
        self.assertTrue(all(action in ('stop', 'start') and args == ('worker-old',)
                            for action, args in self.calls if 'worker' in str(args)))

    def test_apply_coordinates_worker_and_retains_current_base(self):
        result = self.ns['apply']()
        self.assertEqual(self.lookup('web')['Id'], 'web-new')
        self.assertEqual(result['retained_web_id'], 'web-old')
        self.assertTrue(result['existing_data_unchanged'])
        self.assertTrue(result['worker_image_config_preserved'])
        self.assertTrue(result['worker_restarted'])
        self.assertLess(self.calls.index(('stop', ('web-old',))), self.calls.index(('stop', ('worker-old',))))
        self.assertLess(self.calls.index(('start', ('web-new',))), self.calls.index(('health', ())))
        self.assertLess(self.calls.index(('health', ())), self.calls.index(('start', ('worker-old',))))
        self.assert_worker_restored()

    def test_apply_restores_current_web_after_partial_stop(self):
        self.failure = ('stop', 'web-old')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_apply_restores_current_web_after_half_rename(self):
        self.failure = ('rename', 'web-new', 'web')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assert_worker_restored()

    def test_rollback_works_for_stopped_candidate_and_uses_current_base(self):
        self.ns['apply']()
        self.rows['web-new']['State']['Running'] = False
        result = self.ns['rollback']()
        self.assertEqual(result['restored_image_id'], 'image-web')
        self.assertFalse(result['database_restored'])
        self.assertTrue(result['worker_image_config_preserved'])
        self.assertTrue(result['worker_restarted'])
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assert_worker_restored()

    def test_failed_rollback_compensates_to_previous_candidate(self):
        self.ns['apply']()
        self.failure = ('rename', 'web-old', 'web')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['rollback']()
        self.assertEqual(self.lookup('web')['Id'], 'web-new')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_apply_recovers_worker_after_partial_worker_stop(self):
        self.failure = ('stop', 'worker-old')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_apply_recovers_both_services_after_worker_start_failure(self):
        self.failure = ('start', 'worker-old')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['apply']()
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_failed_rollback_worker_start_recovers_candidate_and_worker(self):
        self.ns['apply']()
        self.failure = ('start', 'worker-old')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['rollback']()
        self.assertEqual(self.lookup('web')['Id'], 'web-new')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_worker_is_restarted_even_if_restore_health_check_fails(self):
        self.rows['worker-old']['State']['Running'] = False
        self.ns['health_http'].side_effect = RuntimeError('health_unavailable')
        with self.assertRaisesRegex(RuntimeError, 'health_unavailable'):
            self.ns['restore_services']('web-old', {'web-old'}, self.original)
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_compensation_restores_web_after_partial_worker_stop_failure(self):
        self.ns['apply']()
        self.failure = ('stop', 'worker-old')
        with self.assertRaisesRegex(RuntimeError, 'injected_failure'):
            self.ns['restore_services']('web-old', {'web-old', 'web-new'}, self.original)
        self.assertEqual(self.lookup('web')['Id'], 'web-old')
        self.assertTrue(self.lookup('web')['State']['Running'])
        self.assert_worker_restored()

    def test_changed_worker_is_rejected_before_mutation(self):
        self.rows['worker-old']['Config']['Env'] = ['CHANGED=synthetic']
        with self.assertRaisesRegex(RuntimeError, 'worker_or_postgres_changed'):
            self.ns['apply']()
        self.assertFalse(self.calls)

    def test_unknown_container_at_web_name_is_never_stopped(self):
        self.rows['web-old']['Name'] = '/retained'
        self.rows['unrelated'] = self.row('unrelated', 'web', 'unrelated')
        with self.assertRaisesRegex(RuntimeError, 'unknown_current_web'):
            self.ns['restore_web']('web-old', {'web-old', 'web-new'})
        self.assertFalse(self.calls)

    def test_stale_base_image_is_rejected_before_any_mutation(self):
        self.ns['REQUEST']['expected_web'] = 'expected-current-chat12-image'
        with self.assertRaisesRegex(RuntimeError, 'expected_current_chat12_image_required'):
            self.ns['init']()
        self.assertFalse(self.calls)

    def test_candidate_api_payload_preserves_env_mount_configuration_and_user(self):
        captured = {}
        response = SimpleNamespace(status=201, read=lambda: b'{"Id":"new"}')
        client = SimpleNamespace(request=lambda *args, **kwargs: captured.update(kwargs),
                                 getresponse=lambda: response, close=lambda: None)
        self.ns['h']['DockerConnection'] = lambda _: client
        # Recover the real function from definitions (setUp installs a Docker-free fake).
        path = ROOT / 'ops/agent_chat/jev_remote.py'
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'create_web')
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), self.ns)
        self.ns['create_web'](self.original['web'], 'new-image', 'candidate')
        expected = {**self.original['web']['Config'], 'Image': 'new-image',
                    'HostConfig': self.original['web']['HostConfig']}
        self.assertEqual(json.loads(captured['body']), expected)

    def test_apply_rejects_tests_without_verified_isolated_cleanup(self):
        self.records['tests.json']['isolated_resources_removed'] = False
        with self.assertRaisesRegex(RuntimeError, 'current_candidate_tests_required'):
            self.ns['apply']()
        self.assertFalse(self.calls)


    def test_apply_rejects_empty_or_missing_summary_even_when_exit_zero(self):
        for summary in (None, {'tests': 0, 'failures': [], 'errors': []}):
            self.records['tests.json']['summary'] = summary
            with self.assertRaisesRegex(RuntimeError, 'current_candidate_tests_required'):
                self.ns['apply']()
        self.assertFalse(self.calls)

    def test_apply_rejects_stale_test_sources_for_same_image(self):
        self.records['tests.json']['test_hashes'] = {'test.py': 'olderhash'}
        with self.assertRaisesRegex(RuntimeError, 'current_candidate_tests_required'):
            self.ns['apply']()
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
