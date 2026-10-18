"""Optional benchmark instrumentation. Never installed in application images.

Only names, timings, SQL hashes and counts are emitted; arguments, SQL parameters,
messages, credentials and function results are deliberately absent.
"""
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import wraps
import hashlib
import importlib
import inspect
import re
import sys
import threading
import time
from unittest.mock import patch


class Recorder:
    def __init__(self, active, scope):
        self.active, self.scope = active, scope
        self.stack = ContextVar('latency_spans', default=())
        self.reset()

    def reset(self):
        self.spans = defaultdict(lambda: defaultdict(float))
        self.sql = defaultdict(lambda: defaultdict(float))
        self.open_frames = []
        self.lock = threading.RLock()

    def _finish(self, frame, wall, cpu):
        if frame['closed']:
            return
        frame['closed'] = True
        elapsed, consumed = wall - frame['wall'], cpu - frame['cpu']
        key = (frame['path'], frame['name'])
        with self.lock:
            row = self.spans[key]
            row['calls'] += 1
            row['wall_s'] += elapsed
            row['thread_cpu_s'] += consumed
            row['self_wall_s'] += max(0, elapsed - frame['child_wall'])
            row['self_thread_cpu_s'] += max(0, consumed - frame['child_cpu'])
            if frame['parent'] is not None:
                frame['parent']['child_wall'] += elapsed
                frame['parent']['child_cpu'] += consumed

    @contextmanager
    def span(self, name):
        if not self.active():
            yield
            return
        stack = self.stack.get()
        frame = {'name': name, 'path': self.scope(), 'wall': time.perf_counter(),
            'cpu': time.thread_time(), 'thread': threading.get_ident(),
            'child_wall': 0, 'child_cpu': 0, 'closed': False,
            'parent': stack[-1] if stack else None}
        with self.lock:
            self.open_frames.append(frame)
        token = self.stack.set((*stack, frame))
        try:
            yield
        finally:
            self._finish(frame, time.perf_counter(), time.thread_time())
            self.stack.reset(token)

    def wrap(self, function, name):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.span(name):
                return function(*args, **kwargs)
        return measured

    def execute(self, execute, sql, params):
        if not self.active():
            return execute(sql, params)
        path = self.scope()
        # SQL text contains only its SHA256 in the report, never literals/params.
        shape = re.sub(r'\s+', ' ', sql).strip()
        fingerprint = hashlib.sha256(shape.encode()).hexdigest()[:20]
        verb = shape.split()[0].upper() if shape else 'EMPTY'
        stack, current = [], sys._getframe(1)
        while current and len(stack) < 8:
            filename = current.f_code.co_filename.replace('\\', '/')
            if '/front/' in filename:
                stack.append(filename.split('/front/')[-1] + ':' + current.f_code.co_name)
            current = current.f_back
        caller = ' > '.join(stack)
        started, cpu = time.perf_counter(), time.thread_time()
        try:
            return execute(sql, params)
        finally:
            with self.lock:
                row = self.sql[path, verb, fingerprint, caller]
                row['calls'] += 1
                row['wall_s'] += time.perf_counter() - started
                row['thread_cpu_s'] += time.thread_time() - cpu

    def snapshot(self):
        # Freeze spans crossing the provider boundary at that exact boundary.
        # CPU clocks are thread-local: only finish this thread's live frames.
        wall, cpu, thread = time.perf_counter(), time.thread_time(), threading.get_ident()
        with self.lock:
            for frame in reversed(self.open_frames):
                if frame['thread'] == thread:
                    self._finish(frame, wall, cpu)
            spans = [{'path': path, 'operation': name, **dict(row)}
                for (path, name), row in self.spans.items()]
            queries = [{'path': path, 'verb': verb, 'sql_sha256_prefix': fingerprint,
                'caller': caller, **dict(row)}
                for (path, verb, fingerprint, caller), row in self.sql.items()]
        return {'scope': 'Instrumented diagnostic, excluded from latency percentiles. '
            'Spans include nested work; self spans subtract instrumented children. '
            'SQL wall includes driver CPU and database/transport wait; wall minus '
            'thread CPU is wait, not PostgreSQL CPU. No external provider network.',
            'spans': sorted(spans, key=lambda row: row['wall_s'], reverse=True),
            'sql': sorted(queries, key=lambda row: row['wall_s'], reverse=True)}


@contextmanager
def server_instrumentation(recorder):
    functions = {
        'front.agents.service': ('_context', 'authenticate', 'infer', '_protect_messages', '_protected_messages'),
        'front.agents.jobs': ('accepted', '_bootstrap'),
        'front.agents.professional': ('bootstrap',),
        'front.agents.checkpoints': ('save', 'load'),
        'front.agents.skill_context': ('catalog',),
        'front.policy': ('evaluate_policy', 'scan_rules', 'active_rules'),
        'front.privacy': ('authorize', 'prepare_turn', '_protect_many', 'outbound', 'record_use'),
        'front.masking': ('mask_texts', 'mask_local_texts'),
        'front.local_masking': ('detect_spans',),
    }
    replacements = {}
    for name, attributes in functions.items():
        module = importlib.import_module(name)
        for attribute in attributes:
            original = getattr(module, attribute, None)
            if original is not None:
                replacements[original] = recorder.wrap(original, name + '.' + attribute)
    with ExitStack() as patches:
        # Cover imported aliases as well as the module that defines each function.
        for name, module in list(sys.modules.items()):
            if module is None or not (name == 'front' or name.startswith('front.')):
                continue
            for attribute, original in list(vars(module).items()):
                if inspect.isfunction(original) and original in replacements:
                    patches.enter_context(patch.object(module, attribute, replacements[original]))
        from front.governance import GovernedCalls
        for name in ('preflight', 'protect_texts', 'start_call'):
            patches.enter_context(patch.object(GovernedCalls, name,
                recorder.wrap(getattr(GovernedCalls, name), 'front.governance.' + name)))
        # JSON cost is measured only in this diagnostic process.
        import json
        for name in ('dumps', 'loads'):
            patches.enter_context(patch.object(json, name,
                recorder.wrap(getattr(json, name), 'json.' + name)))
        yield
