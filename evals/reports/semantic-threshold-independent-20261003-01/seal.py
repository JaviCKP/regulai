import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda name: json.loads((HERE / name).read_text(encoding="utf-8"))
prep, run, isolation, observations = map(load, ("preparation.json", "run-result.json", "isolation.json", "observations.json"))
assert run["exit_code"] == 0
assert run["log_sha256"] == sha(HERE / "independent.log")
assert re.search(r"Ran 3 tests.*?\n\nOK", (HERE / "independent.log").read_text(encoding="utf-8"), re.S)
assert isolation["network_attempts"] == 0
assert all(p == ":memory:" or p.startswith("file:") and "mode=memory" in p for p in isolation["database_connections"])
assert all(sha(ROOT / item["path"]) == item["sha256"] for item in prep["historical_inputs"])
assert len(observations["http"]) == 6 and len(observations["adjacent"]) == 9
evidence = {"base_commit": prep["base_commit"], "reviewed_commit": prep["reviewed_commit"],
    "comparison": "git diff 9e1ae5e58981c6ce0d45c236032a17ad6dcd60db...1af809fd209c4260d5314ff55fa090147515b8d0",
    "open_spec_findings": 0, "open_standards_findings": 0, "recommendation": "Accept scoped numeric boundary fix",
    "commands": prep["commands"], "independent_run": run, "independent_tests": 3,
    "independent_coverage": {"http_requests": 6, "http_entries": 3, "adjacent_semantic_comparisons": 9,
        "historical_classifications_unchanged": 24, "historical_verifications": 11,
        "sole_changed_verification": "DOC-01/strong: false to true, replay only"},
    "isolation": isolation, "snapshot_zip_sha256": prep["snapshot_zip_sha256"],
    "historical_inputs": prep["historical_inputs"],
    "author_evidence_not_fresh_independent_tests": prep["author_counts_read_only_not_independent_runs"],
    "limits": ["No new live runs or human adjudication", "Historical results remain unchanged",
               "No original post-mask judge state recovered", "General gates run separately by orchestrator"]}
(HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
files = sorted(p for p in HERE.iterdir() if p.is_file() and p.name not in {"package-files.json", "seal.json"})
listing = [{"path": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]
(HERE / "package-files.json").write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
seal = {"reviewed_commit": prep["reviewed_commit"], "public_files": len(files), "evidence_sha256": sha(HERE / "evidence.json"),
    "package_files_sha256": sha(HERE / "package-files.json"), "spec_review_sha256": sha(HERE / "Spec-review.md"),
    "standards_review_sha256": sha(HERE / "Standards-review.md"), "own_command_exit_code": 0, "open_findings": 0}
(HERE / "seal.json").write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
print(json.dumps({**seal, "seal_sha256": sha(HERE / "seal.json")}))
