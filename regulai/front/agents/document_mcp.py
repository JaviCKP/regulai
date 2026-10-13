"""One managed MCP connector. All external IDs/bytes/credentials stay here.

The official SDK runs the reviewed server over memory streams. No subprocess,
remote tool discovery, sampling, roots, prompts or model backend is installed.
Only Drive HTTPS is used by the server; the executor has no external transport.
"""
import base64
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import re
from urllib.parse import quote

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils import timezone
import anyio
from mcp import ClientSession, types
from mcp.server import Server
from mcp.shared.memory import create_client_server_memory_streams

from front.models import AgentDocumentConnection, AgentDocumentReference, Profile
from front.policy import digest
from .excel_contract import MAX_BYTES, input_rows
from .service import AgentDenied

SERVER = 'regulay-drive-v1'
VERSION = '1'
MIMES = {'text/csv': 'csv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx'}
SCHEMAS = {
    'search': {'type': 'object', 'properties': {'query': {'type': 'string'}},
        'required': ['query'], 'additionalProperties': False},
    'download': {'type': 'object', 'properties': {'document': {'type': 'string'}},
        'required': ['document'], 'additionalProperties': False},
}
ID = re.compile(r'^[a-zA-Z0-9_-]{1,200}$')


def account(actor):
    if not getattr(settings, 'REGULAY_AGENT_MCP_ENABLED', False):
        raise AgentDenied('document_connector_disabled')
    from .jobs import development_profile
    development_profile(actor)
    profile = Profile.objects.get(user=actor)
    connection = AgentDocumentConnection.objects.filter(user=actor, company_id=profile.company_id,
        enabled=True, expires_at__gt=timezone.now()).first()
    if not connection:
        raise AgentDenied('document_account_unavailable')
    try:
        private = json.loads(connection.private_config)
        if (set(private) != {'token', 'identity', 'folders'} or not isinstance(private['token'], str)
                or not private['token'] or not ID.fullmatch(private['identity'])
                or not isinstance(private['folders'], list) or not 1 <= len(private['folders']) <= 10
                or any(not isinstance(f, str) or not ID.fullmatch(f) for f in private['folders'])):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise AgentDenied('document_account_invalid') from None
    binding = digest([str(connection.pk), connection.company_id, connection.user_id,
        connection.version, connection.expires_at.isoformat(), private])
    return connection, private, binding


class Drive:
    """No redirects, proxies, arbitrary hosts/paths, downloads or SDK retries."""
    def __init__(self, private, *, transport=None):
        self.private = private
        self.client = httpx.AsyncClient(base_url='https://www.googleapis.com/drive/v3/',
            headers={'Authorization': 'Bearer ' + private['token']}, transport=transport,
            trust_env=False, follow_redirects=False, timeout=15)

    async def get(self, path, params):
        async with self.client.stream('GET', path, params=params) as response:
            if response.status_code != 200:
                raise AgentDenied('document_remote_denied')
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise AgentDenied('document_too_large')
            return bytes(data)

    async def identity(self):
        data = json.loads(await self.get('about', {'fields': 'user(permissionId)'}))
        if data.get('user', {}).get('permissionId') != self.private['identity']:
            raise AgentDenied('document_identity_changed')

    async def metadata(self, document):
        if not isinstance(document, str) or not ID.fullmatch(document):
            raise AgentDenied('document_scope_denied')
        data = json.loads(await self.get('files/' + quote(document, safe=''),
            {'fields': 'id,mimeType,parents,trashed,capabilities(canDownload)'}))
        if (data.get('id') != document or data.get('trashed') is not False
                or not set(data.get('parents', [])) & set(self.private['folders'])
                or data.get('mimeType') not in MIMES
                or data.get('capabilities', {}).get('canDownload') is not True):
            raise AgentDenied('document_scope_denied')
        return data

    async def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
            raise AgentDenied('document_query_invalid')
        await self.identity()
        escaped = query.replace('\\', '\\\\').replace("'", "\\'")
        folders = ' or '.join("'" + f + "' in parents" for f in self.private['folders'])
        data = json.loads(await self.get('files', {'q': f"trashed = false and ({folders}) and name contains '{escaped}'",
            'pageSize': 10, 'fields': 'files(id)'}))
        result = []
        for item in data.get('files', [])[:10]:
            await self.metadata(item['id'])  # Search listings never grant authority.
            result.append(item['id'])
        return {'documents': result}

    async def download(self, document):
        await self.identity()
        metadata = await self.metadata(document)
        raw = await self.get('files/' + quote(document, safe=''), {'alt': 'media'})
        # Revocation/move during the transfer withholds delivery.
        await self.identity()
        await self.metadata(document)
        kind = MIMES[metadata['mimeType']]
        input_rows(raw, kind)
        return {'kind': kind, 'base64': base64.b64encode(raw).decode()}


