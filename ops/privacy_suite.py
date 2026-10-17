"""Run the same named regressions on isolated checkouts and disposable PostgreSQL."""
import json
import os
from pathlib import Path
import sys

checkout, output, database = sys.argv[1:4]
if not database.startswith('test_regulai_privacy_'):
    raise SystemExit('Disposable database name required')
sys.path.insert(0, str(Path(checkout).resolve() / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
from django.conf import settings
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'postgres', 'USER': 'task58', 'PASSWORD': 'synthetic-ci-only',
    'HOST': '127.0.0.1', 'PORT': '55483', 'TEST': {'NAME': database}}}
import django
django.setup()
from django.test.runner import DiscoverRunner

class RecordedRunner(DiscoverRunner):
    def suite_result(self, suite, result, **kwargs):
        Path(output).write_text(json.dumps({'tests': result.testsRun,
            'failures': [{'test': str(test), 'trace': trace} for test, trace in result.failures],
            'errors': [{'test': str(test), 'trace': trace} for test, trace in result.errors],
            'skipped': [(str(test), reason) for test, reason in result.skipped]}, indent=2), encoding='utf-8')
        return super().suite_result(suite, result, **kwargs)

labels = sys.argv[4:] or ['front.test_agent_inference', 'front.test_agent_professional',
    'front.test_agent_runtime_p0', 'front.test_agent_transparency', 'front.test_agent_preflight_inputs',
    'front.test_chat_page', 'front.test_chat_island', 'front.test_chat_ui', 'front.test_chat_streaming']
raise SystemExit(RecordedRunner(verbosity=0, interactive=False).run_tests(labels))
