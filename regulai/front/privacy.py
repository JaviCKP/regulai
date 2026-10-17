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
            if PrivacyTurn.objects.filter(prompt_id=context.prompt_id).exists():
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
        return {alias_text(context, key): ('[[REGULAI_SECRET]]' if _SECRET_KEY.fullmatch(key)
                else alias_value(context, fields[key.lower()], item)
                if key.lower() in fields and isinstance(item, str) else protect_tree(context, item))
                for key, item in value.items()}
    return value
