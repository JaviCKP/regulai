# Pilot evaluation

Mode: **real**. Runs: 12. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 4 | 0 | 0 | 6 | 5 | 0.00021240 | 0.000184128 | 0 | 1187.5 | 3563.0 |
| economy | all | 4 | 0 | 0 | 6 | 5 | 0.00021240 | 0.000184128 | 0 | 1187.5 | 3563.0 |
| strong | development | 4 | 0 | 0 | 5 | 5 | 0.00054120 | 0.000150906 | 0 | 1023.5 | 3031.0 |
| strong | all | 4 | 0 | 0 | 5 | 5 | 0.00054120 | 0.000150906 | 0 | 1023.5 | 3031.0 |
| router | development | 4 | 0 | 0 | 8 | 6 | 0.00102024 | 0.000212856 | 0 | 1898.5 | 7296.0 |
| router | all | 4 | 0 | 0 | 8 | 6 | 0.00102024 | 0.000212856 | 0 | 1898.5 | 7296.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Answers and judge results come from the configured live providers. Their outputs do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
