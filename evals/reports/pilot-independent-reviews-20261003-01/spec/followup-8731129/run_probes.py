"""Run three independent focal checks on the fixed snapshot and preserve output."""
from contextlib import redirect_stdout, redirect_stderr
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'candidate' / 'regulai'))
sys.path.insert(0, str(HERE))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
labels = [
    'closure_probes.ClosureProbes.test_general_payload_matches_frozen_options',
    'closure_probes.ClosureProbes.test_document_payload_matches_frozen_options',
    'closure_probes.ClosureProbes.test_drift_is_rejected_even_when_bound_to_test_approval',
]
log = HERE / 'independent-probes.log'
with log.open('x', encoding='utf-8') as stream, redirect_stdout(stream), redirect_stderr(stream):
    import django
    django.setup()
    from django.conf import settings
    from django.test.utils import get_runner
    failures = get_runner(settings)(verbosity=2).run_tests(labels)
print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-18:]))
print('Evidence log: ' + str(log))
raise SystemExit(bool(failures))
