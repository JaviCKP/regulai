"""A few bounded, synthetic runtime checks; no flood or external activity."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from django.test import SimpleTestCase
from front.local_masking import mask_local_texts


class BoundedWorkloadTests(SimpleTestCase):
    def test_ordinary_repetition_and_placeholders_complete_within_deadline(self):
        mask_local_texts(['Una prueba sin datos.'], timeout=30)
        samples = {
            'ordinary_20kb': ('datos de proyecto ' * 1200)[:20000],
            'ordinary_80kb': ('datos de proyecto ' * 4800)[:80000],
            'markers_email_80kb': ('[[REGULAI_EMAIL]] ana@example.invalid ' * 2300)[:80000],
            'numeric_json_80kb': '[' + ','.join(['0.125'] * 13000) + ']',
        }
        results = []
        for name, sample in samples.items():
            started = time.monotonic()
            try:
                output = mask_local_texts([sample], timeout=5)
                result = {'name': name, 'input_bytes': len(sample.encode()), 'status': 'completed',
                          'output_bytes': len(output[0].encode())}
            except Exception as error:
                result = {'name': name, 'input_bytes': len(sample.encode()), 'status': type(error).__name__}
            result['seconds'] = round(time.monotonic() - started, 3)
            results.append(result)
        path = Path(__file__).with_name('bounded-workload-observations.json')
        path.write_text(json.dumps(results, indent=2), encoding='utf-8')
        self.assertTrue(all(item['status'] == 'completed' and item['seconds'] < 5 for item in results), results)
