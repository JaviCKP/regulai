import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
evidence = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
result = json.loads((HERE / "run-result.json").read_text(encoding="utf-8"))
assert result["exit_code"] == 0 and evidence["analyzer_sha256"] == sha(HERE / "analyze.py")
assert all(sha(ROOT / item["path"]) == item["sha256"] for item in evidence["public_inputs"])
files = sorted(p for p in HERE.rglob("*") if p.is_file() and p.name not in {"package-files.json", "seal.json"})
listing = [{"path": p.relative_to(HERE).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]
(HERE / "package-files.json").write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
seal = {"source_commit": evidence["source_commit"], "manifest_sha256": evidence["manifest_sha256"],
    "command": result["command"], "exit_code": result["exit_code"], "reviewer_product_calls": 0,
    "open_findings_on_reviewed_source": [{"priority": "P2", "path": "regulai/front/chat_service.py", "line": 789,
        "title": "Float subtraction rejects score exactly at the nominal acceptance boundary",
        "observed_case": "DOC-01/strong", "historical_result_unchanged": True}],
    "public_files": len(files), "evidence_sha256": sha(HERE / "evidence.json"),
    "analysis_sha256": sha(HERE / "Analysis.md"), "package_files_sha256": sha(HERE / "package-files.json")}
(HERE / "seal.json").write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
print(json.dumps({**seal, "seal_sha256": sha(HERE / "seal.json")}))
