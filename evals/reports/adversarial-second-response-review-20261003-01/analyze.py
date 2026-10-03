"""Offline artifact review of the second live run; no product or ledger execution."""
import ast
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = "128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2"
RUN = Path("evals/reports/adversarial-real-20261003-02/live-run-01")
BEFORE = Path("evals/reports/adversarial-real-20261003-01/live-run-01")
PACK = Path("evals/adversarial-live/community-additional-20261003")
EXPECTED_MANIFEST = "b4730105fd1f74bfbd3baf0d6757cd9bfd6484b1170b61517944ad721e058b30"
guard_attempts = {"network": 0, "database": 0}


def forbidden(kind):
    def fail(*args, **kwargs):
        guard_attempts[kind] += 1
        raise AssertionError(kind + " forbidden")
    return fail


socket.socket.connect = forbidden("network")
socket.create_connection = forbidden("network")
socket.getaddrinfo = forbidden("network")
sqlite3.connect = forbidden("database")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


inputs = []
public = [RUN / name for name in ("results.jsonl", "completed-cases.jsonl", "cases.executed.jsonl", "budget.json",
    "manifest.json", "summary.json", "human-review.pending.json", "rubric.md")]
public += [RUN.parent / "live-result.json", BEFORE / "budget.json", BEFORE / "manifest.json",
           PACK / "oracles.json", PACK / "manifest.json"]
for relative in public:
    raw = (ROOT / relative).read_bytes()
    dest = HERE / "inputs" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    inputs.append({"path": relative.as_posix(), "sha256": sha(raw), "bytes": len(raw)})


def load(relative):
    return json.loads((HERE / "inputs" / relative).read_text(encoding="utf-8"))


def rows(relative):
    return [json.loads(line) for line in (HERE / "inputs" / relative).read_text(encoding="utf-8").splitlines()]


manifest, old_manifest = load(RUN / "manifest.json"), load(BEFORE / "manifest.json")
assert sha((HERE / "inputs" / PACK / "manifest.json").read_bytes()) == EXPECTED_MANIFEST
assert manifest["manifest_sha256"] == EXPECTED_MANIFEST
assert manifest["source_sha256"] == manifest["source_sha256_observed"] == old_manifest["source_sha256"]
assert sha((HERE / "inputs" / PACK / "oracles.json").read_bytes()) == manifest["reference_label_sha256"]["oracles.json"]
data, cases, oracles = rows(RUN / "results.jsonl"), rows(RUN / "cases.executed.jsonl"), load(PACK / "oracles.json")
assert data == rows(RUN / "completed-cases.jsonl")
expected_ids = {"BENIGN-02", "PII-03", "DOC-01", "INJ-07"}
assert len(data) == 12 and {(r["case_id"], r["configuration"]) for r in data} == {
    (c, p) for c in expected_ids for p in ("economy", "strong", "router")}
assert {o["id"] for o in oracles} == {c["id"] for c in cases} == expected_ids
assert all(c["input"] == next(o["prompt"] for o in oracles if o["id"] == c["id"]) for c in cases)
assert all(r["human_review"] is None for r in data)
assert all(r["correct_answers"] is None and r["human_reviewed_n"] == 0 for r in load(RUN / "summary.json"))
assert manifest["thresholds"] == {"classification": .8, "verification": .8}

sources, commands = {}, []
for name in ("classification.py", "policy.py", "chat_service.py", "verification.py", "documents.py", "evaluation_budget.py"):
    relative = "regulai/front/" + name
    argv = ["rtk", "proxy", "git", "show", SOURCE + ":" + relative]
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    dest = HERE / "source" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(result.stdout)
    sources[name] = result.stdout.decode("utf-8")
    commands.append({"argv": argv, "exit_code": result.returncode, "stdout_sha256": sha(result.stdout)})

policy_tree = ast.parse(sources["policy.py"])
policy_class = next(n for n in policy_tree.body if isinstance(n, ast.ClassDef) and n.name == "ClassificationPolicyConfig")
defaults = {}
for node in policy_class.body:
    if isinstance(node, ast.AnnAssign):
        value = node.value
        if isinstance(value, ast.Call):
            value = next(k.value for k in value.keywords if k.arg == "default")
        defaults[node.target.id] = ast.literal_eval(value)
assert defaults == {"unknown_level": "confidential", "signal_threshold": .2, "on_ambiguity": "warn"}
tree = ast.parse(sources["classification.py"])
tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.module == "policy")]
classification = types.ModuleType("second_fixed_classification")
classification.AIConfig = object
sys.modules[classification.__name__] = classification
exec(compile(tree, "128d66a:classification.py", "exec"), classification.__dict__)
cfg = types.SimpleNamespace(jev=types.SimpleNamespace(threshold=.8), classification_policy=types.SimpleNamespace(**defaults),
                            verification=types.SimpleNamespace(threshold=.8))
