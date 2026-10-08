"""Trusted chat orchestration. All database access stays in the application."""
import base64
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import PurePath
import secrets
import uuid
import zipfile
import xml.etree.ElementTree as ET

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from front.access import authorized_conversations
from front.models import (AgentArtifact, AgentEvent, AgentExecution, AgentInput,
                         Conversation, Message, Profile, Prompt, Response)
from front.policy import digest
from .excel_contract import MAX_BYTES, input_rows, sha256, valid_title, verify
from .service import AgentDenied, _context, authenticate, begin_execution

LIVE = ('queued', 'active', 'outcome_unknown')
LEASE_SECONDS = 60
MAX_RUN_SECONDS = 3600
EVENT_TEXT = {
    'queued': 'Petición aceptada. Esperando un entorno limpio disponible.',
    'claimed': 'Entorno limpio reservado en exclusiva. Preparando el archivo.',
    'input': 'Leyendo la estructura del archivo autorizado.',
    'calculate': 'Python está calculando y preparando las fórmulas del Excel.',
    'rename': 'Actualizando el título de la revisión actual.',
    'recalculate': 'LibreOffice está recalculando las fórmulas.',
    'verify': 'Reabriendo y comprobando los bytes finales y sus resultados.',
    'compose': 'Preparando el informe sobre la plantilla corporativa.',
    'render': 'Convirtiendo y renderizando todas las páginas de la revisión final.',
    'visual_pending': 'Comprobaciones automáticas completadas. Revisa todas las páginas antes de publicar.',
    'visual_reviewed': 'Revisión visual registrada para estos bytes y estas páginas.',
    'draft': 'La comprobación ha fallado. Se conserva el borrador para reparación local.',
    'verified': 'El Excel ha superado las comprobaciones independientes.',
    'completed': 'Archivo verificado disponible para previsualizar y descargar.',
    'cancelled': 'Ejecución cancelada. No se iniciarán nuevos pasos.',
    'interrupted': 'Ejecución interrumpida. No se repetirán automáticamente operaciones de resultado incierto.',
    'failed': 'No se pudo completar un archivo verificado. Los borradores se conservan.',
}


def development_profile(actor):
    """Explicit laboratory allowlist, empty by default; no account mutations."""
    if (not settings.DEBUG or not getattr(settings, 'REGULAY_AGENT_ENABLED', False)
            or not getattr(settings, 'REGULAY_AGENT_DEVELOPMENT', False) or not actor.is_active
            or not actor.username.startswith('agent-synthetic-')):
        raise AgentDenied('agent_development_only')
    entry = getattr(settings, 'REGULAY_AGENT_DEV_ACCOUNTS', {}).get(str(actor.pk))
    profile = Profile.objects.get(user=actor)
    if not entry or entry.get('company_id') != profile.company_id:
        raise AgentDenied('agent_development_only')
    return int(entry['profile_id'])


def available(actor):
    try:
        development_profile(actor)
        return True
    except (AgentDenied, Profile.DoesNotExist, ValueError, KeyError):
        return False


def event(execution, kind, **data):
    return AgentEvent.objects.create(execution=execution, kind=kind,
        data={'text': EVENT_TEXT[kind], **data})


def _terminal(execution, status):
    execution.status, execution.finished_at = status, timezone.now()
    execution.save(update_fields=['status', 'finished_at'])
    Prompt.objects.filter(pk=execution.prompt_id).update(status=(
        'outcome_unknown' if status == 'interrupted' else status), updated_at=timezone.now())
    event(execution, status)


def reap():
    """Abandoned active jobs have no safe graph checkpoint: stop, never replay."""
    with transaction.atomic():
        for run in AgentExecution.objects.select_for_update(skip_locked=True).filter(
                conversation__isnull=False, status__in=LIVE, expires_at__lte=timezone.now()):
            _terminal(run, 'interrupted')


def _decode(asset):
    raw = base64.b64decode(asset.original, validate=True)
    if sha256(raw) != asset.digest:
        raise AgentDenied('input_digest_changed')
    return raw


def _bytes(artifact):
    raw = base64.b64decode(artifact.content, validate=True)
    if sha256(raw) != artifact.sha256 or artifact.verification.get('sha256') != artifact.sha256:
        raise AgentDenied('artifact_digest_changed')
    return raw


