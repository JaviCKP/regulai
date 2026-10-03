# Pilot evaluation

Mode: **simulated**. Runs: 72. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 414.0 | 859.0 |
| economy | reserved | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 422.0 | 485.0 |
| economy | all | 24 | 20 | 0 | 60 | 40 | 0.00116400 | 0 | 0 | 422.0 | 625.0 |
| strong | development | 12 | 10 | 0 | 30 | 20 | 0.00215400 | 0 | 0 | 414.0 | 640.0 |
| strong | reserved | 12 | 10 | 0 | 30 | 20 | 0.00215400 | 0 | 0 | 445.5 | 3532.0 |
| strong | all | 24 | 20 | 0 | 60 | 40 | 0.00430800 | 0 | 0 | 430.0 | 640.0 |
| router | development | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 421.5 | 562.0 |
| router | reserved | 12 | 10 | 0 | 30 | 20 | 0.00058200 | 0 | 0 | 414.5 | 641.0 |
| router | all | 24 | 20 | 0 | 60 | 40 | 0.00116400 | 0 | 0 | 421.5 | 562.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Simulator answers and judges are fixtures. Their labels do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: none.