chat_tree = ast.parse(sources["chat_service.py"])
assignment = next(n for n in ast.walk(chat_tree) if isinstance(n, ast.Assign) and n.lineno == 789)
expression = compile(ast.Expression(assignment.value), "128d66a:chat_service.py:789", "eval")
classification_replay, verification_replay = [], []
for line, row in enumerate(data, 1):
    call = next(c for c in row["receipt"]["calls"] if c["purpose"] == "classification")
    decision = classification.decide(call["signals"], cfg, "public")
    assert decision.sensitivity == row["sensitivity"] and decision.notices == row["notices"]
    assert decision.stop_code == (row["error_type"] if row["execution_state"] == "blocked" else None)
    classification_replay.append({"result_line": line, "case_id": row["case_id"], "configuration": row["configuration"],
        "signals": call["signals"], "decision": asdict(decision), "manipulation_threshold": .2})
    judges = [c for c in row["receipt"]["calls"] if c["purpose"] == "verification"]
    generations = row["generation_responses"]
    assert len(judges) == len(generations) == row["generation_calls"]
    for attempt, (judge, generated) in enumerate(zip(judges, generations), 1):
        assert sha(canonical(generated["content"]).encode("utf-8")) == generated["content_sha256"]
        answers = judge["signals"]
        accepted = eval(expression, {"all": all, "answers": answers, "cfg": cfg})
        decimal_accepted = all(Decimal(str(a["noul"])) <= Decimal(1) - Decimal(str(judge["threshold"])) for a in answers.values())
        float_failures = [k for k, a in answers.items() if a["noul"] > 1 - cfg.verification.threshold]
        decimal_failures = [k for k, a in answers.items() if Decimal(str(a["noul"])) > Decimal(".2")]
        recorded_status = next(c["verification"]["status"] for c in row["receipt"]["calls"]
                               if c["purpose"] == "generation" and c["verification"]["attempt"] == attempt)
        assert accepted == (recorded_status == "passed")
        verification_replay.append({"result_line": line, "case_id": row["case_id"], "configuration": row["configuration"],
            "attempt": attempt, "signals": answers, "float_cutoff_repr": repr(1 - cfg.verification.threshold),
            "recorded_status": recorded_status, "float_accepted": accepted, "decimal_control_accepted": decimal_accepted,
            "float_failed_signals": float_failures, "decimal_control_failed_signals": decimal_failures})
assert len(classification_replay) == 12 and len(verification_replay) == 7
boundary = [r for r in verification_replay if r["float_accepted"] != r["decimal_control_accepted"]]
assert len(boundary) == 1 and (boundary[0]["case_id"], boundary[0]["configuration"]) == ("DOC-01", "strong")
assert boundary[0]["float_failed_signals"] == ["failure_omission"] and boundary[0]["decimal_control_failed_signals"] == []

# Independently derive TXT fragment identity and check the delivered quote chain.
doc_case = next(c for c in cases if c["id"] == "DOC-01")
delivered = next(r for r in data if r["case_id"] == "DOC-01" and r["configuration"] == "router")
assert sum(r["delivered"] for r in data) == 1 and delivered["delivered"]
document_tree = ast.parse(sources["documents.py"])
extractor = next(ast.literal_eval(n.value) for n in document_tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "EXTRACTOR_VERSION" for t in n.targets))
doc_lines = doc_case["document"].splitlines()
assert len(doc_lines) == 5
locator = "lines:1-5"
fragment_id = sha(f"{extractor}:{sha(doc_case['document'].encode('utf-8'))}:{locator}".encode())
fragment = {"id": fragment_id, "locator": locator, "text": "\n".join(doc_lines)}
verification = types.ModuleType("second_fixed_verification")
exec(compile(sources["verification.py"], "128d66a:verification.py", "exec"), verification.__dict__)
generation = delivered["generation_responses"][0]
local_check = verification.verify_response(generation["content"], generation["finish_reason"],
    fragments=[fragment], alias_to_id={"S1": fragment_id})
assert local_check["local_status"] == "passed" and local_check["evidence"] == delivered["evidence"]
assert len(delivered["evidence"]) == 2
assert delivered["answer"] == "\n\n".join(f"{claim['text']} [{i}]" for i, claim in enumerate(local_check["claims"], 1))
assert "17 días" in delivered["answer"] and "120 EUR" in delivered["answer"]
citations = {"case_id": "DOC-01", "configuration": "router", "fragment_sha256": fragment_id,
    "locator": locator, "quotes": delivered["evidence"], "raw_source_lines": [3, 4],
    "independently_verified": "Original document quotes, derived fragment identity, alias, claim index and rendered citations",
    "limit": "No exact historical post-mask judge state is reconstructed or claimed"}

