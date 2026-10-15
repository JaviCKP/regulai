"""Safe-boundary recovery. A checkpoint is data, never execution authority."""
import base64
from datetime import timedelta
import hmac
import io
import json
from pathlib import PurePosixPath
import stat
import uuid
import zipfile

from django.db import transaction
from django.utils import timezone
from front.models import AgentExecution, AgentInference, AgentInput, AgentOperation
from front.policy import digest
from .service import AgentDenied, _context, _validate_tool_history
from .protocol import InferenceRequest
from .checkpoint_runner import runtime_link_target


def watermark(run):
    return {'inferences': list(AgentInference.objects.filter(execution=run).order_by('id').values_list('id', 'status')),
        'operations': list(AgentOperation.objects.filter(execution=run).order_by('id').values_list('id', 'status'))}


def validate_archive(raw, budget):
    if len(raw) > budget['file_bytes']:
        raise ValueError('checkpoint_size_limit')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        items = archive.infolist()
        if len(items) > 20000 or sum(item.file_size for item in items) > budget['workspace_bytes']:
            raise ValueError('checkpoint_workspace_limit')
        if len({item.filename for item in items}) != len(items):
            raise ValueError('checkpoint_duplicate_path')
        runtime_links = set()
        for item in items:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or not path.parts
                    or len(item.filename) > 4096 or path.parts[0] not in ('work', 'output') or item.flag_bits & 1
                    or item.file_size > budget['file_bytes']):
                raise ValueError('checkpoint_path_denied')
            if stat.S_ISLNK(mode):
                if item.file_size > 4096:
                    raise ValueError('checkpoint_runtime_link_limit')
                runtime_link_target(archive.read(item).decode('utf-8'))
                runtime_links.add(str(path))
        if any(str(parent) in runtime_links for item in items for parent in PurePosixPath(item.filename).parents):
            raise ValueError('checkpoint_symlink_ancestor_denied')
        if archive.testzip() is not None:
            raise ValueError('checkpoint_corrupt')


def save(token, attempt, payload):
    from . import jobs
    if set(payload) != {'messages', 'wire_messages', 'archive', 'runtime_sha256'}:
        raise ValueError('Invalid checkpoint')
    if not isinstance(payload['messages'], list) or len(payload['messages']) > 1000:
        raise ValueError('Checkpoint messages limit')
    if any(not isinstance(m, dict) or m.get('type') not in ('human', 'ai', 'tool', 'system') for m in payload['messages']):
        raise ValueError('Checkpoint message type')
    raw = base64.b64decode(payload['archive'], validate=True)
    with jobs.locked(token, attempt) as (run, _):
        if run.job.get('kind') != 'professional' or run.active_call:
            raise AgentDenied('checkpoint_requires_idle_boundary')
        request = InferenceRequest(call_id=str(uuid.uuid4()), messages=payload['wire_messages'], tools=[])
        _validate_tool_history(run, request)
        validate_archive(raw, run.job['limits'])
        mark = watermark(run)
        if any(status != 'completed' for _, status in mark['operations']) or any(
                status not in ('completed', 'rejected') for _, status in mark['inferences']):
            raise AgentDenied('checkpoint_outcome_uncertain')
        packed = json.dumps({**payload, 'watermark': mark}, ensure_ascii=False)
        row, _ = AgentInput.objects.update_or_create(execution=run, path='checkpoint/latest',
            defaults={'kind': 'checkpoint', 'original': packed, 'digest': digest(packed)})
        run.job['checkpoint'] = str(row.pk)
        run.job['checkpoint_at'] = timezone.now().isoformat()
        run.save(update_fields=['job'])
    return {'status': 'completed'}


def load(run):
    row = AgentInput.objects.filter(execution=run, kind='checkpoint', pk=run.job.get('checkpoint')).first()
    if not row or not hmac.compare_digest(digest(row.original), row.digest):
        raise AgentDenied('checkpoint_unavailable')
    value = json.loads(row.original)
    # JSON normalizes watermark tuples to lists.
    if digest(value['watermark']) != digest(watermark(run)) or run.active_call:
        raise AgentDenied('checkpoint_has_later_or_uncertain_operations')
    return value


def resumable(run):
    if run.job.get('kind') != 'professional' or run.job.get('expired') or run.status not in ('interrupted', 'failed', 'cancelled'):
        return False
    try:
        load(run)
        return True
    except AgentDenied:
        return False


def resume(actor, run_id):
    from . import jobs
    jobs.authorized_run(actor, run_id)
    with transaction.atomic():
        run = AgentExecution.objects.select_for_update().get(pk=run_id)
        if not resumable(run) or run.job.get('resumes', 0) >= 3:
            raise AgentDenied('checkpoint_resume_unavailable')
        if not hmac.compare_digest(_context(run.prompt, run.profile_id)[-1], run.authorization_digest):
            raise AgentDenied('authorization_changed')
        if AgentExecution.objects.filter(conversation=run.conversation, status__in=jobs.LIVE).exclude(pk=run.pk).exists():
            raise AgentDenied('agent_conversation_busy')
        # Keep the original deadline and all usage. Resume adds no free budget.
        if run.started_at and (timezone.now() - run.started_at).total_seconds() >= run.job['limits']['run_seconds']:
            raise AgentDenied('execution_deadline')
        run.status, run.claim_id, run.worker_id = 'queued', None, None
        run.job['resumes'] = run.job.get('resumes', 0) + 1
        run.job['restore_checkpoint'] = True
        run.expires_at = timezone.now() + timedelta(seconds=jobs.LEASE_SECONDS)
        run.finished_at = None
        run.save()
        jobs.event(run, 'recovered')
    return {'run': jobs.run_data(run)}
