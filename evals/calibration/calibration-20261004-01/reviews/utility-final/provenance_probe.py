"""Verify downloaded-source bytes and the historical bank without interpreting them."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
ROOT = HERE.parents[4]
CORPUS = CAMPAIGN / "corpus"
downloads = json.loads((CORPUS / "sources/downloads.json").read_text(encoding="utf-8"))
records = []
for item in downloads:
    path = CORPUS / "sources" / item["source"] / item["file"]
    value = path.read_bytes()
    observed = hashlib.sha256(value).hexdigest()
    records.append({"path": path.relative_to(ROOT).as_posix(), "revision": item["revision"],
                    "sha256": observed, "bytes": len(value),
                    "ok": observed == item["sha256"] and len(value) == item["bytes"]})
manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
historical = manifest["historical_regression"]
observed = hashlib.sha256((ROOT / historical["file"]).read_bytes()).hexdigest()
result = {"kind": "source_and_historical_byte_integrity_no_product_execution", "downloads_n": len(records),
          "downloads": records, "historical_sha256": observed, "historical_unchanged": observed == historical["sha256"],
          "network_calls": 0, "reserved_contents_opened": False}
result["ok"] = all(r["ok"] for r in records) and result["historical_unchanged"]
(HERE / "provenance-probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "downloads"}))
raise SystemExit(0 if result["ok"] else 1)