def latest(conversation, logical_id):
    return AgentArtifact.objects.filter(execution__conversation=conversation, logical_id=logical_id,
        status='verified', execution__status='completed').order_by('-revision').first()


def _base(conversation, logical_id, base_id):
    try:
        row = latest(conversation, uuid.UUID(str(logical_id)))
    except (ValueError, TypeError):
        raise AgentDenied('artifact_not_found') from None
    if not row or str(row.pk) != str(base_id):
        raise AgentDenied('artifact_revision_stale')
    _bytes(row)
    return row


def enqueue(actor, command, conversation, text, request_id):
    from front.chat_service import error_result
    try:
        profile_id = development_profile(actor)
        if conversation and conversation.mode != 'agent':
            raise AgentDenied('conversation_mode_immutable')
        uploaded = command.get('file')
        raw = uploaded.read(MAX_BYTES + 1) if uploaded else None
        kind = PurePath(uploaded.name).suffix.lower().lstrip('.') if uploaded else None
        rows = input_rows(raw, kind) if uploaded else None
        fingerprint = digest([text, sha256(raw) if raw else None, 'agent',
                              command.get('artifact_id'), command.get('base_revision')])
        reap()
        with transaction.atomic():
            previous = Prompt.objects.filter(user=actor, request_id=request_id).first()
            if previous:
                if (previous.company_id != actor.profile.company_id
                        or previous.decision.get('input_digest') != fingerprint
                        or (conversation and previous.conversation_id != conversation.pk)):
                    return error_result('idempotency_conflict', 409)
                run = AgentExecution.objects.get(prompt=previous)
                authorized_run(actor, run.pk)
                return accepted(run)
            if conversation:
                conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
                if AgentExecution.objects.filter(conversation=conversation, status__in=LIVE).exists():
                    return error_result('agent_conversation_busy', 409)
            else:
                conversation = Conversation.objects.create(user=actor, mode='agent', title=text[:50] or 'Excel')
            base = None
            if command.get('artifact_id') or command.get('base_revision'):
                if uploaded:
                    raise AgentDenied('revision_input_immutable')
                base = _base(conversation, command.get('artifact_id'), command.get('base_revision'))
            elif not uploaded:
                raise AgentDenied('agent_input_required')
            message = Message.objects.create(conversation=conversation, role='user', content=text,
                file_name=PurePath(uploaded.name).name[:255] if uploaded else None,
                file_size=len(raw) if raw else 0)
            prompt = Prompt.objects.create(user=actor, company_id=actor.profile.company_id,
                conversation=conversation, user_message=message, content=text, request_id=request_id,
                status='processing', file_name=message.file_name, file_size=message.file_size,
                file_sha256=sha256(raw) if raw else None,
                decision={'schema_version': 1, 'input_digest': fingerprint, 'calls': []})
            run, _ = begin_execution(prompt, profile_id)
            run.conversation = conversation
            if uploaded:
                asset = AgentInput.objects.create(execution=run, kind=kind,
                    path='/workspace/input/source.' + kind,
                    original=base64.b64encode(raw).decode(), digest=sha256(raw))
            else:
                original = base.source
                asset = AgentInput.objects.create(execution=run, kind=original.kind, path=original.path,
                    original=original.original, digest=original.digest)
                rows = input_rows(_decode(asset), asset.kind)
            context = _context(prompt, profile_id)
            if len(rows) < context[2].min_group_size:
                raise AgentDenied('aggregate_group_too_small')
            run.authorization_digest = context[-1]
            run.status = 'queued'
            run.expires_at = timezone.now() + timedelta(seconds=MAX_RUN_SECONDS)
            run.job = {'source': str(asset.pk), 'logical_id': str(base.logical_id if base else uuid.uuid4()),
                'base': str(base.pk) if base else None, 'kind': 'rename' if base else 'build'}
            run.save()
            prompt.status = 'received'
            prompt.save(update_fields=['status'])
            event(run, 'queued')
            return accepted(run)
    except AgentDenied as error:
        return error_result(error.code, 409 if 'stale' in error.code else 403)
    except (ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile, ET.ParseError, OSError):
        return error_result('agent_input_invalid')


