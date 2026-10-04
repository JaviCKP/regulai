# Pilot evaluation

Mode: **simulated**. Runs: 12. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 4 | 4 | 0 | 12 | 8 | 0.00023280 | 0 | 0 | 226.0 | 250.0 |
| economy | all | 4 | 4 | 0 | 12 | 8 | 0.00023280 | 0 | 0 | 226.0 | 250.0 |
| strong | development | 4 | 4 | 0 | 12 | 8 | 0.00086160 | 0 | 0 | 219.0 | 219.0 |
| strong | all | 4 | 4 | 0 | 12 | 8 | 0.00086160 | 0 | 0 | 219.0 | 219.0 |
| router | development | 4 | 4 | 0 | 12 | 8 | 0.00023280 | 0 | 0 | 219.0 | 3328.0 |
| router | all | 4 | 4 | 0 | 12 | 8 | 0.00023280 | 0 | 0 | 219.0 | 3328.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
