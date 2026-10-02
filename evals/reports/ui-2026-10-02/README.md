# Browser verification — 2026-10-02

Executed in the Codex in-app browser against local Django servers. All data is synthetic.

| Scenario | Observed result |
| --- | --- |
| Offline login and greeting | `community-demo` logged in; the greeting returned `Hola`. The banner explicitly labels simulated providers. |
| Automatic document route | Uploaded `evals/documents/demo-contract.txt`; requested its price. Receipt records classification, economy generation, failed verification, stronger generation, verification: five calls, two generations. Final answer `10 euros [1]`; retained fragment `line:2`, `cuesta 10 euros.` |
| Reload saved conversation | Answer, receipt and retained citation loaded again from authenticated endpoints. Original file is not retained for later model context; UI requests reattachment. |
| Secret marker | `SYNTHETIC_SECRET_DEMO` blocked by local rule; receipt: zero calls, zero cost. |
| Cancel confirmation | `SYNTHETIC_CONSENT: responde Hola.` entered pending consent with zero calls; cancellation finished as `cancelled`, without an assistant response. |
| Confirm multipart request | Uploaded the same contract with `SYNTHETIC_CONSENT: ¿Cuál es el precio del contrato?`; confirmed once. The original attachment survived; one user bubble and one final assistant response, `10 euros [1]`, with the correct quote. |
| Simulator comparison and activation | Separate local company with no provider credentials or destinations. Compared an internal draft with a restricted draft; both blocked with their respective reasons. Semantic classification explicitly not evaluated, zero real calls. Separate activation showed success and revision 2. |
| Layout and assets | Repaired missing local jQuery/Bootstrap/Simplebar assets, wrapped controls for narrow view, corrected blocked-message contrast and document-format guidance. Inspected rendered chat and simulator screenshots. |
| Keyboard | Enter in the message field sent the greeting; Enter expanded its receipt, showing automatic economy routing and three simulated calls. Space toggled the automatic selector off/on; restored on. Keyboard activation inside the citation detail remains unverified: after the browser session reset, the browser tool's URL policy rejected reopening the local tab. No workaround was attempted. |

Screenshots: [confirmed document](confirmed-document.jpg), [blocked](blocked.jpg), [simulator activation](simulator-activated.jpg), [persisted evidence](document-evidence.jpg). The last image predates the final responsive layout adjustment; the confirmed-document image shows the final layout.

This is an agent-driven functional UI check, not two human rehearsals or a real-model quality measurement. Costs in the offline demo are fixture calculations. Real smoke evidence is in the adjacent real-smoke reports and combined budget snapshot.

Installation was separately reproduced with `uv venv --python 3.12.11 .claude/reproduction-venv-20261002` and `uv pip sync --python .claude/reproduction-venv-20261002/Scripts/python.exe requirements.txt`. All 45 packages installed; the full 129-test suite passed in 39.764 seconds, including the three automated demo scenarios. `run_demo --settings=regulai.demo_settings --seed-only` and Django `check` succeeded in that environment. Browser checks above used the primary `.venv` with the same pinned dependencies and source.
