"""Read-only checks of the exact approved snapshot; no bridge import or execution."""
import ast
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from front import evaluation

HERE = Path(__file__).resolve().parent


class FrozenScopeChecks(SimpleTestCase):
    def test_approved_eight_case_scope_matches_frozen_manifest_without_database_or_network(self):
        manifest_path = evaluation.ROOT / 'evals/pilot-real/manifest-vercel.json'
        approval_path = evaluation.ROOT / 'evals/reports/pilot-real-vercel-20261003-01/authorization.json'
        manifest, cases = evaluation.load_pilot(manifest_path)
        approval = evaluation.read_json(approval_path)
        self.assertEqual([case['id'] for case in cases], [
            'arithmetic', 'blocked', 'consent-pending', 'consent-accepted',
            'document-success', 'evidence-absent', 'verification-failed', 'second-attempt'])
        self.assertEqual({case['split'] for case in cases}, {'development'})
        self.assertEqual(manifest['configurations'], ['economy', 'strong', 'router'])
        self.assertEqual(manifest['max_generation_attempts'], {'economy': 1, 'strong': 1, 'router': 2})
        self.assertEqual(Decimal(manifest['maximum_usd']), Decimal('1'))
        self.assertEqual(approval['maximum_usd'], manifest['maximum_usd'])
        self.assertIs(approval['reserved_evaluation'], False)
        self.assertIs(approval['mutable_alias_acknowledged'], True)
        self.assertEqual(manifest['bank_purpose'], 'eight_case_rehearsal')
        self.assertEqual(manifest['gateway_scope']['only'], ['typesafe-ai'])
        self.assertIs(manifest['gateway_scope']['immutable_underlying_version_available'], False)
        self.assertIn('typesafe-ai/jev', manifest['mutable_model_aliases'])
        self.assertEqual(manifest['masking']['backend'], 'local')
        self.assertNotIn('mask', manifest['destinations'])
        self.assertEqual(Decimal(manifest['call_caps_usd']['obfuscation']), 0)
        self.assertEqual(approval['actions'], manifest['actions'])
        self.assertEqual(approval['manifest_sha256s'], [evaluation.digest(manifest_path.read_bytes())])
        self.assertFalse(evaluation.LEDGER_PATH.exists())
        # A deterministic time inside the existing approval, never a new approval.
        checked_at = datetime.fromisoformat(approval['valid_from']) + timedelta(seconds=1)
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No HTTP')) as http, \
                patch('httpx.Client.send', side_effect=AssertionError('No SDK')) as sdk, \
                patch('django.db.backends.sqlite3.base.DatabaseWrapper.get_new_connection',
                      side_effect=AssertionError('No database')) as db, \
                patch.object(evaluation, 'EvaluationBudget', side_effect=AssertionError('No ledger')) as ledger:
            report, observed_approval = evaluation.preflight(manifest_path, approval_path,
                now=checked_at, check_credentials=False)
            self.assertTrue(report['ready_for_real'], report['blockers'])
            self.assertEqual(observed_approval, approval)
            for guard in (http, sdk, db, ledger):
                guard.assert_not_called()
        self.assertFalse(evaluation.LEDGER_PATH.exists())
        report.update(credentials_checked=False, bridge_executed=False,
                      deterministic_check_time=checked_at.isoformat(),
                      authorization_sha256=evaluation.digest(approval_path.read_bytes()),
                      case_ids=[case['id'] for case in cases], configurations=manifest['configurations'])
        (HERE / 'frozen-scope-preflight.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    def test_bridge_is_only_parsed_and_uses_environment_not_credential_arguments(self):
        bridge_path = evaluation.ROOT / 'evals/reports/pilot-real-vercel-20261003-01/run_authorized.py'
        source = bridge_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(bridge_path))
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(set(functions), {'credentials_readonly', 'main'})
        command = next(node.value for node in ast.walk(functions['main'])
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'command'
                                                    for target in node.targets))
        self.assertFalse(any(isinstance(node, ast.Name) and node.id in {'pair', 'generator', 'judge', 'secret'}
                             for node in ast.walk(command)))
        self.assertIn("database.as_uri() + '?mode=ro'", source)
        self.assertIn('CompanyEngine.objects.using(alias)', source)
        self.assertIn("environment['REGULAI_EVAL_GENERATOR_KEY'], environment['REGULAI_EVAL_JEV_KEY'] = pair", source)
        self.assertIn("'--settings=regulai.test_settings'", source)
        self.assertIn("text.replace(secret, '[REDACTED_CREDENTIAL]')", source)
        self.assertIn("path.open('x', encoding='utf-8')", source)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in {'eval', 'exec'} for node in ast.walk(tree)))
        (HERE / 'bridge-static.json').write_text(json.dumps({
            'script_sha256': evaluation.digest(bridge_path.read_bytes()),
            'analysis': 'AST and source only; no bridge import, function execution, keys or user database access',
            'credentials_in_argv': False,
            'source_query_connection': 'separate SQLite URI with mode=ro',
            'child_settings': 'regulai.test_settings',
            'secret_transport': 'child process environment',
            'runtime_secret_isolation_tested': False,
        }, indent=2), encoding='utf-8')
