"""Executor subprocess for the live application acceptance test.

Uses the real SDK, worker, HTTP gateway and Linux runner. E2B control transport
is replaced by a local namespace fixture; the provider is simulated by Django.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'regulai'))
from ops.agent_chat.test_professional_runtime import RealWorkspaceTests
from front.agents.adapter import InternalClient
from front.agents.professional_worker import run_professional
from front.agents.worker import Lease

config = json.loads(sys.stdin.read())
fixture = RealWorkspaceTests()
fixture.setUp()
transport = fixture.transport
original = transport.run
def run(command, **kwargs):
    if kwargs.get('user') == 'root':
        # The fixture already gives each command a separate unshared namespace.
        # MicroVM provisioning/tmpfs mount is an E2B control-plane prerequisite,
        # intentionally outside what this local substitute claims to validate.
        if not command.startswith(('mount -t tmpfs ', 'chmod -R a-w /workspace/input')):
            raise AssertionError('Unexpected administrative command')
        return SimpleNamespace(stdout='', stderr='', exit_code=0)
    return original(command, **kwargs)
transport.run = run
transport.set_timeout = lambda *_: None
transport.kill = lambda: None
internal = InternalClient(config['endpoint'], config['token'], config['attempt'])
try:
    with Lease(internal, transport) as lease:
        result = run_professional(internal, transport, lease, internal.operation('run/bootstrap', {}))
    print(json.dumps(result))
finally:
    internal.close()
    fixture.doCleanups()
