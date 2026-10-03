"""Seal this review's explicit public files; do not alter earlier review packages."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


evidence = json.loads((HERE / "analysis-evidence.json").read_text(encoding="utf-8"))
result = json.loads((HERE / "run-result.json").read_text(encoding="utf-8"))
assert result["exit_code"] == 0
assert evidence["analyzer_sha256"] == digest(HERE / "analyze.py")
root = HERE.parent.parent
assert all(digest(root / row["path"]) == row["sha256"] for row in evidence["public_inputs"])
assert all(digest(root / path) == row["observed_runtime_sha256"]
           for path, row in evidence["source_manifest_relations"].items())
files = [p for p in HERE.rglob("*") if p.is_file() and p.name not in {"package-files.json", "seal.json"}]
listing = [{"path": p.relative_to(HERE).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
           for p in sorted(files)]
(HERE / "package-files.json").write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
seal = {"source_commit": evidence["source_commit"], "review_type": "Independent read-only live response analysis",
        "main_command": "rtk proxy .venv\\Scripts\\python.exe -B .claude\\adversarial-live-response-review\\analyze.py",
        "main_command_exit_code": 0, "classification_replays": 12, "verification_replays": 4,
        "public_input_files": len(evidence["public_inputs"]), "source_files": len(evidence["source_commands"]),
        "public_files": len(listing), "evidence_sha256": digest(HERE / "analysis-evidence.json"),
        "analysis_sha256": digest(HERE / "Analysis.md"), "package_files_sha256": digest(HERE / "package-files.json"),
        "product_calls_by_reviewer": 0, "persistent_ledger_opened": False,
        "human_review_created": False, "earlier_review_package_modified": False}
(HERE / "seal.json").write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
print(json.dumps({**seal, "seal_sha256": digest(HERE / "seal.json")}, ensure_ascii=True))
