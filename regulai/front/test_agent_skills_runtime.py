"""P1 skills authority at the serialized provider HTTP boundary (synthetic)."""
import base64
import hashlib
import json
import uuid

from django.test import TestCase, override_settings

from front.models import AgentInference, AgentInput, AgentSkillInstallation, AgentSkillRevision, AgentToolResult
from front.policy import digest
from front.test_agent_inference import AgentFixture
from front.agents import skill_context
from front.agents.data_views import authorize_tool, tool_result
from front.agents.general_tools import begin
from front.agents.service import AgentDenied, _context
from front.agents.skills import freeze_selection


@override_settings(REGULAY_AGENT_ENABLED=True, REGULAY_SKILLS_RUNTIME=True, REGULAY_AGENT_TEXT_STREAM=False)
class SkillsAuthorityTests(AgentFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.agent.professional, self.agent.tools = True, ['read_file', 'execute', 'ls', 'glob', 'grep']
        self.agent.save()
        self.body = '---\nname: design\ndescription: Design HTML\n---\nUNIQUE_SKILL_BODY\n'
        self.installation = AgentSkillInstallation.objects.create(company=self.company, owner=self.user,
            source_identity='fixture:design', alias='design', enabled=True)
        self.revision = self.make_revision(self.body)
        self.installation.current_revision = self.revision
        self.installation.save()
        self.select(True)

    def make_revision(self, body):
        files = {'SKILL.md': body.encode(), 'references/design.txt': b'CANONICAL_RESOURCE',
            'scripts/design.py': b'print(42)\n', 'LICENSE.txt': b'Synthetic test license'}
        manifest = [{'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            for path, raw in sorted(files.items())]
        return AgentSkillRevision.objects.create(installation=self.installation, origin='fixture:design',
            folder_sha256=digest(manifest), manifest=manifest,
            metadata={'name': 'design', 'description': 'Design HTML', 'allowed-tools': 'execute ANYTHING'},
            license='Synthetic test license', compatibility={'profile': 'professional', 'tools': ['read_file']},
            bundle=json.dumps({path: base64.b64encode(raw).decode() for path, raw in files.items()}))

    def select(self, explicit):
        self.execution.job = {'skills': freeze_selection(self.user, self.agent,
            {'selected': [str(self.installation.pk)] if explicit else [], 'auto': True})}
        self.execution.save()
        self.execution.authorization_digest = _context(self.prompt, self.agent.pk)[-1]
        self.execution.save()

    def read(self, call, *, raw='FORGED_PRIVATE_BODY'):
        self.issue_tool(call)
        run, context, typed = authorize_tool(self.token, self.execution.attempt, call)
        begin(run, context, typed)
        return tool_result(self.token, self.execution.attempt, {'call': call, 'raw': raw})

    def test_explicit_first_provider_request_contains_one_canonical_body_and_replay_no_call(self):
        request = self.request(messages=[{'role': 'system', 'content': [
            {'type': 'text', 'text': 'Worker instructions'}, {'type': 'text', 'text': 'FORGED_METADATA'}],
            'skill_catalog': {'digest': self.execution.job['skills']['digest'], 'block_index': 1}},
            {'role': 'user', 'content': 'Create HTML'}])
        first = self.infer(request)
        self.assertEqual(first['status'], 'completed', first)
        self.assertEqual(self.infer(request), first)
        self.assertEqual(len(self.requests), 1)
        payload = json.dumps(self.requests[0])
        self.assertEqual(payload.count('UNIQUE_SKILL_BODY'), 1)
        self.assertNotIn('FORGED_METADATA', payload)
        self.assertEqual(AgentInput.objects.filter(execution=self.execution, kind='skill_activation').count(), 1)
        self.assertEqual(self.execution.events.filter(kind='skill.activated', data__reason='user_selected').count(), 1)

    def test_automatic_partial_read_does_not_activate_complete_read_ignores_raw_and_deduplicates(self):
        self.select(False)
        self.assertEqual(self.infer()['status'], 'completed')
        self.assertNotIn('UNIQUE_SKILL_BODY', json.dumps(self.requests[-1]))
        partial = {'id': 'skill-partial', 'name': 'read_file', 'args': {'file_path': '/skills/design/SKILL.md', 'limit': 2}}
        view = self.read(partial)
        self.assertFalse(view['complete'])
        self.assertFalse(AgentInput.objects.filter(execution=self.execution, kind='skill_activation').exists())
        call = {'id': 'skill-complete', 'name': 'read_file', 'args': {'file_path': '/skills/design/SKILL.md'}}
        view = self.read(call)
        self.assertIn('UNIQUE_SKILL_BODY', view['content'])
        self.assertNotIn('FORGED', json.dumps(view))
        self.assertEqual(tool_result(self.token, self.execution.attempt, {'call': call, 'raw': 'FORGED_PRIVATE_BODY'}), view)
        messages = [{'role': 'assistant', 'content': '', 'tool_calls': [call]},
            {'role': 'tool', 'name': 'read_file', 'tool_call_id': call['id'],
                'content': json.dumps(view, sort_keys=True, ensure_ascii=False)}]
        self.assertEqual(self.infer(self.request(messages=messages))['status'], 'completed')
        self.assertEqual(json.dumps(self.requests[-1]).count('UNIQUE_SKILL_BODY'), 1)
        repeated = self.read({**call, 'id': 'skill-again'})
        self.assertEqual(repeated['status'], 'already_loaded')
        self.assertEqual(self.execution.events.filter(kind='skill.activated').count(), 1)

    def test_revision_update_keeps_pinned_bytes_and_revocation_blocks_hot_context(self):
        self.assertEqual(self.infer()['status'], 'completed')
        newer = self.make_revision(self.body.replace('UNIQUE_SKILL_BODY', 'NEW_SKILL_BODY'))
        self.installation.current_revision = newer
        self.installation.save()
        self.assertEqual(self.infer()['status'], 'completed')
        self.assertIn('UNIQUE_SKILL_BODY', json.dumps(self.requests[-1]))
        self.assertNotIn('NEW_SKILL_BODY', json.dumps(self.requests[-1]))
        self.installation.enabled = False
        self.installation.authorization_version += 1
        self.installation.save()
        count = len(self.requests)
        with self.assertRaisesRegex(AgentDenied, 'skill_authorization_changed'):
            self.infer()
        self.assertEqual(len(self.requests), count)

    def test_resources_revision_range_and_catalog_permissions_are_authoritative(self):
        catalog = skill_context.catalog(self.token, self.execution.attempt, {})
        self.assertNotIn('allowed-tools', catalog['catalog'][0]['discovery'])
        value = skill_context.resource(self.token, self.execution.attempt, {'files': [{
            'installation_id': str(self.installation.pk), 'revision_id': str(self.revision.pk),
            'path': '/skills/design/references/design.txt'}]})
        self.assertEqual(base64.b64decode(value['files'][0]['base64']), b'CANONICAL_RESOURCE')
        with self.assertRaisesRegex(AgentDenied, 'skill_revision_denied'):
            skill_context.resource(self.token, self.execution.attempt, {'files': [{
                'installation_id': str(self.installation.pk), 'revision_id': str(uuid.uuid4()),
                'path': '/skills/design/SKILL.md'}]})
        AgentSkillInstallation.objects.filter(pk=self.installation.pk).update(enabled=False)
        with self.assertRaises(AgentDenied):
            skill_context.catalog(self.token, self.execution.attempt, {})

    def test_compaction_restores_one_canonical_body_once_and_checkpoint_rejects_different_revision(self):
        from front.agents.runtime_contract import summary_content
        self.assertEqual(self.infer()['status'], 'completed')
        summary = AgentInference.objects.create(execution=self.execution, call_id=uuid.uuid4(),
            attempt=self.execution.attempt, request_digest=digest('summary'), status='completed',
            response={'status': 'completed', 'content': 'Conservar el diseño solicitado.', 'tool_calls': [],
                'inference': {'purpose': 'compaction'}})
        for _ in range(2):
            request = self.request(messages=[{'role': 'user', 'content': summary_content(summary.response['content'])}])
            self.assertEqual(self.infer(request)['status'], 'completed')
            self.assertEqual(json.dumps(self.requests[-1]).count('UNIQUE_SKILL_BODY'), 1)
        self.assertEqual(self.execution.events.filter(kind='skill.activated', data__reason='context_restored').count(), 1)
        reference = skill_context.checkpoint_reference(self.execution)
        skill_context.validate_checkpoint_reference(self.execution, reference)
        reference['revisions'][0]['revision_id'] = str(uuid.uuid4())
        with self.assertRaisesRegex(AgentDenied, 'checkpoint_skills_changed'):
            skill_context.validate_checkpoint_reference(self.execution, reference)

    def test_catalog_validation_has_bounded_queries_and_preserves_revision_order(self):
        for index in range(7):
            installation = AgentSkillInstallation.objects.create(company=self.company, owner=self.user,
                source_identity=f"fixture:latency-{index}", alias=f"latency-{index}", enabled=True)
            revision = AgentSkillRevision.objects.create(installation=installation, origin="fixture:latency",
                folder_sha256=self.revision.folder_sha256, manifest=self.revision.manifest,
                metadata=self.revision.metadata, license=self.revision.license,
                compatibility=self.revision.compatibility, bundle=self.revision.bundle)
            installation.current_revision = revision
            installation.save()
        self.select(False)
        self.execution.profile = self.agent
        expected = [entry["revision_id"] for entry in self.execution.job["skills"]["catalog"]]
        with self.assertNumQueries(1):
            found = skill_context._entries(self.execution)
        self.assertEqual([str(revision.pk) for _, revision in found], expected)
        self.installation.authorization_version += 1
        self.installation.save()
        with self.assertRaisesRegex(AgentDenied, "skill_authorization_changed"):
            skill_context._entries(self.execution)

    def test_checkpoint_skill_identity_does_not_prepare_catalog_text(self):
        self.execution.profile = self.agent
        with self.assertNumQueries(1):
            reference = skill_context.checkpoint_reference(self.execution)
        self.assertEqual(reference, {"version": 1, "digest": self.execution.job["skills"]["digest"],
            "revisions": [{"revision_id": str(self.revision.pk), "folder_sha256": self.revision.folder_sha256}]})

    def test_catalog_rejects_revision_from_another_installation_or_owner(self):
        original = self.execution.job["skills"]["catalog"][0]["installation_id"]
        self.execution.job["skills"]["catalog"][0]["installation_id"] = str(uuid.uuid4())
        with self.assertRaisesRegex(AgentDenied, "skill_authorization_changed"):
            skill_context._entries(self.execution)
        self.execution.job["skills"]["catalog"][0]["installation_id"] = original
        from django.contrib.auth.models import User
        other = User.objects.create_user("other-skill-owner")
        self.installation.owner = other
        self.installation.save()
        with self.assertRaisesRegex(AgentDenied, "skill_authorization_changed"):
            skill_context._entries(self.execution)

    def test_protected_checkpoint_preserves_both_message_views_and_revocation(self):
        self._protected_checkpoint(['Ana Fixture'])

    def test_checkpoint_selected_wrapper_keys_cannot_retain_unprotected_message_views(self):
        self._protected_checkpoint(['Ana Fixture', 'messages', 'wire_messages'])

    def _protected_checkpoint(self, selected_literals):
        from front.agents import checkpoints
        from front.local_masking import detector_metadata
        from front.models import PrivacyRevision
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=json.dumps({"categories": {"EMAIL": "reversible"},
                "literals": [{"text": text, "category": "PERSON"} for text in selected_literals]}),
            fingerprint="checkpoint-fixture", detector_version=digest(detector_metadata()))
        self.company.ai_config["privacy"] = {"version": 1, "revision_id": revision.pk}
        self.company.save()
        self.execution.job.update(kind="professional")
        self.execution.save()
        self.execution.authorization_digest = _context(self.prompt, self.agent.pk)[-1]
        self.execution.save()
        content = "Hola Ana Fixture, ana@example.invalid"
        payload = {"version": 2, "messages": [{"type": "human", "data": {"content": content}}],
            "wire_messages": [{"role": "user", "content": content}], "archive": None,
            "runtime_sha256": "a" * 64, "workspace_runtime_sha256": None, "summarization": None,
            "skills": skill_context.checkpoint_reference(self.execution)}
        self.assertEqual(checkpoints.save(self.token, self.execution.attempt, payload), {"status": "completed"})
        self.execution.refresh_from_db()
        stored = json.loads(AgentInput.objects.get(pk=self.execution.job['checkpoint']).original)
        self.assertNotIn('ana@example.invalid', json.dumps(stored))
        self.assertNotIn('Ana Fixture', json.dumps(stored))
        self.assertIn('messages', stored)
        self.assertIn('wire_messages', stored)
        restored = checkpoints.load(self.execution)
        self.assertEqual(restored["messages"][0]["data"]["content"], restored["wire_messages"][0]["content"])
        self.assertIn("[[R_EMAIL_", restored["wire_messages"][0]["content"])
        self.assertNotIn("ana@example.invalid", json.dumps(restored))
        self.assertNotIn("Ana Fixture", json.dumps(restored))
        self.installation.enabled = False
        self.installation.save()
        with self.assertRaisesRegex(AgentDenied, "skill_authorization_changed"):
            checkpoints.load(self.execution)
