"""Session-authenticated presentation endpoints; no executor authentication."""
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .access import authorized_conversations
from .models import Conversation, Prompt
from .privacy import required
from .privacy_presentation import safe_result_view

COVERAGE = 'Patrones explícitos y textos seleccionados. Los nombres libres no marcados no están cubiertos. PDF, imágenes y binarios se bloquean con esta protección.'


def payload(request):
    if len(request.body) > 96000:
        raise ValueError('privacy_request_too_large')
    value = json.loads(request.body)
    if not isinstance(value, dict):
        raise ValueError('privacy_request_invalid')
    return value


def context_for(request, conversation_id):
    from .privacy import ProtectionContext, authorize
    conversation = owned(request, conversation_id)
    context = ProtectionContext(request.user.profile.company_id, request.user.pk, conversation.pk)
    authorize(context)
    return context


def preview_value(text, config, rules):
    from .privacy_policy import preview_text
    protected, ranges = preview_text(text, config, rules)
    return protected, len(ranges)


def _failure(error):
    # Validation libraries can echo sensitive inputs; never return str(error).
    return response({'error': 'No se pudo completar. Revisa los datos, permisos y la revisión vigente.'}, 400)


def response(data, status=200):
    result = JsonResponse(data, status=status)
    result['Cache-Control'] = 'private, no-store'
    result['X-Content-Type-Options'] = 'nosniff'
    return result


def owned(request, conversation_id):
    return get_object_or_404(authorized_conversations(request.user), pk=conversation_id)


@login_required
@require_GET
def history(request, conversation_id):
    conversation = owned(request, conversation_id)
    from .chat_service import request_result
    records = []
    for prompt in Prompt.objects.filter(conversation=conversation, user=request.user,
            company_id=request.user.profile.company_id).order_by('pk'):
        if required(prompt):
            records.append(safe_result_view(request.user.pk, request_result(prompt).data))
    return response({'turns': records})


@login_required
@require_GET
def message(request, request_id):
    prompt = get_object_or_404(Prompt, request_id=request_id, user=request.user,
        conversation__in=authorized_conversations(request.user), company_id=request.user.profile.company_id)
    from .chat_service import request_result
    return response(safe_result_view(request.user.pk, request_result(prompt).data))


@login_required
@require_GET
def inspector(request, conversation_id):
    from django.db.models import Count, Sum, Min, Max
    from .models import ConversationAlias, PrivacyOccurrence, PrivacyUse, Response, AuditLog
    from .privacy import effective_revision
    context = context_for(request, conversation_id)
    try:
        revision = effective_revision(context)
        cursor = max(0, int(request.GET.get('after', 0)))
    except ValueError:
        return _failure(None)
    scoped = ConversationAlias.objects.filter(**context.scope())
    rows = list(scoped.filter(pk__gt=cursor).order_by('pk')[:51])
    occurrences = dict(PrivacyOccurrence.objects.filter(alias__in=rows).values('alias_id').annotate(n=Count('id')).values_list('alias_id', 'n'))
    uses = dict(PrivacyUse.objects.filter(alias__in=rows).values('alias_id').annotate(n=Sum('count')).values_list('alias_id', 'n'))
    details = {}
    for item in PrivacyOccurrence.objects.filter(alias__in=rows).values('alias_id',
            'message__turn__prompt__request_id', 'message__turn__revision_id', 'detector').annotate(count=Count('pk'),
            first=Min('message__created_at'), last=Max('message__created_at')).order_by('alias_id', 'first')[:500]:
        details.setdefault(item['alias_id'], []).append({'request_id': str(item['message__turn__prompt__request_id']),
            'detector': item['detector'], 'revision_id': item['message__turn__revision_id'],
            'count': item['count'], 'first': item['first'], 'last': item['last']})
    calls = dict(PrivacyUse.objects.filter(alias__in=rows).values('alias_id').annotate(n=Count('pk')).values_list('alias_id', 'n'))
    by_turn = {}
    for use in PrivacyUse.objects.filter(alias__in=rows).select_related('turn__prompt', 'alias'):
        prompt = use.turn.prompt
        key = (use.alias_id, prompt.pk)
        item = by_turn.setdefault(key, {'request_id': str(prompt.request_id), 'input': 0,
            'history': 0, 'context': 0, 'response': 0, 'provider_calls': 0, 'uncertain_calls': 0})
        receipt = next((call for call in prompt.decision.get('calls', [])
            if call.get('privacy_call_key') == use.call_key), None)
        if receipt and receipt.get('transport') != 'local':
            item['provider_calls'] += 1
            if receipt.get('status') != 'completed':
                item['uncertain_calls'] += 1
            directions = receipt.get('privacy_directions', {}).get(use.alias.token)
            for direction in ('input', 'history', 'context'):
                item[direction] += directions.get(direction, 0) if directions else (use.count if direction == 'context' else 0)
    # Response references are counted once from the saved, canonical message,
    # never from SSE chunks or a naturally restored projection.
    for saved in Response.objects.filter(prompt_id__in={key[1] for key in by_turn}).only('prompt_id', 'content'):
        for row in rows:
            if (row.pk, saved.prompt_id) in by_turn:
                by_turn[(row.pk, saved.prompt_id)]['response'] = saved.content.count(row.token)
    irreversible = list(PrivacyOccurrence.objects.filter(message__turn__prompt__conversation_id=conversation_id,
        alias__isnull=True).values('category').annotate(count=Count('pk')))
    AuditLog.objects.create(company_id=context.company_id, user=request.user, action='privacy_inspect',
        details=json.dumps({'conversation_id': conversation_id, 'reason': 'owner_requested'}))
    return response({'enabled': revision is not None, 'revision_id': revision.pk if revision else None, 'coverage': COVERAGE,
        'totals': {'values': scoped.count(), 'occurrences': PrivacyOccurrence.objects.filter(alias__in=scoped).count()},
        'aliases': [{'id': row.pk, 'token': row.token, 'category': row.kind,
            'occurrences': occurrences.get(row.pk, 0), 'uses': uses.get(row.pk, 0), 'calls': calls.get(row.pk, 0),
            'locations': details.get(row.pk, []), 'turns': [item for (alias_id, _), item in by_turn.items() if alias_id == row.pk],
            'original': None} for row in rows[:50]],
        'irreversible': irreversible, 'next': rows[49].pk if len(rows) > 50 else None,
        'counts_note': 'Apariciones en revisiones protegidas. Los usos registrados no confirman entrega al proveedor.'})


