"""Isolated benchmark: real SDK/dispatcher, no sandbox or provider access."""
import json
import signal
import threading
from pathlib import Path
from unittest.mock import patch

from front.agents.worker import run
from front.agents.adapter import InternalClient

original_operation = InternalClient.operation


def operation(self, name, payload):
    try:
        return original_operation(self, name, payload)
    except Exception as error:
        print(json.dumps({'operation': name, 'error': type(error).__name__, 'code': str(error)[:120]}), flush=True)
        raise

stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
config = json.loads(Path('/bench/config.json').read_text())
with patch('front.agents.worker.create_clean', side_effect=AssertionError('benchmark_sandbox_denied')), \
        patch.object(InternalClient, 'operation', operation):
    run(config, stop_event=stop)
