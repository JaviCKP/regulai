# Pilot evaluation

Mode: **real**. Runs: 8. Human review is separate; no quality or savings claim.

| Configuration | Split | n | Delivered | Human reviewed | External calls | Local transformations | Estimated USD | Reported USD | Uncertain reserve USD | p50 ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 2 | 0 | 0 | 4 | 3 | 0.00010230 | 0.000096432 | 0 | 2437.0 | 3781.0 |
| economy | all | 2 | 0 | 0 | 4 | 3 | 0.00010230 | 0.000096432 | 0 | 2437.0 | 3781.0 |
| strong | development | 2 | 1 | 0 | 4 | 3 | 0.00006336 | 0.000050106 | 0.003 | 2562.5 | 4109.0 |
| strong | all | 2 | 1 | 0 | 4 | 3 | 0.00006336 | 0.000050106 | 0.003 | 2562.5 | 4109.0 |
| router | development | 4 | 1 | 0 | 9 | 6 | 0.00057930 | 0.000165984 | 0 | 4008.0 | 6828.0 |
| router | all | 4 | 1 | 0 | 9 | 6 | 0.00057930 | 0.000165984 | 0 | 4008.0 | 6828.0 |

Per-case answers, citations, sensitivity, coverage, attempts and all calls are in results.jsonl. These are synthetic data.
Answers and judge results come from the configured live providers. Their outputs do not establish provider quality. Cost per correct answer stays null until complete independent human review and complete cost information.
When masking_backend is local, masking uses the real CPU detector. Its API cost is zero; CPU, memory and operational costs are not measured. Local transformations are excluded from external call counts.
An estimated price is not an invoice; unknown expenses retain their full reservation. p50/p95 are observations of this sample, not an SLA.
Stop reason: failed_or_uncertain_provider_call.
