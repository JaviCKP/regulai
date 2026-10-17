"""Owner-only derived views. No caller in inference may use this module.

The wire always retains canonical text/offsets. Projection envelopes replace a
consumer's view by source sequence; they are never stored or used as context.
"""
from copy import deepcopy
from dataclasses import asdict
import json

from .models import ConversationAlias, PrivacyTurn, Prompt, PrivacyMessage
from .privacy import ProtectionContext, authorize, effective_revision, required, prepare_turn, keyed_digest
from .privacy_projection import Projection, VERSION, UNAVAILABLE


def recoverable(row, config, rules):
    return recoverable_value(row.original, row.kind, config, rules)


def recoverable_value(original, kind, config, rules):
    from .privacy_policy import detect_ranges
    from .local_masking import detect_spans
    ranges = detect_ranges(original, config, rules) if original else []
    return bool(original and not any(kind == 'SECRET' for _, _, kind in detect_spans(original))
        # A full-condition irreversible YARA rule cannot be cleared by testing
        # a value in isolation. A literal spanning this value and its context
        # is likewise not permission to reveal the value on its own.
        and not any(item.treatment == 'irreversible' for item in config.yara)
        and not any(item.treatment == 'irreversible' and (
            original in item.text or item.text in original or any(
                original.endswith(item.text[:size]) or original.startswith(item.text[-size:])
                for size in range(1, min(len(original), len(item.text))))) for item in config.literals)
        and not any(not recover for _, _, _, recover, _ in ranges)
        and (config.categories.get(kind) == 'reversible'
             or any(a == 0 and b == len(original) and recover for a,b,_,recover,_ in ranges)))


class Presentation:
    def __init__(self, actor_id, prompt, *, inference_id=None, call_key=None, user_message=False):
        if actor_id != prompt.user_id:
            raise ValueError('privacy_access_revoked')
        self.prompt, self.actor_id = prompt, actor_id
        self.context = ProtectionContext.from_prompt(prompt)
        self.inference_id, self.call_key, self.user_message = inference_id, call_key, user_message
        self.parser = Projection({})
        self.segments, self.end, self.canonical = [], 0, ''
        self.actor = None

    def authorize(self):
        profile = authorize(self.context)
        revision = effective_revision(self.context)
        turn = PrivacyTurn.objects.filter(prompt=self.prompt).first()
        if not revision or not turn:
            raise ValueError('privacy_projection_unavailable')
        if Prompt.objects.filter(pk=self.prompt.pk, status__in=['processing', 'received']).exists():
            prepare_turn(self.context)
        from .privacy_policy import revision_config
        config, rules = revision_config(self.context, revision)
        self.config, self.rules = config, rules
        uses = turn.uses.all()
        if self.inference_id is not None:
            uses = uses.filter(call_key__startswith=str(self.inference_id) + ':')
        elif self.call_key is not None:
            uses = uses.filter(call_key=self.call_key)
        else:
            uses = uses.none()
        ids = set(uses.values_list('alias_id', flat=True))
        if self.user_message:
            ids.update(turn.messages.values_list('occurrences__alias_id', flat=True))
        values = {}
        for row in ConversationAlias.objects.filter(**self.context.scope(), pk__in=ids):
            original = row.original
            if not recoverable(row, config, rules):
                continue
            values[row.token] = original
        if any(values.get(token) != original for token, original in self.parser.aliases.items()):
            raise ValueError('privacy_projection_revoked')
        self.parser.aliases = values
        self.actor = profile.user
        return profile.user

    def feed(self, text, *, seq=0, final=False, append=False, revalidate=True):
        actor = self.authorize() if revalidate else self.actor
        if actor is None:
            raise ValueError('privacy_access_revoked')
        before = len(self.segments)
        self.canonical += text
        self.end += len(text.encode('utf-8'))
        self.segments.extend(asdict(segment) for segment in self.parser.feed(text, final=final))
        if self.user_message and final:
            message = PrivacyMessage.objects.filter(turn__prompt=self.prompt, protected=self.canonical).first()
            if message:
                variants = json.loads(message.variants)
                for segment in self.segments:
                    if segment['kind'] == 'original' and str(segment['start']) in variants:
                        original = variants[str(segment['start'])]
                        token = self.canonical.encode()[segment['start']:segment['end']].decode()
                        kind = token[4:].split('_', 1)[0]
                        if not recoverable_value(original, kind, self.config, self.rules):
                            raise ValueError('privacy_projection_revoked')
                        segment['text'] = original
        natural = ''.join(segment['text'] for segment in self.segments)
        from .privacy_policy import detect_ranges
        irreversible = [(a, b) for a, b, _, recover, _ in detect_ranges(natural, self.config, self.rules) if not recover]
        offset = 0
        for segment in self.segments:
            end = offset + len(segment['text'])
            if segment['kind'] == 'original' and any(offset < b and end > a for a, b in irreversible):
                raise ValueError('privacy_presentation_blocked')
            offset = end
        # Local only: a restored value never goes to a remote verifier. Rule
        # conditions requiring the whole answer already force complete delivery.
        from .policy import active_rules, scan_rules
        try:
            _, matches = scan_rules(active_rules(actor), [('prompts', natural)])
            if any(rule['action'] == 'block' for rule in matches):
                raise ValueError('privacy_presentation_blocked')
        except Exception:
            raise ValueError('privacy_presentation_blocked') from None
        emitted = self.segments[before:] if append else self.segments
        return {'version': VERSION, 'source_seq': seq, 'protected_end': self.end, 'append': append,
                'text': ''.join(segment['text'] for segment in emitted), 'segments': deepcopy(emitted), 'complete': final,
                'render': 'text'}


