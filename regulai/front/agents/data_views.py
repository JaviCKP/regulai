"""One trusted result gate. Raw arbitrary-code output never becomes model data."""
import csv
import base64
import io
import json
from pathlib import PurePosixPath

from front.models import AgentArtifact, AgentInference, AgentInput, AgentToolResult
from front.policy import digest
from .aliases import alias_value
from .protocol import ToolCall, ToolResultRequest, validate_arguments
from .service import AgentDenied, authenticate


def authorize_tool(token, attempt, payload):
    call = ToolCall.model_validate(payload)
    execution, context = authenticate(token, attempt)
    if call.name not in context[2].tools:
        raise AgentDenied('tool_not_allowed')
    validate_arguments(call)
    issued = [c for row in AgentInference.objects.filter(execution=execution, status='completed')
              for c in row.response.get('tool_calls', [])]
    if call.model_dump() not in issued:
        raise AgentDenied('unissued_tool_call')
    if call.name in ('build_excel', 'rename_excel'):
        from .excel_contract import valid_title
        valid_title(call.args['title'])
        job = execution.job
        if ((call.name == 'build_excel' and (job.get('kind') != 'build'
                or call.args['input_reference'] != job.get('source')))
                or (call.name == 'rename_excel' and (job.get('kind') != 'rename'
                or call.args['logical_id'] != job.get('logical_id')
                or call.args['base_revision'] != job.get('base')))):
            raise AgentDenied('artifact_reference_denied')
    for key in ('input_path', 'file_path', 'path'):
        if key not in call.args:
            continue
        path = PurePosixPath(call.args[key])
        if not path.is_absolute() or '..' in path.parts or not str(path).startswith('/workspace/'):
            raise AgentDenied('tool_path_denied')
        if call.name in ('write_file', 'edit_file') and not str(path).startswith(('/workspace/work/', '/workspace/output/')):
            raise AgentDenied('tool_path_denied')
    return execution, context, call


def grant_csv(execution, *, path, content):
    """Trusted application grant; no executor-facing upload/originals endpoint."""
    if not path.startswith('/workspace/input/') or '..' in PurePosixPath(path).parts:
        raise AgentDenied('invalid_input_path')
    if not isinstance(content, str) or len(content.encode()) > 512_000:
        raise AgentDenied('invalid_input')
    return AgentInput.objects.create(execution=execution, kind='csv', path=path,
        original=content, digest=digest(content))


def render_approved_view(execution, result):
    """Trusted vision input derived only from an already approved result view.

    Raw table renders and user previews are deliberately not accepted here.
    Later document work must supply its own reviewed projection before rendering.
    """
    from PIL import Image, ImageDraw
    result = AgentToolResult.objects.get(pk=result.pk, execution=execution)
    if result.view.get('status') != 'approved':
        raise AgentDenied('unapproved_model_image')
    lines = json.dumps(result.view, sort_keys=True, indent=2, ensure_ascii=True).splitlines()
    if len(lines) > 80 or any(len(line) > 180 for line in lines):
        raise AgentDenied('model_image_too_large')
    image = Image.new('RGB', (1200, max(40, len(lines) * 16 + 20)), 'white')
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((10, 10 + index * 16), line, fill='black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    content = json.dumps({'mime': 'image/png', 'base64': base64.b64encode(output.getvalue()).decode()})
    row, _ = AgentInput.objects.get_or_create(execution=execution, kind='model_image',
        path=f'approved-view-{result.pk}', defaults={'original': content, 'digest': digest(content)})
    return row


def _csv_view(execution, agent, call, raw):
    asset = AgentInput.objects.filter(execution=execution, kind='csv', path=call.args['input_path']).first()
    if not asset or not asset.original or digest(asset.original) != asset.digest:
        raise AgentDenied('input_unavailable')
    reader = csv.DictReader(io.StringIO(asset.original))
    rows = list(reader)
    # The query and grouping are fixed. The model cannot choose individuals or
    # use repeated predicates to extract values via differences between totals.
    if len(rows) < agent.min_group_size:
        return {'status': 'withheld', 'code': 'aggregate_group_too_small'}
    if call.name == 'inspect_csv':
        return {'status': 'approved', 'reference': str(asset.pk), 'rows': len(rows),
            'columns': [{'reference': alias_value(execution, 'FIELD', name),
                         'type': 'integer' if name == 'amount_cents' else 'string'} for name in reader.fieldnames],
            'synthetic_example': {'amount_cents': 100, 'item': 'example'}}
    expected = {'rows': len(rows), 'total_cents': sum(int(row['amount_cents']) for row in rows)}
    # ToolMessage, Command, stdout, stderr, artifact and error are all archived,
    # but only the exact reviewed tool's content is eligible for verification.
    try:
        candidate = json.loads(raw['content'])
    except (ValueError, TypeError, KeyError):
        return {'status': 'withheld', 'code': 'aggregate_not_verified'}
    if (type(candidate) is not dict or set(candidate) != set(expected)
            or any(type(candidate[k]) is not int or candidate[k] != expected[k] for k in expected)):
        return {'status': 'withheld', 'code': 'aggregate_not_verified'}
    return {'status': 'approved', **expected}


def tool_result(token, attempt, payload):
    request = ToolResultRequest.model_validate(payload)
    execution, context, call = authorize_tool(token, attempt, request.call.model_dump())
    fingerprint = digest(request.model_dump())
    previous = AgentToolResult.objects.filter(execution=execution, call_id=call.id).first()
    if previous:
        if previous.request_digest != fingerprint:
            raise AgentDenied('tool_result_id_conflict')
        return previous.view
    # Fixed views are intentionally unable to encode arbitrary output. Do not
    # replace this with a regex or a model-generated "safe summary" of raw logs.
    view = {'status': 'withheld', 'code': 'raw_tool_output_withheld'}
    if request.failed:
        view = {'status': 'withheld', 'code': 'tool_failed'}
    elif call.name in ('csv_totals', 'inspect_csv'):
        try:
            view = _csv_view(execution, context[2], call, request.raw)
        except (ValueError, TypeError, KeyError, csv.Error):
            view = {'status': 'withheld', 'code': 'aggregate_not_verified'}
    elif call.name in ('build_excel', 'rename_excel'):
        # The executor returns an opaque candidate reference. Approval and the
        # aggregate come only from the independent application verifier.
        try:
            reference = json.loads(request.raw['content'])['reference']
            artifact = AgentArtifact.objects.get(pk=reference, execution=execution,
                status='verified', verification__call_id=call.id)
            from .jobs import _bytes
            _bytes(artifact)
            view = {'status': 'approved', 'reference': str(artifact.pk),
                'logical_id': str(artifact.logical_id), 'revision': artifact.revision,
                'rows': artifact.verification['rows'], 'total_cents': artifact.verification['total_cents']}
        except (ValueError, TypeError, KeyError, AgentArtifact.DoesNotExist):
            view = {'status': 'withheld', 'code': 'excel_not_verified'}
    authenticate(token, attempt)
    record, created = AgentToolResult.objects.get_or_create(execution=execution, call_id=call.id,
        defaults={'request_digest': fingerprint, 'view': view,
                  'raw': json.dumps(request.raw, ensure_ascii=False, allow_nan=False)})
    if not created and record.request_digest != fingerprint:
        raise AgentDenied('tool_result_id_conflict')
    return record.view
