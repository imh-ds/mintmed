# Mintmed validation evidence

## Scope and frozen design

The report covers the declared `mintmed_comparator_benchmark_mintmed` design with 1000 observed inferential rows and 2 selected cells. The locked matrix is not changed by reporting.

## Reproducibility and shard contract

Configuration hash: `a89c00731c7f8adf97e7ba6463d02ece5f47cd9911b13ff30ef75c55035fc3f3`. Stable combination key: `('cell_id', 'replicate')`. Scientific rows are comparable after sorting by cell ID and replicate; runtime is descriptive.

## Cell and metric summaries

                cell_id metric outcome_kind  attempted_rows  finite_estimates  fatal_rows  interval_available_rows  unavailable_interval_rows  unavailable_or_fatal_rows  mean_bias  absolute_bias  bias_mc_se  mean_absolute_error     rmse  mean_width  few_failure_withheld_rows  few_failure_withheld_rate  zero_exclusions  zero_exclusion_rate  zero_exclusion_mc_se  runtime_mean_seconds  fit_count_mean  draw_budget_min  draw_budget_max  population_outcome_sd  coverage_successes  coverage_trials  coverage  coverage_wilson_lower  coverage_wilson_upper  coverage_mc_se  truth_above_interval_rows  truth_below_interval_rows  available_only_coverage  available_only_coverage_wilson_lower  available_only_coverage_wilson_upper  available_only_coverage_mc_se  zero_exclusion_wilson_lower  zero_exclusion_wilson_upper  unavailable_interval_rate  unavailable_or_fatal_rate
cell15_a_path_only_n250   PNDE   continuous             500               500           0                      500                          0                          0  -0.007357       0.007357    0.005881             0.104269 0.131573    0.505874                          0                        0.0              154                0.308              0.020646              7.610585             2.0              0.0              0.0               1.048809                 468              500     0.936               0.911048               0.954304        0.010946                         17                         15                    0.936                              0.911048                              0.954304                       0.010946                     0.269126                     0.349802                        0.0                        0.0
cell15_a_path_only_n250     TE   continuous             500               500           0                      500                          0                          0  -0.006952       0.006952    0.005622             0.099586 0.125784    0.489711                          0                        0.0              163                0.326              0.020963              7.610585             2.0              0.0              0.0               1.048809                 470              500     0.940               0.915639               0.957652        0.010621                         17                         13                    0.940                              0.915639                              0.957652                       0.010621                     0.286375                     0.368278                        0.0                        0.0
cell15_a_path_only_n250   TNIE   continuous             500               500           0                      500                          0                          0   0.000405       0.000405    0.001484             0.026039 0.033153    0.134686                          0                        0.0               23                0.046              0.009368              7.610585             2.0              0.0              0.0               1.048809                 477              500     0.954               0.931922               0.969155        0.009368                         13                         10                    0.954                              0.931922                              0.969155                       0.009368                     0.030845                     0.068078                        0.0                        0.0
cell16_b_path_only_n250   PNDE   continuous             500               500           0                      500                          0                          0   0.006773       0.006773    0.005788             0.104127 0.129479    0.490764                          0                        0.0              198                0.396              0.021872              5.391568             2.0              0.0              0.0               1.209339                 473              500     0.946               0.922573               0.962626        0.010108                         12                         15                    0.946                              0.922573                              0.962626                       0.010108                     0.354082                     0.439504                        0.0                        0.0
cell16_b_path_only_n250     TE   continuous             500               500           0                      500                          0                          0   0.002684       0.002684    0.006245             0.112163 0.139520    0.546324                          0                        0.0              154                0.308              0.020646              5.391568             2.0              0.0              0.0               1.209339                 477              500     0.954               0.931922               0.969155        0.009368                          7                         16                    0.954                              0.931922                              0.969155                       0.009368                     0.269126                     0.349802                        0.0                        0.0
cell16_b_path_only_n250   TNIE   continuous             500               500           0                      500                          0                          0  -0.004089       0.004089    0.002763             0.047063 0.061863    0.250386                          0                        0.0               22                0.044              0.009172              5.391568             2.0              0.0              0.0               1.209339                 478              500     0.956               0.934281               0.970766        0.009172                         14                          8                    0.956                              0.934281                              0.970766                       0.009172                     0.029234                     0.065719                        0.0                        0.0

## Gate results

Overall gate result: **FAIL**. Power is descriptive only and is not a release gate.

Bias gates compare the absolute mean bias |mean(estimate - truth)| with the threshold; the mean absolute error is reported descriptively in the summaries. The MC SE column is the Monte Carlo standard error of the worst mean bias.

| Gate | Observed | MC SE | Threshold | Passed |
|---|---:|---:|---:|:---:|
| continuous_abs_bias_sd | 0.007014537718666357 | 0.005607106810440357 | 0.05 | True |
| binary_abs_bias_probability | None |  | 0.02 | False |
| coverage_exact_binomial_bonferroni | 0.0944504828905998 |  | 0.008333333333333333 | True |
| null_false_zero_wilson_upper | 0.06807779276827323 |  | 0.1 | True |
| unavailable_or_fatal_max | 0.0 |  | 0.01 | True |

### Coverage: exact binomial with Bonferroni adjustment

Each of the 6 gated effects fails when the one-sided exact binomial p-value against 0.95 coverage is at most 0.05 / 6. Missing intervals count as misses. Miss sides are descriptive.

| Cell | Metric | Covered | Trials | Critical count | p-value | Truth above / below | Passed |
|---|---|---:|---:|---:|---:|---|:---:|
| cell15_a_path_only_n250 | PNDE | 468 | 500 | 462 | 0.09445 | 17 / 15 | True |
| cell15_a_path_only_n250 | TE | 470 | 500 | 462 | 0.1765 | 17 / 13 | True |
| cell15_a_path_only_n250 | TNIE | 477 | 500 | 462 | 0.6879 | 13 / 10 | True |
| cell16_b_path_only_n250 | PNDE | 473 | 500 | 462 | 0.3686 | 12 / 15 | True |
| cell16_b_path_only_n250 | TE | 477 | 500 | 462 | 0.6879 | 7 / 16 | True |
| cell16_b_path_only_n250 | TNIE | 478 | 500 | 462 | 0.7591 | 14 / 8 | True |

## Failures and unavailable intervals

Unavailable intervals count as noncoverage; failed rows remain in attempted and fatal denominators.

Interval rule: zero-failure. With 399 standard replicates (< 400), a single failed refit withholds every interval for that dataset; `few_failure_withheld_rows` counts the datasets whose intervals were withheld because only one or two refits failed.

## Stress diagnostics

Stress diagnostics are separate from inferential denominators: **False**.

## Limitations and stopping rule

This evidence package is valid only for the frozen cells, seeds, bootstrap settings, and declared gates. Power does not change the stopping decision.

## Provenance

Schema version: `1`; Python/runtime details are recorded in metadata.json without output paths.