def accepted(run):
    from front.chat_service import request_result
    run.prompt.refresh_from_db()
    result = request_result(run.prompt)
    result.data.update(success=True, mode='agent', agent=run_data(run))
    if run.status in LIVE:
        result.data['status'] = 'accepted'
        result.http_status = 202
    return result


def run_data(run):
    return {'id': str(run.pk), 'status': run.status,
        'events_url': f'/chat/agent/runs/{run.pk}/events/',
        'status_url': f'/chat/agent/runs/{run.pk}/',
        'cancel_url': f'/chat/agent/runs/{run.pk}/cancel/'}


def worker_authorized(token):
    expected = getattr(settings, 'REGULAY_AGENT_WORKER_TOKEN', '')
    if (not settings.DEBUG or not getattr(settings, 'REGULAY_AGENT_DEVELOPMENT', False)
            or not getattr(settings, 'REGULAY_AGENT_ENABLED', False)
            or len(expected) < 32 or not hmac.compare_digest(token, expected)):
        raise AgentDenied('worker_unauthorized')
    if connection.vendor != 'postgresql':
        raise AgentDenied('agent_postgresql_required')


def claim(token, payload):
    worker_authorized(token)
    if set(payload) != {'worker_id', 'claim_id'}:
        raise ValueError('Invalid claim')
    worker, claim_id = uuid.UUID(payload['worker_id']), uuid.UUID(payload['claim_id'])
    reap()
    with transaction.atomic():
        run = AgentExecution.objects.select_for_update().filter(claim_id=claim_id).first()
        if run:
            if run.worker_id != worker or run.status != 'active' or run.expires_at <= timezone.now():
                raise AgentDenied('claim_no_longer_valid')
        else:
            run = AgentExecution.objects.select_for_update(skip_locked=True).filter(
                status='queued', conversation__isnull=False).order_by('created_at').first()
            if not run:
                return {'status': 'idle'}
            try:
                context = _context(run.prompt, run.profile_id)
                if not hmac.compare_digest(context[-1], run.authorization_digest):
                    raise AgentDenied()
            except AgentDenied:
                _terminal(run, 'interrupted')
                return {'status': 'idle'}
            run.attempt = uuid.uuid4()
            run.claim_id, run.worker_id = claim_id, worker
            run.started_at = timezone.now()
            run.expires_at = run.started_at + timedelta(seconds=LEASE_SECONDS)
            run.status = 'active'
            event(run, 'claimed')
        # Replaying the same claim after a lost HTTP response yields the same
        # credential; it cannot extend the lease or reclaim an old attempt.
        credential = hmac.new(token.encode(), f'{run.pk}:{run.attempt}:{claim_id}'.encode(), hashlib.sha256).hexdigest()
        run.token_digest = sha256(credential.encode())
        run.save()
        Prompt.objects.filter(pk=run.prompt_id).update(status='processing', updated_at=timezone.now())
        return {'status': 'claimed', 'execution': str(run.pk), 'attempt': str(run.attempt),
                'token': credential, 'lease_seconds': LEASE_SECONDS}


@contextmanager
def locked(token, attempt):
    first, _ = authenticate(token, attempt)
    with transaction.atomic():
        run = AgentExecution.objects.select_for_update().get(pk=first.pk)
        fresh, context = authenticate(token, attempt)
        if fresh.status != 'active' or run.status != 'active':
            raise AgentDenied('attempt_not_active')
        yield run, context


def renew(token, attempt, payload):
    if payload:
        raise ValueError('Invalid renewal')
    with locked(token, attempt) as (run, _):
        if not run.started_at or timezone.now() >= run.started_at + timedelta(seconds=MAX_RUN_SECONDS):
            raise AgentDenied('execution_deadline')
        # Never renew expired credentials. No worker/master credential is accepted
        # here, and a lost/old attempt has no recovery path back to authority.
        run.expires_at = min(timezone.now() + timedelta(seconds=LEASE_SECONDS),
                             run.started_at + timedelta(seconds=MAX_RUN_SECONDS))
        run.save(update_fields=['expires_at'])
        return {'status': 'authorized', 'lease_seconds': LEASE_SECONDS}