def server(drive):
    app = Server(SERVER, version=VERSION)

    @app.list_tools()
    async def tools():
        return [types.Tool(name=name, inputSchema=schema) for name, schema in SCHEMAS.items()]

    @app.call_tool()
    async def invoke(name, arguments):
        try:
            if name == 'search' and set(arguments) == {'query'}:
                value = await drive.search(arguments['query'])
            elif name == 'download' and set(arguments) == {'document'}:
                value = await drive.download(arguments['document'])
            else:
                raise AgentDenied('document_operation_denied')
            return types.CallToolResult(content=[], structuredContent=value)
        except Exception:
            # SDK diagnostics must not contain a provider response or token.
            return types.CallToolResult(content=[], isError=True)
    return app


async def _call(private, operation, arguments, *, transport=None):
    drive = Drive(private, transport=transport)
    try:
        async with session(server(drive)) as client:
            # Pin the whole catalog. An extra tool or changed schema closes access.
            catalog = await client.list_tools()
            if {t.name: t.inputSchema for t in catalog.tools} != SCHEMAS or catalog.nextCursor:
                raise AgentDenied('document_catalog_changed')
            result = await client.call_tool(operation, arguments)
            if result.isError or result.content or not isinstance(result.structuredContent, dict):
                raise AgentDenied('document_operation_failed')
            return result.structuredContent
    except Exception:
        raise AgentDenied('document_operation_failed') from None
    finally:
        await drive.client.aclose()


@asynccontextmanager
async def session(app):
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        async with anyio.create_task_group() as group:
            group.start_soon(app.run, *server_streams, app.create_initialization_options())
            try:
                # No sampling/elicitation/roots callback; no capabilities granted.
                async with ClientSession(*client_streams, read_timeout_seconds=timedelta(seconds=30)) as client:
                    initialized = await client.initialize()
                    if initialized.serverInfo.name != SERVER or initialized.serverInfo.version != VERSION:
                        raise AgentDenied('document_server_changed')
                    yield client
            finally:
                group.cancel_scope.cancel()


def call(private, operation, arguments):
    # Only application-owned code calls this; neither a model nor request chooses
    # transport/server/path. Tests replace the external transport only.
    return async_to_sync(_call)(private, operation, arguments)


def search(actor, query):
    connection, private, binding = account(actor)
    value = call(private, 'search', {'query': query})
    if account(actor)[2] != binding:
        raise AgentDenied('document_authorization_changed')
    if set(value) != {'documents'} or not isinstance(value['documents'], list) or len(value['documents']) > 10:
        raise AgentDenied('document_result_invalid')
    results = []
    for index, original in enumerate(value['documents']):
        if not isinstance(original, str) or not ID.fullmatch(original):
            raise AgentDenied('document_result_invalid')
        reference = AgentDocumentReference.objects.create(connection=connection, original_id=original,
            binding=binding, expires_at=min(connection.expires_at, timezone.now() + timedelta(minutes=10)))
        results.append({'reference': str(reference.pk), 'label': f'Documento autorizado {index + 1}'})
    return {'status': 'authorized', 'documents': results}


def obtain(actor, reference):
    connection, private, binding = account(actor)
    try:
        row = AgentDocumentReference.objects.get(pk=reference, connection=connection,
            binding=binding, expires_at__gt=timezone.now())
    except (ValueError, AgentDocumentReference.DoesNotExist):
        raise AgentDenied('document_reference_denied') from None
    value = call(private, 'download', {'document': row.original_id})
    if account(actor)[2] != binding:
        raise AgentDenied('document_authorization_changed')
    if set(value) != {'kind', 'base64'} or value['kind'] not in ('csv', 'xlsx'):
        raise AgentDenied('document_result_invalid')
    try:
        raw = base64.b64decode(value['base64'], validate=True)
        input_rows(raw, value['kind'])
    except (ValueError, TypeError):
        raise AgentDenied('document_result_invalid') from None
    return raw, value['kind']
