# Offline evaluation

Preprogrammed provider and judge responses exercise real control flow. They do not measure model precision, factual accuracy or real savings. Live execution is disabled.

Cases: 50. Runs: 150. Real provider cases: 0. Commit: `4400f0bb24defef5d3b8f0d10c391565511f52a2`.

| Configuration | Split | Controls passed | Delivered | Exact answers | Known simulated USD | Unknown cost calls | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | development | 30/30 | 12 | 12 | 0.00534000 | 1 | 31.0 |
| economy | reserved | 20/20 | 8 | 8 | 0.00292000 | 1 | 31.0 |
| economy | all | 50/50 | 20 | 20 | 0.00826000 | 2 | 31.0 |
| strong | development | 30/30 | 14 | 14 | 0.01786000 | 1 | 32.0 |
| strong | reserved | 20/20 | 10 | 10 | 0.00984000 | 1 | 31.0 |
| strong | all | 50/50 | 24 | 24 | 0.02770000 | 2 | 32.0 |
| router | development | 30/30 | 14 | 14 | 0.01246000 | 1 | 32.0 |
| router | reserved | 20/20 | 10 | 10 | 0.00514000 | 1 | 32.0 |
| router | all | 50/50 | 24 | 24 | 0.01760000 | 2 | 32.0 |

Provider/judge answers and token usage are preprogrammed. Exact-answer counts exercise reference-label comparisons, not provider precision. Real quality and savings remain unmeasured.

Unknown billed calls stay unknown and are excluded from any complete total or cost-per-correct calculation. Latencies are local observations, with the sample size shown; outcome hashes exclude clocks and run identities.

Failed controls (case ID / configuration / observed / expected):

