"""Server-resolved capabilities and resource budgets; no ambient account grants."""
import json

from pydantic import BaseModel, ConfigDict, Field

FILES = {'ls', 'read_file', 'write_file', 'edit_file', 'glob', 'grep', 'execute'}
WEB = {'web_search', 'web_open', 'web_find', 'web_download', 'web_browse'}
GENERAL = FILES | WEB | {'install_packages', 'publish_artifact', 'inspect_image', 'read_output'}


class Limits(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    model_calls: int = Field(default=48, ge=4, le=200)
    tool_calls: int = Field(default=120, ge=8, le=500)
    run_seconds: int = Field(default=1800, ge=60, le=3600)
    command_seconds: int = Field(default=120, ge=1, le=300)
    output_chars: int = Field(default=16000, ge=1000, le=64000)
    output_bytes: int = Field(default=1048576, ge=16384, le=4194304)
    file_bytes: int = Field(default=20000000, ge=1024, le=30000000)
    workspace_bytes: int = Field(default=536870912, ge=67108864, le=1073741824)
    memory_mb: int = Field(default=1024, ge=256, le=2048)
    processes: int = Field(default=64, ge=8, le=128)
    web_calls: int = Field(default=40, ge=1, le=120)
    web_bytes: int = Field(default=10000000, ge=1024, le=30000000)
    web_seconds: int = Field(default=25, ge=1, le=60)
    pdf_pages: int = Field(default=100, ge=1, le=200)
    human_review: bool = False
    retention_days: int = Field(default=30, ge=1, le=365)


def limits(profile):
    return Limits.model_validate(profile.limits).model_dump()


def search_configuration(profile):
    """One non-generative search provider; no automatic answer or provider LLM."""
    from .service import AgentDenied
    try:
        value = json.loads(profile.search_config or '{}')
        if (not isinstance(value, dict) or set(value) - {'provider', 'api_key', 'call_cost_bound'}
                or value.get('provider') != 'tavily' or not isinstance(value.get('api_key'), str)
                or not value['api_key']):
            raise ValueError()
        from decimal import Decimal
        bound = Decimal(str(value['call_cost_bound']))
        if not bound.is_finite() or not 0 < bound <= 10:
            raise ValueError()
        return value
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise AgentDenied('search_not_configured') from None


def profile_for(actor, *, allow_disabled=False):
    from django.conf import settings
    from front.models import AgentAccessGrant, Profile
    from .service import AgentDenied
    if not actor.is_active or (not allow_disabled and not getattr(settings, 'REGULAY_AGENT_ENABLED', False)):
        raise AgentDenied('agent_disabled')
    account = Profile.objects.get(user=actor)
    grant = AgentAccessGrant.objects.select_related('profile').filter(
        user=actor, company_id=account.company_id).first()
    if grant is not None:
        if not grant.enabled or not grant.profile.enabled or grant.profile.company_id != account.company_id:
            raise AgentDenied('agent_access_denied')
        return grant.profile_id
    # Retain old isolated laboratory fixtures, never enable real accounts by name.
    if (settings.DEBUG and getattr(settings, 'REGULAY_AGENT_DEVELOPMENT', False)
            and actor.username.startswith('agent-synthetic-')):
        entry = getattr(settings, 'REGULAY_AGENT_DEV_ACCOUNTS', {}).get(str(actor.pk))
        if entry and entry.get('company_id') == account.company_id:
            return int(entry['profile_id'])
    raise AgentDenied('agent_access_denied')


def grant_binding(actor, profile_id):
    from front.models import AgentAccessGrant
    row = AgentAccessGrant.objects.filter(user=actor, profile_id=profile_id).first()
    return [row.pk, row.company_id, row.enabled, row.version] if row else None
