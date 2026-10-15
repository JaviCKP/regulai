"""Separate pinned-SDK executor. No Django, database, aliases or provider keys."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import signal
import threading
import time
import uuid

import httpx
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_e2b import E2BSandbox

from .adapter import InternalClient, InternalOperationError, build_agent
from .sandbox_pool import CleanPool, create_clean


def runtime_prompt(tools=()):
    root = Path(__file__).with_name('runtime')
    names = ['system.md', 'documents.md', 'design.md']
    if any(name in tools for name in ('create_mock_excel', 'build_excel', 'rename_excel')):
        names += ['skills/excel/SKILL.md']
    if any(name in tools for name in ('build_document', 'edit_document', 'export_pdf')):
        names += ['skills/docx/SKILL.md', 'skills/pdf/SKILL.md']
    if any(name in tools for name in ('build_presentation', 'edit_presentation')):
        names += ['skills/pptx/SKILL.md']
    return '\n\n'.join((root / name).read_text(encoding='utf-8') for name in names)


class Lease:
    def __init__(self, internal, sandbox):
        self.internal, self.sandbox = internal, sandbox
        self.stop, self.lost = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self._renew, daemon=True)

    def _renew(self):
        while not self.stop.wait(15):
            try:
                self.internal.operation('run/renew', {})
                self.sandbox.set_timeout(180)
            except Exception:
                self.lost.set()
                # Cancellation/revocation stops the active command, not merely
                # the next tool. TTL remains the fallback for a transport loss.
                try:
                    self.sandbox.kill()
                except Exception:
                    pass
                return

    def check(self):
        if self.lost.is_set():
            raise InternalOperationError('Execution lease lost')

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=20)


def run_job(internal, sandbox):
    with Lease(internal, sandbox) as lease:
        granted = internal.operation('run/bootstrap', {})
        if granted['model_context']['operation'] == 'professional':
            from .professional_worker import run_professional
            return run_professional(internal, sandbox, lease, granted)
        if granted['model_context']['operation'] == 'export':
            return run_export(internal, sandbox, lease, granted)
        if granted['input']:
            data = base64.b64decode(granted['input']['base64'], validate=True)
            if hashlib.sha256(data).hexdigest() != granted['input']['sha256']:
                raise InternalOperationError('Input digest changed')
            # This administrative grant is outside the model and graph state.
            sandbox.files.write(granted['input']['path'], data, user='root')
        if granted['base']:
            sandbox.files.write('/workspace/input/base.' + granted.get('base_format', 'xlsx'), base64.b64decode(granted['base']), user='root')
        if granted.get('base_docx'):
            sandbox.files.write('/workspace/input/document.docx', base64.b64decode(granted['base_docx']), user='root')
        sandbox.commands.run(('chmod 0444 /workspace/input/* && ' if granted['input'] else '') + 'chmod 0555 /workspace/input && '
            'mount --bind /workspace/input /workspace/input && mount -o remount,bind,ro /workspace/input',
            user='root', timeout=10)
        backend = E2BSandbox(sandbox=sandbox, workdir='/workspace/work', timeout=90)
        tool_lock = threading.Lock()

        def operate(name, args, runtime):
            # Native parallel tool calls cannot race work/output or the local lease.
            with tool_lock:
                call = {'id': runtime.tool_call_id, 'name': name, 'args': args}
                lease.check()
                fields = internal.operation('run/local-fields', call)
                work = '/workspace/work/' + uuid.uuid4().hex
                logs = []

                def execute(phase, command):
                    lease.check()
                    internal.operation('run/step', {'call': call, 'phase': phase})
                    result = backend.execute(command, timeout=180 if name in ('build_presentation', 'edit_presentation') else 90)
                    logs.append({'phase': phase, 'output': result.output, 'exit_code': result.exit_code})
                    if result.exit_code:
                        raise RuntimeError(json.dumps({'local_operation_failed': logs}))
                    lease.check()

                execute('input', 'mkdir -p ' + work)
                sandbox.files.write(work + '/fields.json', json.dumps({'title': fields['title']}).encode())
                if name in ('build_document', 'edit_document', 'export_pdf', 'build_presentation', 'edit_presentation'):
                    sandbox.files.write(work + '/fields.json', json.dumps(fields).encode())
                    final_dir = work + '/final'
                    presenting = name in ('build_presentation', 'edit_presentation')
                    extension = 'pptx' if presenting else 'docx'
                    narrative = bool(fields.get('narrative'))
                    program = 'python -I /skills/' + ('narrative_program.py ' if narrative else
                        'presentation_program.py ' if presenting else 'document_program.py ')
                    common = ' --output ' + final_dir + (' --extension ' + extension if narrative else '')
                    if narrative and name == 'export_pdf':
                        execute('compose', 'mkdir -p ' + final_dir + ' && cp /workspace/input/document.docx ' + final_dir + '/final.docx')
                    elif narrative:
                        editing = name in ('edit_document', 'edit_presentation')
                        source = '/workspace/input/base.pptx' if presenting else '/workspace/input/document.docx'
                        execute('compose', program + ('edit' if editing else 'build') + common +
                            (' --source ' + shlex.quote(source) if editing else '') + ' --fields ' + work + '/fields.json')
                    elif presenting:
                        source = '/workspace/input/base.pptx' if name == 'edit_presentation' else granted['input']['path']
                        execute('compose', program + ('edit' if name == 'edit_presentation' else 'build') + common +
                            ' --source ' + shlex.quote(source) + ' --template /skills/corporate.pptx --fields ' + work + '/fields.json')
                    elif name == 'export_pdf':
                        execute('compose', 'mkdir -p ' + final_dir + ' && cp /workspace/input/document.docx ' + final_dir + '/final.docx')
                    else:
                        source = ('/workspace/input/document.docx' if name == 'edit_document' else
                            '/workspace/input/base.xlsx' if granted.get('base_format') == 'xlsx' else granted['input']['path'])
                        execute('compose', program + ('edit' if name == 'edit_document' else 'build') + common +
                            ' --source ' + shlex.quote(source) + ' --template /skills/corporate.docx --fields ' + work + '/fields.json')
                    try:
                        execute('render', program + 'render' + common)
                        execute('verify', program + 'seal' + common)
                        downloaded = backend.download_files([final_dir + '/candidate.zip'])[0]
                    except RuntimeError:
                        # Preserve the produced DOCX even when conversion fails.
                        downloaded = backend.download_files([final_dir + '/final.' + extension])[0]
                    if downloaded.error or not downloaded.content:
                        raise RuntimeError('Document candidate unavailable')
                    lease.check()
                    result = internal.operation('run/candidate', {'operation_id': str(uuid.uuid4()), 'call': call,
                        'document_bundle': base64.b64encode(downloaded.content).decode()})
                    from langchain_core.messages import ToolMessage
                    return ToolMessage(content=json.dumps({'reference': result['reference']}),
                        tool_call_id=call['id'], name=name, artifact={'raw_logs': logs})
                if name == 'create_mock_excel':
                    source_data = base64.b64decode(fields['source_base64'], validate=True)
                    if hashlib.sha256(source_data).hexdigest() != fields['source_sha256']:
                        raise InternalOperationError('Generated source digest changed')
                    source = work + '/mock.csv'
                    sandbox.files.write(source, source_data)
                else:
                    source = '/workspace/input/base.xlsx' if name == 'rename_excel' else granted['input']['path']
                mode = 'rename' if name == 'rename_excel' else 'build'
                final = work + '/final/candidate.xlsx'
                target = final if mode == 'rename' else work + '/candidate.xlsx'
                try:
                    execute('rename' if mode == 'rename' else 'calculate',
                        'mkdir -p ' + work + '/final && python -I /skills/spreadsheet_program.py ' + mode + ' ' +
                        shlex.quote(source) + ' --output ' + target + ' --fields ' + work + '/fields.json')
                    if mode == 'build':
                        execute('recalculate', 'libreoffice -env:UserInstallation=file://' + work + '/lo '
                            '--headless --convert-to xlsx --outdir ' + work + '/final ' + target)
                    execute('verify', 'python -I /skills/spreadsheet_program.py check ' + final)
                except RuntimeError:
                    lease.check()
                    # Retain any candidate, including one before failed recalc.
                    # Only the application verifier may authorize publication.
                    pass
                downloaded = backend.download_files([final])[0]
                if (downloaded.error or not downloaded.content) and target != final:
                    downloaded = backend.download_files([target])[0]
                if downloaded.error or not downloaded.content:
                    raise RuntimeError('Candidate download failed')
                lease.check()
                result = internal.operation('run/candidate', {'operation_id': str(uuid.uuid4()),
                    'call': call, 'base64': base64.b64encode(downloaded.content).decode()})
                # All diagnostics pass through 49's one gate; no raw values in content.
                from langchain_core.messages import ToolMessage
                return ToolMessage(content=json.dumps({'reference': result['reference']}),
                    tool_call_id=call['id'], name=name, artifact={'raw_logs': logs})

        @tool
        def build_presentation(input_reference: str, template: str, title: str, section: str, runtime: ToolRuntime,
                               content: list[dict] | None = None, language: str | None = None):
            """Build editable PPTX: narrative pages or an authorized tabular source."""
            return operate('build_presentation', {'input_reference': input_reference, 'template': template,
                'title': title, 'section': section, **({'content': content} if content is not None else {}),
                **({'language': language} if language is not None else {})}, runtime)

        @tool
        def edit_presentation(logical_id: str, base_revision: str, slide: int, field: str, value: str, runtime: ToolRuntime):
            """Change title or body on one authorized slide, preserving every other part."""
            return operate('edit_presentation', {'logical_id': logical_id, 'base_revision': base_revision,
                'slide': slide, 'field': field, 'value': value}, runtime)

        @tool
        def create_mock_excel(title: str, rows: list[dict], runtime: ToolRuntime):
            """Create a verified Excel from invented rows with item and integer amount_cents; no upload needed."""
            return operate('create_mock_excel', {'title': title, 'rows': rows}, runtime)

        @tool
        def build_excel(input_reference: str, title: str, runtime: ToolRuntime):
            """Build and verify XLSX from the authorized opaque input reference."""
            return operate('build_excel', {'input_reference': input_reference, 'title': title}, runtime)

        @tool
        def rename_excel(logical_id: str, base_revision: str, title: str, runtime: ToolRuntime):
            """Change only the title of the current immutable Excel revision."""
            return operate('rename_excel', {'logical_id': logical_id, 'base_revision': base_revision, 'title': title}, runtime)

        @tool
        def build_document(input_reference: str, format: str, title: str, section: str, runtime: ToolRuntime,
                           content: list[dict] | None = None, language: str | None = None):
            """Create DOCX/PDF from structured narrative pages or authorized local data."""
            return operate('build_document', {'input_reference': input_reference, 'format': format,
                'title': title, 'section': section, **({'content': content} if content is not None else {}),
                **({'language': language} if language is not None else {})}, runtime)

        @tool
        def edit_document(logical_id: str, base_revision: str, field: str, value: str, runtime: ToolRuntime):
            """Edit title, section or page:N:block:N; preserve the current document."""
            return operate('edit_document', {'logical_id': logical_id, 'base_revision': base_revision,
                'field': field, 'value': value}, runtime)

        @tool
        def export_pdf(logical_id: str, base_revision: str, runtime: ToolRuntime):
            """Convert the current verified document to PDF, preserving its content."""
            return operate('export_pdf', {'logical_id': logical_id, 'base_revision': base_revision}, runtime)

        @tool
        def research_sources(ids: list[str], runtime: ToolRuntime):
            """Consult only IDs from the server's authorized primary-source catalog."""
            from langchain_core.messages import ToolMessage
            with tool_lock:
                lease.check()
                call = {'id': runtime.tool_call_id, 'name': 'research_sources', 'args': {'ids': ids}}
                result = internal.operation('run/research', {'call': call})
                lease.check()
                return ToolMessage(content=json.dumps({'reference': result['reference']}),
                    tool_call_id=runtime.tool_call_id, name='research_sources')

        graph = build_agent(backend, internal, tools=[research_sources, create_mock_excel, build_excel, rename_excel, build_document, edit_document, export_pdf, build_presentation, edit_presentation],
            model_profile={'max_input_tokens': 200000, 'max_output_tokens': 8000},
            allowed_tools=granted['tools'], system_prompt=runtime_prompt(granted['tools']))
        result = graph.invoke({'messages': [HumanMessage(content=granted['message']),
            HumanMessage(content='Referencias autorizadas del servidor: ' + json.dumps(granted['model_context']))]},
            config={'recursion_limit': 12})
        lease.check()
        while internal.operation('run/review-status', {})['pending']:
            lease.check()
            time.sleep(1)
        internal.operation('run/complete', {})
        return {'status': 'completed', 'message_count': len(result['messages'])}


