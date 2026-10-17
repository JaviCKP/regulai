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
    'base_revision', 'sha256', 'digest', 'folder_sha256', 'instruction_digest', 'request_id'})
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


def alias_text(context, text):
    """Compatibility policy for existing agent callers; all explicit categories."""
    if context.prompt_id:
        from .models import Prompt
        prompt = Prompt.objects.get(pk=context.prompt_id)
        if required(prompt):
            return protect_batch(prompt, [text], prefix='agent')[0]
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('privacy_input_invalid')
    references = list(TOKEN.finditer(text))
    tokens = {m.group() for m in references}
    known = set(ConversationAlias.objects.filter(**context.scope(), token__in=tokens).values_list('token', flat=True))
    if tokens != known:
        raise ValueError('privacy_reference_unavailable')
    spans = [(a, b, kind, kind != 'SECRET', 'local') for a, b, kind in detect_spans(text)
             if not any(a >= m.start() and b <= m.end() for m in references)]
    if len(spans) > MAX_MATCHES:
        raise ValueError('privacy_too_many_matches')
    for start, end, category, reversible, _ in reversed(resolve_spans(spans)):
        replacement = alias_value(context, category, text[start:end]) if reversible else f'[[REGULAI_{category}]]'
        text = text[:start] + replacement + text[end:]
    return text


def protect_tree(context, value):
    from .local_masking import _SECRET_KEY
    if isinstance(value, str):
        return alias_text(context, value)
    if isinstance(value, list):
        return [protect_tree(context, item) for item in value]
    if isinstance(value, dict):
        fields = {'nombre': 'PERSON', 'full_name': 'PERSON', 'titular': 'PERSON',
                  'email': 'EMAIL', 'correo': 'EMAIL', 'telefono': 'PHONE', 'dni': 'ID', 'iban': 'ACCOUNT'}
        def field(key, item):
            if key in STRUCTURAL_IDS and isinstance(item, str) and OPAQUE_ID.fullmatch(item) and context.prompt_id:
                from .privacy_policy import detect_ranges, revision_config
                turn = prepare_turn(context)
                if turn:
                    config, rules = revision_config(context, turn.revision)
                    if detect_ranges(item, config, rules, patterns=False):
                        raise ValueError('privacy_selected_protocol_identifier')
                    return item
            if _SECRET_KEY.fullmatch(key):
                return '[[REGULAI_SECRET]]'
            if key.lower() not in fields or not isinstance(item, str):
                return protect_tree(context, item)
            from .models import Prompt
            category = fields[key.lower()]
            if context.prompt_id and required(Prompt.objects.get(pk=context.prompt_id)):
                return protect_message(context, item, source_key=f'field:{category}:{keyed_digest(item)}',
                                       field_category=category)
            return alias_value(context, category, item)
        return {alias_text(context, key): field(key, item) for key, item in value.items()}
    return value


