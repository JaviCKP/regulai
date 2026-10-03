# Pilot evaluation

Mode: **simulated**. Runs: 24. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | Calls | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 8 | 4 | 0 | 29 | 0.00034710 | 0 | 0 | 242.5 | 328.0 |
| economy | all | 8 | 4 | 0 | 29 | 0.00034710 | 0 | 0 | 242.5 | 328.0 |
| strong | development | 8 | 5 | 0 | 29 | 0.00129030 | 0 | 0 | 250.0 | 297.0 |
| strong | all | 8 | 5 | 0 | 29 | 0.00129030 | 0 | 0 | 250.0 | 297.0 |
| router | development | 8 | 5 | 0 | 34 | 0.00077160 | 0 | 0 | 219.0 | 484.0 |
| router | all | 8 | 5 | 0 | 34 | 0.00077160 | 0 | 0 | 219.0 | 484.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
