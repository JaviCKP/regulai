"""Preserve isolated fixed-SHA test output without reading local settings."""
from contextlib import redirect_stdout, redirect_stderr
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'candidate' / 'regulai'))
sys.path.insert(0, str(HERE))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
labels = sys.argv[1:] or ['temperature_repro.DocumentTemperatureRepro.test_document_request_matches_manifest_temperature']
log = HERE / ('temperature-test.log' if not sys.argv[1:] else 'existing-evaluation-tests.log')
with log.open('x', encoding='utf-8') as stream, redirect_stdout(stream), redirect_stderr(stream):
    import django
    django.setup()
    from django.conf import settings
    from django.test.utils import get_runner
    failures = get_runner(settings)(verbosity=2).run_tests(labels)
print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-28:]))
print('Evidence log: ' + str(log))
raise SystemExit(bool(failures))
