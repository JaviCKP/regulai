"""Bootstrap Django under memory-only SQLite and hard network guards."""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parents[2] / ".claude" / "semantic-threshold-independent"
sys.path[:0] = [str(HERE), str(SANDBOX / "source/regulai")]
sys.modules["regulai.local_settings"] = ModuleType("regulai.local_settings")
tempfile.tempdir = str(SANDBOX / "tmp")
original_connect = sqlite3.connect
database_connections = []
network_attempts = 0


def connect(path, *args, **kwargs):
    name = str(path)
    assert name == ":memory:" or name.startswith("file:") and "mode=memory" in name, name
    database_connections.append(name)
    return original_connect(path, *args, **kwargs)


def denied(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise AssertionError("Independent review forbids network")


with ExitStack() as guards:
    guards.enter_context(patch("sqlite3.connect", side_effect=connect))
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "socket.getaddrinfo",
                 "requests.sessions.Session.request", "httpx.Client.send"):
        guards.enter_context(patch(name, side_effect=denied))
    import django
    django.setup()
    from django.conf import settings
    assert settings.DATABASES["default"]["NAME"] == ":memory:"
    assert vars(sys.modules["regulai.local_settings"]).keys() <= {"__name__", "__doc__", "__package__", "__loader__", "__spec__"}
    from django.core.management import call_command
    try:
        call_command("test", "independent_tests", verbosity=2, interactive=False)
    finally:
        (HERE / "isolation.json").write_text(json.dumps({"network_attempts": network_attempts,
            "database_connections": database_connections, "local_settings_empty_before_django": True,
            "product_calls": 0, "historical_artifacts_modified": False}, indent=2) + "\n", encoding="utf-8")
