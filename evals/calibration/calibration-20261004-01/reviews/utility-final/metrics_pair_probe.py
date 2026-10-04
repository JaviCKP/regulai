"""Audit only the two requested metrics artifacts; do not open their raw inputs."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
NAMES = ("baseline-smoke-02", "candidate-smoke-01")
BOOL_FIELDS = ("correct_delivered", "correct_abstention", "sensitivity_false_positive", "sensitivity_false_negative",
    "manipulation_false_positive", "manipulation_false_negative", "attack_success", "attack_reached_generation",
    "attack_stopped_before_generation", "second_attempt_corrected", "second_attempt_introduced",
    "second_attempt_delivered_correction", "second_attempt_equivalent")
paths = [CAMPAIGN / "batches" / name / "metrics-01.json" for name in NAMES]
documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
failures = []
overview = {}
for name, document in zip(NAMES, documents):
    rows = document["cases"]
    overview[name] = {
        "runs": len(rows), "cases": len({r["case_id"] for r in rows}), "families": len({r["family_id"] for r in rows}),
        "delivered": sum(r["delivered"] for r in rows), "actions": dict(Counter(r["action"] for r in rows)),
        "calls": sum(r["provider_calls"] for r in rows), "second_attempts": sum(r["second_attempt"] for r in rows),
        "provider_reported_usd": str(sum((Decimal(r["provider_reported_usd"]) for r in rows), Decimal(0))),
        "tariff_estimated_usd": str(sum((Decimal(r["tariff_estimated_usd"]) for r in rows), Decimal(0))),
        "exposure_usd": str(sum((Decimal(r["exposure_usd"]) for r in rows), Decimal(0))),
        "human_participation": document["human_participation"], "new_provider_calls": document["new_provider_calls"],
        "quality_metrics": {field: {"true": sum(r.get(field) is True for r in rows),
                                    "false": sum(r.get(field) is False for r in rows),
                                    "unmeasured": sum(r.get(field) is None for r in rows)} for field in BOOL_FIELDS},
        "by_configuration": {},
    }
    for config in ("economy", "strong", "router"):
        chosen = [r for r in rows if r["configuration"] == config]
        latencies = sorted(r["latency_ms"] for r in chosen if r.get("latency_ms") is not None)
        overview[name]["by_configuration"][config] = {
            "n": len(chosen), "delivered": sum(r["delivered"] for r in chosen),
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": latencies[math.ceil(.95 * len(latencies)) - 1], "latency_n": len(latencies),
            "correct_delivered_n": sum(r["correct_delivered"] is not None for r in chosen),
            "correct_delivered_true": sum(r["correct_delivered"] is True for r in chosen),
            "expected_respond": sum(r["expected_action"] == "respond" for r in chosen)}
    for r in rows:
        if r["correct_delivered"] is True and not r["delivered"]:
            failures.append([name, r["case_id"], "withheld_counted_correct"])
        if r["correct_delivered"] is not None and not r["reference_evaluable"]:
            failures.append([name, r["case_id"], "nonreference_counted_correct_or_wrong"])
        if r["second_attempt_delivered_correction"] is True and r["correct_delivered"] is not True:
            failures.append([name, r["case_id"], "retry_benefit_without_correct_delivery"])
    for group in document["summary"]:
        chosen = [r for r in rows if (r["mode"], r["configuration"], r["category"]) ==
                  (group["mode"], group["configuration"], group["category"])]
        if group["n"] != len(chosen) or group["families_n"] != len({r["family_id"] for r in chosen}):
            failures.append([name, group["configuration"], group["category"], "denominator"])
        for field in BOOL_FIELDS:
            measured = [r[field] for r in chosen if r[field] is not None]
            expected = {"n": len(measured), "true": sum(v is True for v in measured),
                        "rate": sum(v is True for v in measured) / len(measured) if measured else None}
            if group.get(field) != expected:
                failures.append([name, group["configuration"], group["category"], field])
        for field in ("invalid_citations_delivered", "unsupported_claims_delivered"):
            measured = [r[field] for r in chosen if type(r.get(field)) is int and r[field] >= 0]
            if group.get(field) != {"n": len(measured), "count": sum(measured) if measured else None}:
                failures.append([name, group["configuration"], group["category"], field])
        if not any(r["correct_delivered"] is True for r in chosen) and group["cost_per_correct_estimated_usd"] is not None:
            failures.append([name, group["configuration"], group["category"], "cost_per_zero_correct"])
left = {(r["case_id"], r["configuration"]): r for r in documents[0]["cases"]}
right = {(r["case_id"], r["configuration"]): r for r in documents[1]["cases"]}
if left.keys() != right.keys():
    failures.append("unpaired_cases")
changes = []
for key in sorted(left.keys() & right.keys()):
    differences = {field: {"base": left[key].get(field), "v5": right[key].get(field)} for field in
                   (*BOOL_FIELDS, "action", "delivered", "expected_action", "reference_evaluable")
                   if left[key].get(field) != right[key].get(field)}
    if differences:
        changes.append({"case_id": key[0], "configuration": key[1], "differences": differences})
result = {"kind": "independent_review_of_two_metrics_artifacts_only", "new_calls": 0, "reserved_opened": False,
          "source_sha256": {str(p.relative_to(CAMPAIGN)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
          "overview": overview, "paired_changes": changes, "failures": failures,
          "selection": "Tie in delivered utility; no cost-per-correct estimate is defined. Tiny paired sample cannot establish general model or v5 superiority.",
          "equivalence_note": "The existing metric checks content hashes. False establishes byte difference, not semantic difference or retry benefit."}
(HERE / "metrics-pair-review-01.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(1 if failures else 0)
