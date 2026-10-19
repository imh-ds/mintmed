# Information diagnostic run: mintmed_information_diagnostic_calibration

- Config hash: `684093b1031c9d8c59bee1e32204d86a42a37778681b3966a6c8204dcfd09d21`; master seed 20261001.
- Rows: 10800 of 10800; complete grid: **True**.
- Rates below use the *nominal* rule p <= 0.05 and are descriptive only. Calibrated thresholds come from `scripts/calibrate_diagnostic_thresholds.py` on the calibration seed.

## Rejections at nominal 0.05 (count / datasets)

### outcome node

| Mechanism | N | information | conventional | information_insample | information_k20 | info unavailable |
|---|---:|---:|---:|---:|---:|---:|
| A1_c_only | 100 | 4/200 | 35/200 | 5/200 | 5/200 | 0 |
| A1_c_only | 250 | 5/200 | 65/200 | 3/200 | 5/200 | 0 |
| A1_c_only | 500 | 4/200 | 118/200 | 4/200 | 4/200 | 0 |
| E1_omitted_quadratic | 100 | 28/200 | 117/200 | 26/200 | 26/200 | 0 |
| E1_omitted_quadratic | 250 | 66/200 | 193/200 | 71/200 | 77/200 | 0 |
| E1_omitted_quadratic | 500 | 142/200 | 200/200 | 146/200 | 151/200 | 0 |
| E2_omitted_interaction | 100 | 25/200 | 76/200 | 25/200 | 37/200 | 0 |
| E2_omitted_interaction | 250 | 62/200 | 166/200 | 58/200 | 82/200 | 0 |
| E2_omitted_interaction | 500 | 117/200 | 198/200 | 116/200 | 141/200 | 0 |
| E3_mediator_variance | 100 | 7/200 | 11/200 | 13/200 | 7/200 | 0 |
| E3_mediator_variance | 250 | 8/200 | 9/200 | 9/200 | 5/200 | 0 |
| E3_mediator_variance | 500 | 5/200 | 12/200 | 5/200 | 8/200 | 0 |
| N1_linear | 100 | 7/200 | 12/200 | 4/200 | 5/200 | 0 |
| N1_linear | 250 | 5/200 | 10/200 | 4/200 | 8/200 | 0 |
| N1_linear | 500 | 6/200 | 10/200 | 4/200 | 3/200 | 0 |
| N2_curved_declared | 100 | 11/200 | 6/200 | 11/200 | 7/200 | 0 |
| N2_curved_declared | 250 | 8/200 | 12/200 | 8/200 | 6/200 | 0 |
| N2_curved_declared | 500 | 7/200 | 15/200 | 5/200 | 12/200 | 0 |
| N3_ties | 100 | 9/200 | 5/200 | 8/200 | 7/200 | 0 |
| N3_ties | 250 | 9/200 | 4/200 | 10/200 | 7/200 | 0 |
| N3_ties | 500 | 15/200 | 7/200 | 11/200 | 8/200 | 0 |
| N4_heavy_tail | 100 | 4/200 | 11/200 | 8/200 | 9/200 | 0 |
| N4_heavy_tail | 250 | 6/200 | 7/200 | 7/200 | 10/200 | 0 |
| N4_heavy_tail | 500 | 8/200 | 12/200 | 5/200 | 6/200 | 0 |
| V1_outcome_variance | 100 | 7/200 | 155/200 | 9/200 | 5/200 | 0 |
| V1_outcome_variance | 250 | 11/200 | 200/200 | 10/200 | 11/200 | 0 |
| V1_outcome_variance | 500 | 7/200 | 200/200 | 5/200 | 5/200 | 0 |

### mediator node

