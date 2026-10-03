import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
snapshot = sys.argv[1]
sys.path[:0] = [str(HERE / snapshot / 'regulai'), str(HERE)]
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['SPEC_DIAGNOSTIC_SNAPSHOT'] = snapshot
import django
django.setup()
from django.test.runner import DiscoverRunner
from spec_probes import save_records
failures = DiscoverRunner(verbosity=2).run_tests(['spec_probes.DiagnosticBehaviorSpec', 'spec_probes.DiagnosticObserverSpec'])
save_records()
raise SystemExit(bool(failures))
