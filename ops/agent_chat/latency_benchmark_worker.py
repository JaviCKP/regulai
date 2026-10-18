"""Isolated benchmark: real SDK/dispatcher, no sandbox or provider access."""
import json
from contextlib import ExitStack, nullcontext
from contextvars import ContextVar
import os
import signal
import socket
import threading
import time
from pathlib import Path
from unittest.mock import patch
import httpx

from front.agents.worker import run
from front.agents.adapter import InternalClient

original_operation = InternalClient.operation
profile_state = ContextVar('worker_benchmark_profile', default=None)
profiling = os.environ.get('BENCH_PROFILE') == '1'


def operation(self, name, payload):
    state = profile_state.get()
    if state and name == 'inference' and state['active']:
        state['active'] = False
        state['before_inference_s'] = time.perf_counter() - state['started']
        state['before_inference_process_cpu_s'] = time.process_time() - state['started_cpu']
        state['profile'] = state['recorder'].snapshot()
    try:
        with state['recorder'].span('http.operation.' + name) if state else nullcontext():
            result = original_operation(self, name, payload)
        if state and name == 'run/bootstrap':
            state['execution'] = result.get('execution')
            state['authorized_tools'] = result.get('tools', [])
        return result
    except Exception as error:
        print(json.dumps({'operation': name, 'error': type(error).__name__, 'code': str(error)[:120]}), flush=True)
        raise


original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex


def local_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('benchmark_external_network_denied')
    return original_connect(sock, address)


def local_connect_ex(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('benchmark_external_network_denied')
    return original_connect_ex(sock, address)


def profiled_job(original, internal, *args, **kwargs):
    from latency_profile import Recorder
    state = {'active': True, 'started': time.perf_counter(), 'started_cpu': time.process_time()}
    state['recorder'] = Recorder(lambda: state['active'], lambda: 'worker')
    token = profile_state.set(state)
    try:
        with state['recorder'].span('sdk.run_job'):
            return original(internal, *args, **kwargs)
    finally:
        state['active'] = False
        if state.get('profile'):
            report = {key: state[key] for key in ('execution', 'authorized_tools', 'before_inference_s',
                'before_inference_process_cpu_s', 'profile') if key in state}
            # Completion telemetry runs after the measured provider boundary.
            endpoint = config['internal_endpoint'].split('/internal/agents/')[0]
            with httpx.Client(trust_env=False, timeout=5) as client:
                response = client.post(endpoint + '/__bench/worker-profile', json=report)
                response.raise_for_status()
        profile_state.reset(token)


def measured(function, name):
    def call(*args, **kwargs):
        state = profile_state.get()
        with state['recorder'].span(name) if state else nullcontext():
            return function(*args, **kwargs)
    return call

stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
config = json.loads(Path('/bench/config.json').read_text())
with ExitStack() as patches:
    patches.enter_context(patch('front.agents.worker.create_clean', side_effect=AssertionError('benchmark_sandbox_denied')))
    patches.enter_context(patch.object(InternalClient, 'operation', operation))
    patches.enter_context(patch.object(socket.socket, 'connect', local_connect))
    patches.enter_context(patch.object(socket.socket, 'connect_ex', local_connect_ex))
    if profiling:
        from front.agents import worker, professional_worker
        original_job = worker.run_job
        patches.enter_context(patch.object(worker, 'run_job', lambda internal, *args, **kwargs:
            profiled_job(original_job, internal, *args, **kwargs)))
        for module in (worker, professional_worker):
            patches.enter_context(patch.object(module, 'build_agent', measured(module.build_agent, 'sdk.build_agent')))
        for name in ('dumps', 'loads'):
            patches.enter_context(patch.object(json, name, measured(getattr(json, name), 'json.' + name)))
    run(config, stop_event=stop)
