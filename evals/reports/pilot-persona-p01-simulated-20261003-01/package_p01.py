"""Copy only reviewed non-secret artifacts and record their exact bytes.

This is local packaging, not publication. No DB, media, credential, cookie,
browser-session state or ZIP is read or copied by this script.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


OWNED = Path(__file__).resolve().parent
COPIES = {
    ".playwright-cli/page-2026-10-03T15-55-51-013Z.png": "evidence/document-pending.png",
    ".playwright-cli/page-2026-10-03T15-56-17-768Z.png": "evidence/document-cancelled-top.png",
    ".playwright-cli/page-2026-10-03T15-56-39-270Z.png": "evidence/document-cancelled-calls.png",
    ".playwright-cli/page-2026-10-03T15-55-38-057Z.yml": "evidence/document-pending-snapshot.yml",
    ".playwright-cli/page-2026-10-03T15-56-16-172Z.yml": "evidence/document-cancelled-snapshot.yml",
    ".playwright-cli/page-2026-10-03T15-55-07-550Z.yml": "evidence/offline-banner-snapshot.yml",
    ".playwright-cli/receipt-0d786fda-cbda-4397-af8c-e54ade766b7c.json": "evidence/receipt-document-cancelled.json",
    "browser01/run.json": "evidence/browser-source-manifest.json",
}
PUBLIC = [
    "informe.md", "formulario-simulado.md", "walkthrough.json", "commands.json",
    "browser-observations.json", "cleanup.json", "state-document-pending.json",
    "state-document-cancelled.json", "verification01/extraction.json",
    "verification01/verification.json", "verification01/source-manifest.json",
    "start_isolated_browser.py", "verify_p01.py", "package_p01.py",
    "public-artifacts.json", *COPIES.values(), "artifact-sha256.json",
]


def write(path, value):
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    for source, target in COPIES.items():
        destination = OWNED / target
        destination.parent.mkdir(exist_ok=True)
        with destination.open("xb") as output:
            output.write((OWNED / source).read_bytes())
    write(OWNED / "public-artifacts.json", {
        "schema_version": 1,
        "purpose": "Explicit safe whitelist for root's local report integration; not external publication",
        "recommended_local_report_directory": "evals/reports/pilot-persona-p01-simulated-20261003-01",
        "files_relative_to_p01": PUBLIC,
        "copy_provenance": COPIES,
        "excluded": ["browser01/pilot.sqlite3", "browser01/media", "browser01 except copied run.json",
                     ".playwright-cli except the explicitly copied image/snapshot/download files",
                     "cookies", "browser sessions", "credentials", "keys", "ZIP archives"],
        "external_publication_authorized": False,
        "notes": ["Do not recursively copy p01 or browser01.",
                  "Scripts are execution provenance; rerunning verify_p01.py requires the retained private synthetic DB.",
                  "The recommended destination has the same depth as the source, preserving ../../../ documentation links.",
                  "Paths inside source manifests refer to original observed locations and must not be rewritten as if recaptured."]})
    files = []
    for name in PUBLIC:
        if name == "artifact-sha256.json":
            continue
        content = (OWNED / name).read_bytes()
        files.append({"file": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    write(OWNED / "artifact-sha256.json", {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Explicit local report whitelist excluding this self-referential index",
        "files": files})
    print(json.dumps({"copied_evidence": len(COPIES), "safe_artifacts": len(PUBLIC),
                      "hashed_artifacts": len(files), "private_database_copied": False,
                      "human_validation": False}))


if __name__ == "__main__":
    main()
