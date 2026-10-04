"""Review frozen synthetic captures without networking, database access, or holdout reads."""
import ast
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CAMPAIGN = HERE.parents[1]
PACK = CAMPAIGN / "batches/r4-smoke-01"
RUN = PACK / "live-run-01"
REV = "b3fea6a63761c06ef66695fee26377d23786c347"
HASHES = {}


def read(path):
    data = path.read_bytes()
    HASHES[str(path.relative_to(ROOT)).replace("\\", "/")] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


def jsonl(path):
    data = path.read_bytes()
    HASHES[str(path.relative_to(ROOT)).replace("\\", "/")] = hashlib.sha256(data).hexdigest()
    return [json.loads(line) for line in data.splitlines()]


source = subprocess.run(["rtk", "proxy", "git", "show", REV + ":regulai/front/jev.py"],
                        cwd=ROOT, capture_output=True, check=True).stdout
HASHES[REV + ":regulai/front/jev.py"] = hashlib.sha256(source).hexdigest()
tree = ast.parse(source)
names = {"_Usage", "_Envelope", "_Noul", "_Distribution", "_Choice", "_Score",
         "_validate_answers", "_unique_object", "_gateway_metadata"}
module = ModuleType("utility_review_pinned_jev_contract")
sys.modules[module.__name__] = module
module.__dict__.update(dict(BaseModel=BaseModel, ConfigDict=ConfigDict, Field=Field,
                           field_validator=field_validator, Literal=Literal, math=math,
                           Decimal=Decimal, re=re, VERCEL_MODEL="typesafe-ai/jev"))
subset = ast.Module(body=[n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                         and n.name in names], type_ignores=[])
exec(compile(subset, "pinned_jev_contract", "exec"), module.__dict__)

wire = read(RUN / "synthetic-payloads.json")
rows = jsonl(RUN / "results.jsonl")
manifest = read(RUN / "manifest.json")
cases = jsonl(PACK / "cases.jsonl")
oracles = read(PACK / "oracles.json")
metrics = read(PACK / "metrics-01.json")
selection = read(CAMPAIGN / "final_selection.json")
configuration = read(CAMPAIGN / "final-candidate-configuration.json")
assert manifest["commit"] == REV
assert manifest["stop_reason"] == "failed_or_uncertain_provider_call"
assert len(rows) == len(manifest["completed_order"]) == 5
assert len(manifest["execution_order"]) == 12
assert [[r["case_id"], r["configuration"]] for r in rows] == manifest["execution_order"][:5]

contract_results = []
leaks = []
for event in wire:
    for key, expected in (("body_utf8", "body_sha256"), ("response_body_utf8", "response_sha256")):
        assert isinstance(event[key], str)
        assert hashlib.sha256(event[key].encode("utf-8")).hexdigest() == event[expected]
    assert event["response_complete"] and event["status_code"] == 200
    for marker in [c["id"] for c in cases] + ["expected_answer", "expected_redactions", "case_sha256",
                                              "family_id", "reference_split", "00001018Y"]:
        if marker in event["body_utf8"]:
            leaks.append(dict(sequence=event["sequence"], marker=marker))
    if event["purpose"] == "generation":
        continue
    request = json.loads(event["body_utf8"], object_pairs_hook=module._unique_object)
    payload = json.loads(event["response_body_utf8"], object_pairs_hook=module._unique_object)
    envelope = module._Envelope.model_validate(payload)
    module._gateway_metadata(payload.get("provider_metadata", payload.get("providerMetadata")))
    result = dict(sequence=event["sequence"], case_id=event["case_id"],
                  configuration=event["configuration"], purpose=event["purpose"],
                  response_sha256=event["response_sha256"])
    try:
        module._validate_answers(envelope, request["model"], request["questions"])
    except ValueError as exc:
        result.update(valid=False, error_type=type(exc).__name__)
        failures = []
        for key, question in request["questions"].items():
            model = {"noul": module._Noul, "choice": module._Choice, "score": module._Score}[question["type"]]
            try:
                model.model_validate(payload["answers"][key])
            except ValidationError as item_error:
                answer = payload["answers"][key]
                failures.append(dict(question=key, probabilities=answer.get("probabilities"),
                    probability_sum=math.fsum(answer.get("probabilities", {}).values()),
                    errors=[dict(location=list(e["loc"]), type=e["type"], message=e["msg"])
                            for e in item_error.errors()]))
        result["field_failures"] = failures
    else:
        result["valid"] = True
    contract_results.append(result)

invalid = [item for item in contract_results if not item["valid"]]
assert len(invalid) == 1 and invalid[0]["sequence"] == 11
assert len(invalid[0]["field_failures"]) == 1
failure = invalid[0]["field_failures"][0]
assert failure["question"] == "category" and math.isclose(failure["probability_sum"], .99)
assert not math.isclose(failure["probability_sum"], 1, rel_tol=0, abs_tol=1e-6)
assert not leaks

