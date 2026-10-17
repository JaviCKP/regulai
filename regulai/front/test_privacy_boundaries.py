"""Actual provider HTTP plus private executor HTTP; no external network."""
import json
from unittest.mock import patch
import httpx
from django.test import TestCase, override_settings
from front.models import AgentAccessGrant, PrivacyRevision, PrivacyUse, ConversationAlias
from front.local_masking import detector_metadata
from front.policy import digest
from front.agents.capabilities import GENERAL
from front.test_agent_inference import AgentFixture
from front import test_agent_professional as professional_fixture


@override_settings(REGULAY_AGENT_ENABLED=True, REGULAY_AGENT_WEB_ENABLED=True,
    REGULAY_AGENT_BROWSER_ENABLED=True, DEBUG=False)
class PrivacyBoundaryTests(AgentFixture, TestCase):
    def queued(self, text):
        import uuid
        from front.models import AgentExecution
        result = self.client.post('/chat/send/', {'prompt': text, 'mode': 'agent', 'request_id': str(uuid.uuid4())})
        self.assertEqual(result.status_code, 202, result.content)
        self.assertIn('agent', result.json(), result.content)
        return AgentExecution.objects.get(pk=result.json()['agent']['id'])
    activate = professional_fixture.ProfessionalTests.activate
    issue = professional_fixture.ProfessionalTests.issue
    http_fixture = professional_fixture.ProfessionalTests.http_fixture

    def setUp(self):
        super().setUp()
        self.enterContext(patch('socket.create_connection', side_effect=AssertionError('External network forbidden')))
        self.agent.professional = True
        self.agent.tools = sorted(GENERAL)
        self.agent.search_config = json.dumps({'provider': 'tavily', 'api_key': 'synthetic-search', 'call_cost_bound': '0.01'})
        self.agent.save()
        AgentAccessGrant.objects.create(company=self.company, user=self.user, profile=self.agent, enabled=True)
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({'categories': {'EMAIL': 'reversible'},
                'literals': [{'text': 'Ana Fixture', 'category': 'PERSON'}]}),
            fingerprint='boundary-fixture', detector_version=digest(detector_metadata()))
        self.company.ai_config['privacy'] = {'version': 1, 'revision_id': revision.pk}
        self.company.ai_config['destinations']['internal'] += ['research:web']
        self.company.save()
        self.client.force_login(self.user)
        self.wire = []

    def private(self, operation, body):
        path = f'/internal/agents/run/{operation}/' if operation != 'tool-results' else '/internal/agents/tool-results/'
        return self.client.post(path, body, content_type='application/json',
            HTTP_AUTHORIZATION='Bearer ' + self.token, HTTP_X_REGULAY_ATTEMPT=str(self.execution.attempt))

    def assert_protected(self, value):
        text = json.dumps(value)
        self.assertNotIn('Ana Fixture', text)
        self.assertNotIn('ana@example.invalid', text)

    def test_professional_bootstrap_retry_has_one_stable_http_identity(self):
        self.activate(self.queued('Redacta un saludo para Ana Fixture, ana@example.invalid'))
        from front.models import PrivacyOccurrence
        occurrences = PrivacyOccurrence.objects.count()
        first = self.private('bootstrap', {})
        self.assertEqual(first.status_code, 200, first.content)
        self.assert_protected(first.json())
        before = list(PrivacyUse.objects.values_list('alias_id', 'call_key', 'count'))
        self.assertTrue(before)
        second = self.private('bootstrap', {})
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(before, list(PrivacyUse.objects.values_list('alias_id', 'call_key', 'count')))
        self.assertFalse(PrivacyUse.objects.filter(call_key='worker:bootstrap').exists())
        self.assertEqual(PrivacyOccurrence.objects.count(), occurrences)

    @override_settings(REGULAY_SKILLS_RUNTIME=True)
    def test_greeting_with_sdk_text_blocks_completes_through_three_send_entries(self):
        import base64
        import hashlib
        import uuid
        from front.models import AgentSkillInstallation, AgentSkillRevision
        body = b'---\nname: design\ndescription: Design HTML\n---\nUse only for design tasks.\n'
        installation = AgentSkillInstallation.objects.create(company=self.company, owner=self.user,
            source_identity='test:greeting-design', alias='design', enabled=True)
        manifest = [{'path': 'SKILL.md', 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}]
        installation.current_revision = AgentSkillRevision.objects.create(installation=installation,
            origin='test:greeting-design', folder_sha256=digest(manifest), manifest=manifest,
            metadata={'name': 'design', 'description': 'Design HTML'}, license='Test package',
            compatibility={'profile': 'professional', 'tools': ['read_file']},
            bundle=json.dumps({'SKILL.md': base64.b64encode(body).decode()}))
        installation.save(update_fields=['current_revision'])
        for path in ('/chat/', '/chat/send/', '/api/chat/send/'):
            with self.subTest(path=path):
                run = professional_fixture.ProfessionalTests.queued(self, 'hola', url=path)
                self.activate(run)
                boot = self.private('bootstrap', {})
                self.assertEqual(boot.status_code, 200, boot.content)
                self.assertEqual(len(boot.json()['skills']['catalog']), 1)
                self.assertFalse(run.job['request']['delivery_required'])
                call_id = str(uuid.uuid4())
                response = self.client.post('/internal/agents/inference/', {
                    'call_id': call_id,
                    'messages': [{'role': 'system', 'content': [
                        {'type': 'text', 'text': 'Responde con un saludo.'},
                        {'type': 'text', 'text': 'Respeta los límites de herramientas.'},
                        {'type': 'text', 'text': 'Usa el contexto autorizado.'},
                        {'type': 'text', 'text': 'Catálogo del SDK reemplazado por el servidor.'}],
                        'skill_catalog': {'digest': run.job['skills']['digest'], 'block_index': 3}},
                                 {'role': 'user', 'content': boot.json()['message']}],
                }, content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + self.token,
                    HTTP_X_REGULAY_ATTEMPT=str(run.attempt))
                self.assertEqual(response.json()['status'], 'completed', response.content)
                result = self.private('complete', {'final_call_id': call_id})
                self.assertEqual(result.status_code, 200, result.content)
                run.refresh_from_db()
                run.prompt.refresh_from_db()
                self.assertEqual(run.status, 'completed')
                self.assertEqual(run.prompt.decision['delivery']['status'], 'not_required')
        self.assertEqual(len(self.requests), 3)

    def test_search_public_read_and_worker_results_cross_captured_boundaries_protected(self):
        def http(request):
            self.wire.append({'url': str(request.url), 'headers': dict(request.headers), 'body': request.content.decode()})
            if request.url.host == 'api.tavily.com':
                return httpx.Response(200, json={'results': [{'title': 'Ana Fixture', 'url': 'https://fixture.example/read',
                    'content': 'Contacta con ana@example.invalid'}]})
            return httpx.Response(200, headers={'content-type': 'text/html'},
                content=b'<html><title>Ana Fixture</title><main>Contacto: ana@example.invalid. Texto de prueba.</main></html>')
        self.http_fixture(http)
        self.activate(self.queued('Busca información pública del proyecto ficticio'))
        for name, args in (('web_search', {'query': 'proyecto ficticio'}), ('web_open', {'url': 'https://fixture.example/read'})):
            call = self.issue(name, args)
            executed = self.private('web', {'call': call})
            self.assertEqual(executed.status_code, 200, executed.content)
            result = self.private('tool-results', {'call': call, 'raw': {'content': 'finished'}})
            self.assertEqual(result.status_code, 200, result.content)
            self.assert_protected(result.json())
            self.assertIn('[[R_', json.dumps(result.json()))
        self.assertEqual(len(self.wire), 2, self.wire)
        self.assert_protected(self.wire)
        self.assert_protected(self.requests)

    def test_tool_text_is_protected_before_truncation_and_worker_delivery(self):
        self.activate(self.queued('Revisa el texto ficticio y responde en el chat'))
        call = self.issue('execute', {'command': 'echo fixture'})
        result = self.private('tool-results', {'call': call,
            'raw': {'content': 'x' * 2042 + 'Ana Fixture ana@example.invalid'}})
        self.assertEqual(result.status_code, 200, result.content)
        self.assert_protected(result.json())
        self.assert_protected(self.requests)

    def test_selected_search_arguments_and_all_binary_routes_stop_before_network(self):
        self.http_fixture(lambda request: (_ for _ in ()).throw(AssertionError('Unexpected external request')))
        self.activate(self.queued('Consulta el proyecto ficticio'))
        call = self.issue('web_search', {'query': 'Ana Fixture ana@example.invalid'})
        self.assert_protected(call)
        result = self.private('web', {'call': call})
        self.assertEqual(result.status_code, 200, result.content)
        finished = self.private('tool-results', {'call': call, 'raw': {'content': 'finished'}})
        self.assertFalse(finished.json().get('succeeded', True), finished.content)
        for name, args in (('web_download', {'url': 'https://fixture.example/file', 'file_path': '/workspace/work/a.pdf'}),
                           ('web_browse', {'url': 'https://fixture.example/page'}),
                           ('inspect_image', {'file_path': '/workspace/work/a.png', 'question': 'Describe'})):
            denied = self.client.post('/internal/agents/authorize-tool/', {'id': 'binary-fixture', 'name': name, 'args': args},
                content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + self.token,
                HTTP_X_REGULAY_ATTEMPT=str(self.execution.attempt))
            self.assertEqual(denied.status_code, 403, denied.content)
            self.assertEqual(denied.json()['code'], 'privacy_binary_channel_blocked')
