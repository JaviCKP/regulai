# Offline evaluation

Preprogrammed provider and judge responses exercise real control flow. They do not measure model precision, factual accuracy or real savings. Live execution is disabled.

Cases: 50. Runs: 150. Real provider cases: 0. Commit: `52bdc8d71d37dcf40b59293346a4f74f043ef416`.

| Configuration | Split | Controls passed | Delivered | Exact answers | Known simulated USD | Unknown cost calls | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 30/30 | 15 | 12 | 0.00594000 | 1 | 32.0 |
| economy | reserved | 20/20 | 8 | 8 | 0.00280000 | 1 | 32.0 |
| economy | all | 50/50 | 23 | 20 | 0.00874000 | 2 | 32.0 |
| strong | development | 30/30 | 17 | 14 | 0.02014000 | 1 | 32.0 |
| strong | reserved | 20/20 | 10 | 10 | 0.00972000 | 1 | 31.0 |
| strong | all | 50/50 | 27 | 24 | 0.02986000 | 2 | 32.0 |
| router | development | 30/30 | 17 | 14 | 0.01306000 | 1 | 47.0 |
| router | reserved | 20/20 | 10 | 10 | 0.00502000 | 1 | 32.0 |
| router | all | 50/50 | 27 | 24 | 0.01808000 | 2 | 32.0 |

Provider/judge answers and token usage are preprogrammed. Exact-answer counts exercise reference-label comparisons, not provider precision. Real quality and savings remain unmeasured.

Unknown billed calls stay unknown and are excluded from any complete total or cost-per-correct calculation. Latencies are local observations, with the sample size shown; outcome hashes exclude clocks and run identities.

Failed controls (case ID / configuration / observed / expected):
