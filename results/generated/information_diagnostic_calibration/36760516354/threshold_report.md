# Task 18 threshold matching (calibration seed)

- Raw rows: 10800; complete grid: True; master seed 20261001; config hash `684093b1031c9d8c59bee1e32204d86a42a37778681b3966a6c8204dcfd09d21`.
- Rule: largest grid t (0.001-0.200, step 0.001) with false-warning rate <= 0.05 on every effect-correct null mechanism (N1-N4) at every N. Warning: status ok and p <= t.
- Calibration results are not evaluation evidence; no gate outcome is declared.

## Thresholds

| Arm | Node | Frozen t | Binding cell (rate at next t) | Pooled-rule t | Per-N t (100 / 250 / 500) |
|---|---|---:|---|---:|---|
| information | outcome | 0.039 | N2_curved_declared N=100 (0.055 at 0.040) | 0.069 | 0.039 / 0.064 / 0.044 |
| conventional | outcome | 0.029 | N2_curved_declared N=500 (0.055 at 0.030) | 0.053 | 0.035 / 0.039 / 0.029 |
| information_insample | outcome | 0.044 | N2_curved_declared N=100 (0.055 at 0.045) | 0.069 | 0.044 / 0.054 / 0.049 |
| information_k20 | outcome | 0.039 | N2_curved_declared N=500 (0.055 at 0.040) | 0.069 | 0.064 / 0.054 / 0.039 |
| information | mediator | 0.064 | N4_heavy_tail N=100 (0.055 at 0.065) | 0.099 | 0.064 / 0.084 / 0.074 |
| conventional | mediator | 0.026 | N2_curved_declared N=250 (0.055 at 0.027) | 0.050 | 0.048 / 0.026 / 0.032 |

## Warning rates at the frozen thresholds (count/datasets, rate [Wilson 95%])

### conventional, mediator node (t = 0.026)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 4/200 = 0.020 [0.008, 0.050] | 3/200 = 0.015 [0.005, 0.043] | 9/200 = 0.045 [0.024, 0.083] |
| N2_curved_declared | effect_correct_null | 2/200 = 0.010 [0.003, 0.036] | 10/200 = 0.050 [0.027, 0.090] | 7/200 = 0.035 [0.017, 0.070] |
| N3_ties | effect_correct_null | 3/200 = 0.015 [0.005, 0.043] | 6/200 = 0.030 [0.014, 0.064] | 8/200 = 0.040 [0.020, 0.077] |
| N4_heavy_tail | effect_correct_null | 4/200 = 0.020 [0.008, 0.050] | 6/200 = 0.030 [0.014, 0.064] | 4/200 = 0.020 [0.008, 0.050] |
| A1_c_only | attribution_null | 1/200 = 0.005 [0.001, 0.028] | 2/200 = 0.010 [0.003, 0.036] | 6/200 = 0.030 [0.014, 0.064] |
| V1_outcome_variance | density_only | 6/200 = 0.030 [0.014, 0.064] | 2/200 = 0.010 [0.003, 0.036] | 5/200 = 0.025 [0.011, 0.057] |
| E1_omitted_quadratic | effect_relevant | 5/200 = 0.025 [0.011, 0.057] | 8/200 = 0.040 [0.020, 0.077] | 4/200 = 0.020 [0.008, 0.050] |
| E2_omitted_interaction | effect_relevant | 5/200 = 0.025 [0.011, 0.057] | 5/200 = 0.025 [0.011, 0.057] | 5/200 = 0.025 [0.011, 0.057] |
| E3_mediator_variance | effect_relevant | 47/200 = 0.235 [0.182, 0.298] | 184/200 = 0.920 [0.874, 0.950] | 200/200 = 1.000 [0.981, 1.000] |