def bootstrap(token, attempt, payload):
    if payload:
        raise ValueError('Invalid bootstrap')
    with locked(token, attempt) as (run, context):
        from .aliases import alias_text, alias_value
        asset = AgentInput.objects.get(pk=run.job['source'], execution=run)
        rows = input_rows(_decode(asset), asset.kind)
        # Originals travel only through this private executor operation, never
        # through a model/tool result. The SDK receives just model_context below.
        model_context = {'operation': run.job['kind'], 'input_reference': str(asset.pk),
            'logical_id': run.job['logical_id'], 'base_revision': run.job['base'], 'rows': len(rows),
            'columns': [alias_value(run, 'FIELD', name) for name in ('item', 'amount_cents')],
            'synthetic_example': {'item': 'Ejemplo', 'amount_cents': 125}}
        base = _base(run.conversation, run.job['logical_id'], run.job['base']) if run.job['base'] else None
        model_context['base_format'] = base.format if base else None
        companion = None
        if base and base.format in ('docx', 'pdf') and base.render_bundle:
            from .document_jobs import source_document
            companion = base64.b64encode(source_document(base)).decode()
        return {'status': 'authorized', 'input': {'path': asset.path, 'base64': asset.original,
            'sha256': asset.digest, 'kind': asset.kind},
            'base': base64.b64encode(_bytes(base)).decode() if base else None,
            'base_format': base.format if base else None, 'base_docx': companion,
            'model_context': model_context, 'message': alias_text(run, run.prompt.content),
            'tools': [name for name in context[2].tools if name in ('build_excel', 'rename_excel',
                'build_document', 'edit_document', 'export_pdf', 'build_presentation', 'edit_presentation')]}


def step(token, attempt, payload):
    from .data_views import authorize_tool
    if set(payload) != {'call', 'phase'} or payload['phase'] not in ('input', 'calculate', 'rename', 'recalculate', 'verify', 'compose', 'render'):
        raise ValueError('Invalid step')
    with locked(token, attempt) as (run, _):
        _, _, call = authorize_tool(token, attempt, payload['call'])
        if call.name not in ('build_excel', 'rename_excel', 'build_document', 'edit_document', 'export_pdf', 'build_presentation', 'edit_presentation'):
            raise AgentDenied('tool_not_allowed')
        if run.events.filter(kind=payload['phase'], data__call_id=call.id).exists():
            raise AgentDenied('step_already_started')
        event(run, payload['phase'], call_id=call.id)
        return {'status': 'authorized'}


def candidate(token, attempt, payload):
    from .data_views import authorize_tool
    from .aliases import resolve_for_operation, TOKEN as TOKEN_RE
    if 'document_bundle' in payload:
        from .document_jobs import candidate as document_candidate
        return document_candidate(token, attempt, payload)
    if set(payload) != {'operation_id', 'call', 'base64'}:
        raise ValueError('Invalid candidate')
    operation_id = uuid.UUID(payload['operation_id'])
    run, context, call = authorize_tool(token, attempt, payload['call'])
    if call.name not in ('build_excel', 'rename_excel') or len(payload['base64']) > MAX_BYTES * 2:
        raise AgentDenied('candidate_denied')
    raw = base64.b64decode(payload['base64'], validate=True)
    title = call.args['title']
    # Resolve only registered references for this concrete local document field.
    tokens = [match.group(0) for match in TOKEN_RE.finditer(title)]
    if tokens:
        for alias, original in resolve_for_operation(run, tokens, operation='local_document_fields').items():
            title = title.replace(alias, original)
    title = valid_title(title)
    asset = AgentInput.objects.get(pk=run.job['source'], execution=run)
    base = _base(run.conversation, run.job['logical_id'], run.job['base']) if run.job['base'] else None
    try:
        proof, _ = verify(raw, _decode(asset), asset.kind, title=title, base=_bytes(base) if base else None)
        verified = True
    except Exception:
        proof, verified = {'code': 'excel_verification_failed', 'sha256': sha256(raw)}, False
    with locked(token, attempt) as (run, _):
        prior = AgentArtifact.objects.filter(execution=run, operation_id=operation_id).first()
        if prior:
            if prior.sha256 != sha256(raw) or prior.verification.get('call_id') != call.id:
                raise AgentDenied('candidate_id_conflict')
            return {'status': 'approved' if prior.status == 'verified' else 'withheld', 'reference': str(prior.pk)}
        if run.job['base']:
            _base(run.conversation, run.job['logical_id'], run.job['base'])
        revision = (AgentArtifact.objects.filter(logical_id=run.job['logical_id']).aggregate(n=Max('revision'))['n'] or 0) + 1
        artifact = AgentArtifact.objects.create(execution=run, logical_id=run.job['logical_id'], revision=revision,
            base=base, source=asset, operation_id=operation_id, content=base64.b64encode(raw).decode(),
            sha256=sha256(raw), status='verified' if verified else 'draft',
            verification={**proof, 'call_id': call.id})
        event(run, 'verified' if verified else 'draft', reference=str(artifact.pk))
        return {'status': 'approved' if verified else 'withheld', 'reference': str(artifact.pk)}


