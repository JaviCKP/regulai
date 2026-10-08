"""Synthetic fault injection: first real E2B render cannot find its converter.

The second native tool call runs the unchanged converter. Nothing in the product
accepts this flag, and this file is not installed in the document image.
"""
import json
from pathlib import Path
from unittest.mock import patch

from langchain_e2b import E2BSandbox
from front.agents.worker import run

original = E2BSandbox.execute
injected = False


def execute(self, command, *args, **kwargs):
    global injected
    if not injected and '/skills/document_program.py render' in command:
        injected = True
        command = command.replace('python -I ', 'env PATH=/converter-unavailable /usr/local/bin/python -I ', 1)
    return original(self, command, *args, **kwargs)


with patch.object(E2BSandbox, 'execute', execute):
    print(json.dumps(run(json.loads(Path('/run/task50/config.json').read_text()), once=True)), flush=True)
assert injected, 'The converter fault was not exercised'
