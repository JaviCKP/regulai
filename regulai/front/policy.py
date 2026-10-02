"""Local, side-effect-free policy decisions. Failure never grants egress."""
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Literal

from django.core.exceptions import ValidationError
from django.db.models import Q
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from decimal import Decimal, InvalidOperation
import yara

Sensitivity = Literal['public', 'internal', 'confidential', 'restricted', 'unknown']


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class JevConfig(StrictConfig):
    transport: Literal['vercel', 'typesafe'] = 'vercel'
    model: str = 'typesafe-ai/jev'
    input_price: str | None = None
    output_price: str | None = None
    currency: Literal['USD'] = 'USD'
    price_date: str | None = None
    # A provider/account contractual ceiling, not a response-size estimate.
    max_call_cost: str | None = None
    threshold: float = Field(default=0.8, ge=0, le=1)
    rubric_version: str = 'sensitivity-v1'

    @field_validator('input_price', 'output_price', 'max_call_cost')
    @classmethod
    def money(cls, value):
        try:
            if value is not None and (not Decimal(value).is_finite() or Decimal(value) < 0):
                raise ValueError('Invalid nonnegative decimal.')
        except InvalidOperation:
            raise ValueError('Invalid nonnegative decimal.') from None
        return value

    @model_validator(mode='after')
    def pinned_model(self):
        import re
        if ((self.transport == 'vercel' and self.model != 'typesafe-ai/jev')
                or (self.transport == 'typesafe' and not re.fullmatch(r'jev-\d+\.\d+\.\d+', self.model))):
            raise ValueError('Invalid Jev model for transport.')
        return self


class CandidateConfig(StrictConfig):
    company_engine_id: int = Field(gt=0)
    model_id: int = Field(gt=0)
    level: Literal['economy', 'balanced', 'strong']
    quality: dict[Literal['general', 'extraction', 'summary', 'document_question'], float]

    @field_validator('quality')
    @classmethod
    def quality_range(cls, value):
        if any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError('Invalid quality.')
        return value


class RoutingConfig(StrictConfig):
    mode: Literal['manual', 'auto'] = 'manual'
    candidates: list[CandidateConfig] = Field(default_factory=list, max_length=64)
    min_quality: dict[Literal['economy', 'balanced', 'strong'], float] = Field(
        default_factory=lambda: {'economy': 0.0, 'balanced': 0.0, 'strong': 0.0})
    max_output_tokens: int = Field(default=1000, gt=0, le=32000)

    @field_validator('min_quality')
    @classmethod
    def quality_range(cls, value):
        if set(value) != {'economy', 'balanced', 'strong'} or any(not 0 <= score <= 1 for score in value.values()):
            raise ValueError('Configure all quality levels.')
        return value


class VerificationConfig(StrictConfig):
    mode: Literal['local', 'advisory', 'enforce'] = 'local'
    threshold: float = Field(default=0.8, ge=0, le=1)
    rubric_version: str = 'verification-v1'


class LimitsConfig(StrictConfig):
    budget: str | None = None
    deadline_seconds: int = Field(default=90, ge=1, le=180)

    @field_validator('budget')
    @classmethod
    def money(cls, value):
        return JevConfig.money(value)


class AIConfig(StrictConfig):
    version: Literal[1] = 1
    revision: int = Field(default=1, ge=1)
    classification: Literal['local', 'required'] = 'local'
    local_sensitivity: Sensitivity = 'unknown'
    allow_empty_rules: bool = False
    destinations: dict[Sensitivity, list[str]] = Field(default_factory=dict)
    jev: JevConfig = Field(default_factory=JevConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)

    @field_validator('destinations')
    @classmethod
    def validate_destinations(cls, value):
        import re
        if any(not re.fullmatch(r'(engine|obfuscation):[1-9][0-9]*|jev', item)
               for items in value.values() for item in items):
            raise ValueError('Use explicit engine/obfuscation IDs or jev.')
        return value


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate_ai_config(value):
    if value == {}:
        return  # Unconfigured means no egress, not implicit permission.
    try:
        AIConfig.model_validate(value)
    except (ValueError, TypeError) as error:
        raise ValidationError('Invalid AI policy configuration.') from error


def validate_yara(source):
    try:
        yara.compile(source=source, includes=False)
    except Exception as error:
        raise ValidationError('Invalid YARA rule; compilation failed.') from error


@dataclass
class PolicyDecision:
    status: str
    reason_codes: list[str]
    sensitivity: str = 'unknown'
    allowed_destinations: list[str] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    fingerprint: str = ''

    def as_dict(self):
        return asdict(self)


def active_rules(actor):
    from .models import Rule
    company = actor.profile.company
    return list(Rule.objects.filter(
        Q(rules_group__company=company) | Q(rules_group__company__isnull=True, rules_group__user=actor),
        active=True,
    ).order_by('pk'))


def scan_rules(rules, texts):
    if not rules:
        return [], []
    compiled = yara.compile(sources={f'rule_{r.pk}': r.yara_rule for r in rules}, includes=False)
    matches, matched = [], {}
    by_namespace = {f'rule_{r.pk}': r for r in rules}
    for content_type, text in texts:
        for match in compiled.match(data=text, timeout=2):
            rule = by_namespace[match.namespace]
            if rule.applies_to not in (content_type, 'both'):
                continue
            if rule.action not in ('block', 'consent'):
                raise ValueError('Invalid rule action')
            matches.append(match)
            matched[rule.pk] = {'id': rule.pk, 'name': rule.name, 'severity': rule.severity,
                                'description': rule.description or '', 'action': rule.action}
    return matches, list(matched.values())


def evaluate_policy(actor, texts, *, config=None, destinations=(), sensitivity=None, rules=None):
    try:
        rules = active_rules(actor) if rules is None else rules
        _, matched = scan_rules(rules, texts)
    except Exception:
        return PolicyDecision('unavailable', ['security_check_failed'])
    # Local prohibitions apply even when configuration/semantic services fail.
    if any(r['action'] == 'block' for r in matched):
        return PolicyDecision('block', ['local_rule_block'], rules=matched)
    try:
        raw = actor.profile.company.ai_config if config is None else config
        if not raw:
            return PolicyDecision('unavailable', ['policy_configuration_invalid'])
        cfg = AIConfig.model_validate(raw)
        fingerprint = digest({'config': cfg.model_dump(), 'rules': [
            [r.pk, r.yara_rule, r.action, r.applies_to, r.active] for r in rules]})
        if not rules and not cfg.allow_empty_rules:
            return PolicyDecision('unavailable', ['empty_policy_not_authorized'], fingerprint=fingerprint)
        sensitivity = sensitivity or cfg.local_sensitivity
        if sensitivity not in ('public', 'internal', 'confidential', 'restricted', 'unknown'):
            raise ValueError('Invalid sensitivity')
        allowed = sorted(set(cfg.destinations.get(sensitivity, [])))
        result = PolicyDecision('allow', ['local_policy_allowed'], sensitivity, allowed, matched, fingerprint)
        if sensitivity == 'restricted':
            result.status, result.reason_codes = 'block', ['restricted_content']
        elif not allowed or any(dest not in allowed for dest in destinations):
            result.status, result.reason_codes = 'block', ['destination_not_allowed']
        elif matched:
            result.status, result.reason_codes = 'consent_required', ['local_rule_consent']
        return result
    except (ValueError, TypeError, AttributeError):
        return PolicyDecision('unavailable', ['policy_configuration_invalid'])
