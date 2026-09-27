# Mintmed baseline evidence (research beta)

This report summarizes the evidence from the Task 15 validation matrix, which is fixed by [`baseline_release_charter.md`](baseline_release_charter.md).

**Headline: the pre-registered validation did not pass.**
- Point estimates were essentially unbiased in all 12 cells.
- The pre-registered **coverage gate failed**. Mean interval coverage was 94.8% across the 32 gated effects. Two indirect-effect intervals under-cover beyond chance: cell 08 (quadratic outcome) and cell 11 (binary mediator).
- A bias-corrected interval was tested as the charter's one permitted correction. It did not fix the failure and was not adopted ([`interval_correction_check.md`](interval_correction_check.md)). The one correction was not used, and there is no run 2.

Mintmed is therefore released as a **research beta**. Its intervals are **not** validated to the pre-registered standard. Passing broad gates, where they were passed, does not establish that Mintmed is adequate for every design, or better than other methods.

| Source | Contents |
|---|---|
| [`baseline_run1_results.md`](baseline_run1_results.md) | The permanent record of run 1 and its gate results. |
| [`interval_correction_check.md`](interval_correction_check.md) | The BC/BCa check and why it was not adopted. |
| [`runtime_pilot.md`](runtime_pilot.md) | The accepted runtime forecast. |
| GitHub artifact `aggregated-benchmark`, run `36296143027` | Raw results (2,400 rows). A git-ignored local copy is in `results/generated/validation-matrix-36296143027/`. |

## Run identity

| Item | Value |
|---|---|
| Run | `.github/workflows/sharded_benchmark.yml`, run `36296143027`, 48 shards |
| Dispatched commit | `04cbf2d` (the charter commit) |
| Platform | GitHub Actions `ubuntu-latest`, Linux x86-64, Python 3.11.16 |
| Configuration hash | `176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94`, a single hash across all rows, matching the charter |
| Grid | 2,400 of 2,400 expected rows. 0 duplicates, 0 missing. |
| Rerun | None. The one-correction rule was not used (see [`interval_correction_check.md`](interval_correction_check.md)). |

## Supported, limited and unsupported designs

"Validated" below means only **the exact cell**: its generating model, node families, terms and sample size. It does not extend to other designs.

| Cell | Design | N | Point estimates | Intervals |
|---|---|---:|---|---|
| 01 | One mediator, linear | 100 | Unbiased | Consistent with 95% |
| 02 | One mediator, linear | 250 | Unbiased | Consistent with 95% |
| 03 | No A → M path (null TNIE) | 100 | Unbiased | Consistent with 95%; null TNIE is a structural zero* |
| 04 | No M → Y path (null TNIE) | 100 | Unbiased | Consistent with 95%; null TNIE is a structural zero* |
| 05 | No mediation (null TNIE) | 100 | Unbiased | Consistent with 95%; null TNIE is a structural zero* |
| 06 | Two correlated parallel mediators with M1 × M2 interaction (joint TNIE) | 150 | Unbiased | Consistent with 95% |
| 07 | Three serial Gaussian mediators | 200 | Unbiased | Consistent with 95% |
| 08 | One mediator, quadratic outcome | 100 | Unbiased | **TNIE under-covers (91.5%)**; TE and PNDE consistent with 95% |
| 09 | One mediator, natural-spline outcome (df = 3) | 250 | Unbiased | Consistent with 95% |
| 10 | Binary moderator of A → M and M → Y | 150 | Unbiased | Paired W1 − W0 difference consistent with 95%. TNIE at each W is point-only. |
| 11 | Binary mediator, Gaussian outcome | 150 | Unbiased | **TNIE under-covers (89.5%)**; TE and PNDE consistent with 95% |
| 12 | Binary and Gaussian serial mediators, binary outcome | 250 | Unbiased | Consistent with 95% |

