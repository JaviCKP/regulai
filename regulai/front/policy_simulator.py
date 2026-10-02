"""Compare temporary policy drafts; simulation never owns chat effects."""
import json
import copy
import time
from decimal import Decimal
from dataclasses import replace

from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.db import OperationalError, transaction

from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from .access import actor_company
from .chat_service import PipelineStop, candidates_for
from .classification import decide
from . import jev
from .models import AuditLog, Company, CompanyEngine, EngineModel, ObfuscationConfig, Profile, Rule, RulesGroup
from .policy import AIConfig, active_rules, digest, evaluate_policy, validate_yara
from .routing import RoutingError, actual_cost, route
from .views import admin_required


def _config(source, company):
    if len(source.encode('utf-8')) > 100_000:
        raise ValueError('configuration_too_large')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_configuration_key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('invalid_number')
    config = AIConfig.model_validate(json.loads(source, object_pairs_hook=unique_object,
        parse_constant=invalid_constant)).model_dump()
    destinations = {item for items in config['destinations'].values() for item in items}
    owned_engines = set(CompanyEngine.objects.filter(company=company, active=True).values_list('pk', flat=True))
    owned_masks = set(ObfuscationConfig.objects.filter(company=company, active=True).values_list('pk', flat=True))
    if owned_masks and config['limits']['budget'] is not None and config['masking']['max_call_cost'] is None:
        raise ValueError('unbounded_masking_cost')
    for destination in destinations:
        if destination == 'jev':
            continue
        kind, identity = destination.split(':')
        if int(identity) not in (owned_engines if kind == 'engine' else owned_masks):
            raise ValueError('destination_not_owned')
    for candidate in config['routing']['candidates']:
        engine = CompanyEngine.objects.filter(pk=candidate['company_engine_id'], company=company, active=True).first()
        if not engine or not EngineModel.objects.filter(pk=candidate['model_id'], engine=engine.engine, active=True).exists():
            raise ValueError('candidate_not_owned')
    return config


def _draft_rule(actor, data, owned):
    source = data.get('rule_source', '').strip()
    if not source:
        return None
    if len(source.encode('utf-8')) > 65_536:
        raise ValueError('rule_too_large')
    validate_yara(source)
    action = data.get('rule_action', 'block')
    if action not in {'block', 'consent'}:
        raise ValueError('invalid_rule_action')
    if data.get('rule_id'):
        original = next((rule for rule in owned if rule.pk == int(data['rule_id'])), None)
        if not original:
            raise ValueError('rule_not_owned')
        rule = copy.copy(original)
    else:
        rule = Rule(pk=0, name='Simulator draft', applies_to='both', severity='medium')
    rule.yara_rule, rule.action = source, action
    rule.active = data.get('rule_active', '') == 'on'
    return rule


def _rule_identity(rule):
    return {'id': rule.pk, 'source_digest': digest(rule.yara_rule), 'active': rule.active,
        'action': rule.action, 'applies_to': rule.applies_to, 'group': rule.rules_group_id}


def _rollback_rule(rule):
    return {**_rule_identity(rule), 'yara_rule': rule.yara_rule} if rule else None


def _baseline(actor, company, owned):
    personal = [rule for rule in active_rules(actor) if rule.rules_group.company_id is None]
    rules = sorted(owned + personal, key=lambda rule: rule.pk)
    baseline = {'actor': actor.pk, 'company': company.pk, 'revision': company.ai_config.get('revision', 0),
        'current_digest': digest(company.ai_config), 'rules_digest': digest([_rule_identity(rule) for rule in rules])}
    return baseline, [rule for rule in rules if rule.active]


def _proof(baseline, proposed, rule):
    return {**baseline, 'draft_digest': digest({'config': proposed, 'rule': _rule_identity(rule) if rule else None})}


def _rollback_config(value):
    if not value:
        return {}
    try:
        return AIConfig.model_validate(value).model_dump(exclude_unset=True)
    except ValueError:
        return {'invalid_config_digest': digest(value)}


