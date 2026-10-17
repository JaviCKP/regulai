"""Disposable privacy laboratory only; no production database or secrets."""
from .test_settings import *

DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'postgres', 'USER': 'task58', 'PASSWORD': 'synthetic-ci-only',
    'HOST': '127.0.0.1', 'PORT': '55483', 'TEST': {'NAME': 'test_regulai_privacy'}}}
