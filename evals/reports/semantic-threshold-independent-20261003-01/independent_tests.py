import ast
from dataclasses import asdict
from decimal import Decimal
import json
import math
from pathlib import Path
import sys
from types import ModuleType
import uuid

from django.test import SimpleTestCase
from front import test_classification, test_pipeline
from front.classification import decide
from front.models import EngineModel, Prompt, Response
from front.policy import AIConfig
from front.test_chat_flow import ChatFixture

HERE = Path(__file__).resolve().parent
OBSERVATIONS = {"http": [], "history": [], "adjacent": []}


def save():
    (HERE / "observations.json").write_text(json.dumps(OBSERVATIONS, indent=2) + "\n", encoding="utf-8")


def expression(base):
    tree = ast.parse((HERE / (("base-" if base else "fixed-") + "chat_service.py")).read_text(encoding="utf-8"))
    if base:
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and n.lineno == 789)
        compiled = compile(ast.Expression(node.value), "base:789", "eval")
        return lambda answers, cfg: eval(compiled, {"all": all, "answers": answers, "cfg": cfg})
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and 790 <= n.lineno <= 793]
    assert len(nodes) == 3
    compiled = compile(ast.Module(body=nodes, type_ignores=[]), "fixed:790-793", "exec")
    def result(answers, cfg):
        context = {"Decimal": Decimal, "answers": answers, "cfg": cfg, "checks": {}}
        exec(compiled, context)
        return context["checks"]["status"] == "passed"
    return result


class PureReplayTests(SimpleTestCase):
    def test_all_retained_live_signals_change_only_the_proven_boundary(self):
        original = ast.parse((HERE / "base-classification.py").read_text(encoding="utf-8"))
        original.body = [n for n in original.body if not (isinstance(n, ast.ImportFrom) and n.module == "policy")]
        module = ModuleType("independent_base_classification")
        module.AIConfig = AIConfig
        sys.modules[module.__name__] = module
        exec(compile(original, "base:classification.py", "exec"), module.__dict__)
        before, after, cfg = expression(True), expression(False), AIConfig()
        classifications, verifications, differences = 0, 0, []
        for run in (1, 2):
            rows = [json.loads(line) for line in (HERE / f"historical-run-{run}.jsonl").read_text(encoding="utf-8").splitlines()]
            for row in rows:
                for call in row["receipt"]["calls"]:
                    if call["purpose"] == "classification":
                        self.assertEqual(asdict(module.decide(call["signals"], cfg, "public")),
                                         asdict(decide(call["signals"], cfg, "public")))
                        classifications += 1
                    elif call["purpose"] == "verification":
                        old, new = before(call["signals"], cfg), after(call["signals"], cfg)
                        verifications += 1
                        if old != new:
                            differences.append([run, row["case_id"], row["configuration"], old, new])
        self.assertEqual((classifications, verifications), (24, 11))
        self.assertEqual(differences, [[2, "DOC-01", "strong", False, True]])
        OBSERVATIONS["history"] = {"classifications_unchanged": 24, "verification_decisions": 11, "differences": differences,
            "historical_records_rewritten": False, "no_new_live_delivery_claim": True}
        save()

    def test_adjacent_scores_and_multi_mass_ordinal_tail(self):
        accept = expression(False)
        for threshold, boundary in ((.8, .2), (.7, .3), (.9, .1)):
            cfg = AIConfig(verification={"threshold": threshold})
            for value, expected in ((math.nextafter(boundary, 0), True), (boundary, True),
                                    (math.nextafter(boundary, 1), False)):
                with self.subTest(threshold=threshold, value=value):
                    self.assertEqual(accept({"failure_omission": {"noul": value}}, cfg), expected)
                    OBSERVATIONS["adjacent"].append({"threshold": threshold, "score": value, "accepted": expected})
        for mass, expected in ((.1, "public"), (math.nextafter(.1, 1), "internal")):
            signals = test_classification.answers()
            signals["category"].update(choice="public", confidence=.8,
                probabilities={"public": .8, "internal": .1, "confidential": mass, "restricted": 0., "unknown": 0.})
            self.assertEqual(decide(signals, AIConfig(), "public").sensitivity, expected)
            self.assertEqual(decide(signals, AIConfig(), "confidential").sensitivity, "confidential")
        save()


class HttpRetryTests(ChatFixture):
    configure = test_pipeline.PipelineTests.configure

    def test_exact_boundary_delivery_and_retry_feedback_on_three_entries(self):
        self.configure()
        stronger = EngineModel.objects.create(engine=self.engine, name="Independent strong", model_id="independent-strong",
            context_window=32768, input_price=2, output_price=3)
        self.company.ai_config["routing"] = {"mode": "manual", "candidates": [
            {"company_engine_id": self.credential.pk, "model_id": self.model.pk, "level": "economy", "quality": {"general": .5}},
            {"company_engine_id": self.credential.pk, "model_id": stronger.pk, "level": "strong", "quality": {"general": .9}}]}
        self.company.save()
        for path in ("/chat/send/", "/api/chat/send/", "/chat/"):
            for retry in (False, True):
                with self.subTest(path=path, retry=retry):
                    self.provider.reset_mock()
                    judges = []
                    def transport(url, **kwargs):
                        if url.endswith("/api/mask"):
                            return test_pipeline.jev_http()(url, **kwargs)
                        request = json.loads(kwargs["data"])
                        failures = {}
                        if "failure_omission" in request["questions"]:
                            failures = {"failure_omission": .2, "failure_contradiction":
                                math.nextafter(.2, 1) if retry and not judges else .2}
                            judges.append(failures)
                        return test_pipeline.jev_http(failures=failures)(url, **kwargs)
                    self.http.side_effect = transport
                    request_id = str(uuid.uuid4())
                    response = self.send(path, "Independent boundary check", request_id=request_id)
                    prompt = Prompt.objects.get(request_id=request_id)
                    self.assertEqual(prompt.status, "completed")
                    self.assertEqual(response.status_code, 302 if path == "/chat/" else 200)
                    self.assertTrue(Response.objects.filter(prompt=prompt).exists())
                    self.assertEqual(self.provider.call_count, 2 if retry else 1)
                    self.assertEqual(len(judges), 2 if retry else 1)
                    self.assertEqual(prompt.decision["verification"]["attempt"], 2 if retry else 1)
                    self.assertEqual(prompt.decision["verification"]["status"], "passed")
                    if retry:
                        feedback = self.provider.call_args.args[0][-1].content
                        self.assertEqual(feedback, "Correct the failed checks: failure_contradiction")
                    for call in prompt.decision["calls"]:
                        if call["purpose"] == "verification":
                            self.assertEqual(call["threshold"], .8)
                    OBSERVATIONS["http"].append({"path": path, "retry": retry, "status": prompt.status,
                        "generations": self.provider.call_count, "judge_signals": judges, "threshold": .8})
        save()
