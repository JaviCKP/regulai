"""Executor-only SDK adapter. Uses the task 48 lock, never provider credentials."""
import asyncio
import json
import os
import uuid
from typing import Any
from urllib.parse import urlsplit

import httpx
from deepagents import create_deep_agent
from deepagents.profiles import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.types import Command
from pydantic import Field

from .protocol import InferenceRequest, ToolCall, TOOL_PARAMETERS

MODEL_NAME = 'regulay-internal:agent-v1'


class InternalOperationError(RuntimeError):
    pass


class InternalClient:
    def __init__(self, endpoint, token, attempt, *, transport=None):
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid internal endpoint')
        self.endpoint = endpoint.rstrip('/') + '/'
        self.token, self.attempt = token, str(attempt)
        self.client = httpx.Client(transport=transport, follow_redirects=False, trust_env=False, timeout=None)

    def close(self):
        self.client.close()

    def operation(self, name, payload):
        if name not in ('inference', 'tool-results', 'authorize-tool', 'run/renew', 'run/bootstrap',
                'run/step', 'run/candidate', 'run/local-fields', 'run/complete', 'run/fail'):
            raise InternalOperationError('Unknown internal operation')
        # Retry only the SAME identified application operation after a transport
        # failure. The durable server record decides whether inference ever ran.
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        for transport_attempt in range(2):
            try:
                response = self.client.post(self.endpoint + name + '/', content=encoded,
                    headers={'Authorization': 'Bearer ' + self.token, 'X-Regulay-Attempt': self.attempt,
                             'Content-Type': 'application/json'})
                if response.status_code != 200:
                    raise InternalOperationError('Internal operation denied')
                value = response.json()
                if not isinstance(value, dict) or value.get('status') not in ('completed', 'authorized', 'approved', 'withheld'):
                    raise InternalOperationError('Internal operation did not complete')
                return value
            except httpx.TransportError:
                if transport_attempt:
                    raise InternalOperationError('Internal transport outcome unknown') from None
            except (ValueError, TypeError):
                raise InternalOperationError('Invalid internal response') from None
        raise InternalOperationError('Internal transport unavailable')


def _wire(message):
    role = {'human': 'user', 'ai': 'assistant', 'system': 'system', 'tool': 'tool'}.get(message.type)
    metadata = message.additional_kwargs
    if role is None or (metadata and metadata != {'lc_source': 'summarization'}):
        raise InternalOperationError('Unsupported model message')
    value = {'role': role, 'content': message.content}
    if isinstance(message, AIMessage):
        if message.invalid_tool_calls:
            raise InternalOperationError('Invalid native tool call')
        value['tool_calls'] = [{k: c[k] for k in ('id', 'name', 'args')} for c in message.tool_calls]
    if isinstance(message, ToolMessage):
        if message.artifact is not None:
            raise InternalOperationError('Unapproved tool artifact')
        value.update(tool_call_id=message.tool_call_id, name=message.name)
    return value


class RegulayModel(BaseChatModel):
    model_name: str = MODEL_NAME
    internal: Any = Field(exclude=True, repr=False)
    allowed_tools: list[str] | None = None

    @property
    def _llm_type(self):
        return 'regulay-internal'

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        if kwargs or tool_choice not in (None, 'auto'):
            raise InternalOperationError('Unsupported model options')
        names = [convert_to_openai_tool(t)['function']['name'] for t in tools]
        if self.allowed_tools is not None:
            names = [name for name in names if name in self.allowed_tools]
        if set(names) - set(TOOL_PARAMETERS):
            raise InternalOperationError('Unsupported tool catalogue')
        # Tool descriptions/schemas from the executor are not forwarded. Regulay
        # owns the schemas and the current profile owns the permitted subset.
        return self.bind(tools=names)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if stop or set(kwargs) - {'tools'}:
            raise InternalOperationError('Unsupported model options')
        metadata = getattr(run_manager, 'metadata', {}) or {}
        purpose = 'compaction' if metadata.get('lc_source') == 'summarization' else 'generation'
        wire = [_wire(m) for m in messages]
        if any(isinstance(m['content'], list) and any(p.get('type') == 'image_ref' for p in m['content']) for m in wire):
            purpose = 'vision'
        request = InferenceRequest(call_id=str(uuid.uuid4()), purpose=purpose, messages=wire, tools=kwargs.get('tools', []))
        result = self.internal.operation('inference', request.model_dump())
        calls = [ToolCall.model_validate(c).model_dump() for c in result['tool_calls']]
        reply = AIMessage(content=result['content'], tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return await asyncio.to_thread(self._generate, messages, stop, run_manager, **kwargs)


def _raw(value):
    if isinstance(value, BaseMessage):
        return value.model_dump(mode='json')
    if isinstance(value, Command):
        return {'update': _raw(value.update)}
    if isinstance(value, dict):
        return {str(key): _raw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_raw(item) for item in value]
    return value


class ResultGate(AgentMiddleware):
    def __init__(self, internal):
        self.internal = internal

    def _call(self, request):
        return {k: request.tool_call[k] for k in ('id', 'name', 'args')}

    def _result(self, call, raw, failed=False):
        view = self.internal.operation('tool-results', {'call': call, 'raw': _raw(raw), 'failed': failed})
        # Never forward Command.update, artifacts, metadata, stderr or logs.
        return ToolMessage(content=json.dumps(view, sort_keys=True, ensure_ascii=False),
            tool_call_id=call['id'], name=call['name'])

    def wrap_tool_call(self, request, handler):
        call = self._call(request)
        self.internal.operation('authorize-tool', call)
        try:
            raw = handler(request)
        except Exception as error:
            return self._result(call, {'exception': str(error)}, True)
        return self._result(call, raw)

    async def awrap_tool_call(self, request, handler):
        call = self._call(request)
        await asyncio.to_thread(self.internal.operation, 'authorize-tool', call)
        try:
            raw = await handler(request)
        except Exception as error:
            return await asyncio.to_thread(self._result, call, {'exception': str(error)}, True)
        return await asyncio.to_thread(self._result, call, raw)


register_harness_profile(MODEL_NAME, HarnessProfile(
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))


def build_agent(backend, internal, *, tools=(), model_profile=None, system_prompt=None, allowed_tools=None):
    # Fail closed if an executor was launched with provider or external tracing
    # credentials. Actual egress enforcement belongs to the host network policy.
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY',
            'DEEPSEEK_API_KEY', 'LANGSMITH_API_KEY', 'LANGCHAIN_API_KEY')):
        raise InternalOperationError('Executor environment contains external credentials')
    os.environ['LANGSMITH_TRACING'] = 'false'
    os.environ['LANGCHAIN_TRACING_V2'] = 'false'
    model = RegulayModel(internal=internal, profile=model_profile, cache=False, allowed_tools=allowed_tools)
    return create_deep_agent(model=model, tools=list(tools), backend=backend,
        middleware=[ResultGate(internal)], subagents=[], memory=None, skills=None,
        store=None, checkpointer=None, system_prompt=system_prompt or 'Use only authorized local operations and approved views.')
