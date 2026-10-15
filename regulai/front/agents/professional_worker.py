"""General Deep Agents tools. This module never imports Django or credentials."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import time
import uuid

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import HumanMessage, ToolMessage, messages_to_dict, messages_from_dict
from langchain.agents.middleware import AgentMiddleware

from .adapter import InternalOperationError, build_agent, _wire
from .workspace_backend import WorkspaceSandbox


def run_professional(internal, sandbox, lease, granted):
    budget = granted['limits']
    # Administrative setup precedes any model-generated command. A fixed-size
    # filesystem bounds aggregate disk use, including package installations.
    sandbox.commands.run('mount -t tmpfs -o size=' + str(budget['workspace_bytes']) + ',nosuid,nodev tmpfs /workspace && '
        'mkdir -p /workspace/input /workspace/work /workspace/output && chown user:user /workspace/work /workspace/output',
        user='root', timeout=10)
    if granted['input']:
        asset = granted['input']
        data = base64.b64decode(asset['base64'], validate=True)
        if hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise InternalOperationError('Input digest changed')
        sandbox.files.write(asset['path'], data, user='root')
    sandbox.commands.run('chmod -R a-w /workspace/input && mount --bind /workspace/input /workspace/input && '
        'mount -o remount,bind,ro /workspace/input', user='root', timeout=10)
    backend = WorkspaceSandbox(sandbox=sandbox, limits=budget, lease=lease)
    probe = json.loads(backend.execute('python -c "import os; assert os.getuid()==1000; assert not os.path.exists(\'/run\')"').output)
    if probe['exit_code']:
        raise InternalOperationError('Workspace isolation unavailable')
    runtime_hash = hashlib.sha256(backend._file('/skills/runtime-versions.txt')).hexdigest()
    restored = granted.get('checkpoint')
    if restored:
        if restored['runtime_sha256'] != runtime_hash:
            raise InternalOperationError('Checkpoint runtime changed')
        archive = base64.b64decode(restored['archive'], validate=True)
        if backend.upload_files([('/workspace/work/.regulay-checkpoint.zip', archive)])[0].error:
            raise InternalOperationError('Checkpoint transfer failed')
        if backend.execute('python -I /skills/checkpoint_runner.py restore ' + str(budget['workspace_bytes']) + ' ' + str(budget['file_bytes'])).exit_code:
            raise InternalOperationError('Checkpoint restore failed')

    def call(runtime, name, args):
        # Preserve omitted optional arguments exactly as issued by the provider;
        # Python's function defaults are not a different authorized tool call.
        for message in reversed(runtime.state.get('messages', [])):
            for issued in getattr(message, 'tool_calls', []):
                if issued['id'] == runtime.tool_call_id and issued['name'] == name:
                    return {key: issued[key] for key in ('id', 'name', 'args')}
        raise InternalOperationError('Issued tool call unavailable')

    def recorded(runtime, name):
        return ToolMessage(content='Recorded by Regulay.', tool_call_id=runtime.tool_call_id, name=name)

    def web(runtime, name, args):
        result = internal.operation('run/web', {'call': call(runtime, name, args)})
        if result.get('base64'):
            content = base64.b64decode(result['base64'], validate=True)
            uploaded = backend.upload_files([(result['file_path'], content)])[0]
            if uploaded.error:
                raise InternalOperationError('Downloaded file could not be stored')
        return recorded(runtime, name)

    @tool
    def web_search(query: str, runtime: ToolRuntime, max_results: int = 5, language: str = '', time_range: str = ''):
        """Search public web, then open sources to read evidence."""
        return web(runtime, 'web_search', {'query': query, 'max_results': max_results,
            **({'language': language} if language else {}), **({'time_range': time_range} if time_range else {})})

    @tool
    def web_open(url: str, runtime: ToolRuntime, offset: int = 0, limit: int = 12000):
        """Read public HTML, text or PDF with stable references and explicit coverage."""
        return web(runtime, 'web_open', {'url': url, 'offset': offset, 'limit': limit})

    @tool
    def web_find(reference: str, term: str, runtime: ToolRuntime):
        """Find literal text in opened source evidence."""
        return web(runtime, 'web_find', {'reference': reference, 'term': term})

    @tool
    def web_download(url: str, file_path: str, runtime: ToolRuntime):
        """Download a public file through the broker into this workspace."""
        return web(runtime, 'web_download', {'url': url, 'file_path': file_path})

    @tool
    def web_browse(url: str, runtime: ToolRuntime):
        """Read a JavaScript page using an isolated browser without private files."""
        from .browser_worker import browse
        selected = call(runtime, 'web_browse', {'url': url})
        browse(internal, sandbox, lease, selected, budget)
        return recorded(runtime, 'web_browse')

    @tool
    def read_output(call_id: str, runtime: ToolRuntime, offset: int = 0):
        """Read more of an earlier command's protected output."""
        internal.operation('run/output', {'call': call(runtime, 'read_output', {'call_id': call_id, 'offset': offset})})
        return recorded(runtime, 'read_output')

    @tool
    def install_packages(ecosystem: str, packages: list[str], runtime: ToolRuntime):
        """Install pinned packages offline into this job's Python/Node environment."""
        result = internal.operation('run/packages', {'call': call(runtime, 'install_packages', {'ecosystem': ecosystem, 'packages': packages})})
        if result.get('succeeded') is False:
            return recorded(runtime, 'install_packages')
        backend.execute('mkdir -p /workspace/work/.packages')
        for asset in result['files']:
            raw = base64.b64decode(asset['base64'], validate=True)
            if hashlib.sha256(raw).hexdigest() != asset['sha256']:
                raise InternalOperationError('Package digest changed')
            if backend.upload_files([(asset['path'], raw)])[0].error:
                raise InternalOperationError('Package transfer failed')
        if ecosystem == 'pip':
            requirements = '\n'.join(f"{p['name']}=={p['version']} --hash=sha256:{p['sha256']}" for p in result['manifest'])
            if backend.upload_files([('/workspace/work/.packages/requirements.lock', requirements.encode())])[0].error:
                raise InternalOperationError('Package lock unavailable')
            command = ('python -m venv --system-site-packages /workspace/work/.venv && '
                '/workspace/work/.venv/bin/python -m pip install --no-index --no-deps --require-hashes '
                '--find-links /workspace/work/.packages -r /workspace/work/.packages/requirements.lock && '
                '/workspace/work/.venv/bin/python -m pip check')
        else:
            paths = [shlex.quote(p['path']) for p in result['files']]
            cache = ' && '.join('npm cache add --offline --ignore-scripts ' + path for path in paths)
            command = cache + ' && npm install --offline --ignore-scripts --no-audit --no-fund --prefix /workspace/work ' + ' '.join(paths)
        response = backend.execute(command, timeout=budget['command_seconds'])
        return ToolMessage(content=json.dumps({'installed': response.exit_code == 0, 'manifest': result['manifest'],
            'diagnostics': json.loads(response.output)}), tool_call_id=runtime.tool_call_id, name='install_packages')

    def files(paths):
        result = {}
        for path in dict.fromkeys(paths):
            downloaded = backend.download_files([path])[0]
            if downloaded.error or downloaded.content is None:
                raise ValueError('Workspace file unavailable: ' + path)
            result[path] = base64.b64encode(downloaded.content).decode()
        return result

    @tool
    def publish_artifact(file_path: str, title: str, runtime: ToolRuntime, pdf_path: str = '',
                         page_paths: list[str] | None = None, sources: list[str] | None = None,
                         base_revision: str = '', synthetic: bool = False):
        """Submit an output, its rendered pages and provenance for server verification."""
        args = {'file_path': file_path, 'title': title, 'synthetic': synthetic,
            **({'pdf_path': pdf_path} if pdf_path else {}), **({'page_paths': page_paths} if page_paths else {}),
            **({'sources': sources} if sources else {}), **({'base_revision': base_revision} if base_revision else {})}
        paths = [file_path, *(page_paths or []), *([pdf_path] if pdf_path else [])]
        rendering = None
        if Path(file_path).suffix.lower() in ('.docx', '.pptx', '.pdf'):
            target = '/workspace/output/.render-' + uuid.uuid4().hex
            rendered = json.loads(backend.execute('python -I /skills/artifact_render.py ' + shlex.quote(file_path)
                + ' ' + target + ' ' + str(budget['pdf_pages'])).output)
            if rendered['exit_code'] or rendered['truncated']:
                raise InternalOperationError('Rendering failed: ' + rendered['stderr'][:2000])
            rendering = json.loads(rendered['stdout'])
            paths = [file_path, rendering['pdf_path'], *rendering['page_paths']]
        internal.operation('run/publish', {'call': call(runtime, 'publish_artifact', args), 'files': files(paths),
            **({'render': rendering} if rendering else {})})
        return recorded(runtime, 'publish_artifact')

    @tool
    def inspect_image(file_path: str, question: str, runtime: ToolRuntime):
        """Send actual authorized pixels through the vision gateway for review."""
        internal.operation('run/image', {'call': call(runtime, 'inspect_image', {'file_path': file_path, 'question': question}),
            'base64': files([file_path])[file_path]})
        return recorded(runtime, 'inspect_image')

    tools = [web_search, web_open, web_find, web_download, web_browse, install_packages,
        publish_artifact, inspect_image, read_output]
    tools = [t for t in tools if t.name in granted['tools']]
    class SafeBoundary(AgentMiddleware):
        def before_model(self, state, runtime):
            lease.check()
            response = backend.execute('python -I /skills/checkpoint_runner.py save ' + str(budget['workspace_bytes']) + ' ' + str(budget['file_bytes']))
            if response.exit_code:
                # Work can continue without a new checkpoint. A stale snapshot
                # cannot pass the server watermark when operations have advanced.
                return None
            try:
                archive = backend._file('/workspace/work/.regulay-checkpoint.zip')
            except ValueError:
                return None
            internal.operation('run/checkpoint', {'messages': messages_to_dict(state['messages']),
                'wire_messages': [_wire(m) for m in state['messages']],
                'archive': base64.b64encode(archive).decode(), 'runtime_sha256': runtime_hash})
            return None
    prompt = Path(__file__).with_name('runtime').joinpath('professional.md').read_text(encoding='utf-8')
    prompt += '\nCapacidades y límites resueltos por el servidor: ' + json.dumps(granted['model_context'], ensure_ascii=False)
    graph = build_agent(backend, internal, tools=tools, allowed_tools=granted['tools'],
        model_profile={'max_input_tokens': 200000, 'max_output_tokens': 8000}, system_prompt=prompt,
        middleware=[SafeBoundary()])
    messages = messages_from_dict(restored['messages']) if restored else [HumanMessage(content=granted['message'])]
    # Final-delivery repairs are separate from the graph's normal tool loop.
    for final_attempt in range(3):
        result = graph.invoke({'messages': messages}, config={'recursion_limit': budget['tool_calls'] * 3 + 10})
        lease.check()
        last = result['messages'][-1]
        receipt = last.response_metadata.get('regulay', {})
        while internal.operation('run/review-status', {})['pending']:
            lease.check()
            time.sleep(1)
        completion = internal.operation('run/complete', {'final_call_id': receipt['call_id']})
        if completion.get('completed'):
            return {'status': 'completed', 'message_count': len(result['messages'])}
        messages = [*result['messages'], HumanMessage(content='Comprobación de entrega de Regulay: ' +
            json.dumps(completion['problems']) + '. Corrige lo pendiente sin inventar evidencia.')]
    raise InternalOperationError('Final delivery remains incomplete')
