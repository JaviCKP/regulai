"""Conversation scoped value aliases, not entity recognition or identity linkage."""
import secrets
from front.models import ConversationAlias
from front.privacy import TOKEN, ProtectionContext, normalize
from front.privacy import alias_value as _alias_value, alias_text as _alias_text


def preserve_aliases(texts, protect):
    """Known aliases have already been authorized; shield random digit runs from D2.

    Sentinels contain letters only (no ID/card/phone patterns). They are local to
    one transform and never enter model context or the correspondence registry.
    An HTTP masker that changes/removes one fails closed instead of losing IDs.
    """
    substitutions = {}
    joined = '\n'.join(texts)
    for token in set(TOKEN.findall(joined)):
        while True:
            sentinel = '[[REGULAY_ALIAS_' + ''.join(chr(65 + int(c, 16)) for c in secrets.token_hex(16)) + ']]'
            if sentinel not in joined and sentinel not in substitutions.values():
                break
        substitutions[token] = sentinel
    safe = texts
    for token, sentinel in substitutions.items():
        safe = [value.replace(token, sentinel) for value in safe]
    result = protect(safe)
    for token, sentinel in substitutions.items():
        if sum(value.count(sentinel) for value in result) != sum(value.count(sentinel) for value in safe):
            raise ValueError('Masker changed a protected reference')
        result = [value.replace(sentinel, token) for value in result]
    return result


def alias_value(execution, kind, original):
    return _alias_value(ProtectionContext.from_prompt(execution.prompt), kind, original)


def alias_text(execution, text):
    return _alias_text(ProtectionContext.from_prompt(execution.prompt), text)


def resolve_for_operation(execution, tokens, *, operation):
    """Application-only resolution; no HTTP/tool/sandbox entry point exports it."""
    if operation != 'local_document_fields':
        raise ValueError('Untrusted reference operation')
    from .service import _context, AgentDenied
    from front.models import AgentExecution
    from django.utils import timezone
    current = AgentExecution.objects.get(pk=execution.pk)
    if (current.status != 'active' or current.attempt != execution.attempt
            or current.expires_at <= timezone.now()
            or current.authorization_digest != _context(execution.prompt, execution.profile_id)[-1]):
        raise AgentDenied()
    prompt = execution.prompt
    rows = list(ConversationAlias.objects.filter(company_id=prompt.company_id,
        user_id=prompt.user_id, conversation_id=prompt.conversation_id, token__in=tokens))
    if len(rows) != len(set(tokens)) or any(not row.original for row in rows):
        raise ValueError('Reference unavailable in this conversation')
    return {row.token: row.original for row in rows}
