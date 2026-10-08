"""
AI Provider Connectors

This module provides a unified interface for different AI providers (OpenAI, Anthropic, etc.)
Each connector implements the same interface for sending chat messages.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


DOCUMENT_RESPONSE_SCHEMA = {
    'type': 'object', 'required': ['claims'], 'additionalProperties': False,
    'properties': {'claims': {'type': 'array', 'items': {
        'type': 'object', 'required': ['text', 'citations'], 'additionalProperties': False,
        'properties': {
            'text': {'type': 'string'},
            'citations': {'type': 'array', 'items': {
                'type': 'object', 'required': ['id', 'quote'], 'additionalProperties': False,
                'properties': {'id': {'type': 'string'}, 'quote': {'type': 'string'}},
            }},
        },
    }}},
}


@dataclass
class ChatMessage:
    """Represents a chat message."""
    role: str  # 'user', 'assistant', 'system'
    content: Any  # str or list (for multimodal content)
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ChatResponse:
    """Represents a response from the AI provider."""
    content: str
    tokens_used: int = 0
    model: str = ""
    finish_reason: str | None = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_request_id: str | None = None
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)


class BaseConnector(ABC):
    """Base class for AI provider connectors."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.6,
        *, supports_json: bool = False, reasoning: bool = False,
        **kwargs
    ) -> ChatResponse:
        """Send a chat request and return the response."""
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        """Return whether this connector supports vision/image inputs."""
        pass


class OpenAIConnector(BaseConnector):
    """Connector for OpenAI and OpenAI-compatible APIs."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        from openai import OpenAI, DefaultHttpxClient
        self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=30,
                            http_client=DefaultHttpxClient(follow_redirects=False))

    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.6,
        *, supports_json: bool = False, reasoning: bool = False,
        **kwargs
    ) -> ChatResponse:
        """Use explicit model capabilities; supports_json requests JSON output.

        A missing finish_reason is preserved: compatible providers must report
        an explicit completion signal before the response can pass verification.
        """
        # Convert ChatMessage objects to dict format
        api_messages = []
        for msg in messages:
            wire = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                from .agents.protocol import ToolCall
                wire['tool_calls'] = [ToolCall.model_validate(call).openai() for call in msg.tool_calls]
            if msg.tool_call_id is not None:
                wire['tool_call_id'] = msg.tool_call_id
            if msg.name is not None:
                wire['name'] = msg.name
            api_messages.append(wire)

        response = self.client.chat.completions.create(
            model=model,
            messages=api_messages,
            **({} if max_tokens is None else
               {'max_completion_tokens': max_tokens} if reasoning else {'max_tokens': max_tokens}),
            **({} if reasoning else {'temperature': temperature}),
            **({'response_format': {'type': 'json_object'}} if supports_json else {}),
            timeout=kwargs.get('timeout', 30),
            **({'tools': kwargs['tools']} if kwargs.get('tools') else {}),
            **({'extra_body': kwargs['extra_body']} if 'extra_body' in kwargs else {}),
        )

        tool_calls = []
        for call in getattr(response.choices[0].message, 'tool_calls', None) or []:
            import json
            from .agents.protocol import ToolCall
            tool_calls.append(ToolCall.model_validate({'id': call.id, 'name': call.function.name,
                'args': json.loads(call.function.arguments)}).model_dump())
        return ChatResponse(
            content=response.choices[0].message.content,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            model=response.model if hasattr(response, 'model') else model,
            finish_reason=response.choices[0].finish_reason if response.choices else "",
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
            provider_request_id=getattr(response, 'id', None),
            usage=response.usage.model_dump() if response.usage else {},
            tool_calls=tool_calls,
        )

    def supports_vision(self) -> bool:
        return True


class AnthropicConnector(BaseConnector):
    """Connector for Anthropic Claude API."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url, max_retries=0, timeout=30,
                http_client=anthropic.DefaultHttpxClient(follow_redirects=False))
            self._available = True
        except ImportError:
            self._available = False
            self.client = None

    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.6,
        *, supports_json: bool = False, reasoning: bool = False,
        **kwargs
    ) -> ChatResponse:
        """Send a chat request using Anthropic API."""
        if not self._available:
            raise ImportError("anthropic package is not installed. Install with: pip install anthropic")
        if kwargs.get('tools') or any(m.tool_calls or m.tool_call_id is not None for m in messages):
            raise ValueError('Native tool messages require the OpenAI-compatible agent protocol.')

        # Anthropic has different message format
        # System messages are passed separately
        system_messages = []
        api_messages = []

        for msg in messages:
            if msg.role == 'system':
                system_messages.append(msg.content if isinstance(msg.content, str) else str(msg.content))
            else:
                # Handle multimodal content for Anthropic
                if isinstance(msg.content, list):
                    # Convert OpenAI format to Anthropic format
                    anthropic_content = []
                    for item in msg.content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                anthropic_content.append({
                                    "type": "text",
                                    "text": item.get('text', '')
                                })
                            elif item.get('type') == 'image_url':
                                # Convert OpenAI image_url format to Anthropic format
                                image_url = item.get('image_url', {})
                                url = image_url.get('url', '') if isinstance(image_url, dict) else str(image_url)

                                # Extract base64 data from data URL
                                if url.startswith('data:'):
                                    # Format: data:image/png;base64,<data>
                                    parts = url.split(',', 1)
                                    if len(parts) == 2:
                                        media_type_part = parts[0].replace('data:', '').replace(';base64', '')
                                        anthropic_content.append({
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type_part,
                                                "data": parts[1]
                                            }
                                        })
                                else:
                                    # URL-based image (Anthropic also supports this)
                                    anthropic_content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "url",
                                            "url": url
                                        }
                                    })
                        else:
                            anthropic_content.append({
                                "type": "text",
                                "text": str(item)
                            })
                    content = anthropic_content
                else:
                    content = msg.content

                api_messages.append({
                    "role": msg.role,
                    "content": content
                })

        # Build request kwargs
        request_kwargs = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "timeout": kwargs.get('timeout', 30),
        }
        if not reasoning:
            request_kwargs['temperature'] = temperature
        if supports_json:
            request_kwargs['output_config'] = {'format': {
                'type': 'json_schema', 'schema': DOCUMENT_RESPONSE_SCHEMA}}

        # Add system message if present
        if system_messages:
            request_kwargs["system"] = '\n\n'.join(system_messages)

        response = self.client.messages.create(**request_kwargs)

        # Extract text from Anthropic response
        content_text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content_text += block.text

        return ChatResponse(
            content=content_text,
            tokens_used=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
            model=response.model if hasattr(response, 'model') else model,
            finish_reason=response.stop_reason if hasattr(response, 'stop_reason') else "",
            input_tokens=response.usage.input_tokens if response.usage else None,
            output_tokens=response.usage.output_tokens if response.usage else None,
            provider_request_id=getattr(response, 'id', None),
            usage=response.usage.model_dump() if response.usage else {},
        )

    def supports_vision(self) -> bool:
        return True


