"""Presentation-only incremental projection. Never use this module for inference.

The caller supplies an inference-scoped map after current authorization. Offsets
refer to UTF-8 bytes in the canonical protected text, never to rendered text.
"""
import codecs
import re
from dataclasses import dataclass

VERSION = 1
PREFIX = '[[R_'
MAX_TOKEN = 63
TOKEN = re.compile(r'\[\[R_[A-Z]{1,24}_[a-f0-9]{32}\]\]')
UNAVAILABLE = '[referencia no disponible]'


@dataclass(frozen=True)
class Segment:
    kind: str
    text: str
    start: int
    end: int


class Projection:
    """One parser per consumer/message; originals are opaque atomic text segments.

    This is a codec, not an authorization boundary. A presentation adapter must
    revalidate before *each* feed, including replay and finalization. No global
    state, DB reads per character, recursive expansion or unbounded token buffer.
    """

    def __init__(self, aliases):
        self.aliases = dict(aliases)
        self.decoder = codecs.getincrementaldecoder('utf-8')('strict')
        self.pending = ''
        self.offset = 0
        self.discard_start = None
        self.discard_bracket = False
        self.closed = False

    def feed(self, value, *, final=False):
        if self.closed:
            raise ValueError('projection_closed')
        if isinstance(value, str):
            value = value.encode('utf-8')
        if not isinstance(value, bytes):
            raise ValueError('projection_requires_utf8')
        decoded = self.decoder.decode(value, final=final)
        segments = []
        plain = []
        plain_start = self.offset

        def emit(kind, text, start, end):
            nonlocal plain_start
            if kind == 'text':
                if not plain:
                    plain_start = start
                plain.append(text)
            else:
                if plain:
                    segments.append(Segment('text', ''.join(plain), plain_start, start))
                    plain.clear()
                segments.append(Segment(kind, text, start, end))

        def consume(text, kind='text', shown=None):
            start = self.offset
            self.offset += len(text.encode('utf-8'))
            emit(kind, text if shown is None else shown, start, self.offset)

        for char in decoded:
            if self.discard_start is not None:
                self.offset += len(char.encode('utf-8'))
                if char == ']' and self.discard_bracket:
                    emit('unavailable', UNAVAILABLE, self.discard_start, self.offset)
                    self.discard_start = None
                self.discard_bracket = char == ']'
                continue
            self.pending += char
            while self.pending:
                if PREFIX.startswith(self.pending):
                    break
                if self.pending.startswith(PREFIX):
                    if self.pending.endswith(']]'):
                        token = self.pending
                        original = self.aliases.get(token) if TOKEN.fullmatch(token) else None
                        consume(token, 'original' if original else 'unavailable', original or UNAVAILABLE)
                        self.pending = ''
                    elif len(self.pending) >= MAX_TOKEN:
                        self.discard_start = self.offset
                        self.offset += len(self.pending.encode('utf-8'))
                        self.discard_bracket = self.pending.endswith(']')
                        self.pending = ''
                    break
                consume(self.pending[0])
                self.pending = self.pending[1:]
        if final:
            if self.discard_start is not None:
                emit('unavailable', UNAVAILABLE, self.discard_start, self.offset)
                self.discard_start = None
            if self.pending:
                reserved = self.pending.startswith(PREFIX) or self.pending == '[[R'
                consume(self.pending, 'unavailable' if reserved else 'text', UNAVAILABLE if reserved else None)
                self.pending = ''
            self.closed = True
        if plain:
            segments.append(Segment('text', ''.join(plain), plain_start, self.offset))
        return segments


def project(text, aliases):
    return Projection(aliases).feed(text, final=True)
