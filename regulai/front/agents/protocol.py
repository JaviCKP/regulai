"""Versioned internal wire contract. No Django or provider SDK in the executor."""
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class ToolCall(Strict):
    id: str = Field(min_length=1, max_length=160, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_]+$')
    args: dict[str, Any]

    def openai(self):
        return {'id': self.id, 'type': 'function', 'function': {
            'name': self.name, 'arguments': json.dumps(self.args, ensure_ascii=False, allow_nan=False)}}


class TextPart(Strict):
    type: Literal['text']
    text: str


class ImageReference(Strict):
    type: Literal['image_ref']
    reference: str = Field(pattern=r'^[0-9a-f-]{36}$')

    @field_validator('reference')
    @classmethod
    def valid_reference(cls, value):
        return str(UUID(value))


class WireMessage(Strict):
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str | list[TextPart | ImageReference]
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=32)
    tool_call_id: str | None = Field(default=None, max_length=160)
    name: str | None = Field(default=None, max_length=64)

    @model_validator(mode='after')
    def coherent_role(self):
        if (self.tool_calls and self.role != 'assistant') or ((self.role == 'tool') != bool(self.tool_call_id)):
            raise ValueError('Invalid tool message')
        if self.role == 'tool' and (not self.name or not isinstance(self.content, str)):
            raise ValueError('Invalid tool result')
        return self


class InferenceRequest(Strict):
    version: Literal[1] = 1
    call_id: str
    purpose: Literal['generation', 'compaction', 'vision'] = 'generation'
    messages: list[WireMessage] = Field(min_length=1, max_length=4096)
    tools: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode='after')
    def valid_identity(self):
        UUID(self.call_id)
        if len(set(self.tools)) != len(self.tools):
            raise ValueError('Duplicate tool')
        return self


class ToolResultRequest(Strict):
    version: Literal[1] = 1
    call: ToolCall
    raw: Any
    failed: bool = False


# Minimal initial contract. This catalogue is owned by Regulay, never by a model,
# dynamic tool schema, skill, or MCP server. Additional views require reviewed code.
TOOL_PARAMETERS = {
    'build_presentation': {'input_reference': {'type': 'string'}, 'template': {'type': 'string'},
                          'title': {'type': 'string'}, 'section': {'type': 'string'}},
    'edit_presentation': {'logical_id': {'type': 'string'}, 'base_revision': {'type': 'string'},
                         'slide': {'type': 'integer'}, 'field': {'type': 'string'}, 'value': {'type': 'string'}},
    'build_document': {'input_reference': {'type': 'string'}, 'format': {'type': 'string'},
                       'title': {'type': 'string'}, 'section': {'type': 'string'}},
    'edit_document': {'logical_id': {'type': 'string'}, 'base_revision': {'type': 'string'},
                      'field': {'type': 'string'}, 'value': {'type': 'string'}},
    'export_pdf': {'logical_id': {'type': 'string'}, 'base_revision': {'type': 'string'}},
    'build_excel': {'input_reference': {'type': 'string'}, 'title': {'type': 'string'}},
    'rename_excel': {'logical_id': {'type': 'string'}, 'base_revision': {'type': 'string'}, 'title': {'type': 'string'}},
    'csv_totals': {'input_path': {'type': 'string'}},
    'inspect_csv': {'input_path': {'type': 'string'}},
    'execute': {'command': {'type': 'string'}, 'timeout': {'type': 'integer'}},
    'read_file': {'file_path': {'type': 'string'}, 'offset': {'type': 'integer'}, 'limit': {'type': 'integer'}},
    'ls': {'path': {'type': 'string'}},
    'glob': {'pattern': {'type': 'string'}, 'path': {'type': 'string'}},
    'grep': {'pattern': {'type': 'string'}, 'path': {'type': 'string'}, 'glob': {'type': 'string'}, 'output_mode': {'type': 'string'}},
    'write_file': {'file_path': {'type': 'string'}, 'content': {'type': 'string'}},
    'edit_file': {'file_path': {'type': 'string'}, 'old_string': {'type': 'string'}, 'new_string': {'type': 'string'}, 'replace_all': {'type': 'boolean'}},
    'write_todos': {'todos': {'type': 'array', 'items': {'type': 'object'}}},
}
REQUIRED = {'execute': ['command'], 'read_file': ['file_path'], 'ls': ['path'],
    'build_presentation': ['input_reference', 'template', 'title', 'section'],
    'edit_presentation': ['logical_id', 'base_revision', 'slide', 'field', 'value'],
    'build_document': ['input_reference', 'format', 'title', 'section'],
    'edit_document': ['logical_id', 'base_revision', 'field', 'value'],
    'export_pdf': ['logical_id', 'base_revision'],
    'build_excel': ['input_reference', 'title'], 'rename_excel': ['logical_id', 'base_revision', 'title'],
    'glob': ['pattern'], 'grep': ['pattern'], 'write_file': ['file_path', 'content'],
    'edit_file': ['file_path', 'old_string', 'new_string'], 'write_todos': ['todos'],
    'csv_totals': ['input_path'], 'inspect_csv': ['input_path']}


def tool_schema(name):
    return {'type': 'function', 'function': {'name': name,
        'description': ('Return a checked view of the authorized CSV.' if name in ('csv_totals', 'inspect_csv')
                        else 'Operate locally. Raw output is withheld from the model.'),
        'parameters': {'type': 'object', 'properties': TOOL_PARAMETERS[name],
                       'required': REQUIRED[name], 'additionalProperties': False}}}


def validate_arguments(call):
    parameters = TOOL_PARAMETERS.get(call.name)
    if parameters is None or set(call.args) - set(parameters) or not set(REQUIRED[call.name]) <= set(call.args):
        raise ValueError('Invalid tool arguments')
    types = {'string': str, 'integer': int, 'boolean': bool, 'array': list}
    if any(type(value) is not types[parameters[key]['type']] for key, value in call.args.items()):
        raise ValueError('Invalid tool argument type')
    json.dumps(call.args, allow_nan=False)
