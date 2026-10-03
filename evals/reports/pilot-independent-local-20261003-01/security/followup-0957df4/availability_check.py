"""Bounded numeric workload and recovery, with a real installed detector."""
import json
from pathlib import Path
import time

from django.test import SimpleTestCase
from front.local_masking import mask_local_texts


class NumericDeadlineControl(SimpleTestCase):
    def test_numeric_array_obeys_deadline_and_releases_detector_for_next_batch(self):
        mask_local_texts(['Prueba previa.'], timeout=30)
        text = '[' + ','.join(['0.125'] * 13000) + ']'
        started = time.monotonic()
        try:
            result = mask_local_texts([text], timeout=1)
        except TimeoutError:
            outcome = 'rejected_atomically_on_deadline'
        else:
            outcome = 'completed'
            self.assertEqual(result, [text])
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3)
        started = time.monotonic()
        next_batch = mask_local_texts(['next@example.invalid'], timeout=5)
        record = {'input_bytes': len(text), 'deadline_seconds': 1, 'outcome': outcome,
            'elapsed_seconds': round(elapsed, 3), 'next_batch': next_batch,
            'next_batch_seconds': round(time.monotonic() - started, 3)}
        Path(__file__).with_name('numeric-deadline.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        self.assertEqual(next_batch, ['[[REGULAI_EMAIL]]'])