def _signals(data):
    signals = {'origin': 'synthetic', 'task': data.get('signal_task', 'general'),
        'level': data.get('signal_level', 'economy'), 'sensitivity': data.get('signal_sensitivity') or None}
    if (signals['task'] not in {'general', 'extraction', 'summary', 'document_question'}
            or signals['level'] not in {'economy', 'balanced', 'strong'}
            or signals['sensitivity'] not in {None, 'public', 'internal', 'confidential', 'restricted', 'unknown'}):
        raise ValueError('invalid_signals')
    return signals


def _outcome(actor, config, sample, rules, signals):
    sensitivity = signals['sensitivity']
    task, difficulty = signals['task'], signals['level']
    local = evaluate_policy(actor, [('prompts', sample)], config=config, rules=rules)
    origin = 'jev_signals' if signals['origin'] == 'jev' else 'synthetic_signals'
    if local.status in {'block', 'unavailable'}:
        return {'policy': local.as_dict(), 'route': {'status': 'not_evaluated',
            'origin': origin, 'reason_codes': ['security_not_allowed']}}
    cfg = AIConfig.model_validate(config)
    notices, plausible_tasks = [], [task]
    if (cfg.limits.budget is not None and cfg.masking.max_call_cost is None
            and ObfuscationConfig.objects.filter(company=actor.profile.company, active=True).exists()):
        policy = local.as_dict()
        policy.update(status='unavailable', reason_codes=['policy_configuration_invalid'], allowed_destinations=[])
        return {'policy': policy, 'route': {'status': 'not_evaluated', 'origin': origin,
            'reason_codes': ['security_not_allowed']}}
    if signals['origin'] == 'jev' and cfg.classification == 'required':
        classification = decide(signals['answers'], cfg, local.sensitivity)
        sensitivity, task, difficulty = classification.sensitivity, classification.task, classification.difficulty
        notices, plausible_tasks = classification.notices, classification.plausible_tasks
        if classification.stop_code:
            policy = local.as_dict()
            policy.update(status='block' if classification.stop_status == 'blocked' else 'unavailable',
                sensitivity=sensitivity, reason_codes=[classification.stop_code], allowed_destinations=[])
            return {'policy': policy, 'notices': notices, 'route': {'status': 'not_evaluated',
                'origin': 'jev_signals', 'reason_codes': ['security_not_allowed']}}
    elif signals['origin'] == 'jev':
        sensitivity, task, difficulty = local.sensitivity, 'general', 'economy'
        plausible_tasks = [task]
    else:
        ranks = {'public': 0, 'internal': 1, 'confidential': 2, 'restricted': 3}
        if sensitivity in ranks and local.sensitivity in ranks:
            sensitivity = max((sensitivity, local.sensitivity), key=ranks.get)
    policy = evaluate_policy(actor, [('prompts', sample)], config=config, rules=rules, sensitivity=sensitivity)
    policy.allowed_destinations = sorted(set(policy.allowed_destinations) & set(local.allowed_destinations))
    if policy.status in {'allow', 'consent_required'} and not policy.allowed_destinations:
        policy.status, policy.reason_codes = 'block', ['destination_not_allowed']
    result = {'policy': policy.as_dict(), 'notices': notices, 'task': task, 'difficulty': difficulty,
        'plausible_tasks': plausible_tasks, 'route': {'status': 'not_evaluated',
        'origin': 'jev_signals' if signals['origin'] == 'jev' else 'synthetic_signals'}}
    if policy.status not in {'allow', 'consent_required'}:
        result['route']['reason_codes'] = ['security_not_allowed']
        return result
    try:
        cfg = AIConfig.model_validate(config)
        candidates = candidates_for(actor, cfg, task)
        if len(plausible_tasks) > 1:
            qualities = {(item.company_engine_id, item.model_id): item.quality for item in cfg.routing.candidates}
            candidates = [replace(item, quality=min(qualities.get((item.company_engine_id, item.model_pk), {}).get(name, -1)
                for name in plausible_tasks)) for item in candidates]
        result['candidates'] = [{'company_engine_id': item.company_engine_id, 'model': item.model_id,
            'level': item.level, 'quality': item.quality} for item in candidates
            if f'engine:{item.company_engine_id}' in policy.allowed_destinations]
        budget = Decimal(cfg.limits.budget) if cfg.limits.budget is not None else None
        required_checks = int(cfg.classification == 'required') + int(cfg.verification.mode != 'local')
        if budget is not None and required_checks:
            if cfg.jev.max_call_cost is None or cfg.jev.input_price is None or cfg.jev.output_price is None:
                raise RoutingError('unknown_price')
            budget -= Decimal(cfg.jev.max_call_cost) * required_checks
            if budget < 0:
                raise RoutingError('budget_exhausted')
        if budget is not None:
            mask_count = ObfuscationConfig.objects.filter(company=actor.profile.company, active=True).count()
            if mask_count:
                budget -= Decimal(cfg.masking.max_call_cost) * mask_count
                if budget < 0:
                    raise RoutingError('budget_exhausted')
        selected = route(candidates, [sample], allowed_destinations=policy.allowed_destinations,
            min_quality=cfg.routing.min_quality[difficulty], max_output_tokens=cfg.routing.max_output_tokens,
            budget=budget)
        result['route'].update(status='selected', model=selected.candidate.model_id,
            company_engine_id=selected.candidate.company_engine_id, level=selected.candidate.level,
            max_output_tokens=selected.max_output_tokens, estimated_cost=str(selected.estimated_cost) if selected.estimated_cost is not None else None,
            currency=selected.candidate.currency, reason_codes=['quality_cost_route'])
    except RoutingError as error:
        result['route'].update(status='unavailable', reason_codes=[error.code])
    return result


