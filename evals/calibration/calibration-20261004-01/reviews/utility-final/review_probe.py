"""Independent, read-only public-corpus and artifact audit (no providers or DB).

Never opens reserved data or the corpus builder. Writes only in this directory.
"""
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
ROOT = CAMPAIGN.parents[2]
CORPUS = CAMPAIGN / "corpus"
HASHES = {}


def raw(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT)
    assert "reserved" not in path.parts and "superseded" not in path.parts
    assert path.name != "build_calibration_corpus.py"
    value = path.read_bytes()
    HASHES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(value).hexdigest()
    return value


def read(path):
    return json.loads(raw(path))


def rows(path):
    return [json.loads(line) for line in raw(path).decode("utf-8").splitlines() if line]


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).replace("\u0085", "\\u0085").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def digest(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()


def request(case):
    return {"prompt": case["prompt"], "instructions": case.get("instructions", ""),
            "history": [{"role": x["role"], "content": x["content"]} for x in case.get("history", [])],
            "documents": [{"text": x["text"]} for x in case.get("documents", [])]}


def expr_value(source):
    def value(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(ast.get_source_segment(source, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            n = value(node.operand)
            return n if isinstance(node.op, ast.UAdd) else -n
        if isinstance(node, ast.BinOp):
            left, right = value(node.left), value(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
        raise ValueError("Unsupported arithmetic node")
    return value(ast.parse(source, mode="eval").body)


def audit():
    manifest = read(CORPUS / "manifest.json")
    cases = [c for split in ("development", "validation") for c in rows(CORPUS / split / "cases.jsonl")]
    originals = {c["case_id"]: c for split in ("development", "validation") for c in rows(CORPUS / split / "originals.jsonl")}
    failures = defaultdict(list)
    scopes, documents, inputs = defaultdict(set), {}, set()
    annotations = Counter()
    distribution = {}
    sample_cases = []
    for case in cases:
        cid = case["id"]
        scopes[case["family_id"]].add(case["split"])
        clone = dict(case)
        if digest({k: v for k, v in clone.items() if k != "case_sha256"}) != case["case_sha256"]:
            failures["case_hash"].append(cid)
        full = request(case)
        if len(canon(full).encode()) != case["length"]["utf8_bytes"]:
            failures["request_length"].append(cid)
        input_hash = digest({"text_request": full, "uploaded_document_sha256s": [d["sha256"] for d in case["documents"]]})
        if input_hash in inputs or input_hash != case["input_sha256"]:
            failures["request_hash_or_duplicate"].append(cid)
        inputs.add(input_hash)
        texts = {"prompt": case["prompt"], **{f"history:{n}": x["content"] for n, x in enumerate(case.get("history", []))},
                 **{"document:" + d["ref"]: d["text"] for d in case["documents"]}}
        for doc in case["documents"]:
            if doc["ref"] not in documents:
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
            for expr, expected in case["oracle"]["arithmetic_checks"]:
                actual = expr_value(expr)
                if actual != Decimal(expected.replace(",", "")):
                    failures["arithmetic"].append({"id": cid, "expr": expr, "actual": str(actual), "expected": expected})
            if Decimal(case["oracle"]["arithmetic_checks"][-1][1].replace(",", "")) != Decimal(case["oracle"]["value"]):
                failures["arithmetic_final"].append(cid)
        if cid in ("D0801", "D0802", "P0801", "P0802"):
            sample_cases.append(case)
    failures["families_cross_partition"] = [f for f, parts in scopes.items() if len(parts) > 1]
    for split in ("development", "validation"):
        selected = [c for c in cases if c["split"] == split]
        distribution[split] = {
            "cases": len(selected), "families": len({c["family_id"] for c in selected}),
            "category": dict(Counter(c["category"] for c in selected)),
            "oracle_kind": dict(Counter(c["oracle"]["kind"] for c in selected)),
            "expected_action": dict(Counter(c["expected_action"] for c in selected)),
            "language": dict(Counter(c["language"] for c in selected)),
            "length": dict(Counter(c["length"]["band"] for c in selected)),
            "history_cases": sum(bool(c.get("history")) for c in selected),
            "instructions_cases": sum(bool(c.get("instructions")) for c in selected),
            "largest_families": Counter(c["family_id"] for c in selected).most_common(5),
        }
    comparisons = {}
    for split in ("development", "validation"):
        value = read(CAMPAIGN / "evaluation" / f"{split}-comparison-01.json")
        comparisons[split] = {k: v for k, v in value.items() if k != "cases"}
        for source, expected in value["source_sha256"].items():
            if hashlib.sha256(raw(ROOT / source)).hexdigest() != expected:
                failures["comparison_source_hash"].append(source)
        summaries = []
        for variant in ("base", "candidate"):
            folder = CAMPAIGN / "evaluation" / f"{split}-{variant}-01"
            summary = read(folder / "summary.json")
            summary["variant"] = variant
            plan = read(folder / "plan.json")
            summary["selected_http_cases"] = plan["selected_http_cases"]
            summary["corpus_manifest_sha256"] = plan["harness_sha256"][str(CORPUS / "manifest.json")]
            expected_artifacts = read(folder / "artifact-hashes.json")
            for name, expected in expected_artifacts.items():
                if hashlib.sha256(raw(folder / name)).hexdigest() != expected:
                    failures["artifact_hash"].append(str(folder / name))
            http = rows(folder / "http-results.jsonl")
            summary["http_failed"] = [{k: row.get(k) for k in ("case_id", "endpoint", "provider_profile", "observed_control", "control_passed")} for row in http if not row.get("control_passed")]
            summaries.append(summary)
        comparisons[split]["runs"] = summaries
    gates = read(CAMPAIGN / "gates-01/manifest.json")
    gate_summary = {k: v for k, v in gates.items() if k not in ("source_sha256", "artifact_sha256")}
    for command in gates.get("commands", []):
        if hashlib.sha256(raw(CAMPAIGN / "gates-01" / command["log"])).hexdigest() != command["sha256"]:
            failures["gate_log_hash"].append(command["gate"])
    for name in ("README.md", "ATTRIBUTIONS.md", "api.py", "integrity-audit.json", "source-dedup-audit.json", "sources/downloads.json"):
        raw(CORPUS / name)
    raw(ROOT / "regulai/front/evaluation.py")
    raw(ROOT / "regulai/front/local_masking.py")
    raw(ROOT / "scripts/calibration_local_checks.py")
    raw(ROOT / "scripts/run_calibration_campaign.py")
    result = {"fixed_commit": "3940fdc698c34998b2541309b0b697b6c06c2287", "base_commit": "9d7f9424a70143614c9d673e64ebed9723ff3439",
        "generated_utc": datetime.now(timezone.utc).isoformat(), "reserved_opened": False,
        "builder_imported": False, "mode": "independent_artifact_and_public_corpus_audit",
        "network_calls": 0, "product_database_opened": False,
        "manifest": {k: v for k, v in manifest.items() if k != "files"},
        "public_distribution": distribution, "checked_documents": len(documents), "annotations": dict(annotations),
        "failures": {k: v for k, v in failures.items() if v}, "comparisons": comparisons,
        "gates": gate_summary, "source_sha256": HASHES}
    (HERE / "public-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": not result["failures"], "cases": len(cases), "checked_documents": len(documents), "annotations": dict(annotations),
                      "failures": result["failures"], "output_sha256": hashlib.sha256((HERE / "public-audit.json").read_bytes()).hexdigest()}, ensure_ascii=False))
    return bool(result["failures"])


if __name__ == "__main__":
    raise SystemExit(audit())
