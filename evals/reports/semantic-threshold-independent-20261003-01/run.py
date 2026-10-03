"""Launch only independent probes using an explicit empty-credential environment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SANDBOX = ROOT / ".claude" / "semantic-threshold-independent"
python = Path(sys.executable).resolve()
env = {"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows",
    "PATH": str(python.parent) + r";C:\Users\javi\.local\bin;C:\Windows\System32",
    "TEMP": str(SANDBOX / "tmp"), "TMP": str(SANDBOX / "tmp"),
    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "DJANGO_SETTINGS_MODULE": "regulai.test_settings",
    "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "REGULAI_EVAL_GENERATOR_KEY": "", "REGULAI_EVAL_JEV_KEY": ""}
argv = ["rtk", "proxy", str(python), "-B", str(HERE / "driver.py")]
started = time.monotonic()
result = subprocess.run(argv, cwd=SANDBOX, env=env, capture_output=True, encoding="utf-8")
log = result.stdout + result.stderr
(HERE / "independent.log").write_text(log, encoding="utf-8")
record = {"command": "rtk proxy .venv\\Scripts\\python.exe -B evals\\reports\\semantic-threshold-independent-20261003-01\\run.py",
    "child_command": argv, "exit_code": result.returncode, "seconds": round(time.monotonic() - started, 3),
    "log_sha256": hashlib.sha256((HERE / "independent.log").read_bytes()).hexdigest(),
    "constructed_environment_no_caller_read": True, "database": "memory only"}
(HERE / "run-result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
print(log[-7000:])
raise SystemExit(result.returncode)