| Mechanism | N | information | conventional | info unavailable |
|---|---:|---:|---:|---:|
| A1_c_only | 100 | 3/200 | 5/200 | 0 |
| A1_c_only | 250 | 2/200 | 10/200 | 0 |
| A1_c_only | 500 | 4/200 | 8/200 | 0 |
| E1_omitted_quadratic | 100 | 9/200 | 10/200 | 0 |
| E1_omitted_quadratic | 250 | 11/200 | 12/200 | 0 |
| E1_omitted_quadratic | 500 | 2/200 | 9/200 | 0 |
| E2_omitted_interaction | 100 | 7/200 | 8/200 | 0 |
| E2_omitted_interaction | 250 | 8/200 | 11/200 | 0 |
| E2_omitted_interaction | 500 | 2/200 | 10/200 | 0 |
| E3_mediator_variance | 100 | 23/200 | 75/200 | 0 |
| E3_mediator_variance | 250 | 85/200 | 193/200 | 0 |
| E3_mediator_variance | 500 | 153/200 | 200/200 | 0 |
| N1_linear | 100 | 2/200 | 11/200 | 0 |
| N1_linear | 250 | 6/200 | 6/200 | 0 |
| N1_linear | 500 | 3/200 | 12/200 | 0 |
| N2_curved_declared | 100 | 6/200 | 9/200 | 0 |
| N2_curved_declared | 250 | 8/200 | 18/200 | 0 |
| N2_curved_declared | 500 | 9/200 | 9/200 | 0 |
| N3_ties | 100 | 8/200 | 8/200 | 0 |
| N3_ties | 250 | 3/200 | 8/200 | 0 |
| N3_ties | 500 | 1/200 | 13/200 | 0 |
| N4_heavy_tail | 100 | 7/200 | 9/200 | 0 |
| N4_heavy_tail | 250 | 7/200 | 9/200 | 0 |
| N4_heavy_tail | 500 | 8/200 | 7/200 | 0 |
| V1_outcome_variance | 100 | 5/200 | 9/200 | 0 |
| V1_outcome_variance | 250 | 2/200 | 7/200 | 0 |
| V1_outcome_variance | 500 | 5/200 | 8/200 | 0 |

## Runtime per dataset (seconds)

| N | Node | Check | Mean | Median | p95 | Max |
|---:|---|---|---:|---:|---:|---:|
| 100 | mediator | information | 0.124 | 0.132 | 0.136 | 0.156 |
| 100 | mediator | conventional | 0.009 | 0.009 | 0.011 | 0.068 |
| 100 | mediator | node_total | 0.134 | 0.141 | 0.148 | 0.190 |
| 100 | outcome | information | 0.130 | 0.131 | 0.150 | 0.247 |
| 100 | outcome | information_insample | 0.130 | 0.131 | 0.150 | 0.175 |
| 100 | outcome | information_k20 | 0.140 | 0.142 | 0.160 | 0.182 |
| 100 | outcome | conventional | 0.010 | 0.010 | 0.012 | 0.023 |
| 100 | outcome | node_total | 0.411 | 0.415 | 0.474 | 0.588 |
| 250 | mediator | information | 0.431 | 0.445 | 0.475 | 0.492 |
| 250 | mediator | conventional | 0.009 | 0.009 | 0.011 | 0.020 |
| 250 | mediator | node_total | 0.440 | 0.455 | 0.484 | 0.502 |
| 250 | outcome | information | 0.351 | 0.362 | 0.393 | 0.433 |
| 250 | outcome | information_insample | 0.351 | 0.362 | 0.393 | 0.415 |
| 250 | outcome | information_k20 | 0.434 | 0.447 | 0.483 | 0.537 |
| 250 | outcome | conventional | 0.010 | 0.010 | 0.012 | 0.015 |
| 250 | outcome | node_total | 1.147 | 1.182 | 1.279 | 1.355 |
| 500 | mediator | information | 1.345 | 1.373 | 1.473 | 1.572 |
| 500 | mediator | conventional | 0.009 | 0.009 | 0.011 | 0.015 |
| 500 | mediator | node_total | 1.355 | 1.383 | 1.483 | 1.582 |
| 500 | outcome | information | 0.956 | 0.979 | 1.060 | 1.131 |
| 500 | outcome | information_insample | 0.956 | 0.978 | 1.057 | 1.134 |
| 500 | outcome | information_k20 | 1.286 | 1.317 | 1.424 | 1.549 |
| 500 | outcome | conventional | 0.010 | 0.011 | 0.012 | 0.023 |
| 500 | outcome | node_total | 3.209 | 3.291 | 3.538 | 3.767 |
