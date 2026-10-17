"""Session-authenticated presentation endpoints; no executor authentication."""
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from .access import authorized_conversations
from .models import Conversation, Prompt
from .privacy import required
from .privacy_presentation import safe_result_view


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
