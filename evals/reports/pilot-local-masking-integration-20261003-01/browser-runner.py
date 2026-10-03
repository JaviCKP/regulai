"""Fresh isolated local configuration UI; no provider traffic or user database."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT / '.claude' / 'pilot-local-mask-ui-20261003-01'
assert WORKSPACE.resolve().is_relative_to((ROOT / '.claude').resolve())
database = WORKSPACE / 'synthetic.sqlite3'
resume = sys.argv[1:] == ['--resume']
if resume:
    original = json.loads(Path(__file__).with_name('browser-environment.json').read_text(encoding='utf-8'))
    assert Path(original['database']).resolve() == database.resolve()
    assert database.is_file() and not database.is_symlink()
else:
    assert not sys.argv[1:]
    WORKSPACE.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / 'regulai'))
from django.conf import settings
from regulai import test_settings
values = {key: getattr(test_settings, key) for key in dir(test_settings) if key.isupper()}
values.update(DEBUG=True, DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': database}},
    MEDIA_ROOT=WORKSPACE / 'media', ALLOW_REGISTRATION=False,
    SESSION_COOKIE_NAME='local_privacy_ui_session', CSRF_COOKIE_NAME='local_privacy_ui_csrf',
    SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, SECURE_SSL_REDIRECT=False)
settings.configure(**values)
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from front.models import Company, Profile
if resume:
    company = Company.objects.get(pk=original['company'], name='Local privacy visual fixture')
    user = User.objects.get(pk=original['user'], username='local-privacy-ui')
    assert user.profile.company_id == company.pk
else:
    call_command('migrate', interactive=False, verbosity=0)
    company = Company.objects.create(name='Local privacy visual fixture')
    user = User.objects.create_user('local-privacy-ui', password='synthetic-ui-only', is_staff=True, is_superuser=True)
    Profile.objects.create(user=user, company=company)
    Path(__file__).with_name('browser-environment.json').write_text(json.dumps({
        'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'database': str(database),
        'company': company.pk, 'user': user.pk, 'listen': '127.0.0.1:8777', 'fresh_synthetic_database': True,
        'providers_forbidden': True}, indent=2) + '\n', encoding='utf-8')
with patch('socket.socket.connect', side_effect=AssertionError('Provider network is forbidden')):
    print('Synthetic configuration UI: http://127.0.0.1:8777/login/', flush=True)
    call_command('runserver', addrport='127.0.0.1:8777', use_reloader=False, use_threading=True)