class VercelGatewayConnector(OpenAIConnector):
    """Fixed gateway and one upstream provider per requested model."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        endpoint = 'https://ai-gateway.vercel.sh/v1'
        if base_url and base_url.rstrip('/') != endpoint:
            raise ValueError('Vercel AI Gateway requires its official endpoint.')
        super().__init__(api_key, endpoint)

    def chat(self, messages, model, max_tokens=1000, temperature=0.6, **kwargs):
        provider, separator, identifier = model.partition('/')
        if provider not in {'anthropic', 'mistral', 'google', 'openai'} or not separator or not identifier:
            raise ValueError('Unsupported Vercel AI Gateway chat model.')
        # Do not allow a caller to add destinations or model fallbacks.
        kwargs['extra_body'] = {'providerOptions': {'gateway': {'only': [provider]}}}
        return super().chat(messages, model, max_tokens, temperature, **kwargs)


def get_connector(connector_type: str, api_key: str, base_url: Optional[str] = None) -> BaseConnector:
    """
    Factory function to get the appropriate connector based on type.

    Args:
        connector_type: One of 'openai', 'anthropic', 'openai_compatible'
        api_key: API key for the provider
        base_url: Optional custom base URL

    Returns:
        BaseConnector instance
    """
    connectors = {
        'openai': OpenAIConnector,
        'openai_compatible': OpenAIConnector,
        'anthropic': AnthropicConnector,
        'vercel_gateway': VercelGatewayConnector,
    }

    connector_class = connectors.get(connector_type)
    if not connector_class:
        raise ValueError(f"Unknown connector type: {connector_type}. Available: {list(connectors.keys())}")

    return connector_class(api_key=api_key, base_url=base_url)
