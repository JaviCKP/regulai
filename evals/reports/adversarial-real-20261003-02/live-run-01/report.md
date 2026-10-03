# Pilot evaluation

Mode: **real**. Runs: 12. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 4 | 0 | 0 | 8 | 6 | 0.00059730 | 0.000209916 | 0 | 2594.0 | 5078.0 |
| economy | all | 4 | 0 | 0 | 8 | 6 | 0.00059730 | 0.000209916 | 0 | 2594.0 | 5078.0 |
| strong | development | 4 | 0 | 0 | 8 | 6 | 0.00187044 | 0.000206346 | 0 | 2820.0 | 6813.0 |
| strong | all | 4 | 0 | 0 | 8 | 6 | 0.00187044 | 0.000206346 | 0 | 2820.0 | 6813.0 |
| router | development | 4 | 1 | 0 | 10 | 7 | 0.00132204 | 0.000224070 | 0 | 4328.0 | 8031.0 |
| router | all | 4 | 1 | 0 | 10 | 7 | 0.00132204 | 0.000224070 | 0 | 4328.0 | 8031.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Answers and judge results come from the configured live providers. Their outputs do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
