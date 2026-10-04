"""Independent probes of pinned source; no Django/database/provider execution."""
import ast
from dataclasses import asdict, dataclass, field
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
REV = "b3fea6a63761c06ef66695fee26377d23786c347"
HASHES = {}


def source(revision, path):
    result = subprocess.run(["rtk", "proxy", "git", "show", revision + ":" + path], cwd=ROOT,
                            capture_output=True, check=True)
    HASHES[revision + ":" + path] = hashlib.sha256(result.stdout).hexdigest()
    return ast.parse(result.stdout, filename=path)


def module_from_nodes(name, tree, accept, globals):
    module = ModuleType(name)
    sys.modules[name] = module
    module.__dict__.update(globals)
    subset = ast.Module(body=[node for node in tree.body if accept(node)], type_ignores=[])
    exec(compile(subset, name, "exec"), module.__dict__)
    return module


policy = module_from_nodes("utility_review_policy", source(REV, "regulai/front/policy.py"),
    lambda n: isinstance(n, ast.ClassDef) and n.name in {"StrictConfig", "ClassificationPolicyConfig"},
    dict(BaseModel=BaseModel, ConfigDict=ConfigDict, Field=Field, Literal=Literal))
configs = policy.ClassificationPolicyConfig
modules = [module_from_nodes("utility_review_classification_" + rev[:7], source(rev, "regulai/front/classification.py"),
    lambda n: isinstance(n, (ast.Assign, ast.ClassDef, ast.FunctionDef)),
    dict(dataclass=dataclass, field=field, Decimal=Decimal, math=math, AIConfig=object))
    for rev in ("3940fdc", REV)]
before, after = modules


def cfg(**values):
    return SimpleNamespace(classification_policy=configs.model_validate(values), jev=SimpleNamespace(threshold=.8))


def signals(randomizer=None):
    values = {}
    for key, choices in (("category", (*after.LEVELS, "unknown")), ("task", after.TASKS),
                         ("difficulty", ("economy", "balanced", "strong"))):
        chosen = randomizer.choice(choices) if randomizer else choices[0]
        values[key] = dict(type="choice", choice=chosen, confidence=1.0,
                           probabilities={choice: float(choice == chosen) for choice in choices})
    for key in after.SIGNALS:
        values[key] = dict(type="noul", noul=randomizer.choice([0.0, .19, .2, .29, .3, .39, .4, .9, 1.0]) if randomizer else 0.0)
    return values


randomizer = random.Random(20261004)
legacy_checks = 0
for limit in (.1, .2, .3, .8, 1.0):
    for _ in range(100):
        answers = signals(randomizer)
        floor = randomizer.choice((*after.LEVELS, "unknown"))
        config = cfg(signal_threshold=limit)
        assert asdict(before.decide(answers, config, floor)) == asdict(after.decide(answers, config, floor))
        legacy_checks += 1
boundary_checks = 0
for threshold in (.35, .4, .5):
    config = cfg(manipulation_threshold=threshold)
    for probability, stop in ((math.nextafter(threshold, 0), None),
                              (threshold, "classification_manipulation"),
                              (math.nextafter(threshold, 1), "classification_manipulation")):
        answers = signals()
        answers["manipulation"]["noul"] = probability
        assert after.decide(answers, config, "public").stop_code == stop
        boundary_checks += 1
other_signal_checks = 0
for threshold in (.35, .4, .5):
    for key in set(after.SIGNALS) - {"manipulation"}:
        for probability in (math.nextafter(.2, 0), .2, math.nextafter(.2, 1)):
            answers = signals()
            answers[key]["noul"] = probability
            assert asdict(before.decide(answers, cfg(), "public")) == asdict(after.decide(answers, cfg(manipulation_threshold=threshold), "public"))
            other_signal_checks += 1
rejected = 0
for value in (".4", True, 0, -.1, 1.1, float("nan"), float("inf")):
    try:
        cfg(manipulation_threshold=value)
    except ValueError:
        rejected += 1
    else:
        raise AssertionError("Invalid override was accepted")
metrics = module_from_nodes("utility_review_metrics_b3fea6a", source(REV, "regulai/front/evaluation.py"),
    lambda n: isinstance(n, ast.FunctionDef) and n.name in
        {"adjudicate_calibration_answer", "calibration_case_metrics", "summarize_calibration"},
    dict(Decimal=Decimal, money=Decimal, re=re, math=math, statistics=statistics))
case = dict(id="review", family_id="one", category="reasoning", oracle=dict(kind="numeric", value="42"))
row = dict(mode="real", configuration="router", execution_state="failed", delivered=False, generation_calls=2,
           generation_responses=[dict(content="41", content_sha256="one"), dict(content="42", content_sha256="two")],
           invalid_citations_delivered=0)
summary = metrics.summarize_calibration([metrics.calibration_case_metrics(case, row)])[0]
assert summary["second_attempt_corrected"] == dict(n=1, true=1, rate=1.0)
assert summary["second_attempt_delivered_correction"] == dict(n=1, true=0, rate=0.0)
assert summary["invalid_citations_delivered"] == dict(n=1, count=0)
assert summary["unsupported_claims_delivered"] == dict(n=0, count=None)
result = dict(fixed_commit=REV, comparison_commit="3940fdc", source_sha256=HASHES, kind="independent_pinned_function_probe",
              legacy_decision_comparisons=legacy_checks, preregistered_threshold_boundaries=boundary_checks,
              unchanged_other_signal_boundaries=other_signal_checks, invalid_policy_values_rejected=rejected,
              retained_and_delivered_aggregate_checks=4, u1="closed_on_pinned_source",
              new_provider_calls=0, database_opened=False, reserved_opened=False,
              limitation="Synthetic function checks establish compatibility and metric behavior, not a safe or useful real manipulation threshold.")
(HERE / "review-b3fea6a-probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
