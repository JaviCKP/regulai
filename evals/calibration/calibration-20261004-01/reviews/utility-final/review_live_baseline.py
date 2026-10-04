"""Read only the completed public development live batch; never call providers."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
PACK = CAMPAIGN / "batches/baseline-smoke-02"
RUN = PACK / "live-run-01"
paths = [PACK / "cases.jsonl", PACK / "oracles.json", RUN / "results.jsonl", RUN / "synthetic-payloads.json"]
oracles = json.loads(paths[1].read_text(encoding="utf-8"))
cases = {c["id"]: c for c in map(json.loads, paths[0].read_text(encoding="utf-8").splitlines())}
rows = list(map(json.loads, paths[2].read_text(encoding="utf-8").splitlines()))
wire = json.loads(paths[3].read_text(encoding="utf-8"))
case_results = []
for row in rows:
    cid = row["case_id"]
    generations = row.get("generation_responses", [])
    calls = row.get("receipt", {}).get("calls", [])
    classifiers = [c.get("signals", {}) for c in calls if c.get("purpose") == "classification"]
    case_results.append({"case_id": cid, "configuration": row["configuration"],
        "expected_action": oracles[cid]["expected_action"], "oracle_kind": oracles[cid]["oracle"]["kind"],
        "execution_state": row["execution_state"], "error_type": row["error_type"], "delivered": row["delivered"],
        "answer": row.get("answer"), "generation_calls": row["generation_calls"],
        "generation_responses": [{"content": g.get("content"), "sha256": g.get("content_sha256")} for g in generations],
        "identical_second_response": len(generations) == 2 and generations[0].get("content_sha256") == generations[1].get("content_sha256"),
        "classification_manipulation": [s.get("manipulation") for s in classifiers],
        "verification": row.get("verification")})
leaks = []
body_records_checked = 0
for index, event in enumerate(wire):
    body = event["body_utf8"]
    assert isinstance(body, str), "A missing capture cannot count as a clean request"
    body_records_checked += 1
    for marker in (*cases, "expected_answer", "expected_redactions", "case_sha256", "family_id", "reference_split"):
        if marker in body:
            leaks.append({"event": index, "marker": marker})
result = {"kind": "agent_review_of_captured_public_development_batch", "new_calls": 0, "human_review": False,
    "n": len(rows), "distinct_cases": len({r["case_id"] for r in rows}),
    "distinct_families": len({oracles[r["case_id"]]["family_id"] for r in rows}),
    "delivered": sum(r["delivered"] for r in rows), "states": dict(Counter(r["execution_state"] for r in rows)),
    "wire_by_purpose": dict(Counter(e["purpose"] for e in wire)),
    "request_bodies_checked": body_records_checked,
    "benchmark_marker_leaks_in_captured_request_bodies": leaks, "cases": case_results,
    "source_sha256": {str(p.relative_to(CAMPAIGN)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    "limitations": ["Four families, twelve configuration runs, no independent replicate claim.",
        "No model-judged rejection is adjudicated as correct merely from its score.",
        "Unexercised generation under an early block does not show generator injection resistance."]}
(HERE / "live-baseline-review-02.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k not in ("cases", "source_sha256")}, ensure_ascii=False))
