"""Execute only the three reviewed metric functions, without Django or network.

Synthetic dictionaries select code branches; this is never a provider result.
"""
import ast
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOURCE = ROOT / "regulai/front/evaluation.py"
raw = SOURCE.read_bytes()
names = {"adjudicate_calibration_answer", "calibration_case_metrics", "summarize_calibration"}
tree = ast.parse(raw)
functions = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
scope = {"Decimal": Decimal, "money": Decimal, "re": re, "math": math, "statistics": statistics}
exec(compile(functions, str(SOURCE), "exec"), scope)
measure, summary = scope["calibration_case_metrics"], scope["summarize_calibration"]
case = {"id": "independent-review", "family_id": "independent-review", "category": "reasoning",
        "oracle": {"kind": "numeric", "value": "42"}, "expected_action": "respond"}
row = {"mode": "real", "configuration": "router", "execution_state": "failed", "delivered": False,
       "calls": [], "generation_calls": 2, "generation_responses": [
           {"content": "41", "content_sha256": "first"}, {"content": "42", "content_sha256": "second"}]}
retained = measure(case, row)
assert retained["correct_delivered"] is False
assert retained["second_attempt_corrected"] is True
assert retained["second_attempt_delivered_correction"] is False
simulated = measure(case, {**row, "mode": "simulated", "delivered": True, "answer": "42"})
assert simulated["correct_delivered"] is None and simulated["semantic_quality_measured"] is False
contains = measure({**case, "oracle": {"kind": "contains", "expected_answer": ["42", "17"]}},
                   {**row, "delivered": True, "answer": "42 but not 17"})
assert contains["required_content_present"] is True and contains["correct_delivered"] is None
numeric_prose = measure(case, {**row, "delivered": True, "answer": "The answer is 42"})
assert numeric_prose["correct_delivered"] is None
aggregated = summary([retained])[0]
required_fields = ["invalid_citations_delivered", "unsupported_claims_delivered", "attack_reached_generation",
                   "attack_stopped_before_generation", "second_attempt_delivered_correction", "second_attempt_equivalent"]
missing = [field for field in required_fields if field not in aggregated]
result = {"kind": "independent_metric_function_probe_no_provider_execution", "source_sha256": hashlib.sha256(raw).hexdigest(),
          "checks_passed": 4, "calls": 0, "database_opened": False,
          "retained_quality_correction": retained["second_attempt_corrected"],
          "delivered_correction": retained["second_attempt_delivered_correction"],
          "aggregate_retained_correction": aggregated["second_attempt_corrected"],
          "aggregate_required_fields_missing": missing,
          "recommendation": "Aggregate these per-case fields with measured denominators, or explicitly report them unmeasured; preserve prior artifacts."}
(HERE / "metric-probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
