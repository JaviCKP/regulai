"""Independent follow-up. Original fixed snapshot remains untouched."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
baseline = '--baseline' in sys.argv
if baseline:
    sys.argv.remove('--baseline')
source = ROOT.parent / 'snapshot' if baseline else ROOT / 'snapshot'
sys.path.insert(0, str(source / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
(ROOT / 'tmp').mkdir(exist_ok=True)
tempfile.tempdir = str(ROOT / 'tmp')

from django.conf import settings
settings.MEDIA_ROOT = ROOT / 'media'
from django.core.management import execute_from_command_line

print('SOURCE ' + ('c1e3a360e7ba3051bb8f0bda487b005dd29834a0' if baseline
                   else 'a3bc67b25b341cb28172bebd5001ef48c5b8d34f'), flush=True)
with patch('socket.socket.connect', side_effect=AssertionError('Independent review forbids network')):
    execute_from_command_line(['review-standards-followup', 'test', *sys.argv[1:], '--noinput', '--verbosity=1'])
