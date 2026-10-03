"""Verify retained synthetic evidence and rerun the frozen corpus without a DB.

Outputs are exclusive-create under this directory. This does not run a human
session, a provider, a browser, a suite, or a new tenant-isolation experiment.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
OWNED = Path(__file__).resolve().parent
DOC = ROOT / "evals/reports/pilot-documents-20261003-01"
UI = ROOT / "evals/reports/pilot-ui-followup-20261003-01"
OPS = ROOT / "evals/reports/pilot-operations-20261003-08"
READ_HEAD = "535eb9d8421006ea8476ea511427a7dcda9cee3b"
BROWSER_HEAD = "972edb88c82a5220a43ffcc89316a9f9033e82f7"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def blocked_network(*args, **kwargs):
    raise RuntimeError("P01 verification prohibits socket network activity")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    out = options.output_dir.resolve()
    if not out.is_relative_to(OWNED) or out.exists():
        parser.error("Choose a NEW output directory inside .claude/pilot-personas/p01")
    out.mkdir()
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    checks, inputs = [], {}

    def remember(path, kind="retained_evidence"):
        relative = path.relative_to(ROOT).as_posix()
        inputs[relative] = {"sha256": sha(path), "bytes": path.stat().st_size, "kind": kind}

    def check(name, condition, detail):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    indexed = 0
    for directory in (DOC, UI):
        index = directory / "evidence-sha256.json"
        remember(index)
        for item in read(index)["files"]:
            path = directory / item["file"]
            remember(path)
            indexed += 1
            check("retained_hash:" + str(path.relative_to(ROOT)),
                  sha(path) == item["sha256"] and path.stat().st_size == item["bytes"],
                  "Hash and byte length checked now; original action not repeated")

    pending = read(DOC / "state-postfix-pending.json")["requests"][0]
    expired = read(DOC / "state-postfix-expired.json")["requests"][0]
    finished = read(DOC / "state-postfix-completed.json")["requests"][0]
    check("historical_expiry_preserves_identity",
          all(len({item[key] for item in (pending, expired, finished)}) == 1
              for key in ("request_id", "file_name", "file_sha256", "user_message_id")),
          "Browser04 historical request/file/message preserved; no new clock wait")
    check("historical_expiry_precedes_calls",
          pending["calls"] == expired["calls"] == 0 and expired["status"] == "pending_consent"
          and expired["consent_reason"] == "consent_expired", "Existing states, not a new run")
    old_observations = read(DOC / "browser-observations.json")
    expiry = next(x for x in old_observations["observations"] if x["case"] == "final_real_expiry_then_completion")
    check("historical_wait_recorded_over_300_seconds", expiry["elapsed_wall_seconds"] > 300,
          {"historical_seconds": expiry["elapsed_wall_seconds"], "new_wait_seconds": None})
    receipt = read(DOC / "receipt-postfix-completed.json")["receipt"]
    generations = [x for x in receipt["calls"] if x["purpose"] == "generation"]
    check("historical_two_attempts_not_eight_generations",
          len(receipt["calls"]) == 8 and len(generations) == 2
          and [x["verification"]["status"] for x in generations] == ["failed", "passed"],
          "Eight synthetic operations, two generation attempts; first rejected, second accepted")
    check("historical_synthetic_cost_adds_up",
          sum(Decimal(x["cost"]) for x in receipt["calls"]) == Decimal(receipt["total"]["cost"]),
          {"synthetic_estimate_usd": receipt["total"]["cost"], "real_invoice": False})
    old_cancel = read(DOC / "receipt-cancelled.json")
    check("historical_marker_cancel_is_not_document_cancel",
          old_cancel["status"] == "cancelled" and old_cancel["receipt"]["calls"] == []
          and "coverage" not in old_cancel["receipt"], "Previous evidence is kept separate from the new DOCX cancellation")
    old_unknown = read(DOC / "receipt-outcome-unknown-reconstruction.json")
    check("reconstructed_unknown_not_zero_or_success",
          old_unknown["status"] == "outcome_unknown" and "total" not in old_unknown["receipt"]
          and old_unknown["receipt"]["calls"][0]["cost"] is None,
          "Retained UI reconstruction only, not an actual process interruption")
    for name in ("result.json", "restart-result.json", "source-manifest.json", "source-head.log"):
        remember(OPS / name)
    restart = read(OPS / "restart-result.json")
    check("historical_real_restart_keeps_unknown",
          restart["success"] is False and restart["status"] == "outcome_unknown"
          and "total" not in restart["receipt"]
          and any(x["purpose"] == "generation" and x["status"] == "started" and x["cost"] is None
                  for x in restart["receipt"]["calls"]),
          "Historical synthetic lab08 interruption, distinct from the UI reconstruction and live-provider run")
    operations = read(OPS / "result.json")
    check("historical_tenant_gate_retained",
          operations["checks"]["https_cookies_hosts_static_private_files_and_tenants"] is True,
          "Retained aggregate gate only; no new Alpha/Beta session and no universal isolation claim")
    snapshot = (UI / "browser-completed-snapshot.yml").read_text(encoding="utf-8")
    check("historical_completed_notice_is_past_tense",
          "Previous confirmation notice: A previous confirmation expired." in snapshot
          and 'button "Confirm sending"' not in snapshot and 'button "Cancel request"' not in snapshot,
          "Fixed historical wording retained, not reported as an open regression")

    for name in ("state-document-pending.json", "state-document-cancelled.json", "browser01/run.json",
                 "start_isolated_browser.py", ".playwright-cli/receipt-0d786fda-cbda-4397-af8c-e54ade766b7c.json"):
        remember(OWNED / name, "new_automated_browser_evidence")
    before = read(OWNED / "state-document-pending.json")
    after = read(OWNED / "state-document-cancelled.json")
    first, last = before["requests"][0], after["requests"][0]
    downloaded = read(OWNED / ".playwright-cli/receipt-0d786fda-cbda-4397-af8c-e54ade766b7c.json")
    check("new_document_cancel_same_identity",
          len(before["requests"]) == len(after["requests"]) == 1
          and all(first[key] == last[key] for key in ("request_id", "file_sha256", "file_name", "user_message_id"))
          and last["file_name"] == "text-and-image.docx",
          {"request_id": last["request_id"], "file_sha256": last["file_sha256"]})
    check("new_document_cancel_zero_calls_and_no_assistant",
          first["status"] == "pending_consent" and last["status"] == "cancelled"
          and first["calls"] == last["calls"] == 0 and after["messages"] == {"user": 1},
          "New agent browser action: Tab from focused Confirm sending, verified Cancel request focus, Enter")
    check("new_download_preserves_cancellation_and_disclosure",
          downloaded["status"] == "cancelled" and downloaded["request_id"] == last["request_id"]
          and downloaded["receipt"]["calls"] == []
          and downloaded["receipt"]["coverage"]["disclosures"][0]["locators"] == ["word/document.xml/paragraph:3"],
          "Actual download through receipt link; not manually reconstructed")
    environment = read(OWNED / "browser01/run.json")
    for name, digest in environment["sources"].items():
        remember(ROOT / name, "current_source_compared_to_browser_loaded_hash")
        check("browser_source_unchanged:" + name, sha(ROOT / name) == digest,
              "Source recorded at new server startup")
    database = OWNED / "browser01/pilot.sqlite3"
    if Path(environment["database"]).resolve() != database or database.is_symlink():
        raise ValueError("P01 synthetic database identity mismatch")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        configured_backends = connection.execute("SELECT backend, COUNT(*) FROM front_obfuscationconfig GROUP BY backend").fetchall()
    check("new_demo_configures_local_mask", configured_backends == [("local", 1)],
          "Read-only aggregate from P01's new synthetic DB; mask not invoked because request cancelled before calls")

    corpus = ROOT / "evals/documents/pilot-20261003"
    for path in [corpus / "expectations.json", corpus / "verify_corpus.py", corpus / "files/manifest.json"]:
        remember(path, "frozen_corpus_or_verifier")
    for item in read(corpus / "files/manifest.json")["files"]:
        remember(corpus / "files" / item["file"], "synthetic_corpus")
    for path in OWNED.glob(".playwright-cli/*"):
        if path.suffix in {".png", ".yml"}:
            remember(path, "new_automated_browser_evidence")

    # Explicit settings avoid loading settings.py/local_settings.py or a user DB.
    # The public extractor still executes its normal bounded parser subprocess.
    from django.conf import settings
    settings.configure(SECRET_KEY="p01-synthetic-verification-only", INSTALLED_APPS=[],
                       DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
                       DOCUMENT_PARSER_TIMEOUT=5)
    with patch.object(socket.socket, "connect", blocked_network), \
         patch.object(socket.socket, "connect_ex", blocked_network), \
         patch.object(socket, "create_connection", blocked_network):
        module = runpy.run_path(str(corpus / "verify_corpus.py"), run_name="p01_frozen_corpus")
        corpus_exit = module["verify"](out / "extraction.json")
    extraction = read(out / "extraction.json")
    check("fresh_frozen_corpus", corpus_exit == 0 and extraction["cases"] == extraction["passed"] == 12,
          "NEW extraction only: no Django HTTP/send route, browser, native Office, OCR, provider or human evaluation")

    # Preserve exact provenance of the planning text initially read even while
    # the root agent updates shared docs. No duplicate glossary is written.
    planning = {}
    for name in ("docs/plan-blackhat/README.md", "docs/plan-blackhat/documentos-y-ensayos-piloto.md",
                 "docs/plan-blackhat/piloto-controlado.md"):
        result = subprocess.run(["rtk", "proxy", "git", "show", f"{READ_HEAD}:{name}"],
                                cwd=ROOT, capture_output=True, check=True)
        planning[name] = {"revision": READ_HEAD, "sha256": hashlib.sha256(result.stdout).hexdigest(),
                          "kind": "git_blob_at_initial_reference", "bytes": len(result.stdout)}
    write(out / "source-manifest.json", {"initial_reference_head": READ_HEAD,
          "new_browser_reference_head": BROWSER_HEAD, "planning_git_blobs": planning,
          "inputs": inputs, "limits": ["Hashes prove bytes, not human truth or provider quality.",
          "No input ledger or original human form was written."]})
    result = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "kind": "new offline evidence consistency check and corpus extraction",
              "human_participants": 0, "human_times_seconds": None, "real_provider_calls": 0,
              "retained_report_files_checked": indexed,
              "checks": checks, "passed": sum(x["passed"] for x in checks), "total": len(checks),
              "all_passed": all(x["passed"] for x in checks),
              "corpus": {"passed": extraction["passed"], "cases": extraction["cases"]},
              "limits": ["Consistency checks are not a repeated product test suite.",
                         "Historical reports remain historical.",
                         "The extractor parent has socket guards; parser children run the normal local parser.",
                         "Only the new browser cancellation was performed in this persona review."]}
    write(out / "verification.json", result)
    print(json.dumps({k: result[k] for k in ("all_passed", "passed", "total", "retained_report_files_checked", "corpus")}))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
