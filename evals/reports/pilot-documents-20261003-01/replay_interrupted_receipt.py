"""Persist a labelled synthetic interrupted receipt in a verified B pilot database.

This does not reproduce an actual process interruption. It only prepares the
equivalent UI state (generation started, null cost, absent total, no response).
"""
import argparse
import json
from pathlib import Path
import sys
import uuid


ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
options = parser.parse_args()
workspace = options.workspace.resolve()
if not workspace.is_relative_to((ROOT / '.claude').resolve()):
    parser.error('Only the isolated pilot workspace is permitted')
metadata = json.loads((workspace / 'run.json').read_text(encoding='utf-8'))
database = workspace / 'pilot.sqlite3'
if Path(metadata['database']).resolve() != database or not database.is_file() or database.is_symlink():
    parser.error('Pilot metadata/database mismatch')
sys.path.insert(0, str(ROOT / 'regulai'))
from django.conf import settings
from regulai import test_settings
values = {key: getattr(test_settings, key) for key in dir(test_settings) if key.isupper()}
values['DATABASES'] = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': database}}
settings.configure(**values)
import django
django.setup()
from django.contrib.auth.models import User
from django.db import transaction
from front.models import Conversation, Message, Prompt

with transaction.atomic():
    actor = User.objects.get(username='community-demo', profile__company__name='Community offline demo')
    request_id = uuid.UUID('e4f65559-158a-4d22-99f5-ed78e846d9b5')
    if Prompt.objects.filter(request_id=request_id).exists():
        raise SystemExit('Reconstruction already exists; no records changed')
    conversation = Conversation.objects.create(user=actor, title='SYNTHETIC RECONSTRUCTION outcome_unknown')
    message = Message.objects.create(conversation=conversation, role='user',
        content='SYNTHETIC RECONSTRUCTION: persisted UI state after interruption; no provider was called by this fixture.')
    Prompt.objects.create(user=actor, company=actor.profile.company, conversation=conversation,
        user_message=message, content=message.content, request_id=request_id, status='outcome_unknown',
        decision={'schema_version': 1, 'error_type': 'outcome_unknown',
                  'calls': [{'purpose': 'generation', 'status': 'started', 'provider': 'synthetic-reconstruction',
                             'model': 'not-a-live-model', 'cost': None}]})
print(json.dumps({'conversation_id': conversation.pk, 'request_id': str(request_id),
                  'status': 'outcome_unknown', 'receipt_total_present': False,
                  'fixture_only': True, 'actual_interruption': False}))
