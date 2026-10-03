# Pilot evaluation

Mode: **simulated**. Runs: 72. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | Calls | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 250.0 | 313.0 |
| economy | reserved | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 250.0 | 328.0 |
| economy | all | 24 | 20 | 0 | 100 | 0.00116400 | 0 | 0 | 250.0 | 313.0 |
| strong | development | 12 | 10 | 0 | 50 | 0.00215400 | 0 | 0 | 257.5 | 344.0 |
| strong | reserved | 12 | 10 | 0 | 50 | 0.00215400 | 0 | 0 | 234.5 | 312.0 |
| strong | all | 24 | 20 | 0 | 100 | 0.00430800 | 0 | 0 | 250.0 | 312.0 |
| router | development | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 242.0 | 297.0 |
| router | reserved | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 266.0 | 360.0 |
| router | all | 24 | 20 | 0 | 100 | 0.00116400 | 0 | 0 | 265.5 | 312.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