### information, mediator node (t = 0.064)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 2/200 = 0.010 [0.003, 0.036] | 6/200 = 0.030 [0.014, 0.064] | 5/200 = 0.025 [0.011, 0.057] |
| N2_curved_declared | effect_correct_null | 6/200 = 0.030 [0.014, 0.064] | 9/200 = 0.045 [0.024, 0.083] | 9/200 = 0.045 [0.024, 0.083] |
| N3_ties | effect_correct_null | 9/200 = 0.045 [0.024, 0.083] | 3/200 = 0.015 [0.005, 0.043] | 1/200 = 0.005 [0.001, 0.028] |
| N4_heavy_tail | effect_correct_null | 10/200 = 0.050 [0.027, 0.090] | 7/200 = 0.035 [0.017, 0.070] | 10/200 = 0.050 [0.027, 0.090] |
| A1_c_only | attribution_null | 6/200 = 0.030 [0.014, 0.064] | 3/200 = 0.015 [0.005, 0.043] | 6/200 = 0.030 [0.014, 0.064] |
| V1_outcome_variance | density_only | 6/200 = 0.030 [0.014, 0.064] | 4/200 = 0.020 [0.008, 0.050] | 5/200 = 0.025 [0.011, 0.057] |
| E1_omitted_quadratic | effect_relevant | 10/200 = 0.050 [0.027, 0.090] | 12/200 = 0.060 [0.035, 0.102] | 3/200 = 0.015 [0.005, 0.043] |
| E2_omitted_interaction | effect_relevant | 8/200 = 0.040 [0.020, 0.077] | 11/200 = 0.055 [0.031, 0.096] | 3/200 = 0.015 [0.005, 0.043] |
| E3_mediator_variance | effect_relevant | 26/200 = 0.130 [0.090, 0.184] | 92/200 = 0.460 [0.392, 0.529] | 161/200 = 0.805 [0.745, 0.854] |

### conventional, outcome node (t = 0.029)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 9/200 = 0.045 [0.024, 0.083] | 4/200 = 0.020 [0.008, 0.050] | 5/200 = 0.025 [0.011, 0.057] |
| N2_curved_declared | effect_correct_null | 3/200 = 0.015 [0.005, 0.043] | 5/200 = 0.025 [0.011, 0.057] | 10/200 = 0.050 [0.027, 0.090] |
| N3_ties | effect_correct_null | 2/200 = 0.010 [0.003, 0.036] | 1/200 = 0.005 [0.001, 0.028] | 3/200 = 0.015 [0.005, 0.043] |
| N4_heavy_tail | effect_correct_null | 5/200 = 0.025 [0.011, 0.057] | 5/200 = 0.025 [0.011, 0.057] | 7/200 = 0.035 [0.017, 0.070] |
| A1_c_only | attribution_null | 30/200 = 0.150 [0.107, 0.206] | 56/200 = 0.280 [0.222, 0.346] | 98/200 = 0.490 [0.422, 0.559] |
| V1_outcome_variance | density_only | 132/200 = 0.660 [0.592, 0.722] | 200/200 = 1.000 [0.981, 1.000] | 200/200 = 1.000 [0.981, 1.000] |
| E1_omitted_quadratic | effect_relevant | 105/200 = 0.525 [0.456, 0.593] | 190/200 = 0.950 [0.910, 0.973] | 200/200 = 1.000 [0.981, 1.000] |
| E2_omitted_interaction | effect_relevant | 58/200 = 0.290 [0.232, 0.356] | 156/200 = 0.780 [0.718, 0.832] | 195/200 = 0.975 [0.943, 0.989] |
| E3_mediator_variance | effect_relevant | 5/200 = 0.025 [0.011, 0.057] | 4/200 = 0.020 [0.008, 0.050] | 11/200 = 0.055 [0.031, 0.096] |

### information, outcome node (t = 0.039)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 5/200 = 0.025 [0.011, 0.057] | 3/200 = 0.015 [0.005, 0.043] | 5/200 = 0.025 [0.011, 0.057] |
| N2_curved_declared | effect_correct_null | 10/200 = 0.050 [0.027, 0.090] | 5/200 = 0.025 [0.011, 0.057] | 3/200 = 0.015 [0.005, 0.043] |
| N3_ties | effect_correct_null | 7/200 = 0.035 [0.017, 0.070] | 6/200 = 0.030 [0.014, 0.064] | 5/200 = 0.025 [0.011, 0.057] |
| N4_heavy_tail | effect_correct_null | 4/200 = 0.020 [0.008, 0.050] | 5/200 = 0.025 [0.011, 0.057] | 5/200 = 0.025 [0.011, 0.057] |
| A1_c_only | attribution_null | 3/200 = 0.015 [0.005, 0.043] | 2/200 = 0.010 [0.003, 0.036] | 3/200 = 0.015 [0.005, 0.043] |
| V1_outcome_variance | density_only | 5/200 = 0.025 [0.011, 0.057] | 6/200 = 0.030 [0.014, 0.064] | 5/200 = 0.025 [0.011, 0.057] |
| E1_omitted_quadratic | effect_relevant | 18/200 = 0.090 [0.058, 0.138] | 59/200 = 0.295 [0.236, 0.362] | 133/200 = 0.665 [0.597, 0.727] |
| E2_omitted_interaction | effect_relevant | 18/200 = 0.090 [0.058, 0.138] | 50/200 = 0.250 [0.195, 0.314] | 106/200 = 0.530 [0.461, 0.598] |
| E3_mediator_variance | effect_relevant | 6/200 = 0.030 [0.014, 0.064] | 6/200 = 0.030 [0.014, 0.064] | 4/200 = 0.020 [0.008, 0.050] |