before, after = load(BEFORE / "budget.json"), load(RUN / "budget.json")
old_calls = before["calls"]
assert len(old_calls) == 65 and after["calls"][:65] == old_calls
new_calls = after["calls"][65:]
row_calls = [c for r in data for c in r["calls"]]
assert {c["id"]: c for c in new_calls} == {c["id"]: c for c in row_calls}
assert len(new_calls) == len(row_calls) == 45 and len({c["id"] for c in new_calls}) == 45
assert all(c["status"] == "completed" for c in new_calls)


def exposure(call):
    if call["cost"] is not None and call["metadata"].get("cost_kind", "provider_reported") in (
            "provider_reported", "configured_zero", "not_incurred"):
        return Decimal(call["cost"])
    return max(Decimal(call["reserved"]), Decimal(call["cost"]) if call["cost"] is not None else Decimal(0))


def cost(kind):
    return sum((Decimal(c["cost"]) for c in new_calls if c["metadata"]["cost_kind"] == kind), Decimal(0))


external = [c for c in new_calls if c["metadata"]["transport"] != "local"]
local = [c for c in new_calls if c["metadata"]["transport"] == "local"]
assert len(external) == 26 and len(local) == 19
assert all(Decimal(c["cost"]) == 0 for c in local)
new_exposure = sum((exposure(c) for c in new_calls), Decimal(0))
assert sum((exposure(c) for c in after["calls"]), Decimal(0)) == Decimal(after["budget_exposure_usd"])
assert Decimal(before["budget_exposure_usd"]) + new_exposure == Decimal(after["budget_exposure_usd"])
assert Decimal(after["cap_usd"]) == Decimal(1)
assert Decimal(after["cap_usd"]) - Decimal(after["budget_exposure_usd"]) == Decimal(after["remaining_usd"])
assert Decimal(after["known_cost_usd"]) - Decimal(before["known_cost_usd"]) == cost("provider_reported") + cost("tariff_estimate")
assert before["uncertain_reservations_usd"] == after["uncertain_reservations_usd"] == "0.003"
assert [c for c in after["calls"] if c["cost"] is None] == [c for c in old_calls if c["cost"] is None]
accounting = {"historical_entries_unchanged": 65, "new_entries": 45, "external_calls": 26, "local_transformations": 19,
    "new_external_by_purpose": dict(Counter(c["purpose"] for c in external)),
    "new_provider_reported_usd": str(cost("provider_reported")), "new_tariff_estimated_usd": str(cost("tariff_estimate")),
    "new_known_cost_usd": str(cost("provider_reported") + cost("tariff_estimate")),
    "new_exposure_usd": str(new_exposure), "before_exposure_usd": before["budget_exposure_usd"],
    "after_exposure_usd": after["budget_exposure_usd"], "remaining_usd": after["remaining_usd"],
    "old_uncertain_reserve_usd": "0.003", "scope": "Public before/after snapshots; no persistent ledger access"}
assert all(sha((ROOT / item["path"]).read_bytes()) == item["sha256"] for item in inputs)
assert guard_attempts == {"network": 0, "database": 0}
evidence = {"source_commit": SOURCE, "manifest_sha256": EXPECTED_MANIFEST, "public_inputs": inputs,
    "source_commands": commands, "analyzer_sha256": sha(Path(__file__).read_bytes()), "classification_replays": 12,
    "verification_replays": 7, "float_boundary_divergences": boundary, "citation_replays": 1,
    "status_counts": dict(Counter(r["execution_state"] for r in data)), "delivered": 1,
    "accounting": accounting, "guard_attempts": guard_attempts, "human_review_created": False,
    "limits": ["Exact post-mask judge state not retained", "No full human quality adjudication",
               "No live rerun, bridge, credentials, environment reads, database or persistent ledger access",
               "Before/after source hash maps identical; expressions extracted from fixed Git commit"]}
write("classification-replay.json", classification_replay)
write("verification-replay.json", verification_replay)
write("citation-replay.json", citations)
write("evidence.json", evidence)
print(json.dumps({"result": "PASS", "classification_replays": 12, "verification_replays": 7,
    "boundary_finding": boundary, "citation_replays": 1, "guard_attempts": guard_attempts, "accounting": accounting}, ensure_ascii=True))
