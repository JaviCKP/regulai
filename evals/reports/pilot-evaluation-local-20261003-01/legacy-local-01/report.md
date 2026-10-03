# Offline evaluation

Preprogrammed provider and judge responses exercise real control flow. They do not measure model precision, factual accuracy or real savings. Live execution is disabled.

Cases: 50. Runs: 150. Real provider cases: 0. Commit: `2c147f40951dc4744a640b268699c1ec941488d8`.

| Configuration | Split | Controls passed | Delivered | Exact answers | Known simulated USD | Unknown cost calls | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 28/30 | 15 | 10 | 0.00594000 | 1 | 328.0 |
| economy | reserved | 20/20 | 8 | 8 | 0.00280000 | 1 | 375.0 |
| economy | all | 48/50 | 23 | 18 | 0.00874000 | 2 | 375.0 |
| strong | development | 28/30 | 17 | 12 | 0.02014000 | 1 | 390.0 |
| strong | reserved | 20/20 | 10 | 10 | 0.00972000 | 1 | 328.0 |
| strong | all | 48/50 | 27 | 22 | 0.02986000 | 2 | 344.0 |
| router | development | 28/30 | 17 | 12 | 0.01306000 | 1 | 437.0 |
| router | reserved | 20/20 | 10 | 10 | 0.00502000 | 1 | 360.0 |
| router | all | 48/50 | 27 | 22 | 0.01808000 | 2 | 390.0 |

Provider/judge answers and token usage are preprogrammed. Exact-answer counts exercise reference-label comparisons, not provider precision. Real quality and savings remain unmeasured.

Masking uses the real local CPU detector. API cost is zero; CPU and operational costs are unmeasured. HTTP masking fixtures are reserved for remote compatibility tests.

Unknown billed calls stay unknown and are excluded from any complete total or cost-per-correct calculation. Latencies are local observations, with the sample size shown; outcome hashes exclude clocks and run identities.

Failed controls (case ID / configuration / observed / expected):

- multi-constraint-es / strong / completed / completed
- multi-constraint-es / router / completed / completed
- multi-constraint-es / economy / completed / completed
- duplicate-request / strong / completed / completed
- duplicate-request / router / completed / completed
- duplicate-request / economy / completed / completed
