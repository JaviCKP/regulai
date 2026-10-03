"""Run the immutable candidate with an in-memory DB and no socket connections."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'snapshot' / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

from django.conf import settings
settings.MEDIA_ROOT = ROOT / 'media'
from django.core.management import execute_from_command_line

with patch('socket.socket.connect', side_effect=AssertionError('Independent review forbids network')):
    execute_from_command_line(['review-standards', 'test', *sys.argv[1:], '--noinput', '--verbosity=1'])