def local_fields(token, attempt, payload):
    """Reviewed tool preparation; neither this response nor its raw fields enter the graph."""
    from .data_views import authorize_tool
    from .aliases import resolve_for_operation, TOKEN as TOKEN_RE
    run, _, call = authorize_tool(token, attempt, payload)
    if call.name in ('build_document', 'edit_document', 'export_pdf', 'build_presentation', 'edit_presentation'):
        from .document_jobs import local_fields as document_fields
        return document_fields(run, call)
    title = call.args.get('title')
    valid_title(title)
    aliases = [m.group(0) for m in TOKEN_RE.finditer(title)]
    if aliases:
        for alias, original in resolve_for_operation(run, aliases, operation='local_document_fields').items():
            title = title.replace(alias, original)
    return {'status': 'authorized', 'title': valid_title(title)}


def complete(token, attempt, payload):
    if payload:
        raise ValueError('Invalid completion')
    with locked(token, attempt) as (run, _):
        artifact = run.artifacts.order_by('-revision').first()
        if not artifact or artifact.status != 'verified' or run.active_call:
            raise AgentDenied('verified_artifact_required')
        _bytes(artifact)
        if run.job['base']:
            _base(run.conversation, run.job['logical_id'], run.job['base'])
        message = Message.objects.create(conversation=run.conversation, role='assistant',
            content=('Excel verificado. Fórmulas y totales comprobados; preview y descarga disponibles.'
                if artifact.format == 'xlsx' else 'Documento verificado y revisado visualmente. Preview y descarga disponibles.'))
        Response.objects.create(prompt=run.prompt, assistant_message=message, content=message.content,
            evidence={'artifact': str(artifact.pk), 'sha256': artifact.sha256})
        prompt = run.prompt
        prompt.decision['verification'] = {'status': 'passed', **artifact.verification}
        prompt.save(update_fields=['decision'])
        _terminal(run, 'completed')
        return {'status': 'completed'}


def fail(token, attempt, payload):
    if payload:
        raise ValueError('Invalid failure')
    with locked(token, attempt) as (run, _):
        _terminal(run, 'interrupted' if run.active_call else 'failed')
    return {'status': 'completed'}


def authorized_run(actor, run_id):
    # Re-evaluate membership on each SSE batch, read and download, including after
    # a user changes company or an administrator revokes the profile/connection.
    run = AgentExecution.objects.select_related('prompt__user', 'conversation').filter(pk=run_id,
        prompt__user=actor, conversation__in=authorized_conversations(actor)).first()
    if not run or development_profile(actor) != run.profile_id:
        raise AgentDenied('agent_not_found')
    _context(run.prompt, run.profile_id)
    return run


def cancel(actor, run_id):
    authorized_run(actor, run_id)
    with transaction.atomic():
        run = AgentExecution.objects.select_for_update().get(pk=run_id)
        if run.status in LIVE:
            _terminal(run, 'cancelled')
    return run_data(run)


def artifact_data(artifact):
    if artifact.format != 'xlsx':
        from .document_jobs import artifact_data as document_data
        return document_data(artifact)
    raw = _bytes(artifact)
    from .excel_contract import workbook
    book = workbook(raw)
    title = book.active['A1'].value
    book.close()
    _, preview = verify(raw, _decode(artifact.source), artifact.source.kind, title=title)
    return {'id': str(artifact.pk), 'logical_id': str(artifact.logical_id), 'revision': artifact.revision,
        'sha256': artifact.sha256, 'format': 'xlsx', 'status': artifact.status, 'preview': preview,
        'download_url': f'/chat/agent/artifacts/{artifact.pk}/download/'}
