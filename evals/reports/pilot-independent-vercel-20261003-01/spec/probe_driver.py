import os
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'source/regulai'), str(HERE)]
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import django
django.setup()
from django.test.runner import DiscoverRunner

with patch('socket.socket.connect', side_effect=AssertionError('Independent spec review forbids sockets')), \
        patch('socket.getaddrinfo', side_effect=AssertionError('Independent spec review forbids DNS')):
    labels = ['spec_probes.GatewayBoundarySpec.test_timeout_retains_judge_reservation_and_stops_after_first_boundary',
        'spec_probes.GatewayBoundarySpec.test_gateway_tariff_estimate_never_releases_conservative_reserve',
        'spec_probes.GatewayBoundarySpec.test_approval_revoked_during_local_mask_prevents_gateway_and_generator',
        'spec_probes.GatewayBoundarySpec.test_only_two_exact_tuples_accepted_even_with_rebound_synthetic_approval',
        'spec_probes.FrozenScopeSpec', 'front.test_evaluation_pilot.VercelPilotTests',
        'front.test_evaluation_pilot.PilotReportModeTests']
    raise SystemExit(bool(DiscoverRunner(verbosity=2).run_tests(labels)))