@login_required
@require_POST
def reveal(request, conversation_id):
    from .models import ConversationAlias, AuditLog
    from .privacy import effective_revision
    from .privacy_policy import revision_config
    from .privacy_presentation import recoverable
    context = context_for(request, conversation_id)
    try:
        value = payload(request)
        ids = value.get('ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 25 or any(type(key) is not int for key in ids):
            raise ValueError()
        revision = effective_revision(context)
        if revision is None:
            raise ValueError()
        config, rules = revision_config(context, revision)
        rows = list(ConversationAlias.objects.filter(**context.scope(), pk__in=ids))
        if len(rows) != len(set(ids)):
            raise ValueError()
        result = [{'id': row.pk, 'original': row.original if recoverable(row, config, rules) else None} for row in rows]
        AuditLog.objects.create(company_id=context.company_id, user=request.user, action='privacy_reveal',
            details=json.dumps({'alias_ids': ids, 'conversation_id': conversation_id, 'reason': 'owner_requested'}))
        return response({'aliases': result})
    except (ValueError, TypeError):
        return _failure(None)


@login_required
@require_POST
def preview(request, conversation_id=None):
    from .privacy import effective_revision
    from .privacy_policy import PrivacyConfig, revision_config, preview_text, preview_segments
    from .models import PrivacyRevision, Profile
    from .policy import evaluate_policy, digest
    try:
        value = payload(request)
        profile = Profile.objects.select_related('company', 'user').get(user=request.user, user__is_active=True)
        if conversation_id is not None:
            context = context_for(request, conversation_id)
            revision = effective_revision(context)
            config, rules = revision_config(context, revision) if revision else (PrivacyConfig(), [])
        else:
            reference = profile.company.ai_config.get('privacy')
            revision = PrivacyRevision.objects.get(pk=reference['revision_id'], company=profile.company) if reference else None
            config = PrivacyConfig.model_validate(json.loads(revision.configuration)) if revision else PrivacyConfig()
            from .local_masking import detector_metadata
            if revision and revision.detector_version != digest(detector_metadata()):
                raise ValueError('privacy_detector_changed')
            from .models import Rule
            rules = list(Rule.objects.filter(pk__in=[item.rule_id for item in config.yara], rules_group__company=profile.company))
        text = value.get('text')
        protected, ranges = preview_text(text, config, rules)
        decision = evaluate_policy(request.user, [('prompts', text)])
        return response({'protected': protected, 'count': len(ranges), 'coverage': COVERAGE, 'scope': 'draft_only',
            'source_segments': preview_segments(text, ranges), 'protected_segments': preview_segments(protected, protected=True),
            'notice': 'Solo este borrador. No incluye historial ni adjuntos. Los identificadores son ilustrativos. Al enviar se revalida todo.',
            'policy_status': decision.status, 'revision_id': revision.pk if revision else None, 'calls': []})
    except (ValueError, TypeError, KeyError, PrivacyRevision.DoesNotExist):
        return _failure(None)


@login_required
@require_POST
def selection(request, conversation_id):
    from django.core import signing
    from django.db import transaction
    from .models import ConversationAlias, PrivacySelection, AuditLog
    from .privacy import effective_revision, alias_value, keyed_digest, TOKEN
    from .privacy_policy import revision_config, ProtectedLiteral, detect_ranges, preview_segments
    context = context_for(request, conversation_id)
    try:
        value = payload(request)
        text = value.get('text')
        if not isinstance(text, str) or not 1 <= len(text) <= 512 or not text.strip():
            raise ValueError()
        with transaction.atomic():
            Conversation.objects.select_for_update().get(pk=conversation_id)
            revision = effective_revision(context)
            if revision is None:
                raise ValueError()
            config, rules = revision_config(context, revision)
            before = list(PrivacySelection.objects.filter(alias__conversation_id=conversation_id).order_by('pk').values_list('pk', flat=True))
            proof = {'actor': request.user.pk, 'company': context.company_id, 'conversation': conversation_id,
                'revision': revision.pk, 'selections': before, 'text': keyed_digest(text)}
            existing = detect_ranges(text, config, rules)
            category = next((kind for a, b, kind, recover, _ in existing if a == 0 and b == len(text) and recover), 'FIELD')
            config.literals.append(ProtectedLiteral(text=text, category=category))
            if any(not recover for _, _, _, recover, _ in detect_ranges(text, config, rules)):
                raise ValueError('privacy_selection_irreversible')
            if value.get('review_token'):
                if signing.loads(value['review_token'], salt='privacy-selection', max_age=900) != proof:
                    raise ValueError()
                token = alias_value(context, category, text)
                if not TOKEN.fullmatch(token):
                    raise ValueError('privacy_secret_irreversible')
                row = ConversationAlias.objects.get(**context.scope(), token=token)
                PrivacySelection.objects.get_or_create(alias=row)
                AuditLog.objects.create(company_id=context.company_id, user=request.user, action='privacy_select',
                    details=json.dumps({'alias_id': row.pk, 'conversation_id': conversation_id, 'reason': 'exact_selection'}))
                return response({'saved': True, 'notice': 'Se aplicará en futuros envíos, incluido el historial reenviado. No retira lo ya enviado.'})
            protected, count = preview_value(text, config, rules)
            return response({'protected': protected, 'count': count,
                'protected_segments': preview_segments(protected, protected=True),
                'review_token': signing.dumps(proof, salt='privacy-selection'), 'coverage': COVERAGE})
    except (ValueError, TypeError, KeyError, signing.BadSignature):
        return _failure(None)


from .access import company_policy_required


@company_policy_required
@require_GET
def settings_page(request):
    from django.shortcuts import render
    result = render(request, 'privacy/settings.html')
    result['Cache-Control'] = 'private, no-store'
    return result


@company_policy_required
@require_http_methods(['GET', 'POST'])
def configuration(request):
    from .privacy_policy import PrivacyConfig, compatible_strings, simulate_revision, activate_revision
    from .models import PrivacyRevision, Rule
    from .policy import digest
    from .access import actor_company
    from django.core import signing
    company = actor_company(request.user)
    if request.method == 'GET':
        reference = company.ai_config.get('privacy')
        revision = PrivacyRevision.objects.filter(pk=(reference or {}).get('revision_id'), company=company).first()
        rules = []
        for rule in Rule.objects.filter(rules_group__company=company):
            try:
                strings, reason = sorted(compatible_strings(rule.yara_rule)), None
            except ValueError:
                strings, reason = [], 'Esta regla no pertenece al subconjunto localizable de texto.'
            rules.append({'rule_id': rule.pk, 'name': rule.name, 'action': rule.action,
                          'source_hash': digest(rule.yara_rule), 'strings': strings, 'reason': reason})
        return response({'enabled': bool(reference), 'configuration': json.loads(revision.configuration) if revision else PrivacyConfig().model_dump(),
            'rules': rules, 'coverage': COVERAGE})
    try:
        value = payload(request)
        if value.get('action') == 'simulate':
            if value.get('synthetic') is not True:
                raise ValueError()
            return response(simulate_revision(request.user, value.get('configuration'), value.get('sample')))
        if value.get('action') == 'activate':
            revision = activate_revision(request.user, value.get('revision_id'), value.get('review_token'))
            return response({'activated': True, 'revision_id': revision.pk})
        raise ValueError()
    except (ValueError, TypeError, KeyError, signing.BadSignature, PrivacyRevision.DoesNotExist):
        return _failure(None)
