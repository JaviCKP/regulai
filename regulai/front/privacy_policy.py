"""Local, bounded detectors and immutable policy revisions; no inference APIs."""
import json
import re
from typing import Literal

import yara
from pydantic import Field, model_validator

from .local_masking import detect_spans, detector_metadata
from .policy import StrictConfig, digest

Category = Literal['EMAIL', 'PHONE', 'ID', 'ACCOUNT', 'CARD', 'PERSON', 'FIELD']
Treatment = Literal['reversible', 'irreversible', 'off']


class ProtectedLiteral(StrictConfig):
    text: str = Field(min_length=1, max_length=512)
    category: Category = 'FIELD'
    treatment: Literal['reversible', 'irreversible'] = 'reversible'


class YaraSelection(StrictConfig):
    rule_id: int = Field(gt=0)
    source_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    strings: list[str] = Field(min_length=1, max_length=32)
    treatment: Literal['reversible', 'irreversible'] = 'reversible'


class PrivacyConfig(StrictConfig):
    version: Literal[1] = 1
    categories: dict[Category, Treatment] = Field(default_factory=dict)
    literals: list[ProtectedLiteral] = Field(default_factory=list, max_length=128)
    yara: list[YaraSelection] = Field(default_factory=list, max_length=32)

    @model_validator(mode='after')
    def bounded(self):
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode()) > 64000:
            raise ValueError('privacy_configuration_too_large')
        return self


_DECLARATION = re.compile(r'\s*(\$[A-Za-z_][A-Za-z_0-9]*)\s*=\s*'
    r'("(?:\\.|[^"\\])*"|/(?:\\.|[^/\\])*/)'  # UTF-8 literals and YARA regex only.
    r'((?:\s+(?:ascii|nocase|fullword))*)\s*', re.S)


def compatible_strings(source):
    """Conservative allowlist: no binary/wide/transforms/modules/includes."""
    if (len(source.encode()) > 32000 or re.search(r'\b(?:import|include)\b', source)
            or len(re.findall(r'\brule\s+[A-Za-z_][A-Za-z_0-9]*\b', source)) != 1
            or source.count('strings:') != 1 or source.count('condition:') != 1):
        raise ValueError('privacy_yara_unsupported')
    try:
        strings = source.split('strings:', 1)[1].split('condition:', 1)[0].strip()
    except IndexError:
        raise ValueError('privacy_yara_no_positions') from None
    position, identifiers = 0, []
    while position < len(strings):
        match = _DECLARATION.match(strings, position)
        if not match:
            raise ValueError('privacy_yara_unsupported')
        identifiers.append(match[1])
        position = match.end()
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError('privacy_yara_no_positions')
    return set(identifiers)


def yara_ranges(text, selection, rule):
    if not rule or digest(rule.yara_rule) != selection.source_hash:
        raise ValueError('privacy_yara_revision_changed')
    available = compatible_strings(rule.yara_rule)
    if not set(selection.strings) <= available or len(set(selection.strings)) != len(selection.strings):
        raise ValueError('privacy_yara_strings_invalid')
    raw = text.encode('utf-8')
    try:
        matches = yara.compile(source=rule.yara_rule, includes=False).match(data=raw, timeout=2)
    except Exception:
        raise ValueError('privacy_yara_failed') from None
    if not matches:
        return []
    boundaries, offset = {0: 0}, 0
    for index, char in enumerate(text):
        offset += len(char.encode('utf-8'))
        boundaries[offset] = index + 1
    ranges, located = [], set()
    for match in matches:
        for string in match.strings:
            if string.identifier not in selection.strings:
                continue
            for instance in string.instances:
                start, size, value = instance.offset, instance.matched_length, instance.matched_data
                end = start + size
                if (not size or size != len(value) or start not in boundaries or end not in boundaries
                        or raw[start:end] != value):
                    raise ValueError('privacy_yara_position_invalid')
                ranges.append((boundaries[start], boundaries[end], 'FIELD',
                    selection.treatment == 'reversible', f'yara:{rule.pk}:{string.identifier}'))
                located.add(string.identifier)
                if len(ranges) > 4096:
                    raise ValueError('privacy_too_many_matches')
    if located != set(selection.strings):
        raise ValueError('privacy_yara_no_positions')
    return ranges


def detect_ranges(text, config, rules=(), *, patterns=True):
    from .privacy import MAX_BYTES, MAX_MATCHES, TOKEN, resolve_spans
    if not isinstance(text, str) or len(text.encode()) > MAX_BYTES:
        raise ValueError('privacy_input_invalid')
    references = [m.span() for m in TOKEN.finditer(text)]
    spans = []
    for start, end, category in detect_spans(text) if patterns else []:
        treatment = config.categories.get(category, 'off')
        if category == 'SECRET' or treatment != 'off':
            spans.append((start, end, category, category != 'SECRET' and treatment == 'reversible', 'local'))
    for literal in config.literals:
        start = 0
        while (start := text.find(literal.text, start)) >= 0:
            spans.append((start, start + len(literal.text), literal.category, literal.treatment == 'reversible', 'literal'))
            start += 1
            if len(spans) > MAX_MATCHES:
                raise ValueError('privacy_too_many_matches')
    by_id = {rule.pk: rule for rule in rules}
    for selected in config.yara:
        spans.extend(yara_ranges(text, selected, by_id.get(selected.rule_id)))
    if len(spans) > MAX_MATCHES:
        raise ValueError('privacy_too_many_matches')
    # Only complete existing tokens are structural. A range crossing a token is
    # ambiguous and blocks instead of exposing a partially transformed value.
    kept = []
    for span in spans:
        a, b = span[:2]
        if any(a >= left and b <= right for left, right in references):
            continue
        if any(a < right and b > left for left, right in references):
            raise ValueError('privacy_reference_overlap')
        kept.append(span)
    return resolve_spans(kept)


