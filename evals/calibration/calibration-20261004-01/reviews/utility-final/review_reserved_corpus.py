"""Independent final corpus audit after the custodian's one-time LOCAL release."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

# This module's main guard is inactive: reuse only its pure canonical/arithmetic helpers.
from review_probe import canon, digest, expr_value, request

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
ROOT = HERE.parents[4]
CORPUS = CAMPAIGN / "corpus"
HASHES = {}


def raw(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT)
    assert "superseded" not in path.parts and path.name != "build_calibration_corpus.py"
    value = path.read_bytes()
    HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(value).hexdigest()
    return value


def read(path):
    return json.loads(raw(path))


def rows(path):
    return [json.loads(line) for line in raw(path).splitlines() if line]


release = read(CORPUS / "reserved-release.json")
assert HASHES[(CORPUS / "reserved-release.json").relative_to(ROOT).as_posix()] == "4e8828c907eb19bccfe221f6a3ec68b3f75de23a4f9037d99b434be6c8eb085b"
assert release["status"] == "released_once_for_final_comparison"
assert release["scope"]["phase"] == "final_local_comparison"
assert release["scope"]["new_provider_calls_permitted"] is False
assert release["scope"]["post_holdout_tuning_permitted"] is False
assert hashlib.sha256(raw(CAMPAIGN / "final_selection.json")).hexdigest() == release["final_selection_sha256"]
assert hashlib.sha256(raw(CAMPAIGN / "final-candidate-configuration.json")).hexdigest() == release["candidate_configuration_sha256"]
assert hashlib.sha256(raw(CORPUS / "manifest.json")).hexdigest() == release["corpus_manifest_sha256"]
manifest = read(CORPUS / "manifest.json")

failures = defaultdict(list)
for path, expected in manifest["files"].items():
    if hashlib.sha256(raw(CORPUS / path)).hexdigest() != expected:
        failures["manifest_file_hash"].append(path)

all_cases = [c for split in ("development", "validation", "reserved") for c in rows(CORPUS / split / "cases.jsonl")]
cases = [c for c in all_cases if c["split"] == "reserved"]
originals = {c["case_id"]: c for c in rows(CORPUS / "reserved/originals.jsonl")}
scopes, ids, inputs = defaultdict(set), set(), set()
for case in all_cases:
    scopes[case["family_id"]].add(case["split"])
    if case["id"] in ids:
        failures["duplicate_case_id"].append(case["id"])
    ids.add(case["id"])
    if case["input_sha256"] in inputs:
        failures["duplicate_input_sha256"].append(case["id"])
    inputs.add(case["input_sha256"])
failures["families_cross_partition"] = [family for family, split in scopes.items() if len(split) > 1]

annotations = Counter()
documents = {}
for case in cases:
    cid = case["id"]
    if digest({k:v for k,v in case.items() if k != "case_sha256"}) != case["case_sha256"]:
        failures["case_hash"].append(cid)
    complete = request(case)
    if len(canon(complete).encode()) != case["length"]["utf8_bytes"]:
        failures["request_length"].append(cid)
    if digest(dict(text_request=complete, uploaded_document_sha256s=[d["sha256"] for d in case["documents"]])) != case["input_sha256"]:
        failures["request_hash"].append(cid)
    texts = {"prompt": case["prompt"], **{f"history:{n}": x["content"] for n,x in enumerate(case.get("history", []))},
             **{"document:" + d["ref"]: d["text"] for d in case["documents"]}}
    for doc in case["documents"]:
        documents[doc["ref"]] = hashlib.sha256(raw(CORPUS / doc["ref"])).hexdigest()
        if documents[doc["ref"]] != doc["sha256"]:
            failures["document_hash"].append(cid)
    for key in ("expected_redactions", "preserve"):
        for item in case[key]:
            annotations[key] += 1
            if texts[item["scope"]][item["start"]:item["end"]] != item["value"]:
                failures["span"].append(cid)
    for evidence in case["evidence"]:
        if evidence["quote"] not in texts["document:" + evidence["document_ref"]]:
            failures["quote"].append(cid)
    if cid in originals:
        original = originals[cid]
        if digest(original["original"]) != original["sha256"] or original["sha256"] != case["provenance"]["original_sha256"]:
            failures["original_hash"].append(cid)
    if case["oracle"]["kind"] == "numeric":
        annotations["numeric_references"] += 1
        for expression, expected in case["oracle"]["arithmetic_checks"]:
            if expr_value(expression) != Decimal(expected.replace(",", "")):
                failures["arithmetic"].append(cid)
        if Decimal(case["oracle"]["arithmetic_checks"][-1][1].replace(",", "")) != Decimal(case["oracle"]["value"]):
            failures["arithmetic_final"].append(cid)

assert len(cases) == release["scope"]["cases_per_comparator"] == 571
distribution = {key: dict(Counter(c[key] for c in cases)) for key in ("category", "language", "expected_action")}
distribution["length"] = dict(Counter(c["length"]["band"] for c in cases))
distribution["oracle"] = dict(Counter(c["oracle"]["kind"] for c in cases))
distribution["families"] = len({c["family_id"] for c in cases})
result = dict(kind="agent_integrity_audit_after_one_time_local_release", generated_utc=datetime.now(timezone.utc).isoformat(),
    reserved_opened=True, release_sha256=HASHES[(CORPUS / "reserved-release.json").relative_to(ROOT).as_posix()],
    fixed_candidate=release["candidate_commit"], corpus_files_hashed=len(manifest["files"]),
    all_cases=4004, reserved_cases=len(cases), distribution=distribution, checked_reserved_documents=len(documents),
    annotations=dict(annotations), failures={k:v for k,v in failures.items() if v},
    all_family_partitions_disjoint=not failures["families_cross_partition"],
    family_independence="Operational groups only; integrity/disjointness is not proof of >=1500 semantically independent families.",
    adequacy_note="Reserved has one documentary case and zero very_long cases; global quotas do not establish confirmation coverage.",
    product_calls=0, network_calls=0, product_database_opened=False, builder_imported=False,
    superseded_reserved_opened=False, post_holdout_tuning=False, oracle_changes=False,
    source_sha256=HASHES)
output = HERE / "reserved-corpus-review-01.json"
output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k != "source_sha256"}, ensure_ascii=True))
print("OUTPUT_SHA256", hashlib.sha256(output.read_bytes()).hexdigest())
raise SystemExit(bool(result["failures"]))