def _semantic(actor, company, sample, rules):
    """One explicitly requested classifier call; a draft cannot authorize egress."""
    state = {'request': sample, 'context': [], 'sources': []}
    questions = {**jev.classification_questions(), **jev.task_questions()}
    serialized = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False)
    decision = evaluate_policy(actor, [('prompts', sample), ('prompts', serialized)],
        config=company.ai_config, destinations=['jev'], rules=rules)
    if decision.status != 'allow':
        return {'status': 'not_authorized', 'reason_codes': decision.reason_codes}, [], None
    cfg = AIConfig.model_validate(company.ai_config)
    if ObfuscationConfig.objects.filter(company=company, active=True).exists():
        code = ('policy_configuration_invalid' if cfg.limits.budget is not None
            and cfg.masking.max_call_cost is None else 'masking_required')
        # ponytail: semantic masking disabled; enable through shared mask_texts and its ledger.
        return {'status': 'not_authorized', 'reason_codes': [code]}, [], None
    if (not company.jev_api_key or cfg.limits.budget is None or cfg.jev.max_call_cost is None
            or cfg.jev.input_price is None or cfg.jev.output_price is None or cfg.jev.currency != 'USD'):
        return {'status': 'not_evaluated', 'reason_codes': ['budget_or_credentials_unconfigured']}, [], None
    bound = Decimal(cfg.jev.max_call_cost)
    if bound > Decimal(cfg.limits.budget):
        return {'status': 'not_evaluated', 'reason_codes': ['budget_exhausted']}, [], None
    fresh = Profile.objects.select_related('company', 'user').get(user=actor)
    actor.profile = fresh
    check = evaluate_policy(actor, [('prompts', sample), ('prompts', serialized)], destinations=['jev'])
    if (not fresh.user.is_active or not fresh.user.is_superuser or fresh.company_id != company.pk
            or digest(fresh.company.ai_config) != digest(company.ai_config)
            or digest(fresh.company.jev_api_key) != digest(company.jev_api_key)
            or check.status != 'allow' or check.fingerprint != decision.fingerprint):
        return {'status': 'not_authorized', 'reason_codes': ['authorization_changed']}, [], None
    prices = {key: getattr(cfg.jev, key) for key in ('input_price', 'output_price', 'currency', 'price_date')}
    call = {'purpose': 'simulation_classification', 'provider': 'jev', 'model': cfg.jev.model,
        'status': 'started', 'cost': None, 'cost_bound': str(bound), 'currency': cfg.jev.currency,
        'price_snapshot': prices, 'threshold': cfg.jev.threshold, 'rubric_version': cfg.jev.rubric_version,
        'task_rubric_version': jev.TASK_RUBRIC_VERSION}
    # Persist an attempt before crossing the provider boundary; a timeout is never free.
    audit = AuditLog.objects.create(user=actor, company=company, action='policy_simulate',
        details=json.dumps({'policy_digest': digest(company.ai_config), 'sample_digest': digest(sample), 'call': call}))
    started = time.monotonic()
    semantic, signals = {'status': 'completed', 'reason_codes': []}, None
    try:
        seconds = cfg.limits.deadline_seconds
        result = jev.evaluate(fresh.company.jev_api_key, cfg.jev.model, state, questions,
            transport=cfg.jev.transport, timeout=(min(3, seconds / 2), min(15, seconds / 2)))
        cost = actual_cost(prices, result.input_tokens, result.output_tokens)
        gateway_cost = result.provider_metadata.get('gateway', {}).get('cost')
        if gateway_cost is not None:
            cost = Decimal(gateway_cost)
        call.update(status='completed', cost=str(cost) if cost is not None else None,
            model_effective=result.effective_model, provider_request_id=result.request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens, usage=result.usage,
            signals=result.answers)
        signals = {'origin': 'jev', 'sensitivity': result.answers['category']['choice'],
            'task': result.answers['task']['choice'], 'level': result.answers['difficulty']['choice'],
            'answers': result.answers}
        if time.monotonic() - started > seconds:
            raise PipelineStop('deadline_exceeded')
        if cost is not None and cost > bound:
            call['cost_bound'] = str(cost)
            raise PipelineStop('budget_bound_exceeded')
        classification = decide(result.answers, cfg, decision.sensitivity)
        signals.update(sensitivity=classification.sensitivity, task=classification.task,
            level=classification.difficulty, notices=classification.notices,
            plausible_tasks=classification.plausible_tasks)
        if classification.stop_code:
            raise PipelineStop(classification.stop_code, classification.stop_status)
    except jev.JevError as error:
        call.update(status='failed', reason_codes=[error.code], outcome_unknown=error.outcome_unknown)
        semantic = {'status': 'unavailable', 'reason_codes': [error.code]}
    except PipelineStop as error:
        semantic = {'status': error.status, 'reason_codes': [error.code]}
    finally:
        call['duration_ms'] = round((time.monotonic() - started) * 1000)
        audit.details = json.dumps({'policy_digest': digest(company.ai_config), 'sample_digest': digest(sample), 'call': call})
        audit.save(update_fields=['details'])
    return semantic, [call], signals