def project_message(actor_id, prompt, text, *, user_message=False, inference_id=None, final=True, seq=0):
    binding = prompt.decision.get('privacy_answer', {}) if inference_id is None else {}
    return Presentation(actor_id, prompt, user_message=user_message, call_key=binding.get('call_key'),
                        inference_id=inference_id or binding.get('inference_id')).feed(text, final=final, seq=seq)


def canonical_user(prompt, stored):
    row = PrivacyMessage.objects.filter(turn__prompt=prompt, input_digest=keyed_digest(stored)).first()
    canonical = PrivacyMessage.objects.filter(turn__prompt=prompt, protected=stored).exists()
    return row.protected if row else stored if canonical else '[Mensaje no enviado: versión protegida no disponible]'


def result_view(actor_id, data):
    """Attach authorized projections at HTTP delivery, never in request_result."""
    if not data.get('request_id'):
        return data
    prompt = Prompt.objects.filter(request_id=data['request_id'], user_id=actor_id).first()
    if not prompt or not required(prompt):
        return data
    result = deepcopy(data)
    for key in ('user_message', 'assistant_message'):
        if isinstance(result.get(key), dict) and isinstance(result[key].get('content'), str):
            if key == 'user_message':
                stored = result[key]['content']
                # User/agent records can retain the input. Obtain its committed
                # protected revision; never label that input a protected copy.
                result[key]['content'] = canonical_user(prompt, stored)
            result[key]['projection'] = project_message(actor_id, prompt, result[key]['content'],
                user_message=key == 'user_message')
            # Copy/export is plain text. Remove Markdown destinations entirely;
            # neither sensitive links nor executable markup gets reconstructed.
            import re
            result[key]['protected_copy'] = re.sub(r'!?\[([^\]\n]*)\]\([^\n)]*\)', r'\1', result[key]['content'])
    return result


def safe_result_view(actor_id, data):
    try:
        return result_view(actor_id, data)
    except ValueError:
        return {'request_id': data.get('request_id'), 'status': 'failed', 'success': False,
                'error_type': 'privacy_access_revoked', 'error': 'La vista ya no está autorizada. Actualiza la conversación.'}


class ChatPresentation:
    """One per HTTP consumer, rebuilt from canonical events on reconnect."""
    def __init__(self, actor_id, request_id):
        self.actor_id, self.request_id = actor_id, request_id
        self.presentation, self.attempt = None, None

    def event(self, event):
        value = deepcopy(event)
        prompt = Prompt.objects.filter(user_id=self.actor_id, request_id=self.request_id).first()
        if not prompt or not required(prompt):
            return value
        authorize(ProtectionContext.from_prompt(prompt))
        if event['type'] == 'retract':
            self.presentation = None
        elif event['type'] == 'delta':
            if self.presentation is None or event.get('attempt') != self.attempt:
                self.presentation = Presentation(self.actor_id, prompt, call_key=event.get('privacy_call_key'))
                self.attempt = event.get('attempt')
            value['projection'] = self.presentation.feed(event.get('text', ''), seq=event['seq'], append=True)
        elif event['type'] == 'final':
            value['result'] = result_view(self.actor_id, event.get('result', {}))
        return value


def agent_batch(actor_id, run, events, cursor=0, sessions=None):
    if not required(run.prompt):
        return events
    # Stateless polling reconstructs a consumer from canonical rows, never from
    # another browser's parser. Each message has its own inference allowlist.
    sessions = {} if sessions is None else sessions
    by_id = {event['id']: event for event in events}
    maximum = max(by_id, default=cursor)
    if not sessions and cursor:
        # One reconstruction per HTTP consumer at its initial cursor, outside
        # the writer lock; no mutable state is shared with another tab.
        history = {}
        for row in run.events.filter(pk__lte=cursor, kind__in=['text.delta', 'text.snapshot']).order_by('pk'):
            key = row.data['message_id']
            if key not in history or row.kind == 'text.snapshot':
                history[key] = [row.data['inference_id'], '']
            history[key][1] += row.public_text
        for key, (inference, text) in history.items():
            sessions[key] = Presentation(actor_id, run.prompt, inference_id=inference)
            sessions[key].feed(text)
    authorized = set()
    for row in run.events.filter(pk__gt=cursor, pk__lte=maximum).order_by('pk'):
        key = row.data.get('message_id')
        if key in sessions and key not in authorized:
            sessions[key].authorize()
            authorized.add(key)
        if row.kind == 'inference.finished':
            if key in sessions and not sessions[key].parser.closed:
                envelope = sessions[key].feed('', seq=row.pk, final=True, append=True, revalidate=False)
                if row.pk in by_id:
                    by_id[row.pk]['data']['projection'] = envelope
            continue
        if row.kind not in ('text.delta', 'text.snapshot'):
            continue
        key = row.data['message_id']
        if key not in sessions or row.kind == 'text.snapshot':
            sessions[key] = Presentation(actor_id, run.prompt, inference_id=row.data['inference_id'])
            sessions[key].authorize()
            authorized.add(key)
        envelope = sessions[key].feed(row.public_text, seq=row.pk, append=True, revalidate=False)
        if row.pk in by_id:
            by_id[row.pk]['data']['projection'] = envelope
    return events


def agent_snapshots(actor_id, run, segments):
    if required(run.prompt):
        finished = set(run.events.filter(kind='inference.finished').values_list('data__message_id', flat=True))
        for segment in segments:
            segment['projection'] = project_message(actor_id, run.prompt, segment['text'],
                inference_id=segment['inference_id'], final=run.status not in ('active', 'queued') or segment['message_id'] in finished)
    return segments
