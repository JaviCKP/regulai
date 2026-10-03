# Offline evaluation

Preprogrammed provider and judge responses exercise real control flow. They do not measure model precision, factual accuracy or real savings. Live execution is disabled.

Cases: 50. Runs: 150. Real provider cases: 0. Commit: `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`.

| Configuration | Split | Controls passed | Delivered | Exact answers | Known simulated USD | Unknown cost calls | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 30/30 | 15 | 12 | 0.00594000 | 1 | 93.0 |
| economy | reserved | 20/20 | 8 | 8 | 0.00280000 | 1 | 93.0 |
| economy | all | 50/50 | 23 | 20 | 0.00874000 | 2 | 93.0 |
| strong | development | 30/30 | 17 | 14 | 0.02014000 | 1 | 94.0 |
| strong | reserved | 20/20 | 10 | 10 | 0.00972000 | 1 | 109.0 |
| strong | all | 50/50 | 27 | 24 | 0.02986000 | 2 | 109.0 |
| router | development | 30/30 | 17 | 14 | 0.01306000 | 1 | 125.0 |
| router | reserved | 20/20 | 10 | 10 | 0.00502000 | 1 | 110.0 |
| router | all | 50/50 | 27 | 24 | 0.01808000 | 2 | 125.0 |

Provider/judge answers and token usage are preprogrammed. Exact-answer counts exercise reference-label comparisons, not provider precision. Real quality and savings remain unmeasured.

This legacy regression bank uses an identity HTTP masking fixture to preserve its original literal-output contract. New pilot-real and pilot-human manifests use the real local CPU detector and report its transformations separately.

Unknown billed calls stay unknown and are excluded from any complete total or cost-per-correct calculation. Latencies are local observations, with the sample size shown; outcome hashes exclude clocks and run identities.

Failed controls (case ID / configuration / observed / expected):

