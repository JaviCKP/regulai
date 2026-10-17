"""Measured synthetic batches, separating lookup/authorization from local projection."""
import json
import platform
import statistics
import time
import tracemalloc
from pathlib import Path
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from front.test_privacy_presentation import PresentationTests
from front.test_privacy_service import RegistryFixture
from front.privacy_presentation import Presentation


class PrivacyPerformanceTests(PresentationTests):

    def test_loaded_projection_budget_and_constant_query_count(self):
        sample = ('🙂 ' + self.protected + ' Texto neutro. ') * 32
        def prepared():
            view = Presentation(self.user.pk, self.prompt, inference_id='inference-one')
            view.authorize()
            return view
        durations = []
        for _ in range(100):
            view = prepared()
            start = time.perf_counter_ns()
            result = view.feed(sample, final=True, revalidate=False)
            durations.append((time.perf_counter_ns() - start) / 1e6)
            self.assertIn('Ana Fixture', result['text'])
        view = prepared()
        tracemalloc.start()
        view.feed(sample, final=True, revalidate=False)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        queries = []
        for text in ('x', sample):
            view = prepared()
            with CaptureQueriesContext(connection) as capture:
                view.feed(text, final=True, revalidate=False)
            queries.append(len(capture))
        p95 = sorted(durations)[94]
        report = {'fixture': True, 'platform': platform.platform(), 'processor': platform.processor(),
            'python': platform.python_version(), 'iterations': 100, 'batch_bytes': len(sample.encode()),
            'aliases': 2, 'references_per_batch': 64, 'median_ms': statistics.median(durations),
            'p95_ms': p95, 'peak_bytes': peak, 'queries_one_char_and_batch': queries,
            'scope': 'Presentation.feed with authorized mappings already loaded; includes current local policy scan'}
        out = Path(__file__).resolve().parents[2] / 'output' / 'privacy-20261017'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'performance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        self.assertEqual(queries[0], queries[1])
        self.assertLess(p95, 50, report)