**How the labels were assigned.** "Consistent with 95%" and "under-covers" are descriptive, not gates. They mark whether an exact one-sided binomial test against 95% coverage gives p < 0.05. Only cell 11 TNIE (p = 0.001) and cell 08 TNIE (p = 0.024) do; the next lowest is cell 07 TE, at p = 0.078. No effect was tested against a multiple-comparison correction. Under the pre-registered gate, 16 of 32 effects fell short (see [Coverage](#coverage)).

\* **Structural zeros.** In cells 03–05, the declared models omit the null path, so the TNIE is zero by construction: the width is 0 and the error is 0. These cells test how Mintmed handles structurally absent paths. They do **not** test how well it detects a null indirect effect when the model includes both paths.

**Unvalidated.** Mintmed runs these, but this matrix does not validate them:
- four-mediator inference;
- continuous exposures;
- continuous moderators and declared moderator evaluation values;
- categorical predictors with more than two levels;
- individual parallel contributions;
- the `assumption_based_causal` interpretation, which rests on untestable assumptions;
- samples below 100.

**Unsupported.** Repeated, clustered or multilevel rows; latent measurement models; ordinal and count nodes; automatic term or smoothness selection.

## Known limitation: skewed indirect effects

When the sampling distribution of the indirect effect is skewed, the percentile bootstrap interval for the TNIE under-covers. This happened with a quadratic outcome (cell 08, N = 100) and a binary mediator (cell 11, N = 150):
- The observed coverage was 89.5–91.5% rather than 95%.
- The misses fall mostly on one side: in cell 11 the truth lay above the interval 15 times and below it 6 times.

BC and BCa intervals balanced the misses, but raised coverage only to 92–93.5% ([`interval_correction_check.md`](interval_correction_check.md)).

**What to do:** treat TNIE intervals in comparable designs, such as nonlinear outcomes, binary mediators or modest N, as somewhat too narrow.

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|:---:|
| Continuous bias, |mean bias| / population SD (worst cell-metric) | 0.0111 | ≤ 0.05 | pass |
| Binary bias, |mean bias| in probability units (cell 12) | 0.0060 | ≤ 0.02 | pass |
| Coverage, 95% Wilson lower bound (worst cell-metric) | 0.8448 | ≥ 0.90 | **fail** |
| Null false zero-exclusion, Wilson upper bound (cells 03–05 TNIE) | 0.0188 | ≤ 0.10 | pass |
| Unavailable or fatal rows (worst eligible cell-metric) | 0.0000 | ≤ 0.01 | pass |

**The coverage gate as written was nearly unattainable.** It requires at least 189 of 200 covered intervals for **every** one of 32 effects. Even if every interval covered exactly 95%, all 32 would pass together with probability about 1 × 10⁻⁵. Run 1 is **not** re-graded under any other rule. A feasible rule for future validation is proposed in the decision log.

## Bias and error

Mean bias is `mean(estimate − truth)`, and its Monte Carlo SE is `SD(estimate − truth) / √200`. Bias / SD uses the population outcome SD; it is not defined for binary cell 12. Continuous effects are in outcome units, and cell 12's are probability differences.

| Cell | Effect | Mean bias | MC SE | |Bias| / SD | RMSE | Mean abs. error |
|---|---|---:|---:|---:|---:|---:|
| `cell01_linear_n100` | PNDE | 0.0021 | 0.0142 | 0.0017 | 0.201 | 0.156 |
| `cell01_linear_n100` | TE | 0.0004 | 0.0152 | 0.0003 | 0.214 | 0.172 |
| `cell01_linear_n100` | TNIE | -0.0017 | 0.0085 | 0.0013 | 0.120 | 0.097 |
| `cell02_linear_n250` | PNDE | 0.0047 | 0.0090 | 0.0038 | 0.128 | 0.103 |
| `cell02_linear_n250` | TE | 0.0049 | 0.0104 | 0.0040 | 0.147 | 0.118 |
| `cell02_linear_n250` | TNIE | 0.0003 | 0.0051 | 0.0002 | 0.071 | 0.059 |
| `cell03_no_a_to_m_n100` | PNDE | 0.0134 | 0.0145 | 0.0111 | 0.205 | 0.162 |
| `cell03_no_a_to_m_n100` | TE | 0.0134 | 0.0145 | 0.0111 | 0.205 | 0.162 |
| `cell03_no_a_to_m_n100` | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.000 | 0.000 |
| `cell04_no_m_to_y_n100` | PNDE | 0.0028 | 0.0141 | 0.0026 | 0.199 | 0.163 |
| `cell04_no_m_to_y_n100` | TE | 0.0028 | 0.0141 | 0.0026 | 0.199 | 0.163 |
| `cell04_no_m_to_y_n100` | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.000 | 0.000 |
| `cell05_no_mediation_n100` | PNDE | 0.0104 | 0.0129 | 0.0099 | 0.182 | 0.143 |
| `cell05_no_mediation_n100` | TE | 0.0104 | 0.0129 | 0.0099 | 0.182 | 0.143 |
| `cell05_no_mediation_n100` | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.000 | 0.000 |
| `cell06_parallel_interaction_n150` | TNIE | -0.0011 | 0.0093 | 0.0008 | 0.131 | 0.104 |
| `cell07_serial_three_n200` | PNDE | 0.0063 | 0.0107 | 0.0045 | 0.151 | 0.121 |
| `cell07_serial_three_n200` | TE | 0.0015 | 0.0127 | 0.0010 | 0.179 | 0.138 |
| `cell07_serial_three_n200` | TNIE | -0.0048 | 0.0069 | 0.0034 | 0.098 | 0.080 |
| `cell08_quadratic_n100` | PNDE | 0.0007 | 0.0142 | 0.0006 | 0.200 | 0.160 |
| `cell08_quadratic_n100` | TE | -0.0032 | 0.0142 | 0.0025 | 0.201 | 0.162 |
| `cell08_quadratic_n100` | TNIE | -0.0040 | 0.0046 | 0.0031 | 0.065 | 0.049 |
| `cell09_spline_n250` | PNDE | -0.0008 | 0.0088 | 0.0006 | 0.125 | 0.099 |
| `cell09_spline_n250` | TE | 0.0021 | 0.0097 | 0.0017 | 0.136 | 0.108 |
| `cell09_spline_n250` | TNIE | 0.0029 | 0.0037 | 0.0023 | 0.053 | 0.042 |
| `cell10_moderated_n150` | TNIE_W0 | -0.0047 | 0.0051 | 0.0038 | 0.072 | 0.058 |
| `cell10_moderated_n150` | TNIE_W1 | -0.0065 | 0.0120 | 0.0053 | 0.169 | 0.137 |
| `cell10_moderated_n150` | TNIE_difference | -0.0019 | 0.0127 | 0.0015 | 0.179 | 0.144 |
| `cell11_binary_mediator_n150` | PNDE | 0.0017 | 0.0112 | 0.0015 | 0.158 | 0.128 |
| `cell11_binary_mediator_n150` | TE | -0.0006 | 0.0120 | 0.0006 | 0.169 | 0.137 |
| `cell11_binary_mediator_n150` | TNIE | -0.0023 | 0.0046 | 0.0021 | 0.066 | 0.052 |
| `cell12_mixed_binary_serial_n250` | PNDE | -0.0046 | 0.0044 | — | 0.062 | 0.049 |
| `cell12_mixed_binary_serial_n250` | TE | -0.0060 | 0.0044 | — | 0.062 | 0.048 |
| `cell12_mixed_binary_serial_n250` | TNIE | -0.0014 | 0.0014 | — | 0.020 | 0.016 |

Every mean bias is within about 1.4 Monte Carlo SEs of zero.

## Coverage

Coverage uses the **full denominator**: all 200 attempted datasets, with a missing interval counted as a miss. "Available-only" coverage counts only datasets with an interval. In this run the two agree, because no gated interval was missing. The MC SE is `√(p(1 − p) / 200)`. The Wilson interval is a 95% interval for the true coverage. Widths are in effect units.

| Cell | Effect | Covered / 200 | Coverage | MC SE | Wilson 95% | Available-only | Mean width | Descriptive label |
|---|---|---:|---:|---:|---|---:|---:|---|
| `cell01_linear_n100` | PNDE | 187 | 0.935 | 0.017 | 0.892–0.962 | 0.935 | 0.792 | consistent with 95% |
| `cell01_linear_n100` | TE | 191 | 0.955 | 0.015 | 0.917–0.976 | 0.955 | 0.864 | consistent with 95% |
| `cell01_linear_n100` | TNIE | 186 | 0.930 | 0.018 | 0.886–0.958 | 0.930 | 0.443 | consistent with 95% |
| `cell02_linear_n250` | PNDE | 193 | 0.965 | 0.013 | 0.930–0.983 | 0.965 | 0.508 | consistent with 95% |
| `cell02_linear_n250` | TE | 186 | 0.930 | 0.018 | 0.886–0.958 | 0.930 | 0.552 | consistent with 95% |
| `cell02_linear_n250` | TNIE | 193 | 0.965 | 0.013 | 0.930–0.983 | 0.965 | 0.279 | consistent with 95% |
| `cell03_no_a_to_m_n100` | PNDE | 186 | 0.930 | 0.018 | 0.886–0.958 | 0.930 | 0.782 | consistent with 95% |
| `cell03_no_a_to_m_n100` | TE | 186 | 0.930 | 0.018 | 0.886–0.958 | 0.930 | 0.782 | consistent with 95% |
| `cell03_no_a_to_m_n100` | TNIE | 200 | 1.000 | 0.000 | 0.981–1.000 | 1.000 | 0.000 | structural zero |
| `cell04_no_m_to_y_n100` | PNDE | 188 | 0.940 | 0.017 | 0.898–0.965 | 0.940 | 0.768 | consistent with 95% |
| `cell04_no_m_to_y_n100` | TE | 188 | 0.940 | 0.017 | 0.898–0.965 | 0.940 | 0.768 | consistent with 95% |
| `cell04_no_m_to_y_n100` | TNIE | 200 | 1.000 | 0.000 | 0.981–1.000 | 1.000 | 0.000 | structural zero |
| `cell05_no_mediation_n100` | PNDE | 195 | 0.975 | 0.011 | 0.943–0.989 | 0.975 | 0.775 | consistent with 95% |
| `cell05_no_mediation_n100` | TE | 195 | 0.975 | 0.011 | 0.943–0.989 | 0.975 | 0.775 | consistent with 95% |
| `cell05_no_mediation_n100` | TNIE | 200 | 1.000 | 0.000 | 0.981–1.000 | 1.000 | 0.000 | structural zero |
| `cell06_parallel_interaction_n150` | TNIE | 189 | 0.945 | 0.016 | 0.904–0.969 | 0.945 | 0.516 | consistent with 95% |
| `cell07_serial_three_n200` | PNDE | 188 | 0.940 | 0.017 | 0.898–0.965 | 0.940 | 0.576 | consistent with 95% |
| `cell07_serial_three_n200` | TE | 185 | 0.925 | 0.019 | 0.880–0.954 | 0.925 | 0.669 | consistent with 95% |
| `cell07_serial_three_n200` | TNIE | 191 | 0.955 | 0.015 | 0.917–0.976 | 0.955 | 0.427 | consistent with 95% |
| `cell08_quadratic_n100` | PNDE | 190 | 0.950 | 0.015 | 0.910–0.973 | 0.950 | 0.779 | consistent with 95% |
| `cell08_quadratic_n100` | TE | 191 | 0.955 | 0.015 | 0.917–0.976 | 0.955 | 0.815 | consistent with 95% |
| `cell08_quadratic_n100` | TNIE | 183 | 0.915 | 0.020 | 0.868–0.946 | 0.915 | 0.247 | **under-covers** |
| `cell09_spline_n250` | PNDE | 191 | 0.955 | 0.015 | 0.917–0.976 | 0.955 | 0.511 | consistent with 95% |
| `cell09_spline_n250` | TE | 188 | 0.940 | 0.017 | 0.898–0.965 | 0.940 | 0.516 | consistent with 95% |
| `cell09_spline_n250` | TNIE | 187 | 0.935 | 0.017 | 0.892–0.962 | 0.935 | 0.199 | consistent with 95% |
| `cell10_moderated_n150` | TNIE_W0 | — | — | — | — | — | — | point-only by contract |
| `cell10_moderated_n150` | TNIE_W1 | — | — | — | — | — | — | point-only by contract |
| `cell10_moderated_n150` | TNIE_difference | 187 | 0.935 | 0.017 | 0.892–0.962 | 0.935 | 0.701 | consistent with 95% |
| `cell11_binary_mediator_n150` | PNDE | 188 | 0.940 | 0.017 | 0.898–0.965 | 0.940 | 0.646 | consistent with 95% |
| `cell11_binary_mediator_n150` | TE | 189 | 0.945 | 0.016 | 0.904–0.969 | 0.945 | 0.658 | consistent with 95% |
| `cell11_binary_mediator_n150` | TNIE | 179 | 0.895 | 0.022 | 0.845–0.930 | 0.895 | 0.235 | **under-covers** |
| `cell12_mixed_binary_serial_n250` | PNDE | 186 | 0.930 | 0.018 | 0.886–0.958 | 0.930 | 0.240 | consistent with 95% |
| `cell12_mixed_binary_serial_n250` | TE | 189 | 0.945 | 0.016 | 0.904–0.969 | 0.945 | 0.239 | consistent with 95% |
| `cell12_mixed_binary_serial_n250` | TNIE | 193 | 0.965 | 0.013 | 0.930–0.983 | 0.965 | 0.087 | consistent with 95% |

Across all 32 gated effects the mean coverage is 94.8%. Excluding the three structural zeros, it is 94.3%.

## Zero-exclusion, availability and failures

Zero-exclusion is the share of intervals that exclude 0. In non-null effects it is descriptive power, not a gate. For the null TNIE in cells 03–05 it is the false zero-exclusion rate, which is gated.

| Cell | Effect | Zero-exclusion | Wilson 95% | Intervals available | Unavailable or fatal | Fatal |
|---|---|---:|---|---:|---:|---:|
| `cell01_linear_n100` | PNDE | 0.150 | 0.107–0.206 | 200 | 0 | 0 |
| `cell01_linear_n100` | TE | 0.535 | 0.466–0.603 | 200 | 0 | 0 |
| `cell01_linear_n100` | TNIE | 0.670 | 0.602–0.731 | 200 | 0 | 0 |
| `cell02_linear_n250` | PNDE | 0.315 | 0.255–0.382 | 200 | 0 | 0 |
| `cell02_linear_n250` | TE | 0.895 | 0.845–0.930 | 200 | 0 | 0 |
| `cell02_linear_n250` | TNIE | 0.975 | 0.943–0.989 | 200 | 0 | 0 |
| `cell03_no_a_to_m_n100` | PNDE | 0.175 | 0.129–0.234 | 200 | 0 | 0 |
| `cell03_no_a_to_m_n100` | TE | 0.175 | 0.129–0.234 | 200 | 0 | 0 |
| `cell03_no_a_to_m_n100` | TNIE | 0.000 | 0.000–0.019 | 200 | 0 | 0 |
| `cell04_no_m_to_y_n100` | PNDE | 0.190 | 0.142–0.250 | 200 | 0 | 0 |
| `cell04_no_m_to_y_n100` | TE | 0.190 | 0.142–0.250 | 200 | 0 | 0 |
| `cell04_no_m_to_y_n100` | TNIE | 0.000 | 0.000–0.019 | 200 | 0 | 0 |
| `cell05_no_mediation_n100` | PNDE | 0.180 | 0.133–0.239 | 200 | 0 | 0 |
| `cell05_no_mediation_n100` | TE | 0.180 | 0.133–0.239 | 200 | 0 | 0 |
| `cell05_no_mediation_n100` | TNIE | 0.000 | 0.000–0.019 | 200 | 0 | 0 |
| `cell06_parallel_interaction_n150` | TNIE | 0.905 | 0.856–0.938 | 200 | 0 | 0 |
| `cell07_serial_three_n200` | PNDE | 0.300 | 0.241–0.367 | 200 | 0 | 0 |
| `cell07_serial_three_n200` | TE | 0.895 | 0.845–0.930 | 200 | 0 | 0 |
| `cell07_serial_three_n200` | TNIE | 0.925 | 0.880–0.954 | 200 | 0 | 0 |
| `cell08_quadratic_n100` | PNDE | 0.170 | 0.124–0.228 | 200 | 0 | 0 |
| `cell08_quadratic_n100` | TE | 0.280 | 0.222–0.346 | 200 | 0 | 0 |
| `cell08_quadratic_n100` | TNIE | 0.445 | 0.378–0.514 | 200 | 0 | 0 |
| `cell09_spline_n250` | PNDE | 0.360 | 0.297–0.429 | 200 | 0 | 0 |
| `cell09_spline_n250` | TE | 0.645 | 0.577–0.708 | 200 | 0 | 0 |
| `cell09_spline_n250` | TNIE | 0.635 | 0.566–0.699 | 200 | 0 | 0 |
| `cell10_moderated_n150` | TNIE_W0 | — | — | 0 | 200 (point-only by contract) | 0 |
| `cell10_moderated_n150` | TNIE_W1 | — | — | 0 | 200 (point-only by contract) | 0 |
| `cell10_moderated_n150` | TNIE_difference | 0.360 | 0.297–0.429 | 200 | 0 | 0 |
| `cell11_binary_mediator_n150` | PNDE | 0.220 | 0.168–0.282 | 200 | 0 | 0 |
| `cell11_binary_mediator_n150` | TE | 0.505 | 0.436–0.574 | 200 | 0 | 0 |
| `cell11_binary_mediator_n150` | TNIE | 0.580 | 0.511–0.646 | 200 | 0 | 0 |
| `cell12_mixed_binary_serial_n250` | PNDE | 0.110 | 0.074–0.161 | 200 | 0 | 0 |
| `cell12_mixed_binary_serial_n250` | TE | 0.325 | 0.264–0.393 | 200 | 0 | 0 |
| `cell12_mixed_binary_serial_n250` | TNIE | 0.800 | 0.739–0.850 | 200 | 0 | 0 |

The 2,400 analyses finished with status `complete` (1,800) or `complete_with_warnings` (600). There were no fit or integration failures and no refit failures that withheld an interval.

**Stress diagnostics** (descriptive, outside every gate). The four N = 50 stress fixtures (`tied_score`, `sparse_events`, `missingness`, `opposing_paths`) ran with `--stress-only` on commit `a3e9dc5`, locally with Python 3.11.9. All four finished `complete_with_warnings`, with no failure codes.

## Runtime

Mean time per dataset on GitHub Actions `ubuntu-latest`, covering the point analysis and 399 bootstrap refits:

| Cell | Mean seconds per dataset | CPU-hours for 200 datasets |
|---|---:|---:|
| `cell01_linear_n100` | 5.3 | 0.29 |
| `cell02_linear_n250` | 5.9 | 0.33 |
| `cell03_no_a_to_m_n100` | 5.8 | 0.32 |
| `cell04_no_m_to_y_n100` | 4.9 | 0.27 |
| `cell05_no_mediation_n100` | 6.9 | 0.38 |
| `cell06_parallel_interaction_n150` | 27.8 | 1.54 |
| `cell07_serial_three_n200` | 10.1 | 0.56 |
| `cell08_quadratic_n100` | 14.7 | 0.82 |
| `cell09_spline_n250` | 21.9 | 1.22 |
| `cell10_moderated_n150` | 75.1 | 4.17 |
| `cell11_binary_mediator_n150` | 9.8 | 0.54 |
| `cell12_mixed_binary_serial_n250` | 12.4 | 0.69 |

The total shard runtime was 40,130 s (11.1 CPU-hours), within the amended 36 CPU-hour budget and below the pilot forecast of 20.7 CPU-hours. The run took about 1 h 22 min of wall-clock time.

## What this evidence does not show

- It does not show that Mintmed's intervals meet the pre-registered coverage standard. They did not.
- It does not validate any design outside the 12 exact cells: other node families, terms, sample sizes, more mediators, or model misspecification.
- It does not test the causal identification assumptions. No simulation can.
- It does not show that Mintmed performs better than any other mediation method.
