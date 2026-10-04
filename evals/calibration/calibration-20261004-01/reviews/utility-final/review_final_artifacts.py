"""Verify final local comparison and published reconciliation artifacts, without rerunning product."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CAMPAIGN = HERE.parents[1]
HASHES = {}
REV = "b3fea6a63761c06ef66695fee26377d23786c347"


def raw(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT)
    assert "superseded" not in path.parts and path.name != "build_calibration_corpus.py"
    data = path.read_bytes()
    HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()
    return data


def read(path):
    return json.loads(raw(path))


def rows(path):
    return [json.loads(line) for line in raw(path).splitlines()]


release = read(CAMPAIGN / "corpus/reserved-release.json")
selection = read(CAMPAIGN / "final_selection.json")
assert release["candidate_commit"] == selection["candidate_commit"] == REV
assert release["final_selection_sha256"] == hashlib.sha256(raw(CAMPAIGN / "final_selection.json")).hexdigest()
comparison_path = CAMPAIGN / "evaluation/reserved-comparison-01.json"
comparison = read(comparison_path)
assert hashlib.sha256(raw(comparison_path)).hexdigest() == "51a6bb30b08deb83d354016cf8891bda89f87030999b4e95331e03e4e2d11bf9"
for path, expected in comparison["source_sha256"].items():
    assert hashlib.sha256(raw(ROOT / path)).hexdigest() == expected

corpus = rows(CAMPAIGN / "corpus/reserved/cases.jsonl")
expected_ids = {c["id"] for c in corpus}
plans, summaries, local_rows, http_rows = {}, {}, {}, {}
run_results = {}
for variant in ("base", "candidate"):
    folder = CAMPAIGN / "evaluation" / ("reserved-" + variant + "-01")
    artifact_hashes = read(folder / "artifact-hashes.json")
    for path, expected in artifact_hashes.items():
        assert hashlib.sha256(raw(folder / path)).hexdigest() == expected
    plan, summary = read(folder / "plan.json"), read(folder / "summary.json")
    plans[variant], summaries[variant] = plan, summary
    assert datetime.fromisoformat(plan["started_at"]) > datetime.fromisoformat(release["custodian_released_at"])
    assert plan["holdout_release_sha256"] == hashlib.sha256(raw(CAMPAIGN / "corpus/reserved-release.json")).hexdigest()
    for path, expected in plan["harness_sha256"].items():
        assert hashlib.sha256(raw(Path(path))).hexdigest() == expected
    for path, expected in plan["source_sha256"].items():
        data = raw(ROOT / path)
        assert hashlib.sha256(data).hexdigest() == expected
        frozen = subprocess.run(["rtk", "proxy", "git", "show", REV + ":" + path],
                                cwd=ROOT, capture_output=True, check=True).stdout
        assert data.replace(b"\r\n", b"\n") == frozen.replace(b"\r\n", b"\n"), path
    local = rows(folder / "local-results.jsonl")
    http = rows(folder / "http-results.jsonl")
    local_rows[variant], http_rows[variant] = local, http
    assert len(local) == len(expected_ids) == 571 and {r["case_id"] for r in local} == expected_ids
    assert all(r["semantic_quality_measured"] is False for r in local)
    assert len(http) == 120 and sum(r["control_passed"] for r in http) == 114
    expected_cells = {(cid, endpoint, profile) for cid in plan["selected_http_cases"]
                      for endpoint in plan["http_endpoints"] for profile in plan["http_profiles"]}
    assert {(r["case_id"], r["endpoint"], r["provider_profile"]) for r in http} == expected_cells
    assert len(expected_cells) == len(http)
    assert len(plan["selected_http_cases"]) == release["scope"]["http_cases_per_comparator"] == 20
    assert len({r["family_id"] for r in local}) == summary["families_n"] == 372
    assert summary["changed_sources_during_execution"] == []
    assert not any(summary["network_attempts"].values())
    assert Decimal(summary["real_api_cost_usd"]) == 0 and summary["exit_code"] == 0
    annotations = [r for r in local if r["privacy"]["passed"] is not None]
    passed = sum(r["privacy"]["passed"] for r in annotations)
    assert (len(annotations), passed) == (summary["annotated_cases_n"], summary["local_annotation_passed"]) == (290, 239)
    assert len(local) - len(annotations) == summary["unannotated_cases_n"] == 281
    counts = {}
    for kind in ("redactions", "preservations"):
        items = [v for r in local for v in r["privacy"][kind]]
        assert all(v["present_in_original"] for v in items)
        for item in items:
            assert item["passed"] == (not item["retained"] if kind == "redactions" else item["retained"])
        counts[kind] = dict(n=len(items), passed=sum(v["passed"] for v in items))
    failed = [dict(case_id=r["case_id"], endpoint=r["endpoint"], provider_profile=r["provider_profile"],
                   observed_control=r["observed_control"]) for r in http if not r["control_passed"]]
    assert {r["case_id"] for r in failed} == {"I0965", "I0944"}
    assert all(r["provider_profile"] == "neutral" and r["observed_control"]["error_type"] == "verification_failed" for r in failed)
    run_results[variant] = dict(counts=counts, annotated_cases=290, annotation_passed=239,
        unannotated_cases=281, http_cases=20, http_runs=len(http), http_passed=114,
        http_categories=dict(Counter(c["category"] for c in corpus if c["id"] in plan["selected_http_cases"])),
        http_families=len({r["family_id"] for r in http}), failed_http=failed,
        network_attempts=sum(summary["network_attempts"].values()), detector=plan["detector"]["detector_version"])

assert plans["base"]["selected_http_cases"] == plans["candidate"]["selected_http_cases"]
assert plans["base"]["detector"]["detector_version"] == "regulai-local-v2"
assert plans["candidate"]["detector"]["detector_version"] == "regulai-local-v5"
left, right = [{r["case_id"]: r for r in local_rows[v]} for v in ("base", "candidate")]
assert all(left[cid]["privacy"] == right[cid]["privacy"] for cid in expected_ids)
assert run_results["base"]["failed_http"] == run_results["candidate"]["failed_http"]
for kind, n, passed in (("redactions", 323, 248), ("preservations", 243, 225)):
    assert run_results["base"]["counts"][kind] == run_results["candidate"]["counts"][kind] == dict(n=n, passed=passed)
    assert comparison["summary"][0][kind] == dict(n=n, base_evaluable=n, candidate_evaluable=n,
        base_passed=passed, candidate_passed=passed, gained=0, lost=0)

economics = read(CAMPAIGN / "economics/final-reconciliation-01/summary.json")
for key in ("known_cost_usd", "provider_reported_usd", "tariff_estimated_usd", "budget_exposure_usd", "uncertain_reservations_usd"):
    assert Decimal(economics["historical"][key]) + Decimal(economics["campaign_increment"][key]) == Decimal(economics["total"][key])
assert Decimal(economics["cap_usd"]) - Decimal(economics["total"]["budget_exposure_usd"]) == Decimal(economics["remaining_usd"])
captures_n = 0
totals = Counter()
request_marker_findings = []
capture_hash_checks = 0
for batch in ("baseline-smoke-02", "candidate-smoke-01", "r4-smoke-01"):
    metrics = read(CAMPAIGN / "batches" / batch / "metrics-01.json")
    wire = read(CAMPAIGN / "batches" / batch / "live-run-01/synthetic-payloads.json")
    batch_cases = rows(CAMPAIGN / "batches" / batch / "cases.jsonl")
    oracles = read(CAMPAIGN / "batches" / batch / "oracles.json")
    markers = [c["id"] for c in batch_cases] + ["expected_answer", "expected_redactions", "case_sha256", "family_id", "reference_split"]
    markers += [span["value"] for oracle in oracles.values() for span in oracle.get("expected_redactions", [])]
    for event in wire:
        for key, expected in (("body_utf8", "body_sha256"), ("response_body_utf8", "response_sha256")):
            assert isinstance(event[key], str)
            assert hashlib.sha256(event[key].encode("utf-8")).hexdigest() == event[expected]
            capture_hash_checks += 1
        for marker in markers:
            if marker in event["body_utf8"]:
                request_marker_findings.append(dict(batch=batch, sequence=event["sequence"], marker=marker))
    captures_n += len(wire)
    for metric in metrics["cases"]:
        for key in ("provider_reported_usd", "tariff_estimated_usd", "exposure_usd", "uncertain_reserved_usd"):
            totals[key] += Decimal(metric[key])
assert captures_n == economics["campaign_external_calls_n"] == 49
assert capture_hash_checks == 98 and request_marker_findings == []
for metric, key in (("provider_reported_usd", "provider_reported_usd"), ("tariff_estimated_usd", "tariff_estimated_usd"),
                    ("exposure_usd", "budget_exposure_usd"), ("uncertain_reserved_usd", "uncertain_reservations_usd")):
    assert totals[metric] == Decimal(economics["campaign_increment"][key])

result = dict(kind="independent_agent_final_artifact_review", fixed_commit=REV, release_before_runs=True,
    corpus_ids_complete=True, source_matches_pinned_git_after_only_line_ending_normalization=True,
    artifact_hashes_match=True, identical_http_cells=True, runs=run_results,
    local_interpretation="Tie on all held-out annotated privacy outcomes; 281 unannotated cases are not successes. Simulated HTTP controls do not measure provider semantic quality.",
    selection="Privacy-v5 with legacy None policy is provisional; no general semantic winner. R4 .40 is not adopted.",
    mandatory_real_stratified_confirmation="Not executed: new paid calls stopped after uncertain Jev classification. Local reserved comparison is separate evidence, not a substitute for this objective.",
    economics_artifact_arithmetic_checked=True, campaign_captured_external_http=49,
    request_response_body_hash_checks=capture_hash_checks, request_marker_findings=request_marker_findings,
    total_budget_exposure_usd=economics["total"]["budget_exposure_usd"],
    total_uncertain_reservations_usd=economics["total"]["uncertain_reservations_usd"],
    economics_scope="Cross-check of JSON arithmetic and captures; reviewer did not open ledger or user database.",
    inputs_sha256=HASHES, product_calls=0, new_provider_calls=0, database_opened=False,
    post_holdout_tuning=False, oracle_changes=False, human_review=False)
output = HERE / "final-artifacts-review-01.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in ("inputs_sha256", "runs")}, ensure_ascii=True))
print(json.dumps(dict(runs=run_results), ensure_ascii=True))
print("OUTPUT_SHA256", hashlib.sha256(output.read_bytes()).hexdigest())