def run_export(internal, sandbox, lease, granted):
    """Official HITL + SQLite checkpointer; only protected graph state on disk."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.types import Command
    from langchain_core.messages import ToolMessage
    state = Path('/state/checkpoints.sqlite')
    if not state.parent.is_dir():
        raise InternalOperationError('Private durable checkpoint directory required')

    @tool
    def save_revision(artifact_reference: str, sha256: str, name: str, runtime: ToolRuntime):
        """Create the exact verified revision in the configured authorized Drive folder."""
        lease.check()
        call = {'id': runtime.tool_call_id, 'name': 'save_revision',
            'args': {'artifact_reference': artifact_reference, 'sha256': sha256, 'name': name}}
        response = internal.operation('run/save-revision', call)
        return ToolMessage(content=json.dumps({'reference': response['reference']}),
            tool_call_id=runtime.tool_call_id, name='save_revision')

    with SqliteSaver.from_conn_string(str(state)) as checkpointer:
        graph = build_agent(E2BSandbox(sandbox=sandbox, workdir='/workspace/work'), internal,
            tools=[save_revision], allowed_tools=['save_revision'], checkpointer=checkpointer,
            interrupt_on={'save_revision': {'allowed_decisions': ['approve', 'reject']}},
            model_profile={'max_input_tokens': 200000, 'max_output_tokens': 8000},
            system_prompt='Use save_revision exactly once with the authorized references. Never change content or destination.')
        config = {'configurable': {'thread_id': granted['execution']}, 'recursion_limit': 8}
        snapshot = graph.get_state(config)
        if not snapshot.values:
            if granted.get('checkpoint_ready'):
                raise InternalOperationError('Durable export checkpoint missing; manual recovery required')
            result = graph.invoke({'messages': [HumanMessage(content=granted['message']),
                HumanMessage(content='Referencias autorizadas del servidor: ' + json.dumps(granted['model_context']))]}, config=config)
            if not result.get('__interrupt__'):
                raise InternalOperationError('Official export interrupt required')
            snapshot = graph.get_state(config)
        calls = [call for message in snapshot.values['messages'] if hasattr(message, 'tool_calls') for call in message.tool_calls]
        if len(calls) != 1 or calls[0]['name'] != 'save_revision':
            raise InternalOperationError('Exactly one export proposal required')
        internal.operation('run/propose-export', {k: calls[0][k] for k in ('id', 'name', 'args')})
        while True:
            lease.check()
            decision = internal.operation('run/approval-state', {})['decision']
            if decision in ('intent', 'uncertain', 'completed'):
                response = internal.operation('run/reconcile-export', {})
                if response['status'] != 'approved':
                    raise InternalOperationError('Export outcome requires reconciliation')
                break
            if decision == 'approved':
                if not snapshot.next:
                    raise InternalOperationError('Approval requires an interrupted checkpoint')
                graph.invoke(Command(resume={'decisions': [{'type': 'approve'}]}), config=config)
                break
            if decision == 'rejected':
                graph.invoke(Command(resume={'decisions': [{'type': 'reject', 'message': 'Rejected by authorized user'}]}), config=config)
                raise InternalOperationError('Export rejected')
            time.sleep(1)
        lease.check()
        internal.operation('run/export-complete', {})
        return {'status': 'completed'}


def prune_checkpoints(client, endpoint, token):
    state = Path('/state/checkpoints.sqlite')
    if not state.is_file():
        return
    response = client.post(endpoint + 'checkpoints/', json={}, headers={'Authorization': 'Bearer ' + token})
    response.raise_for_status()
    keep = set(response.json()['keep'])
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(state)) as saver:
        threads = {item.config['configurable']['thread_id'] for item in saver.list(None)}
        for thread_id in threads - keep:
            saver.delete_thread(thread_id)


def run(config, *, once=False):
    worker_id = str(uuid.uuid4())
    token = Path(config['worker_token_file']).read_text().strip()
    endpoint = config['internal_endpoint'].rstrip('/') + '/'
    pool = CleanPool(lambda: create_clean(config))
    try:
        with httpx.Client(follow_redirects=False, trust_env=False, timeout=15) as client:
            while True:
                # Claim only after a clean environment is ready; queued requests
                # already explain capacity waiting, with no fake progress.
                sandbox = pool.take()
                if sandbox is None:
                    time.sleep(0.5)
                    continue
                internal = None
                try:
                    prune_checkpoints(client, endpoint, token)
                    claim_id = str(uuid.uuid4())
                    response = None
                    for retry in range(2):
                        try:
                            response = client.post(endpoint + 'claim/', json={
                                'worker_id': worker_id, 'claim_id': claim_id}, headers={'Authorization': 'Bearer ' + token})
                            break
                        except httpx.TransportError:
                            if retry:
                                raise InternalOperationError('Claim transport uncertain') from None
                    response.raise_for_status()
                    claimed = response.json()
                    if claimed['status'] == 'idle':
                        # This slot was never used or assigned to a conversation.
                        pool.return_unassigned(sandbox)
                        sandbox = None
                        if once:
                            return {'status': 'idle'}
                        time.sleep(1)
                        continue
                    internal = InternalClient(endpoint, claimed['token'], claimed['attempt'])
                    started = time.monotonic()
                    run_job(internal, sandbox)
                    print(json.dumps({'execution': claimed['execution'], 'sandbox_id': sandbox.sandbox_id,
                        'seconds': time.monotonic() - started, 'pool': pool.metrics,
                        'status': 'completed'}), flush=True)
                    if once:
                        return {'status': 'completed', 'pool': pool.metrics}
                except Exception:
                    if internal:
                        try:
                            internal.operation('run/fail', {})
                        except Exception:
                            pass  # Expiry/revocation/cancellation retains authority on server.
                    if once:
                        raise InternalOperationError('Execution interrupted; inspect authorized run state') from None
                finally:
                    if internal:
                        internal.close()
                    if sandbox:
                        pool.release(sandbox)
    finally:
        pool.close()


def main():
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(json.loads(args.config.read_text()), once=args.once)))
    except KeyboardInterrupt:
        pass  # run's finally destroys the exclusive sandbox and the warm slot.


if __name__ == '__main__':
    main()
