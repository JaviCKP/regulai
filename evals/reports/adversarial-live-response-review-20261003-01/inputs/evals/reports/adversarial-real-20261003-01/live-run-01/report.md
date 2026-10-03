# Pilot evaluation

Mode: **real**. Runs: 12. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 4 | 0 | 0 | 6 | 5 | 0.00001590 | 0.000164304 | 0 | 1273.5 | 4141.0 |
| economy | all | 4 | 0 | 0 | 6 | 5 | 0.00001590 | 0.000164304 | 0 | 1273.5 | 4141.0 |
| strong | development | 4 | 0 | 0 | 6 | 5 | 0.00010296 | 0.000164724 | 0 | 1312.0 | 5000.0 |
| strong | all | 4 | 0 | 0 | 6 | 5 | 0.00010296 | 0.000164724 | 0 | 1312.0 | 5000.0 |
| router | development | 4 | 0 | 0 | 8 | 6 | 0.00010170 | 0.000179256 | 0 | 2476.5 | 6844.0 |
| router | all | 4 | 0 | 0 | 8 | 6 | 0.00010170 | 0.000179256 | 0 | 2476.5 | 6844.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Answers and judge results come from the configured live providers. Their outputs do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
