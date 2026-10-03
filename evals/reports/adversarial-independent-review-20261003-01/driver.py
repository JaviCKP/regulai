"""Django bootstrap under empty private settings and owned synthetic state only."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
from types import ModuleType
from unittest.mock import patch

OWN = Path(__file__).resolve().parent
SOURCE = OWN / ("followup" if sys.argv[1] == 'extension-fixed' else "source")
sys.dont_write_bytecode = True
sys.path[:0] = [str(OWN), str(SOURCE / "regulai")]
sys.modules['regulai.local_settings'] = ModuleType('regulai.local_settings')
tempfile.tempdir = str(OWN / "tmp")
original_connect = sqlite3.connect

def connect(path, *args, **kwargs):
    name = str(path)
    if name != ':memory:' and not (name.startswith('file:') and 'mode=memory' in name):
        if name.startswith('file:'):
            from urllib.parse import urlsplit, unquote
            parsed = unquote(urlsplit(name).path).lstrip('/')
            checked = Path(parsed)
        else:
            checked = Path(name)
        if not checked.resolve().is_relative_to(OWN):
            raise AssertionError('Persistent DB access outside independent review denied: ' + name)
    return original_connect(path, *args, **kwargs)

with ExitStack() as guards:
    guards.enter_context(patch('sqlite3.connect', side_effect=connect))
    for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection', 'socket.getaddrinfo'):
        guards.enter_context(patch(name, side_effect=AssertionError('Independent review forbids network')))
    import django
    django.setup()
    from django.conf import settings
    assert settings.DATABASES['default']['NAME'] == ':memory:'
    assert vars(sys.modules['regulai.local_settings']).keys() <= {'__name__', '__doc__', '__package__', '__loader__', '__spec__'}
    from django.core.management import call_command
    if sys.argv[1] == 'extension':
        call_command('test', 'front.test_evaluation_authorization_extension', 'independent_cases', verbosity=2, interactive=False)
    elif sys.argv[1] == 'extension-fixed':
        call_command('test', 'followup_cases.FollowupExtensionTests', verbosity=2, interactive=False)
    else:
        from django.test.utils import setup_test_environment
        setup_test_environment()
        call_command('migrate', verbosity=0, interactive=False)
        import runner_probe
        runner_probe.run()
