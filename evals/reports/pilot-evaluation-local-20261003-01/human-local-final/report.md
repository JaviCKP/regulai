# Pilot evaluation

Mode: **simulated**. Runs: 72. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 398.5 | 593.0 |
| economy | reserved | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 398.5 | 484.0 |
| economy | all | 24 | 20 | 0 | 60 | 40 | 0.00116400 | 0 | 0 | 398.5 | 563.0 |
| strong | development | 12 | 10 | 0 | 30 | 20 | 0.00215400 | 0 | 0 | 422.0 | 829.0 |
| strong | reserved | 12 | 10 | 0 | 30 | 20 | 0.00215400 | 0 | 0 | 398.5 | 2844.0 |
| strong | all | 24 | 20 | 0 | 60 | 40 | 0.00430800 | 0 | 0 | 406.0 | 829.0 |
| router | development | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 430.0 | 547.0 |
| router | reserved | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 429.5 | 766.0 |
| router | all | 24 | 20 | 0 | 60 | 40 | 0.00116400 | 0 | 0 | 429.5 | 578.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
