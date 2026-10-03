import os
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
root = here / sys.argv[1]
sys.path[:0] = [str(root / 'regulai'), str(here)]
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import django
django.setup()
from django.test.runner import DiscoverRunner
labels = [
    'spec_probes.IndependentLocalSpec.test_latest_whole_history_masked_at_sdk_without_rewriting_old_audit',
    'spec_probes.IndependentLocalSpec.test_unknown_floor_remains_confidential_with_actual_local_detector',
    'spec_probes.IndependentLocalSpec.test_visual_omission_requires_consent_before_actual_local_work_in_three_entries',
]
if sys.argv[1] == 'closure':
    labels.extend([
        'spec_probes.IndependentLocalSpec.test_numeric_privacy_reaches_all_sdk_entries_after_closure',
        'front.test_local_masking.LocalMaskingTests',
        'front.test_local_masking_integration.LocalMaskingMigrationTests',
        'front.test_document_fidelity.FrozenPilotCorpusTests',
        'front.test_onboarding_migrations',
        'front.test_access',
    ])
if len(sys.argv) > 2 and sys.argv[2] == 'independent':
    labels = [label for label in labels if label.startswith('spec_probes.')]
raise SystemExit(bool(DiscoverRunner(verbosity=2).run_tests(labels)))
