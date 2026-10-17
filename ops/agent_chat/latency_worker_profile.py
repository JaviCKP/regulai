"""SDK-only preparation profile; synthetic HTTP, no database or external sockets.

Run with the pinned SDK environment. Timing stops at the first inference request,
before its synthetic response, and includes construction of the internal client.
The separate cProfile pass is excluded from the latency sample.
"""
import argparse
import cProfile
from contextlib import nullcontext
import io
import json
import math
from pathlib import Path
import pstats
import statistics
import subprocess
import time
from types import ModuleType
from unittest.mock import Mock, patch

import httpx

from test_p0_runtime import LazyRuntimeTests, RuntimeBoundary
from front.agents import professional_worker

PROFESSIONAL_TOOLS = ['web_search', 'web_open', 'web_find', 'web_download', 'web_browse',
                      'install_packages', 'publish_artifact', 'inspect_image', 'read_output',
                      'replace_file', 'edit_file']


def sample(tool_names):
    boundary = RuntimeBoundary()
    original = boundary.respond
    first = {}

    def respond(request):
        if request.url.path.endswith('/inference/') and not first:
            first.update(wall=time.perf_counter(), cpu=time.process_time())
        result = original(request)
        if request.url.path.endswith('/run/bootstrap/'):
            value = result.json()
            value['tools'] = ['execute', *tool_names]
            result = httpx.Response(200, json=value)
        return result

    boundary.respond = respond
    wall, cpu = time.perf_counter(), time.process_time()
    result = LazyRuntimeTests().invoke(boundary, Mock(side_effect=AssertionError('Sandbox denied')))
    assert result['status'] == 'completed'
    assert len(boundary.inferences) == 1
    return {'wall_ms': (first['wall'] - wall) * 1000,
            'cpu_ms': (first['cpu'] - cpu) * 1000}


def stats(rows, name):
    values = sorted(row[name] for row in rows)
    return {'n': len(values), 'median': statistics.median(values),
            'p95': values[math.ceil(.95 * len(values)) - 1], 'max': max(values)}


def schema_comparison(ref):
    """Compare the exact SDK schemas with the immutable source ref supplied."""
    path = 'regulai/front/agents/professional_worker.py'
    ref = subprocess.check_output(['rtk', 'proxy', 'git', 'rev-parse', ref + '^{commit}'], text=True).strip()
    source = subprocess.check_output(['rtk', 'proxy', 'git', 'show', ref + ':' + path], text=True)
    baseline = ModuleType('front.agents._worker_schema_baseline')
    baseline.__package__, baseline.__file__ = 'front.agents', professional_worker.__file__
    exec(compile(source, baseline.__file__, 'exec'), baseline.__dict__)
    build = professional_worker.build_agent

    def collect(module):
        schemas = {}

        def capture(*args, **kwargs):
            schemas.update({item.name: item.tool_call_schema.model_json_schema() for item in kwargs['tools']})
            return build(*args, **kwargs)

        with patch.object(module, 'build_agent', side_effect=capture), \
                patch.object(professional_worker, 'run_professional', module.run_professional):
            sample(PROFESSIONAL_TOOLS)
        return schemas

    before, after = collect(baseline), collect(professional_worker)
    if before != after:
        raise AssertionError('Professional SDK tool schemas changed')
    return {'baseline_ref': ref, 'count': len(after), 'equal': True, 'names': sorted(after)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=31)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--tools', choices=('minimal', 'all', 'installed'), default='minimal')
    parser.add_argument('--compare-ref', help='Also compare every tool schema with a git source ref')
    parser.add_argument('--schema-cache', choices=('current', 'disabled'), default='current')
    args = parser.parse_args()
    if args.count < 2:
        parser.error('--count must be at least 2')
    tool_names = (PROFESSIONAL_TOOLS if args.tools == 'all' else
                  ['edit_file', 'glob', 'grep', 'ls', 'publish_artifact', 'read_file',
                   'read_output', 'web_download', 'web_find', 'web_open', 'write_file']
                  if args.tools == 'installed' else [])
    with (patch.object(professional_worker, '_runtime_tool', professional_worker.tool)
          if args.schema_cache == 'disabled' else nullcontext()):
        rows = [sample(tool_names) for _ in range(args.count)]
        profiler = cProfile.Profile()
        profiler.runcall(sample, tool_names)
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(40)
    report = {'scope': 'Pinned SDK synthetic InternalClient HTTP; first inference request; no database/network',
              'granted_tools': ['execute', *tool_names],
              'schema_cache': args.schema_cache,
              'cold_scope': 'First graph invocation after module imports; not process startup or Django',
              'cold': rows[0], 'warm': {name: stats(rows[1:], name) for name in rows[0]},
              'rows': rows, 'profile': stream.getvalue()}
    if args.compare_ref:
        report['schema_comparison'] = schema_comparison(args.compare_ref)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