@admin_required
@require_http_methods(['GET', 'POST'])
def policy_simulator(request):
    company = actor_company(request.user)
    context = {'current_config': json.dumps(company.ai_config, indent=2),
        'proposed_config': request.POST.get('proposed_config', json.dumps(company.ai_config or AIConfig().model_dump(), indent=2)),
        'sample': request.POST.get('sample', 'Synthetic public report'),
        'company': company, 'rules': Rule.objects.filter(rules_group__company=company),
        'rule_source': request.POST.get('rule_source', ''), 'rule_id': request.POST.get('rule_id', ''),
        'rule_action': request.POST.get('rule_action', 'block'),
        'rule_active': request.POST.get('rule_active', 'on' if request.method == 'GET' else ''),
        'mode': request.POST.get('mode', 'local'), 'signals': _signals({})}
    status = 200
    if request.method == 'POST':
        try:
            proposed = _config(context['proposed_config'], company)
            owned = list(Rule.objects.filter(rules_group__company=company))
            baseline, rules = _baseline(request.user, company, owned)
            draft_rule = _draft_rule(request.user, request.POST, owned)
            signals = _signals(request.POST)
            context['signals'] = signals
            proposed_rules = rules
            if draft_rule:
                proposed_rules = [rule for rule in rules if rule.pk != draft_rule.pk]
                if draft_rule.active:
                    proposed_rules = proposed_rules + [draft_rule]
            if not context['sample'] or len(context['sample'].encode('utf-8')) > 32_000:
                raise ValueError('invalid_sample')
            context['comparison'] = {
                'current_revision': company.ai_config.get('revision', 0),
                'draft_digest': _proof(baseline, proposed, draft_rule)['draft_digest'],
                'current': _outcome(request.user, company.ai_config, context['sample'], rules, signals),
                'proposed': _outcome(request.user, proposed, context['sample'], proposed_rules, signals),
                'signals': signals,
                'coverage': {'status': 'complete', 'format': 'synthetic_text',
                    'bytes_read': len(context['sample'].encode('utf-8')), 'digest': digest(context['sample'])},
                'semantic': {'status': 'not_evaluated'}, 'calls': [],
            }
            mode = request.POST.get('mode', 'local')
            if mode not in {'local', 'semantic'}:
                raise ValueError('invalid_mode')
            if mode == 'semantic':
                semantic, calls, semantic_signals = _semantic(request.user, company, context['sample'], rules)
                context['comparison'].update(semantic=semantic, calls=calls)
                if semantic_signals:
                    context['comparison'].update(signals=semantic_signals,
                        current=_outcome(request.user, company.ai_config, context['sample'], rules, semantic_signals),
                        proposed=_outcome(request.user, proposed, context['sample'], proposed_rules, semantic_signals))
            context['activation_token'] = signing.dumps(_proof(baseline, proposed, draft_rule), salt='policy-simulator')
        except (ValueError, TypeError, ValidationError):
            context['error'] = 'Invalid policy JSON or synthetic sample. No configuration was changed.'
            status = 400
    return render(request, 'policy_simulator.html', context, status=status)