def revision_config(context, revision):
    from .models import PrivacySelection, Rule
    config = PrivacyConfig.model_validate_json(revision.configuration)
    if revision.detector_version != digest(detector_metadata()):
        raise ValueError('privacy_detector_changed')
    selected = PrivacySelection.objects.filter(alias__company_id=context.company_id,
        alias__user_id=context.user_id, alias__conversation_id=context.conversation_id).select_related('alias')
    for row in selected:
        if not row.alias.original:
            raise ValueError('privacy_selection_unavailable')
        config.literals.append(ProtectedLiteral(text=row.alias.original, category=row.alias.kind))
    rules = list(Rule.objects.filter(pk__in=[r.rule_id for r in config.yara], rules_group__company_id=context.company_id))
    return config, rules


def simulate_revision(actor, proposed, sample):
    """Reuse the policy simulator baseline and local decision; never call a model."""
    from django.core import signing
    from .access import actor_company, can_manage_company_policy
    from .agents.aliases import preserve_aliases
    from .local_masking import mask_local_texts
    from .models import PrivacyRevision, Rule
    from .policy_simulator import _baseline, _outcome, _signals
    from .privacy import keyed_digest
    if not can_manage_company_policy(actor):
        raise ValueError('privacy_admin_required')
    if not isinstance(sample, str) or not 1 <= len(sample.encode()) <= 32000:
        raise ValueError('privacy_synthetic_sample_required')
    company = actor_company(actor)
    config = PrivacyConfig.model_validate(proposed)
    owned = list(Rule.objects.filter(rules_group__company=company))
    baseline, rules = _baseline(actor, company, owned)
    ranges = detect_ranges(sample, config, owned)
    for selection in config.yara:
        if not any(detector.startswith(f'yara:{selection.rule_id}:') for *_, detector in ranges):
            raise ValueError('privacy_yara_sample_requires_match')
    result, substitutions = sample, {}
    for start, end, category, recover, _ in reversed(ranges):
        if recover:
            key = (category, sample[start:end])
            substitutions.setdefault(key, f'[[R_{category}_{len(substitutions):032x}]]')
            token = substitutions[key]
        else:
            token = '[[REGULAI_SECRET]]'
        result = result[:start] + token + result[end:]
    protected = preserve_aliases([result], mask_local_texts)[0]
    encoded = json.dumps(config.model_dump(), ensure_ascii=False, sort_keys=True)
    revision = PrivacyRevision.objects.create(company=company, author=actor, configuration=encoded,
        fingerprint=keyed_digest(encoded), detector_version=digest(detector_metadata()))
    proof = {**baseline, 'revision_id': revision.pk, 'fingerprint': revision.fingerprint,
             'detector': revision.detector_version}
    return {'revision_id': revision.pk, 'protected': protected, 'current': mask_local_texts([sample])[0],
        'decision': _outcome(actor, company.ai_config, sample, rules, _signals({})),
        'review_token': signing.dumps(proof, salt='privacy-review'), 'calls': [],
        'coverage': 'Texto explícito y patrones locales. No detecta todos los nombres libres ni sanea PDF, imágenes o binarios.'}


def activate_revision(actor, revision_id, token):
    """Final explicit admin action after a signed simulation, with CAS baseline."""
    from django.core import signing
    from django.db import transaction
    from .access import can_manage_company_policy
    from .models import AuditLog, Company, PrivacyRevision, Profile, Rule
    from .policy_simulator import _baseline
    from .policy import AIConfig
    with transaction.atomic():
        profile = Profile.objects.select_for_update().select_related('user').get(user=actor)
        if not can_manage_company_policy(profile.user):
            raise ValueError('privacy_admin_required')
        company = Company.objects.select_for_update().get(pk=profile.company_id)
        actor.profile = profile
        owned = list(Rule.objects.filter(rules_group__company=company))
        baseline, _ = _baseline(actor, company, owned)
        revision = PrivacyRevision.objects.get(pk=revision_id, company=company, author=actor)
        proof = {**baseline, 'revision_id': revision.pk, 'fingerprint': revision.fingerprint,
                 'detector': digest(detector_metadata())}
        if signing.loads(token, salt='privacy-review', max_age=900) != proof:
            raise ValueError('privacy_review_stale')
        if not company.ai_config:
            raise ValueError('privacy_policy_unconfigured')
        proposed = {**company.ai_config, 'privacy': {'version': 1, 'revision_id': revision.pk},
                    'revision': company.ai_config.get('revision', 0) + 1}
        AIConfig.model_validate(proposed)
        company.ai_config = proposed
        company.save(update_fields=['ai_config'])
        AuditLog.objects.create(company=company, user=actor, action='privacy_activate',
            details=json.dumps({'revision_id': revision.pk, 'reason': 'signed_synthetic_review'}))
        return revision
