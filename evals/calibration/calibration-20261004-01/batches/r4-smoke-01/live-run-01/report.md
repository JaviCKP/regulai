# Pilot evaluation

Mode: **real**. Runs: 5. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 1 | 1 | 0 | 3 | 2 | 0.00001890 | 0.000050946 | 0 | 3812.0 | 3812.0 |
| economy | all | 1 | 1 | 0 | 3 | 2 | 0.00001890 | 0.000050946 | 0 | 3812.0 | 3812.0 |
| strong | development | 1 | 0 | 0 | 1 | 1 | 0 | 0.000035784 | 0 | 1016.0 | 1016.0 |
| strong | all | 1 | 0 | 0 | 1 | 1 | 0 | 0.000035784 | 0 | 1016.0 | 1016.0 |
| router | development | 3 | 0 | 0 | 7 | 5 | 0.00115884 | 0.000146454 | 0.003 | 2938.0 | 7390.0 |
| router | all | 3 | 0 | 0 | 7 | 5 | 0.00115884 | 0.000146454 | 0.003 | 2938.0 | 7390.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Answers and judge results come from the configured live providers. Their outputs do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: failed_or_uncertain_provider_call.
