"""Authorized SDK schemas and invocation survive deferred tool construction."""
import json
from concurrent.futures import ThreadPoolExecutor
import gc
from threading import Barrier
from unittest.mock import Mock, patch
import unittest
import weakref

import httpx

import test_p0_runtime as runtime_tests
from latency_worker_profile import PROFESSIONAL_TOOLS
from front.agents import professional_worker
from front.agents.protocol import REQUIRED, TOOL_PARAMETERS


class GrantedBoundary(runtime_tests.RuntimeBoundary):
    def __init__(self, names, *, call_output=False):
        super().__init__()
        self.names, self.call_output = names, call_output
        self.source_call = 'earlier-command'

    def respond(self, request):
        if request.url.path.endswith('/run/output/'):
            self.events.append(('run/output', json.loads(request.content)))
            return httpx.Response(200, json={'status': 'completed'})
        response = super().respond(request)
        if request.url.path.endswith('/run/bootstrap/'):
            value = response.json()
            value['tools'] = ['execute', *self.names]
            return httpx.Response(200, json=value)
        if (self.call_output and request.url.path.endswith('/inference/')
                and len(self.inferences) == 1):
            value = response.json()
            value.update(content='', tool_calls=[{'id': 'output-1', 'name': 'read_output',
                'args': {'call_id': self.source_call, 'offset': 17}}])
            return httpx.Response(200, json=value)
        return response


class ProfessionalToolPreparationTests(unittest.TestCase):
    def setUp(self):
        with professional_worker._TOOL_SCHEMA_LOCK:
            professional_worker._TOOL_SCHEMAS.clear()

    def invoke(self, boundary):
        return runtime_tests.LazyRuntimeTests().invoke(boundary, Mock(side_effect=AssertionError('No sandbox')))

    def test_excluded_tools_do_not_construct_schemas(self):
        # A process-warm schema is not a grant for the next execution.
        self.invoke(GrantedBoundary(PROFESSIONAL_TOOLS))
        boundary = GrantedBoundary([])
        with patch.object(professional_worker, 'tool', wraps=professional_worker.tool) as decorated:
            self.assertEqual(self.invoke(boundary)['status'], 'completed')
        decorated.assert_not_called()
        self.assertEqual(boundary.inferences[0]['tools'], ['execute'])

    def test_all_authorized_tools_keep_server_fields_and_required_arguments(self):
        schemas = {}
        build = professional_worker.build_agent

        def capture(*args, **kwargs):
            schemas.update({tool.name: tool.tool_call_schema.model_json_schema() for tool in kwargs['tools']})
            return build(*args, **kwargs)

        boundary = GrantedBoundary(PROFESSIONAL_TOOLS)
        with patch.object(professional_worker, 'build_agent', side_effect=capture):
            self.assertEqual(self.invoke(boundary)['status'], 'completed')
        self.assertEqual(set(schemas), set(PROFESSIONAL_TOOLS))
        for name, schema in schemas.items():
            with self.subTest(tool=name):
                self.assertEqual(set(schema['properties']), set(TOOL_PARAMETERS[name]))
                self.assertEqual(set(schema.get('required', [])), set(REQUIRED[name]))
                self.assertIn(name, boundary.inferences[0]['tools'])

    def test_runtime_injection_keeps_identified_tool_arguments(self):
        boundary = GrantedBoundary(['read_output'], call_output=True)
        self.assertEqual(self.invoke(boundary)['status'], 'completed')
        calls = [payload['call'] for name, payload in boundary.events if name == 'run/output']
        self.assertEqual(calls, [{'id': 'output-1', 'name': 'read_output',
                                 'args': {'call_id': 'earlier-command', 'offset': 17}}])
        self.assertEqual(len(boundary.inferences), 2)

    def test_warm_schema_keeps_successive_internal_clients_isolated(self):
        first = GrantedBoundary(['read_output'], call_output=True)
        first.source_call = 'first-execution'
        second = GrantedBoundary(['read_output'], call_output=True)
        second.source_call = 'second-execution'
        for boundary in (first, second):
            self.assertEqual(self.invoke(boundary)['status'], 'completed')
        for boundary in (first, second):
            calls = [payload['call']['args']['call_id'] for name, payload in boundary.events
                     if name == 'run/output']
            self.assertEqual(calls, [boundary.source_call])
        self.assertEqual(len(professional_worker._TOOL_SCHEMAS), 1)

    def test_cached_schema_does_not_retain_execution_or_function(self):
        class Marker:
            pass

        def bind(marker):
            def identify(value: str):
                """Return the execution-local value."""
                return marker, value
            return identify

        marker = Marker()
        function = bind(marker)
        reference, function_reference = weakref.ref(marker), weakref.ref(function)
        wrapped = professional_worker._runtime_tool(function)
        self.assertEqual(wrapped.invoke({'value': 'synthetic'}), (marker, 'synthetic'))
        del wrapped, function, marker
        gc.collect()
        self.assertIsNone(reference())
        self.assertIsNone(function_reference())
        self.assertEqual(len(professional_worker._TOOL_SCHEMAS), 1)

    def test_concurrent_schema_reuse_keeps_each_execution_closure(self):
        barrier = Barrier(8)

        def bind(label):
            def identify(value: str):
                """Return this execution's identity."""
                return label + value
            return identify

        def prepare(index):
            barrier.wait(5)
            wrapped = professional_worker._runtime_tool(bind(str(index)))
            return wrapped.invoke({'value': '!'}), id(wrapped.args_schema)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(prepare, range(8)))
        self.assertEqual([value for value, _ in results], [str(index) + '!' for index in range(8)])
        self.assertEqual(len({schema for _, schema in results}), 1)

    def test_changed_signature_is_rebuilt_and_cache_is_bounded(self):
        def bind(default):
            def identify(value: str = default):
                """Return the supplied value."""
                return value
            return identify

        first = professional_worker._runtime_tool(bind('first'))
        second = professional_worker._runtime_tool(bind('second'))
        self.assertIsNot(first.args_schema, second.args_schema)
        self.assertEqual(first.invoke({}), 'first')
        self.assertEqual(second.invoke({}), 'second')
        for index in range(20):
            professional_worker._runtime_tool(bind(str(index)))
        self.assertEqual(len(professional_worker._TOOL_SCHEMAS), 11)


if __name__ == '__main__':
    unittest.main()
