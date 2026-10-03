# Pilot evaluation

Mode: **simulated**. Runs: 72. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | Calls | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 140.5 | 266.0 |
| economy | reserved | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 172.0 | 250.0 |
| economy | all | 24 | 20 | 0 | 100 | 0.00116400 | 0 | 0 | 148.5 | 250.0 |
| strong | development | 12 | 10 | 0 | 50 | 0.00215400 | 0 | 0 | 172.0 | 265.0 |
| strong | reserved | 12 | 10 | 0 | 50 | 0.00215400 | 0 | 0 | 156.0 | 219.0 |
| strong | all | 24 | 20 | 0 | 100 | 0.00430800 | 0 | 0 | 156.0 | 235.0 |
| router | development | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 211.0 | 266.0 |
| router | reserved | 12 | 10 | 0 | 50 | 0.00058200 | 0 | 0 | 187.5 | 359.0 |
| router | all | 24 | 20 | 0 | 100 | 0.00116400 | 0 | 0 | 195.5 | 281.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