@admin_required
@require_POST
def policy_simulator_activate(request):
    company = actor_company(request.user)
    try:
        with transaction.atomic():
            fresh = Profile.objects.select_for_update().select_related('company', 'user').get(user=request.user)
            if not fresh.user.is_active or not fresh.user.is_superuser:
                raise PermissionDenied('Administrator permission is required.')
            if fresh.company_id != company.pk:
                raise signing.BadSignature('Company changed')
            request.user.profile = fresh
            company.refresh_from_db()
            proposed = _config(request.POST.get('proposed_config', ''), company)
            owned = list(Rule.objects.filter(rules_group__company=company))
            baseline, rules = _baseline(request.user, company, owned)
            rule = _draft_rule(request.user, request.POST, owned)
            proof = signing.loads(request.POST.get('activation_token', ''), salt='policy-simulator', max_age=900)
            if proof != _proof(baseline, proposed, rule):
                raise signing.BadSignature('Policy changed')
            previous = _rollback_config(company.ai_config)
            proposed['revision'] = int(company.ai_config.get('revision', 0)) + 1
            if not Company.objects.filter(pk=company.pk, ai_config=company.ai_config).update(ai_config=proposed):
                raise signing.BadSignature('Policy changed')
            before_rule = None
            if rule:
                original = next((item for item in owned if item.pk == rule.pk), None)
                if original:
                    before_rule = _rollback_rule(original)
                    if not Rule.objects.filter(pk=original.pk, yara_rule=original.yara_rule,
                            active=original.active, action=original.action).update(
                            yara_rule=rule.yara_rule, active=rule.active, action=rule.action):
                        raise signing.BadSignature('Rule changed')
                else:
                    group = RulesGroup.objects.filter(company=company).order_by('pk').first()
                    if not group:
                        group = RulesGroup.objects.create(company=company, name='Simulator rules')
                    rule.pk, rule.rules_group = None, group
                    rule.save()
            AuditLog.objects.create(user=request.user, company=company, action='policy_activate', details=json.dumps({
                'company': company.pk, 'previous_config': previous, 'new_config': proposed,
                'rule_before': before_rule, 'rule_after': _rollback_rule(rule),
            }))
        return render(request, 'policy_simulator.html', {'activated': True, 'company': company,
            'current_config': json.dumps(proposed, indent=2)})
    except (signing.BadSignature, OperationalError):
        return render(request, 'policy_simulator.html', {'error': 'Policy changed or comparison expired. Repeat the comparison before activation.'}, status=409)
    except (ValueError, TypeError, ValidationError):
        return render(request, 'policy_simulator.html', {'error': 'Invalid draft. No configuration was changed.'}, status=400)
