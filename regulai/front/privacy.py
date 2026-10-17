"""Common server protection primitives, independent of agent execution/runtime.

Only protected text leaves these functions. Presentation uses a different module
and must authorize a turn/inference before loading any original.
"""
import hashlib
import hmac
import json
import re
import secrets
import unicodedata
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from .local_masking import _PLACEHOLDER, _matching_view, detect_spans
from .models import Conversation, ConversationAlias, Profile, PrivacyRevision, PrivacyTurn, PrivacySelection

TOKEN = re.compile(r'\[\[R_[A-Z]{1,24}_[a-f0-9]{32}\]\]')
MAX_BYTES = 512_000
MAX_MATCHES = 4096
STRUCTURAL_IDS = frozenset({'id', 'execution', 'execution_id', 'attempt', 'attempt_id', 'call_id',
    'reference', 'revision_id', 'installation_id', 'artifact_id', 'input_reference', 'logical_id',
    'base_revision', 'sha256', 'digest', 'folder_sha256', 'instruction_digest', 'request_id', 'reservation_id'})
OPAQUE_ID = re.compile(r'(?:[a-f0-9]{64}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})')


def structural_ids(value):
    """Shield typed protocol IDs from accidental phone/card pattern matches.

    Explicit selections/YARA are always checked on the unshielded value first.
    Arbitrary text (including a JSON string in a message) receives no exemption.
    """
    if isinstance(value, list):
        return [structural_ids(item) for item in value]
    if isinstance(value, dict):
        return {key: 'PROTOCOLIDENTIFIER' if key in STRUCTURAL_IDS and isinstance(item, str)
                and OPAQUE_ID.fullmatch(item) else structural_ids(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class ProtectionContext:
    company_id: int
    user_id: int
    conversation_id: int
    prompt_id: int | None = None

    @classmethod
    def from_prompt(cls, prompt):
        if not prompt.company_id or not prompt.conversation_id:
            raise ValueError('privacy_scope_missing')
        return cls(prompt.company_id, prompt.user_id, prompt.conversation_id, prompt.pk)

    def scope(self):
        return dict(company_id=self.company_id, user_id=self.user_id, conversation_id=self.conversation_id)


def normalize(kind, value):
    if kind in ('PERSON', 'FIELD'):
        return unicodedata.normalize('NFC', value)
    value = _matching_view(value)[0].strip()
    if kind == 'EMAIL':
        value = re.sub(r'\s+(arroba|at)\s+', '@', value, flags=re.I)
        value = re.sub(r'\s+(punto|dot)\s+', '.', value, flags=re.I)
        local, at, domain = value.rpartition('@')
        return local + at + domain.lower()
    if kind in ('ID', 'ACCOUNT', 'CARD', 'PHONE'):
        return re.sub(r'[\s.()\-]', '', value).upper()
    raise ValueError('privacy_category_unsupported')


def keyed_digest(value, *, key=None):
    return hmac.new((key or settings.SECRET_KEY).encode(), value.encode(), hashlib.sha256).hexdigest()


def authorize(context):
    """Owner and current tenant, never an administrator override or stale actor."""
    from .access import authorized_conversations
    profile = Profile.objects.select_related('user', 'company').filter(user_id=context.user_id,
        company_id=context.company_id, user__is_active=True).first()
    if not profile or not authorized_conversations(profile.user).filter(pk=context.conversation_id).exists():
        raise ValueError('privacy_access_revoked')
    return profile


def effective_revision(context):
    profile = authorize(context)
    reference = profile.company.ai_config.get('privacy')
    if reference is None:
        return None
    if (not isinstance(reference, dict) or reference.get('version') != 1
            or type(reference.get('revision_id')) is not int):
        raise ValueError('privacy_revision_invalid')
    revision = PrivacyRevision.objects.filter(pk=reference['revision_id'], company_id=context.company_id).first()
    if not revision or not revision.configuration:
        raise ValueError('privacy_revision_unavailable')
    return revision


def prepare_turn(context):
    """Immutable effective revision, including exact conversation selections."""
    if not context.prompt_id:
        raise ValueError('privacy_request_missing')
    with transaction.atomic():
        Conversation.objects.select_for_update().get(pk=context.conversation_id)
        revision = effective_revision(context)
        if revision is None:
            if PrivacyTurn.objects.filter(prompt__conversation_id=context.conversation_id).exists():
                raise ValueError('privacy_policy_revoked')
            return None
        selections = list(PrivacySelection.objects.filter(alias__company_id=context.company_id,
            alias__user_id=context.user_id, alias__conversation_id=context.conversation_id).order_by('pk').values_list('pk', flat=True))
        fingerprint = keyed_digest(json.dumps([revision.pk, revision.fingerprint, selections]))
        turn, created = PrivacyTurn.objects.get_or_create(prompt_id=context.prompt_id,
            defaults={'revision': revision, 'fingerprint': fingerprint})
        if not created and (turn.revision_id != revision.pk or turn.fingerprint != fingerprint):
            raise ValueError('privacy_policy_changed')
        # The revision was just authorized and is immutable; avoid refetching
        # the same row through the existing turn's lazy foreign key.
        turn.revision = revision
        return turn


def _keys():
    # Existing aliases used SECRET_KEY and version 1. Preserve that default and
    # allow deployments to retain old keys while introducing a new current key.
    keys = getattr(settings, 'PRIVACY_LOOKUP_KEYS', {1: settings.SECRET_KEY})
    if (not isinstance(keys, dict) or not keys or any(type(v) is not int or v < 1
            or not isinstance(k, str) or not k for v, k in keys.items())):
        raise ValueError('privacy_lookup_keys_invalid')
    return keys


def alias_value(context, kind, original):
    if not isinstance(original, str) or len(original.encode('utf-8')) > MAX_BYTES:
        raise ValueError('privacy_input_invalid')
    if _PLACEHOLDER.fullmatch(original):
        return original
    if kind == 'SECRET' or any(category == 'SECRET' for _, _, category in detect_spans(original)):
        return '[[REGULAI_SECRET]]'
    if TOKEN.fullmatch(original):
        if not ConversationAlias.objects.filter(**context.scope(), kind=kind, token=original).exists():
            raise ValueError('privacy_reference_unavailable')
        return original
    normalized = normalize(kind, original)
    keys = _keys()
    # Serializes creation even across key rotation. No transaction spans IO.
    with transaction.atomic():
        if not Conversation.objects.select_for_update().filter(pk=context.conversation_id, user_id=context.user_id).exists():
            raise ValueError('privacy_scope_unavailable')
        for version, key in sorted(keys.items()):
            scope = f'{context.company_id}:{context.user_id}:{context.conversation_id}:{kind}:{version}:'
            lookup = keyed_digest(scope + normalized, key=key)
            row = ConversationAlias.objects.filter(**context.scope(), kind=kind, version=version, lookup_digest=lookup).first()
            if row:
                if not row.original:
                    raise ValueError('privacy_original_unavailable')
                return row.token
        version = max(keys)
        scope = f'{context.company_id}:{context.user_id}:{context.conversation_id}:{kind}:{version}:'
        row = ConversationAlias.objects.create(**context.scope(), kind=kind, version=version,
            lookup_digest=keyed_digest(scope + normalized, key=keys[version]),
            token=f'[[R_{kind}_{secrets.token_hex(16)}]]', original=original)
        return row.token


def resolve_spans(spans):
    """Merge all ranges before any mutation. Ambiguous unions are irreversible."""
    merged = []
    for start, end, kind, reversible, detector in sorted(set(spans), key=lambda x: (x[0], -x[1])):
        if merged and start < merged[-1][1]:
            left, right, previous, recover, source = merged[-1]
            identical = (start, end, kind, reversible) == (left, right, previous, recover)
            if not identical:
                merged[-1] = (left, max(end, right), 'SECRET', False, 'overlap')
        else:
            merged.append((start, end, kind, reversible, detector))
    return merged


def _alias_batch(context, values, *, locked=False):
    """Resolve distinct sensitive values with one scoped lookup and one insert.

    The cache is local to this synchronous transaction. Conversation locking and
    the existing unique constraint serialize competing writers and key rotation.
    """
    values = list(dict.fromkeys(values))
    if not values:
        return {}
    keys = _keys()
    normalized, results, token_values = {}, {}, {}
    for kind, original in values:
        if not isinstance(original, str) or len(original.encode('utf-8')) > MAX_BYTES:
            raise ValueError('privacy_input_invalid')
        if _PLACEHOLDER.fullmatch(original):
            results[kind, original] = (original, None)
        elif kind == 'SECRET' or any(category == 'SECRET' for _, _, category in detect_spans(original)):
            results[kind, original] = ('[[REGULAI_SECRET]]', None)
        elif TOKEN.fullmatch(original):
            token_values[kind, original] = original
        else:
            normalized[kind, original] = normalize(kind, original)
    if not locked and (normalized or token_values):
        if not Conversation.objects.select_for_update().filter(
                pk=context.conversation_id, user_id=context.user_id).exists():
            raise ValueError('privacy_scope_unavailable')
    if token_values:
        by_token = {row.token: row for row in ConversationAlias.objects.filter(
            **context.scope(), token__in=set(token_values.values()))}
        for (kind, original), token in token_values.items():
            row = by_token.get(token)
            if row is None or row.kind != kind:
                raise ValueError('privacy_reference_unavailable')
            results[kind, original] = (token, row)
    lookups = {}
    for kind, value in dict.fromkeys((kind, value) for (kind, _), value in normalized.items()):
        for version, key in sorted(keys.items()):
            scope = f'{context.company_id}:{context.user_id}:{context.conversation_id}:{kind}:{version}:'
            lookups[kind, value, version] = keyed_digest(scope + value, key=key)
    rows = {(row.kind, row.version, row.lookup_digest): row for row in
            ConversationAlias.objects.filter(**context.scope(), lookup_digest__in=list(lookups.values()))}
    resolved, created = {}, []
    for (kind, original), value in normalized.items():
        identity = kind, value
        if identity not in resolved:
            row = next((rows.get((kind, version, lookups[kind, value, version]))
                        for version in sorted(keys)
                        if (kind, version, lookups[kind, value, version]) in rows), None)
            if row is not None:
                if not row.original:
                    raise ValueError('privacy_original_unavailable')
            else:
                version = max(keys)
                row = ConversationAlias(**context.scope(), kind=kind, version=version,
                    lookup_digest=lookups[kind, value, version],
                    token=f'[[R_{kind}_{secrets.token_hex(16)}]]', original=original)
                created.append(row)
            resolved[identity] = row
        row = resolved[identity]
        results[kind, original] = (row.token, row)
    if created:
        ConversationAlias.objects.bulk_create(created)
    return results


def _mask_batches(texts):
    """Apply local D2 in bounded groups, preserving every fragment boundary."""
    from .agents.aliases import preserve_aliases
    from .local_masking import MAX_BATCH_BYTES, MAX_SEGMENTS, mask_local_texts
    result, group, size = [], [], 0
    for text in texts:
        # preserve_aliases shields each token with a fixed 50-byte sentinel.
        # Budget its transformed size, including every repeated reference.
        text_size = len(text.encode('utf-8')) + sum(
            50 - len(match.group()) for match in TOKEN.finditer(text))
        if group and (size + text_size > MAX_BATCH_BYTES or len(group) == MAX_SEGMENTS):
            result.extend(preserve_aliases(group, mask_local_texts))
            group, size = [], 0
        group.append(text)
        size += text_size
    if group:
        result.extend(preserve_aliases(group, mask_local_texts))
    return result


def _protect_many(context, entries, *, persist, structural=()):
    """One local operation; no authorization or policy cache survives its return.

    Entries retain their historical content-addressed source keys. Reads, alias
    resolution and durable writes are grouped, while detectors still receive
    each complete fragment so YARA conditions cannot match across fragments.
    No provider/network work is performed inside this transaction.
    """
    from .models import PrivacyMessage, PrivacyOccurrence
    from .privacy_policy import detect_ranges, revision_config
    unique = {}
    for source_key, text, category in entries:
        if not isinstance(source_key, str) or not 1 <= len(source_key) <= 160:
            raise ValueError('privacy_source_invalid')
        if not isinstance(text, str) or len(text.encode()) > MAX_BYTES:
            raise ValueError('privacy_input_invalid')
        entry = (text, category)
        if source_key in unique and unique[source_key] != entry:
            raise ValueError('privacy_idempotency_conflict')
        unique[source_key] = entry
    with transaction.atomic():
        turn = prepare_turn(context) if persist else None
        if persist and turn is None:
            return {key: text for key, (text, _) in unique.items()}
        config, rules = revision_config(context, turn.revision) if turn else (None, ())
        if turn:
            for value in structural:
                if detect_ranges(value, config, rules, patterns=False):
                    raise ValueError('privacy_selected_protocol_identifier')
        previous = {row.source_key: row for row in PrivacyMessage.objects.filter(
            turn=turn, source_key__in=list(unique))} if turn else {}
        output, pending = {}, {}
        for key, (text, category) in unique.items():
            row = previous.get(key)
            if row:
                if row.input_digest != keyed_digest(text):
                    raise ValueError('privacy_idempotency_conflict')
                output[key] = row.protected
            else:
                pending[key] = (text, category)
        tokens = {token for text, _ in pending.values() for token in TOKEN.findall(text)}
        known = set(ConversationAlias.objects.filter(**context.scope(), token__in=tokens)
                    .values_list('token', flat=True)) if tokens else set()
        if tokens != known:
            raise ValueError('privacy_reference_unavailable')
        spans, values = {}, []
        for key, (text, category) in pending.items():
            if turn:
                ranges = detect_ranges(text, config, rules)
                if category and text and not TOKEN.fullmatch(text):
                    ranges = resolve_spans([*ranges, (0, len(text), category,
                        config.categories.get(category) == 'reversible', 'field')])
            elif category:
                # Legacy explicit fields alias the whole value, including empty
                # values; preserve that existing contract.
                ranges = [(0, len(text), category, True, 'field')]
            else:
                references = [match.span() for match in TOKEN.finditer(text)]
                ranges = [(a, b, kind, kind != 'SECRET', 'local')
                    for a, b, kind in detect_spans(text)
                    if not any(a >= left and b <= right for left, right in references)]
                if len(ranges) > MAX_MATCHES:
                    raise ValueError('privacy_too_many_matches')
                ranges = resolve_spans(ranges)
            spans[key] = ranges
            # Legacy replacement visited the text from right to left. Retain
            # which spelling becomes canonical for equivalent values.
            alias_ranges = ranges if turn else reversed(ranges)
            values.extend((kind, text[start:end]) for start, end, kind, recover, _ in alias_ranges if recover)
        aliases = _alias_batch(context, values, locked=bool(turn))
        prepared = []
        for key, (text, _) in pending.items():
            replacements, markers = [], []
            for start, end, category, reversible, detector in spans[key]:
                replacement, row = (aliases[category, text[start:end]] if reversible else
                    (f'[[REGULAI_{category if category != "FIELD" else "SECRET"}]]', None))
                replacements.append((start, end, category, detector, replacement, row))
                while True:
                    marker = 'PRIVACY' + ''.join(chr(65 + int(c, 16)) for c in secrets.token_hex(24))
                    if marker not in text and marker not in markers:
                        markers.append(marker)
                        break
            protected = text
            for (start, end, _, _, _, _), marker in reversed(list(zip(replacements, markers))):
                protected = protected[:start] + marker + protected[end:]
            prepared.append((key, text, protected, replacements, markers))
        masked = _mask_batches([item[2] for item in prepared]) if turn else [item[2] for item in prepared]
        messages, occurrences = [], []
        for (key, text, _, replacements, markers), protected in zip(prepared, masked):
            located = []
            for item, marker in zip(replacements, markers):
                if protected.count(marker) != 1:
                    raise ValueError('privacy_protected_reference_changed')
                located.append((protected.index(marker), marker, item))
            positions, variants, shift = [], {}, 0
            for position, marker, item in sorted(located):
                start, end, category, detector, replacement, row = item
                position += shift
                byte_start = len(protected[:position].encode('utf-8'))
                protected = protected[:position] + replacement + protected[position + len(marker):]
                shift += len(replacement) - len(marker)
                finish = byte_start + len(replacement.encode('utf-8'))
                positions.append((row, byte_start, finish, category, detector))
                if row and row.original != text[start:end]:
                    variants[str(byte_start)] = text[start:end]
            output[key] = protected
            if turn:
                message = PrivacyMessage(turn=turn, source_key=key, input_digest=keyed_digest(text),
                    protected=protected, variants=json.dumps(variants, ensure_ascii=False))
                messages.append(message)
                occurrences.extend(PrivacyOccurrence(message=message, alias=row, start=start, end=end,
                    category=category, detector=detector) for row, start, end, category, detector in positions)
        if messages:
            PrivacyMessage.objects.bulk_create(messages)
        if occurrences:
            PrivacyOccurrence.objects.bulk_create(occurrences)
        return output


def alias_text(context, text):
    """Compatibility policy for existing agent callers; all explicit categories."""
    active = bool(context.prompt_id and required(context))
    key = f'agent:0:{keyed_digest(text)}' if isinstance(text, str) else 'agent:invalid'
    return _protect_many(context, [(key, text, None)], persist=active)[key]


def protect_tree(context, value):
    """Protect arbitrary keys and text with one operation-scoped policy snapshot."""
    from .local_masking import _SECRET_KEY
    fields = {'nombre': 'PERSON', 'full_name': 'PERSON', 'titular': 'PERSON',
              'email': 'EMAIL', 'correo': 'EMAIL', 'telefono': 'PHONE', 'dni': 'ID', 'iban': 'ACCOUNT'}
    active = bool(context.prompt_id and required(context))
    entries, structural = [], []

    def entry(text, category=None):
        key = (f'field:{category}:{keyed_digest(text)}' if category else
               f'agent:0:{keyed_digest(text)}')
        entries.append((key, text, category))
        return key

    def collect(item):
        if isinstance(item, str):
            entry(item)
        elif isinstance(item, list):
            for child in item:
                collect(child)
        elif isinstance(item, dict):
            for key, child in item.items():
                entry(key)
                if key in STRUCTURAL_IDS and isinstance(child, str) and OPAQUE_ID.fullmatch(child) and active:
                    structural.append(child)
                elif _SECRET_KEY.fullmatch(key):
                    continue
                elif key.lower() in fields and isinstance(child, str):
                    entry(child, fields[key.lower()])
                else:
                    collect(child)
    collect(value)
    protected = _protect_many(context, entries, persist=active, structural=structural)

    def rebuild(item):
        if isinstance(item, str):
            return protected[f'agent:0:{keyed_digest(item)}']
        if isinstance(item, list):
            return [rebuild(child) for child in item]
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if key in STRUCTURAL_IDS and isinstance(child, str) and OPAQUE_ID.fullmatch(child) and active:
                    safe = child
                elif _SECRET_KEY.fullmatch(key):
                    safe = '[[REGULAI_SECRET]]'
                elif key.lower() in fields and isinstance(child, str):
                    safe = protected[f'field:{fields[key.lower()]}:{keyed_digest(child)}']
                else:
                    safe = rebuild(child)
                result[protected[f'agent:0:{keyed_digest(key)}']] = safe
            return result
        return item
    return rebuild(value)


def protect_message(context, text, *, source_key, field_category=None):
    """Persist canonical text + occurrences atomically before any caller sends."""
    return _protect_many(context, [(source_key, text, field_category)], persist=True)[source_key]

def required(prompt):
    from .models import Company
    return bool((Company.objects.filter(pk=prompt.company_id).values_list('ai_config', flat=True).first() or {}).get('privacy')
                or PrivacyTurn.objects.filter(prompt__conversation_id=prompt.conversation_id).exists())


def protect_batch(prompt, texts, *, prefix='content'):
    """Content-addressed retries have one durable revision, never one per SSE."""
    if not required(prompt):
        return texts
    context = ProtectionContext.from_prompt(prompt)
    entries = [(f'{prefix}:{index}:{keyed_digest(text)}', text, None)
               for index, text in enumerate(texts)]
    protected = _protect_many(context, entries, persist=True)
    return [protected[key] for key, _, _ in entries]


def block_unsupported(prompt):
    if required(prompt):
        raise ValueError('privacy_binary_channel_blocked')


def protected_user_message(prompt):
    """Canonical revision of this user's input, shared by admission and bootstrap."""
    from .models import PrivacyMessage
    if not required(prompt):
        return alias_text(ProtectionContext.from_prompt(prompt), prompt.content)
    context = ProtectionContext.from_prompt(prompt)
    turn = prepare_turn(context)
    previous = PrivacyMessage.objects.filter(turn=turn, input_digest=keyed_digest(prompt.content)).first()
    return previous.protected if previous else protect_message(context, prompt.content, source_key='user:input')


def transient_response(prompt, text):
    """Check a cumulative stream prefix without persisting SSE occurrences."""
    from .privacy_policy import detect_ranges, revision_config
    from .agents.aliases import preserve_aliases
    from .local_masking import mask_local_texts
    context = ProtectionContext.from_prompt(prompt)
    turn = prepare_turn(context)
    config, rules = revision_config(context, turn.revision)
    for start, end, category, recover, _ in reversed(detect_ranges(text, config, rules)):
        value = alias_value(context, category, text[start:end]) if recover else '[[REGULAI_SECRET]]'
        text = text[:start] + value + text[end:]
    return preserve_aliases([text], mask_local_texts)[0]


def stream_cut(prompt, text, cut):
    """A selected literal or YARA match cannot straddle a published prefix."""
    from .privacy_policy import revision_config
    context = ProtectionContext.from_prompt(prompt)
    turn = prepare_turn(context)
    config, _ = revision_config(context, turn.revision)
    if config.yara:
        return 0  # Full-condition rules require the complete response.
    previous = None
    while previous != cut:
        previous = cut
        for literal in config.literals:
            for size in range(min(len(literal.text) - 1, cut), 0, -1):
                if text.endswith(literal.text[:size], 0, cut):
                    cut -= size
                    break
    reserved = text.rfind('[[R_', 0, cut)
    if reserved >= 0 and ']]' not in text[reserved:cut]:
        cut = reserved
    return cut


def record_use(context, call_key, texts):
    """Idempotent inference allowlist. No claim about delivery or money is made."""
    from collections import Counter
    from .models import PrivacyUse, PrivacyCall
    with transaction.atomic():
        turn = prepare_turn(context)
        if turn is None:
            return
        signature = keyed_digest(json.dumps(texts, ensure_ascii=False))
        call, _ = PrivacyCall.objects.get_or_create(turn=turn, call_key=call_key, defaults={'input_digest': signature})
        if call.input_digest != signature:
            raise ValueError('privacy_idempotency_conflict')
        counts = Counter(token for text in texts for token in TOKEN.findall(text))
        rows = list(ConversationAlias.objects.filter(**context.scope(), token__in=counts))
        if len(rows) != len(counts):
            raise ValueError('privacy_reference_unavailable')
        historical = None
        for row in rows:
            if (not row.privacyoccurrence_set.filter(message__turn=turn).exists()
                    and not PrivacyUse.objects.filter(alias=row,
                        turn__prompt__conversation_id=context.conversation_id,
                        turn__prompt__user_id=context.user_id, turn__prompt__company_id=context.company_id,
                        turn__prompt__status='completed').exists()):
                if historical is None:
                    from .chat_service import authorized_history
                    actor = authorize(context).user
                    historical = set(token for message in authorized_history(actor,
                        Conversation.objects.get(pk=context.conversation_id)) for token in TOKEN.findall(message.content))
                if row.token not in historical:
                    raise ValueError('privacy_reference_not_issued')
            use, _ = PrivacyUse.objects.get_or_create(turn=turn, call_key=call_key, alias=row,
                defaults={'count': counts[row.token]})
            if use.count != counts[row.token]:
                raise ValueError('privacy_idempotency_conflict')


def usage_directions(texts, sections):
    """Only counts cross into receipts; section contents are never persisted here."""
    from collections import Counter
    expected = Counter(token for text in texts for token in TOKEN.findall(text))
    result, observed = {}, Counter()
    for direction, text in sections:
        if direction not in {'input', 'history', 'context'}:
            raise ValueError('privacy_direction_invalid')
        for token, count in Counter(TOKEN.findall(text)).items():
            row = result.setdefault(token, {'input': 0, 'history': 0, 'context': 0})
            row[direction] += count
            observed[token] += count
    if observed != expected:
        raise ValueError('privacy_direction_mismatch')
    return result


def outbound(prompt, call_key, texts, *, metadata=(), credentials=(), record=True):
    if not required(prompt):
        return
    context = ProtectionContext.from_prompt(prompt)
    turn = prepare_turn(context)
    aliases = ConversationAlias.objects.filter(**context.scope(), privacyoccurrence__message__turn=turn).distinct()
    values = [row.original for row in aliases if row.original]
    for row in turn.messages.all():
        values.extend(json.loads(row.variants).values())
    candidates = [text for text in [*texts, *metadata] if isinstance(text, str)]
    from .privacy_policy import detect_ranges, revision_config
    config, rules = revision_config(context, turn.revision)
    def semantic_forms(text):
        from urllib.parse import unquote_plus
        yield text
        # Destinations and JSON string values can carry percent-encoded PII.
        # Bound decoding; an encoding deeper than this is not accepted.
        for _ in range(3):
            decoded = unquote_plus(text)
            if decoded == text:
                return
            yield decoded
            text = decoded
        if unquote_plus(text) != text:
            raise ValueError('privacy_encoding_too_deep')
    def unsafe(text):
        from decimal import Decimal
        if any(detect_ranges(value, config, rules, patterns=False) for value in semantic_forms(text)):
            return True
        try:
            decoded = json.loads(text, parse_float=Decimal)
        except (ValueError, TypeError):
            decoded = text
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                # JSON numeric scalars can be phone/account/card values too.
                # Normalize scientific notation before applying the detectors.
                number = Decimal(str(value))
                if not number.is_finite() or abs(number.adjusted()) > 128 or len(number.as_tuple().digits) > 128:
                    raise ValueError('privacy_number_out_of_bounds')
                yield format(number, 'f')
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
            elif isinstance(value, dict):
                for key, item in value.items():
                    yield key
                    yield from strings(item)
        # JSON escaping is a transport representation, not privacy protection.
        if any(detect_ranges(form, config, rules, patterns=False)
               for value in strings(decoded) for form in semantic_forms(value)):
            return True
        shielded = structural_ids(decoded)
        return any(detect_ranges(form, config, rules)
                   for value in strings(shielded) for form in semantic_forms(value))
    if (any(unsafe(text) for text in candidates)
            or any(detect_ranges(value, config, rules, patterns=False) for text in credentials for value in semantic_forms(text))
            or any(value in text for value in values for text in candidates)):
        raise ValueError('privacy_original_at_boundary')
    if record:
        record_use(context, call_key, texts)