def protect_message(context, text, *, source_key, field_category=None):
    """Persist canonical text + occurrences atomically, before any caller sends.

    Idempotency keys identify message revisions, not transport chunks. Changed
    input under the same key is an error; callers cannot silently overwrite it.
    """
    from .models import PrivacyMessage, PrivacyOccurrence
    from .privacy_policy import detect_ranges, revision_config
    if not isinstance(source_key, str) or not 1 <= len(source_key) <= 160:
        raise ValueError('privacy_source_invalid')
    if not isinstance(text, str) or len(text.encode()) > MAX_BYTES:
        raise ValueError('privacy_input_invalid')
    with transaction.atomic():
        turn = prepare_turn(context)
        if turn is None:
            return text
        input_digest = keyed_digest(text)
        previous = PrivacyMessage.objects.filter(turn=turn, source_key=source_key).first()
        if previous:
            if previous.input_digest != input_digest:
                raise ValueError('privacy_idempotency_conflict')
            return previous.protected
        config, rules = revision_config(context, turn.revision)
        tokens = set(TOKEN.findall(text))
        known = set(ConversationAlias.objects.filter(**context.scope(), token__in=tokens).values_list('token', flat=True))
        if tokens != known:
            raise ValueError('privacy_reference_unavailable')
        ranges = detect_ranges(text, config, rules)
        if field_category and text and not TOKEN.fullmatch(text):
            ranges = resolve_spans([*ranges, (0, len(text), field_category,
                config.categories.get(field_category) == 'reversible', 'field')])
        replacements, variants = [], {}
        for start, end, category, reversible, detector in ranges:
            original = text[start:end]
            replacement = alias_value(context, category, original) if reversible else f'[[REGULAI_{category if category != "FIELD" else "SECRET"}]]'
            row = ConversationAlias.objects.filter(**context.scope(), token=replacement).first() if TOKEN.fullmatch(replacement) else None
            replacements.append((start, end, category, detector, replacement, row))
        # Unique, letter-only local markers retain occurrence identity through
        # D2 (including JSON reformatting). Searching by the final token would
        # confuse a new occurrence with a reference already present in input.
        markers = []
        for _ in replacements:
            while True:
                marker = 'PRIVACY' + ''.join(chr(65 + int(c, 16)) for c in secrets.token_hex(24))
                if marker not in text and marker not in markers:
                    markers.append(marker)
                    break
        protected = text
        for (start, end, _, _, _, _), marker in reversed(list(zip(replacements, markers))):
            protected = protected[:start] + marker + protected[end:]
        # D2 still covers unselected categories. It runs locally first so even a
        # configured HTTP masker cannot receive the selected originals.
        from .agents.aliases import preserve_aliases
        from .local_masking import mask_local_texts
        protected = preserve_aliases([protected], mask_local_texts)[0]
        located = []
        for item, marker in zip(replacements, markers):
            if protected.count(marker) != 1:
                raise ValueError('privacy_protected_reference_changed')
            located.append((protected.index(marker), marker, item))
        occurrences, shift = [], 0
        for position, marker, item in sorted(located):
            start, end, category, detector, replacement, row = item
            position += shift
            byte_start = len(protected[:position].encode('utf-8'))
            protected = protected[:position] + replacement + protected[position + len(marker):]
            shift += len(replacement) - len(marker)
            finish = byte_start + len(replacement.encode('utf-8'))
            occurrences.append((row, byte_start, finish, category, detector))
            if row and row.original != text[start:end]:
                variants[str(byte_start)] = text[start:end]
        message = PrivacyMessage.objects.create(turn=turn, source_key=source_key,
            input_digest=input_digest, protected=protected)
        for row, byte_start, finish, category, detector in occurrences:
            PrivacyOccurrence.objects.create(message=message, alias=row, start=byte_start, end=finish,
                category=category, detector=detector)
        if variants:
            message.variants = json.dumps(variants, ensure_ascii=False)
            message.save(update_fields=['variants'])
        return protected


def required(prompt):
    from .models import Company
    return bool((Company.objects.filter(pk=prompt.company_id).values_list('ai_config', flat=True).first() or {}).get('privacy')
                or PrivacyTurn.objects.filter(prompt__conversation_id=prompt.conversation_id).exists())


def protect_batch(prompt, texts, *, prefix='content'):
    """Content-addressed retries have one durable revision, never one per SSE."""
    if not required(prompt):
        return texts
    context = ProtectionContext.from_prompt(prompt)
    return [protect_message(context, text, source_key=f'{prefix}:{index}:{keyed_digest(text)}')
            for index, text in enumerate(texts)]


def block_unsupported(prompt):
    if required(prompt):
        raise ValueError('privacy_binary_channel_blocked')


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
    from .models import PrivacyUse
    with transaction.atomic():
        turn = prepare_turn(context)
        if turn is None:
            return
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


def outbound(prompt, call_key, texts, *, metadata=(), credentials=()):
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
    def unsafe(text):
        if detect_ranges(text, config, rules, patterns=False):
            return True
        try:
            shielded = json.dumps(structural_ids(json.loads(text)), ensure_ascii=False)
        except (ValueError, TypeError):
            shielded = text
        return bool(detect_ranges(shielded, config, rules))
    if (any(unsafe(text) for text in candidates)
            or any(detect_ranges(text, config, rules, patterns=False) for text in credentials)
            or any(value in text for value in values for text in candidates)):
        raise ValueError('privacy_original_at_boundary')
    record_use(context, call_key, texts)
