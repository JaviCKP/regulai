"""Export immutable public source into an owned review sandbox."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SANDBOX = ROOT / ".claude" / "semantic-threshold-independent"
BASE = "9e1ae5e58981c6ce0d45c236032a17ad6dcd60db"
FIXED = "1af809fd209c4260d5314ff55fa090147515b8d0"
SANDBOX.mkdir(parents=True, exist_ok=True)
(SANDBOX / "tmp").mkdir(exist_ok=True)
commands = []


def git(*args):
    argv = ["rtk", "proxy", "git", *args]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=True)
    commands.append({"argv": argv, "exit_code": result.returncode,
                     "stdout_sha256": hashlib.sha256(result.stdout).hexdigest()})
    return result.stdout


diff = git("diff", BASE + "..." + FIXED)
assert diff
assert set(git("diff", "--name-only", BASE + "..." + FIXED).decode().splitlines()) == {
    "regulai/front/chat_service.py", "regulai/front/classification.py", "regulai/front/test_semantic_threshold_boundary.py"}
(HERE / "reviewed.diff").write_bytes(diff)
(HERE / "commits.txt").write_bytes(git("log", BASE + ".." + FIXED, "--oneline"))
paths = git("ls-tree", "-r", "--name-only", FIXED, "regulai/front", "regulai/api", "regulai/regulai").decode().splitlines()
assert all(Path(p).suffix in {".py", ".html", ".js", ".sh"} and Path(p).name != "local_settings.py" for p in paths)
archive = SANDBOX / "source.zip"
git("archive", "--format=zip", "--output=" + str(archive), FIXED, "regulai/front", "regulai/api", "regulai/regulai")
source = SANDBOX / "source"
with zipfile.ZipFile(archive) as zipped:
    assert all((source / name).resolve().is_relative_to(source.resolve()) for name in zipped.namelist())
    zipped.extractall(source)
(source / "regulai/regulai/local_settings.py").write_bytes(b"")
(source / "regulai/static").mkdir(exist_ok=True)
for name in ("chat_service.py", "classification.py"):
    (HERE / ("base-" + name)).write_bytes(git("show", BASE + ":regulai/front/" + name))
    (HERE / ("fixed-" + name)).write_bytes(git("show", FIXED + ":regulai/front/" + name))
inputs = []
for index in (1, 2):
    path = ROOT / f"evals/reports/adversarial-real-20261003-0{index}/live-run-01/results.jsonl"
    raw = path.read_bytes()
    target = HERE / f"historical-run-{index}.jsonl"
    target.write_bytes(raw)
    inputs.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
author = ROOT / "evals/reports/semantic-threshold-boundary-20261003-01"
author_counts = {}
for phase in ("red", "green", "focused"):
    record = json.loads((author / (phase + ".json")).read_text(encoding="utf-8"))
    log = (author / (phase + ".stderr.log")).read_bytes()
    text = log.decode("utf-8")
    author_counts[phase] = {"exit_code": record["exit_code"], "tests": int(re.search(r"Ran (\d+) tests", text)[1]),
        "failures": record.get("failures"), "stderr_sha256": hashlib.sha256(log).hexdigest()}
record = {"base_commit": BASE, "reviewed_commit": FIXED, "commands": commands,
    "snapshot_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "snapshot_file_count": len(paths),
    "historical_inputs": inputs, "author_counts_read_only_not_independent_runs": author_counts}
(HERE / "preparation.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"result": "prepared", "reviewed_commit": FIXED, "author_counts": author_counts}))
