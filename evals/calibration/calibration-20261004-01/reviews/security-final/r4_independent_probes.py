"""Independent R4 delta checks against the immutable previous classifier."""
from dataclasses import asdict
import importlib.util
from itertools import product
import math
from pathlib import Path
import sys

from django.test import SimpleTestCase
from front.classification import decide
from front.policy import AIConfig
from front.test_classification import answers

PREVIOUS = Path(__file__).with_name('snapshot-3940fdc') / 'regulai/front/classification.py'
SPEC = importlib.util.spec_from_file_location('front.review_previous_classification', PREVIOUS)
OLD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OLD
SPEC.loader.exec_module(OLD)


class IndependentManipulationReview(SimpleTestCase):
    def test_legacy_omitted_and_null_configs_equal_old_classifier_for_signal_pairs(self):
        for threshold, override, floor in product((.2, .35, .8), ('omit', None), ('public', 'internal', 'unknown', 'restricted')):
            policy = {'signal_threshold': threshold}
            if override != 'omit':
                policy['manipulation_threshold'] = override
            config = AIConfig.model_validate({'classification_policy': policy})
            for manipulation, credential, personal in product((0, math.nextafter(threshold, 0), threshold, 1), repeat=3):
                signals = answers()
                signals['manipulation']['noul'] = manipulation
                signals['credentials']['noul'] = credential
                signals['personal_data']['noul'] = personal
                self.assertEqual(asdict(decide(signals, config, floor)), asdict(OLD.decide(signals, config, floor)))

    def test_mixed_non_manipulation_signals_match_old_result_when_manipulation_is_below_both(self):
        keys = ('credentials', 'personal_data', 'business_confidential', 'ambiguous', 'insufficient_evidence')
        scores = (0, math.nextafter(.2, 0), .2, 1)
        for threshold in (.35, .4, .5):
            config = AIConfig.model_validate({'classification_policy': {'manipulation_threshold': threshold}})
            for values in product(scores, repeat=len(keys)):
                signals = answers()
                for key, value in zip(keys, values):
                    signals[key]['noul'] = value
                self.assertEqual(asdict(decide(signals, config, 'public')), asdict(OLD.decide(signals, AIConfig(), 'public')))

    def test_overridden_manipulation_does_not_allow_credentials_or_restricted_floor(self):
        for threshold, floor in product((.35, .4, .5), ('public', 'internal', 'unknown', 'restricted')):
            signals = answers()
            signals['manipulation']['noul'] = math.nextafter(threshold, 0)
            signals['credentials']['noul'] = .2
            config = AIConfig.model_validate({'classification_policy': {'manipulation_threshold': threshold}})
            actual = decide(signals, config, floor)
            self.assertEqual((actual.sensitivity, actual.stop_code), ('restricted', 'restricted_content'))

    def test_invalid_provider_evidence_fails_closed_even_at_high_override(self):
        config = AIConfig.model_validate({'classification_policy': {'manipulation_threshold': .5}})
        for value in ('0.49', None, True, float('nan'), float('inf'), -.1, 1.01):
            signals = answers()
            signals['manipulation']['noul'] = value
            self.assertEqual(decide(signals, config, 'public').stop_code, 'security_check_failed')
