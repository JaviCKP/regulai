"""Race probe at the actual SDK boundary; synthetic DB, approval and network."""
from datetime import date
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import requests
from django.test import TestCase

from front import evaluation
from front.evaluation_budget import BudgetExceeded, EvaluationBudget
from front.models import Engine, EngineModel


class ApprovalAtTransportProbe(TestCase):
    def test_revocation_during_sdk_construction_prevents_generation_transport(self):
        repo = Path(__file__).resolve().parents[5]
        manifest = json.loads(subprocess.check_output(['rtk', 'proxy', 'git', 'show',
            '4fdbe1a:evals/adversarial-live/community-additional-20261003/manifest.json'], cwd=repo))
        manifest['price_date'] = date.today().isoformat()
        manifest['campaign_frozen_files'] = {}
        runner_path = evaluation.ROOT / 'scripts/run_calibration_campaign.py'
        spec = importlib.util.spec_from_file_location('review_fixed_race_runner', runner_path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        case = {'id': 'review-authorization-race', 'input': 'Calcula 2 + 2.', 'task': 'general',
            'difficulty': 'economy', 'split': 'development', 'group': 'arithmetic'}
        engine = Engine.objects.create(name='Reviewer synthetic engine', connector_type='openai_compatible',
            base_url=manifest['destinations']['generation'])
        models = {level: EngineModel.objects.create(engine=engine, name=level,
            model_id=manifest['model_versions'][level], context_window=manifest['context_window'],
            max_tokens=512, supports_json=True,
            input_price=Decimal(manifest['prices_per_million'][level]['input']),
            output_price=Decimal(manifest['prices_per_million'][level]['output']), price_date=date.today())
            for level in ('economy', 'strong')}
        sent_after_revocation, authorization_checks = [], []
        def judge_send(adapter, request, **kwargs):
            body = json.loads(request.body)
            answers = {}
            for key, question in body['questions'].items():
                if question['type'] == 'choice':
                    chosen = {'category': 'public', 'task': 'general', 'difficulty': 'economy'}[key]
                    answers[key] = {'type': 'choice', 'choice': chosen, 'confidence': 1.0,
                        'probabilities': {option: float(option == chosen) for option in question['criteria']}}
                else:
                    answers[key] = {'type': 'noul', 'noul': 0.0}
            response = requests.Response()
            response.status_code, response._content_consumed = 200, True
            response._content = json.dumps({'model': body['model'], 'answers': answers,
                'usage': {'input_tokens': 100, 'output_tokens': 20}}).encode()
            return response
        with TemporaryDirectory() as directory:
            approval = Path(directory) / 'approval.json'
            approval.write_text('{"status":"approved"}', encoding='utf-8')
            def authorize():
                status = json.loads(approval.read_text())['status']
                authorization_checks.append(status)
                if status != 'approved':
                    raise BudgetExceeded('Synthetic approval revoked')
            def generator_send(request):
                sent_after_revocation.append(json.loads(approval.read_text())['status'] == 'revoked')
                body = json.loads(request.content)
                return httpx.Response(200, json={'id': 'review-fake', 'object': 'chat.completion', 'created': 0,
                    'model': body['model'], 'choices': [{'index': 0,
                        'message': {'role': 'assistant', 'content': '4'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 20, 'completion_tokens': 1, 'total_tokens': 21}})
            def client_after_revocation(**kwargs):
                approval.write_text('{"status":"revoked"}', encoding='utf-8')
                return httpx.Client(transport=httpx.MockTransport(generator_send), **kwargs)
            with patch.dict(os.environ, {'REGULAI_EVAL_GENERATOR_KEY': 'review-fake',
                    'REGULAI_EVAL_JEV_KEY': 'review-fake'}), \
                 patch('requests.adapters.HTTPAdapter.send', judge_send), \
                 patch('openai.DefaultHttpxClient', side_effect=client_after_revocation):
                ledger = EvaluationBudget(Path(directory) / 'synthetic-ledger.sqlite3', '1.00')
                with evaluation.SyntheticPayloadRecorder(synthetic=True, configuration=manifest,
                        request_guard=runner.make_guard(manifest, [])) as recorder:
                    row = evaluation.exercise_case(case, 'economy', manifest, engine, models, ledger,
                        real=True, authorize=authorize)
                findings = {'generation_calls_after_revocation': sum(sent_after_revocation),
                    'authorization_checks': authorization_checks,
                    'recorded_purposes': [event['purpose'] for event in recorder.events],
                    'stop_reason': row['stop_reason']}
                commit = evaluation.ROOT.name.removeprefix('snapshot-')
                with Path(__file__).with_name(commit + '-authorization-gap-observed.json').open('x', encoding='utf-8') as output:
                    output.write(json.dumps(findings, indent=2) + '\n')
                self.assertEqual(sum(sent_after_revocation), 0, findings)
