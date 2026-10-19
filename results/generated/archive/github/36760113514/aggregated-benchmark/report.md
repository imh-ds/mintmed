# Information diagnostic run: mintmed_information_diagnostic_pilot

- Config hash: `916234ef8ecefcebf616bf807fbea253a5d8bb4fe1fbbdaef4eaa008fdf06428`; master seed 20260930.
- Rows: 216 of 216; complete grid: **True**.
- Rates below use the *nominal* rule p <= 0.05 and are descriptive only. Calibrated thresholds come from `scripts/calibrate_diagnostic_thresholds.py` on the calibration seed.

## Rejections at nominal 0.05 (count / datasets)

### outcome node

| Mechanism | N | information | conventional | information_insample | information_k20 | info unavailable |
|---|---:|---:|---:|---:|---:|---:|
| A1_c_only | 100 | 1/4 | 1/4 | 1/4 | 1/4 | 0 |
| A1_c_only | 250 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| A1_c_only | 500 | 0/4 | 3/4 | 0/4 | 0/4 | 0 |
| E1_omitted_quadratic | 100 | 1/4 | 3/4 | 1/4 | 0/4 | 0 |
| E1_omitted_quadratic | 250 | 1/4 | 4/4 | 1/4 | 1/4 | 0 |
| E1_omitted_quadratic | 500 | 2/4 | 4/4 | 2/4 | 2/4 | 0 |
| E2_omitted_interaction | 100 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| E2_omitted_interaction | 250 | 1/4 | 2/4 | 1/4 | 2/4 | 0 |
| E2_omitted_interaction | 500 | 4/4 | 4/4 | 3/4 | 4/4 | 0 |
| E3_mediator_variance | 100 | 0/4 | 1/4 | 0/4 | 0/4 | 0 |
| E3_mediator_variance | 250 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| E3_mediator_variance | 500 | 1/4 | 0/4 | 0/4 | 0/4 | 0 |
| N1_linear | 100 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N1_linear | 250 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N1_linear | 500 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 100 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 250 | 1/4 | 0/4 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 500 | 1/4 | 1/4 | 0/4 | 0/4 | 0 |
| N3_ties | 100 | 0/4 | 0/4 | 0/4 | 1/4 | 0 |
| N3_ties | 250 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N3_ties | 500 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N4_heavy_tail | 100 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N4_heavy_tail | 250 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| N4_heavy_tail | 500 | 0/4 | 0/4 | 0/4 | 0/4 | 0 |
| V1_outcome_variance | 100 | 0/4 | 4/4 | 0/4 | 0/4 | 0 |
| V1_outcome_variance | 250 | 0/4 | 4/4 | 0/4 | 0/4 | 0 |
| V1_outcome_variance | 500 | 0/4 | 4/4 | 0/4 | 0/4 | 0 |

### mediator node

| Mechanism | N | information | conventional | info unavailable |
|---|---:|---:|---:|---:|
| A1_c_only | 100 | 0/4 | 0/4 | 0 |
| A1_c_only | 250 | 0/4 | 1/4 | 0 |
| A1_c_only | 500 | 0/4 | 0/4 | 0 |
| E1_omitted_quadratic | 100 | 0/4 | 1/4 | 0 |
| E1_omitted_quadratic | 250 | 0/4 | 0/4 | 0 |
| E1_omitted_quadratic | 500 | 0/4 | 0/4 | 0 |
| E2_omitted_interaction | 100 | 0/4 | 0/4 | 0 |
| E2_omitted_interaction | 250 | 0/4 | 0/4 | 0 |
| E2_omitted_interaction | 500 | 1/4 | 0/4 | 0 |
| E3_mediator_variance | 100 | 0/4 | 1/4 | 0 |
| E3_mediator_variance | 250 | 2/4 | 4/4 | 0 |
| E3_mediator_variance | 500 | 2/4 | 4/4 | 0 |
| N1_linear | 100 | 0/4 | 0/4 | 0 |
| N1_linear | 250 | 0/4 | 0/4 | 0 |
| N1_linear | 500 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 100 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 250 | 0/4 | 0/4 | 0 |
| N2_curved_declared | 500 | 0/4 | 0/4 | 0 |
| N3_ties | 100 | 0/4 | 0/4 | 0 |
| N3_ties | 250 | 0/4 | 0/4 | 0 |
| N3_ties | 500 | 0/4 | 0/4 | 0 |
| N4_heavy_tail | 100 | 0/4 | 1/4 | 0 |
| N4_heavy_tail | 250 | 0/4 | 0/4 | 0 |
| N4_heavy_tail | 500 | 0/4 | 0/4 | 0 |
| V1_outcome_variance | 100 | 0/4 | 0/4 | 0 |
| V1_outcome_variance | 250 | 1/4 | 1/4 | 0 |
| V1_outcome_variance | 500 | 0/4 | 0/4 | 0 |

## Runtime per dataset (seconds)

| N | Node | Check | Mean | Median | p95 | Max |
|---:|---|---|---:|---:|---:|---:|
| 100 | mediator | information | 0.116 | 0.131 | 0.140 | 0.149 |
| 100 | mediator | conventional | 0.009 | 0.009 | 0.010 | 0.011 |
| 100 | mediator | node_total | 0.125 | 0.140 | 0.151 | 0.159 |
| 100 | outcome | information | 0.123 | 0.133 | 0.154 | 0.156 |
| 100 | outcome | information_insample | 0.122 | 0.132 | 0.150 | 0.152 |
| 100 | outcome | information_k20 | 0.131 | 0.145 | 0.161 | 0.164 |
| 100 | outcome | conventional | 0.010 | 0.011 | 0.012 | 0.012 |
| 100 | outcome | node_total | 0.386 | 0.424 | 0.480 | 0.483 |
| 250 | mediator | information | 0.406 | 0.445 | 0.489 | 0.522 |
| 250 | mediator | conventional | 0.009 | 0.009 | 0.010 | 0.011 |
| 250 | mediator | node_total | 0.415 | 0.455 | 0.500 | 0.532 |
| 250 | outcome | information | 0.331 | 0.363 | 0.398 | 0.413 |
| 250 | outcome | information_insample | 0.331 | 0.363 | 0.399 | 0.416 |
| 250 | outcome | information_k20 | 0.413 | 0.447 | 0.504 | 0.519 |
| 250 | outcome | conventional | 0.010 | 0.011 | 0.012 | 0.012 |
| 250 | outcome | node_total | 1.086 | 1.184 | 1.313 | 1.359 |
| 500 | mediator | information | 1.268 | 1.371 | 1.516 | 1.674 |
| 500 | mediator | conventional | 0.009 | 0.009 | 0.011 | 0.011 |
| 500 | mediator | node_total | 1.277 | 1.382 | 1.526 | 1.684 |
| 500 | outcome | information | 0.908 | 0.984 | 1.129 | 1.239 |
| 500 | outcome | information_insample | 0.905 | 0.988 | 1.138 | 1.240 |
| 500 | outcome | information_k20 | 1.221 | 1.314 | 1.500 | 1.685 |
| 500 | outcome | conventional | 0.010 | 0.011 | 0.012 | 0.013 |
| 500 | outcome | node_total | 3.045 | 3.300 | 3.779 | 4.177 |