### information_insample, outcome node (t = 0.044)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 4/200 = 0.020 [0.008, 0.050] | 4/200 = 0.020 [0.008, 0.050] | 3/200 = 0.015 [0.005, 0.043] |
| N2_curved_declared | effect_correct_null | 9/200 = 0.045 [0.024, 0.083] | 7/200 = 0.035 [0.017, 0.070] | 3/200 = 0.015 [0.005, 0.043] |
| N3_ties | effect_correct_null | 7/200 = 0.035 [0.017, 0.070] | 9/200 = 0.045 [0.024, 0.083] | 6/200 = 0.030 [0.014, 0.064] |
| N4_heavy_tail | effect_correct_null | 7/200 = 0.035 [0.017, 0.070] | 6/200 = 0.030 [0.014, 0.064] | 4/200 = 0.020 [0.008, 0.050] |
| A1_c_only | attribution_null | 2/200 = 0.010 [0.003, 0.036] | 3/200 = 0.015 [0.005, 0.043] | 4/200 = 0.020 [0.008, 0.050] |
| V1_outcome_variance | density_only | 8/200 = 0.040 [0.020, 0.077] | 8/200 = 0.040 [0.020, 0.077] | 5/200 = 0.025 [0.011, 0.057] |
| E1_omitted_quadratic | effect_relevant | 21/200 = 0.105 [0.070, 0.155] | 65/200 = 0.325 [0.264, 0.393] | 134/200 = 0.670 [0.602, 0.731] |
| E2_omitted_interaction | effect_relevant | 22/200 = 0.110 [0.074, 0.161] | 56/200 = 0.280 [0.222, 0.346] | 108/200 = 0.540 [0.471, 0.608] |
| E3_mediator_variance | effect_relevant | 9/200 = 0.045 [0.024, 0.083] | 6/200 = 0.030 [0.014, 0.064] | 5/200 = 0.025 [0.011, 0.057] |

### information_k20, outcome node (t = 0.039)

| Mechanism | Category | N = 100 | N = 250 | N = 500 |
|---|---|---|---|---|
| N1_linear | effect_correct_null | 3/200 = 0.015 [0.005, 0.043] | 4/200 = 0.020 [0.008, 0.050] | 2/200 = 0.010 [0.003, 0.036] |
| N2_curved_declared | effect_correct_null | 5/200 = 0.025 [0.011, 0.057] | 4/200 = 0.020 [0.008, 0.050] | 9/200 = 0.045 [0.024, 0.083] |
| N3_ties | effect_correct_null | 5/200 = 0.025 [0.011, 0.057] | 6/200 = 0.030 [0.014, 0.064] | 5/200 = 0.025 [0.011, 0.057] |
| N4_heavy_tail | effect_correct_null | 7/200 = 0.035 [0.017, 0.070] | 4/200 = 0.020 [0.008, 0.050] | 5/200 = 0.025 [0.011, 0.057] |
| A1_c_only | attribution_null | 2/200 = 0.010 [0.003, 0.036] | 4/200 = 0.020 [0.008, 0.050] | 3/200 = 0.015 [0.005, 0.043] |
| V1_outcome_variance | density_only | 5/200 = 0.025 [0.011, 0.057] | 8/200 = 0.040 [0.020, 0.077] | 3/200 = 0.015 [0.005, 0.043] |
| E1_omitted_quadratic | effect_relevant | 21/200 = 0.105 [0.070, 0.155] | 71/200 = 0.355 [0.292, 0.423] | 137/200 = 0.685 [0.618, 0.745] |
| E2_omitted_interaction | effect_relevant | 29/200 = 0.145 [0.103, 0.200] | 64/200 = 0.320 [0.259, 0.388] | 131/200 = 0.655 [0.587, 0.717] |
| E3_mediator_variance | effect_relevant | 6/200 = 0.030 [0.014, 0.064] | 4/200 = 0.020 [0.008, 0.050] | 6/200 = 0.030 [0.014, 0.064] |