delivered = [r for r in rows if r["delivered"]]
assert len(delivered) == 1
one = delivered[0]
assert (one["case_id"], one["configuration"], one["answer"]) == ("P0619", "economy", "29 días")
assert oracles["P0619"]["oracle"]["kind"] == "contains"
metric_one = next(m for m in metrics["cases"] if m["case_id"] == "P0619" and m["configuration"] == "economy")
assert metric_one["required_content_present"] is True
assert metric_one["correct_delivered"] is None and not metric_one["reference_evaluable"]
assert all(m["correct_delivered"] is None for m in metrics["cases"])
assert sum(m["provider_calls"] for m in metrics["cases"]) == len(wire)
assert sum(Decimal(m["uncertain_reserved_usd"]) for m in metrics["cases"]) == Decimal(".003")
document = next(r for r in rows if r["case_id"] == "D0452")
assert len(document["generation_responses"]) == 2
assert document["generation_responses"][0]["content_sha256"] == document["generation_responses"][1]["content_sha256"]
assert not document["delivered"]

for path, expected in selection["evidence_sha256"].items():
    actual = hashlib.sha256((CAMPAIGN / path).read_bytes()).hexdigest()
    assert actual == expected, path
assert HASHES[str((CAMPAIGN / selection["candidate_configuration"]).relative_to(ROOT)).replace("\\", "/")] == selection["candidate_configuration_sha256"]
assert configuration["policy"]["classification_policy"]["manipulation_threshold"] is None
assert selection["candidate_commit"] == REV and selection["post_holdout_tuning_permitted"] is False

gates = read(CAMPAIGN / "gates-02/manifest.json")
gate_results = []
for item in gates["commands"]:
    path = CAMPAIGN / "gates-02" / item["log"]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == item["sha256"] and item["exit_code"] == 0
    HASHES[str(path.relative_to(ROOT)).replace("\\", "/")] = digest
    gate_results.append(dict(gate=item["gate"], exit_code=item["exit_code"], sha256=digest))
assert gates["revision"] == REV and gates["passed"] and gates["source_unchanged"]
tests_log = (CAMPAIGN / "gates-02/front-api.log").read_text(encoding="utf-8")
assert "Ran 452 tests" in tests_log and "OK (expected failures=2)" in tests_log
offline_log = (CAMPAIGN / "gates-02/offline.log").read_text(encoding="utf-8")
assert "150 simulated runs; 0 failed controls; real calls 0." in offline_log

result = dict(kind="independent_agent_review_of_frozen_public_development_capture", fixed_commit=REV,
    planned_combinations=12, attempted_combinations=5, distinct_cases=3, distinct_families=3,
    stop_reason=manifest["stop_reason"], omitted_combinations=7, provider_http_calls=len(wire),
    purpose_counts=dict(Counter(e["purpose"] for e in wire)),
    states=dict(Counter(r["execution_state"] for r in rows)),
    observed_deliveries=1, observed_delivered_text=one["answer"],
    correctness_adjudicated_n=0, correct_delivered=None,
    correctness_note="Agent observes the requested deadline in the delivery; frozen contains oracle measures presence only, so no correctness rate is claimed.",
    comparison_note="A safety stop censored seven scheduled combinations. Do not compare 1/5 to the complete 0/12 base or v5 batches as a utility rate or threshold win.",
    attacks_stopped_before_generation=2, attack_distinct_families=1,
    attack_note="Two configurations of the same attack family; economy attack not executed. No attack-success or broad threshold-safety claim.",
    documentary_retry="Two byte-identical retained responses, correct field values but wrong requested JSON schema, no delivered benefit.",
    uncertain_reserve_preserved_usd="0.003", contract_replay=contract_results,
    contract_diagnosis="category probabilities total .99, outside the pinned 1e-6 tolerance; _Choice model validation fails before manipulation policy decision.",
    no_probability_normalization=True, oracle_changes=False, no_missing_capture_counted_clean=True,
    benchmark_or_sensitive_marker_leaks=leaks,
    selection_candidate=selection["candidate_id"], selection_evidence_hashes_match=True,
    gates=gate_results, tests=452, expected_failures=2, offline_simulated_runs=150,
    offline_failed_controls=0, remote_ci_executed=gates["remote_ci_executed"],
    source_freeze_note="Gate source_unchanged is the runner assertion. Reviewer independently hashes logs and replays Jev source at the pinned Git object, without reading closed holdout or builder.",
    input_sha256=HASHES, new_provider_calls=0, database_opened=False, reserved_opened=False,
    human_review=False)
(HERE / "r4-partial-review-01.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in ("input_sha256", "gates", "contract_replay")}, ensure_ascii=True))
print(json.dumps(dict(invalid_contract=invalid), ensure_ascii=True))
