"""General jobs on the existing chat, identity, lease and artifact lifecycle."""
import base64
from datetime import timedelta
import io
import json
from pathlib import PurePath
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from front.models import AgentArtifact, AgentExecution, AgentInference, AgentInput, AgentModelProfile, Conversation, Message, Prompt, Response
from front.policy import digest
from .capabilities import GENERAL, limits
from .excel_contract import sha256
from .request_contract import interpret
from .service import AgentDenied, _context, begin_execution


def inspect_input(raw, kind):
    """The same full extraction used by policy, including all workbook sheets."""
    if kind == 'pptx':
        from .professional_artifacts import office_parts
        parts = office_parts(raw)
        texts = [' '.join(ET.fromstring(value).itertext()) for name, value in parts.items()
            if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
        return {'text': '\n'.join(texts), 'format': kind, 'status': 'complete', 'units_total': len(texts)}
    from front.documents import extract_document
    document = extract_document(SimpleUploadedFile('source.' + kind, raw))
    if document.status == 'unreadable' or not document.text:
        raise AgentDenied('agent_input_unreadable')
    # Local calculation may retain originals with partial visual coverage; the
    # policy must see every extractable text unit, never a truncated prefix.
    if any(x in document.warnings for x in ('text_limit', 'fragment_limit', 'parser_timeout', 'parser_error')):
        raise AgentDenied('agent_input_policy_coverage_incomplete')
    return {'text': document.text, **document.metadata()}


def enqueue(actor, command, conversation, text, request_id, profile_id):
    from front.chat_service import error_result
    from . import jobs
    if conversation and conversation.mode != 'agent':
        raise AgentDenied('conversation_mode_immutable')
    profile = AgentModelProfile.objects.get(pk=profile_id)
    budget = limits(profile)
    upload = command.get('file')
    if command.get('document_reference'):
        if upload:
            raise AgentDenied('document_input_conflict')
        from .document_mcp import obtain
        data, kind = obtain(actor, command['document_reference'])
        upload = SimpleUploadedFile('document.' + kind, data)
    raw = upload.read(budget['file_bytes'] + 1) if upload else None
    kind = PurePath(upload.name).suffix.lower().lstrip('.') if upload else None
    if raw is not None:
        if not raw or len(raw) > budget['file_bytes']:
            raise AgentDenied('agent_input_size_limit')
        inspection = inspect_input(raw, kind)
    else:
        inspection = None
    fingerprint = digest([text, sha256(raw) if raw else None, 'professional-v1',
        command.get('artifact_id'), command.get('base_revision'), command.get('document_reference')])
    jobs.reap()
    with transaction.atomic():
        previous = Prompt.objects.filter(user=actor, request_id=request_id).first()
        if previous:
            if (previous.company_id != actor.profile.company_id or previous.decision.get('input_digest') != fingerprint
                    or conversation and previous.conversation_id != conversation.pk):
                return error_result('idempotency_conflict', 409)
            return jobs.accepted(jobs.authorized_run(actor, previous.agentexecution.pk))
        if conversation:
            conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
            if AgentExecution.objects.filter(conversation=conversation, status__in=jobs.LIVE).exists():
                return error_result('agent_conversation_busy', 409)
        else:
            conversation = Conversation.objects.create(user=actor, mode='agent', title=text[:50] or 'Agente')
        base = None
        if command.get('artifact_id') or command.get('base_revision'):
            if upload:
                raise AgentDenied('revision_input_immutable')
            base = jobs._base(conversation, command.get('artifact_id'), command.get('base_revision'))
            raw, kind = jobs._bytes(base), base.format
            inspection = inspect_input(raw, kind)
        requested = interpret(text, uploaded=bool(upload), base_format=base.format if base else None, general=True)
        message = Message.objects.create(conversation=conversation, role='user', content=text,
            file_name=PurePath(upload.name).name[:255] if upload else None, file_size=len(raw) if raw else 0)
        prompt = Prompt.objects.create(user=actor, company_id=actor.profile.company_id, conversation=conversation,
            user_message=message, content=text, request_id=request_id, status='processing',
            file_name=message.file_name, file_size=message.file_size, file_sha256=sha256(raw) if raw else None,
            decision={'schema_version': 1, 'input_digest': fingerprint, 'calls': []})
        run, _ = begin_execution(prompt, profile_id)
        asset = None
        if raw is not None:
            asset = AgentInput.objects.create(execution=run, kind='private_file', path='/workspace/input/source.' + kind,
                original=base64.b64encode(raw).decode(), digest=sha256(raw))
            # Cached full extraction is encrypted; never bootstrap it into the model.
            packed = json.dumps(inspection, ensure_ascii=False)
            AgentInput.objects.create(execution=run, kind='policy_text', path='policy/source', original=packed, digest=digest(packed))
        manifest = json.dumps({'input_sha256': sha256(raw) if raw else None, 'base': str(base.pk) if base else None})
        source = AgentInput.objects.create(execution=run, kind='manifest', path='manifest', original=manifest, digest=digest(manifest))
        run.conversation = conversation
        run.job = {'kind': 'professional', 'source': str(asset.pk) if asset else None, 'source_kind': kind,
            'manifest': str(source.pk), 'base': str(base.pk) if base else None,
            'logical_id': str(base.logical_id if base else uuid.uuid4()), 'request': requested,
            'private_data': bool(asset), 'network_sealed': False, 'limits': budget}
        run.authorization_digest = _context(prompt, profile_id)[-1]
        run.status = 'queued'
        run.expires_at = timezone.now() + timedelta(seconds=budget['run_seconds'])
        run.save()
        prompt.status = 'received'
        prompt.save(update_fields=['status'])
        jobs.event(run, 'queued')
        return jobs.accepted(run)


def bootstrap(run, context):
    from .aliases import alias_text
    from . import jobs
    asset = AgentInput.objects.get(pk=run.job['source'], execution=run) if run.job.get('source') else None
    tools = sorted(set(context[2].tools) & GENERAL)
    from django.conf import settings
    from .capabilities import WEB, search_configuration
    if not getattr(settings, 'REGULAY_AGENT_WEB_ENABLED', False):
        tools = [name for name in tools if name not in WEB]
    try:
        search_configuration(context[2])
    except AgentDenied:
        tools = [name for name in tools if name != 'web_search']
    if not getattr(settings, 'REGULAY_AGENT_PACKAGES_ENABLED', False):
        tools = [name for name in tools if name != 'install_packages']
    if not getattr(settings, 'REGULAY_AGENT_BROWSER_ENABLED', False):
        tools = [name for name in tools if name != 'web_browse']
    if not context[2].vision or not context[5].supports_vision or run.job.get('private_data') or not context[3].limits.provider_managed:
        tools = [name for name in tools if name != 'inspect_image']
    base = jobs._base(run.conversation, run.job['logical_id'], run.job['base']) if run.job.get('base') else None
    from .checkpoints import load
    return {'status': 'authorized', 'execution': str(run.pk), 'input': {'path': asset.path, 'base64': asset.original,
            'sha256': asset.digest} if asset else None, 'base': None, 'base_format': base.format if base else None,
        'message': alias_text(run, run.prompt.content), 'tools': tools, 'limits': run.job['limits'],
        'checkpoint': load(run) if run.job.get('restore_checkpoint') else None,
        'model_context': {'operation': 'professional', 'request': run.job['request'],
            'date': timezone.now().isoformat(), 'input_path': asset.path if asset else None,
            'base_revision': str(base.pk) if base else None, 'private_data': run.job['private_data'],
            'network_policy': 'Public research and package preparation first. Network closes irreversibly on the first workspace operation when private inputs are present.',
            'limits': run.job['limits'], 'vision': 'inspect_image' in tools}}


def complete(token, attempt, payload):
    from . import jobs
    from .web_tools import consulted_sources
    from .professional_artifacts import current_artifacts
    if set(payload) != {'final_call_id'}:
        raise ValueError('Invalid professional completion')
    with jobs.locked(token, attempt) as (run, _):
        if run.active_call:
            raise AgentDenied('execution_busy_or_uncertain')
        final = AgentInference.objects.filter(execution=run, status='completed').order_by('-id').first()
        if (not final or str(final.call_id) != payload['final_call_id'] or final.response.get('tool_calls')
                or not isinstance(final.response.get('content'), str)):
            raise AgentDenied('final_inference_required')
        content = final.response['content']
        artifacts = [item for item in current_artifacts(run) if item.status == 'verified']
        requested = run.job['request']
        formats = {item.format for item in artifacts}
        if any(item.format == 'docx' and item.verification.get('pdf_sha256') for item in artifacts):
            formats.add('pdf')
        missing = set(requested['formats']) - formats
        problems = ['missing_format:' + value for value in sorted(missing)]
        if requested.get('pages'):
            for item in artifacts:
                if item.format in ('docx', 'pdf', 'pptx') and item.verification.get('pages') != requested['pages']:
                    problems.append('page_count_mismatch')
        sources = consulted_sources(run)
        urls = {s['url'] for s in sources.values()} | {s['final_url'] for s in sources.values()}
        if any(url not in urls for url in re.findall(r'\]\((https?://[^\s)]+)\)', content)):
            problems.append('citation_not_opened')
        if requested.get('research_required') and not sources:
            problems.append('research_not_completed')
        if {'docx', 'pdf'} <= set(requested['formats']):
            pdf_hashes = {a.sha256 for a in artifacts if a.format == 'pdf'} | {
                a.verification.get('pdf_sha256') for a in artifacts if a.format == 'docx'}
            if any(a.verification.get('pdf_sha256') not in pdf_hashes for a in artifacts if a.format == 'docx'):
                problems.append('word_pdf_content_pair_required')
        if problems:
            return {'status': 'authorized', 'completed': False, 'problems': sorted(set(problems))}
        if run.job.get('base'):
            jobs._base(run.conversation, run.job['logical_id'], run.job['base'])
        for item in artifacts:
            jobs._bytes(item)
        message = Message.objects.create(conversation=run.conversation, role='assistant', content=content)
        Response.objects.create(prompt=run.prompt, assistant_message=message, content=content,
            evidence={'artifacts': [{'id': str(a.pk), 'sha256': a.sha256} for a in artifacts], 'sources': list(sources)})
        run.prompt.decision['verification'] = {'status': 'partial', 'scope': 'artifact_integrity_and_declared_coverage',
            'artifacts': [str(a.pk) for a in artifacts], 'semantic_quality': 'not_guaranteed'}
        run.prompt.save(update_fields=['decision'])
        jobs._terminal(run, 'completed')
        return {'status': 'completed', 'completed': True}
