# Coverage revalidation — run 2 results (failed null false-positive gate)

This file permanently records the **second** full execution of the validation matrix, fixed by [`coverage_revalidation_charter.md`](coverage_revalidation_charter.md). It is kept as-is. Run 1 is recorded separately in [`baseline_run1_results.md`](baseline_run1_results.md) and is not re-graded.

**Verdict: FAIL.** The pre-registered null false zero-exclusion gate failed. All other gates passed, including the new coverage gate.

## Run identity

| Item | Value |
|---|---|
| Workflow | `.github/workflows/sharded_benchmark.yml`, run `36349731184` |
| Dispatched commit | `9ff5de6` (the charter commit) |
| When | 2026-09-27, 20:54–23:14 UTC |
| Platform | GitHub Actions `ubuntu-latest`, Python 3.11.16 |
| Configuration | `configs/mediation_validation_v2.yaml`, master seed `20260927` |
| Layout | 140 shards: 14 cells × `--replicate-block 0of10…9of10` (50 datasets each). All 140 succeeded. |
| Configuration hash | `0f2f738887b2a1669cf8c281e43fb9c258652291a4c50bbed9a009ffaafb953b` (single hash across all rows, matching the charter) |
| Grid | 7,000 of 7,000 expected rows, 0 duplicates, 0 missing, 0 extra |
| Total shard runtime | 109,078 s (30.30 CPU-hours summed across shards), against a forecast of 29.79 (31.28 with the 5% allowance) and a budget of 36 |
| Slowest shard | `cell10_moderated_n150`, block 8: 1.26 h of per-dataset runtime, against a limit of 4 h |
| Artifacts | GitHub artifact `aggregated-benchmark` from run `36349731184`, plus a local copy in `results/generated/validation-matrix-36349731184/` (git-ignored) |

Every analysis finished `complete` (5,500) or `complete_with_warnings` (1,500: all rows of cells 06, 07 and 12), with 399 of 399 successful bootstrap refits and no failure codes. No interval was withheld.

The gates were re-evaluated from the raw rows with `expand_metrics`, `summarize_metrics` and `evaluate_gates` (`mintmed.experiments`). They agree with the artifact's `summary.json`.

## Gates

| Gate | Observed | Threshold | Passed |
|---|---:|---:|:---:|
| `binary_abs_bias_probability` | 0.0026 | 0.02 | yes |
| `continuous_abs_bias_sd` | 0.0108 | 0.05 | yes |
| `coverage_exact_binomial_bonferroni` (smallest p-value) | 0.0046 | > 0.0013 | yes |
| `null_false_zero_wilson_upper` | 0.1049 | 0.10 | **no** |
| `unavailable_or_fatal_max` | 0.0000 | 0.01 | yes |

- **Coverage** (Option B). k = 38 gated effects, so the per-effect level is 0.05 / 38 = 0.0013 and an effect fails at **458 or fewer** of 500 covered. No effect failed. The lowest were cell 07 PNDE and cell 14 TNIE, both at 461 of 500 (p = 0.0046).
- **Null false zero-exclusion.** The gate takes the largest 95% Wilson upper bound of the TNIE zero-exclusion rate over cells 03, 04, 05, 13 and 14. Cell 14 gave 39 of 500 (7.8%), with a Wilson upper bound of 0.1049, just above the 0.10 threshold. See [Null gate detail](#null-gate-detail).

## Per-cell results

"Covered / 500" and "Coverage" use the full denominator, in which a missing interval counts as a miss. No intervals were missing in this run, so available-only coverage equals full coverage everywhere. The p-value is `BinomialCDF(covered; 500, 0.95)`. Every gated effect has the same critical count, **458**. "Truth above / below" counts the intervals that missed on each side. Bias / SD uses the population outcome SD; it is not defined for binary cell 12. Cell 10's TNIE at W = 0 and at W = 1 are point-only by contract and excluded from the interval gates.

| Cell | Effect | Covered / 500 | Coverage | p-value | Gate | Truth above / below | Mean bias | Bias / SD | Mean width | Zero-exclusion | Available intervals |
|---|---|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| `cell01_linear_n100` | TE | 474 | 0.948 | 0.4471 | pass | 11 / 15 | 0.0007 | 0.0006 | 0.865 | 0.532 | 500 |
| `cell01_linear_n100` | PNDE | 475 | 0.950 | 0.5286 | pass | 10 / 15 | -0.0006 | 0.0005 | 0.803 | 0.174 | 500 |
| `cell01_linear_n100` | TNIE | 475 | 0.950 | 0.5286 | pass | 15 / 10 | 0.0013 | 0.0010 | 0.454 | 0.690 | 500 |
| `cell02_linear_n250` | TE | 480 | 0.960 | 0.8728 | pass | 8 / 12 | 0.0031 | 0.0025 | 0.548 | 0.914 | 500 |
| `cell02_linear_n250` | PNDE | 472 | 0.944 | 0.2961 | pass | 14 / 14 | -0.0012 | 0.0010 | 0.507 | 0.346 | 500 |
| `cell02_linear_n250` | TNIE | 464 | 0.928 | 0.0196 | pass | 19 / 17 | 0.0043 | 0.0035 | 0.277 | 0.972 | 500 |
| `cell03_no_a_to_m_n100` | TE | 479 | 0.958 | 0.8211 | pass | 11 / 10 | -0.0032 | 0.0027 | 0.780 | 0.178 | 500 |
| `cell03_no_a_to_m_n100` | PNDE | 479 | 0.958 | 0.8211 | pass | 11 / 10 | -0.0032 | 0.0027 | 0.780 | 0.178 | 500 |
| `cell03_no_a_to_m_n100` | TNIE | 500 | 1.000 | 1.0000 | pass (structural zero) | 0 / 0 | 0.0000 | 0.0000 | 0.000 | 0.000 | 500 |
| `cell04_no_m_to_y_n100` | TE | 470 | 0.940 | 0.1765 | pass | 13 / 17 | -0.0078 | 0.0074 | 0.775 | 0.158 | 500 |
| `cell04_no_m_to_y_n100` | PNDE | 470 | 0.940 | 0.1765 | pass | 13 / 17 | -0.0078 | 0.0074 | 0.775 | 0.158 | 500 |
| `cell04_no_m_to_y_n100` | TNIE | 500 | 1.000 | 1.0000 | pass (structural zero) | 0 / 0 | 0.0000 | 0.0000 | 0.000 | 0.000 | 500 |
| `cell05_no_mediation_n100` | TE | 471 | 0.942 | 0.2317 | pass | 14 / 15 | -0.0091 | 0.0087 | 0.778 | 0.168 | 500 |
| `cell05_no_mediation_n100` | PNDE | 471 | 0.942 | 0.2317 | pass | 14 / 15 | -0.0091 | 0.0087 | 0.778 | 0.168 | 500 |
| `cell05_no_mediation_n100` | TNIE | 500 | 1.000 | 1.0000 | pass (structural zero) | 0 / 0 | 0.0000 | 0.0000 | 0.000 | 0.000 | 500 |
| `cell06_parallel_interaction_n150` | TNIE | 480 | 0.960 | 0.8728 | pass | 12 / 8 | 0.0084 | 0.0063 | 0.521 | 0.920 | 500 |
| `cell07_serial_three_n200` | TE | 469 | 0.938 | 0.1309 | pass | 16 / 15 | -0.0028 | 0.0020 | 0.666 | 0.888 | 500 |
| `cell07_serial_three_n200` | PNDE | 461 | 0.922 | 0.0046 | pass | 22 / 17 | 0.0036 | 0.0025 | 0.578 | 0.300 | 500 |
| `cell07_serial_three_n200` | TNIE | 473 | 0.946 | 0.3686 | pass | 17 / 10 | -0.0064 | 0.0045 | 0.427 | 0.930 | 500 |
| `cell08_quadratic_n100` | TE | 473 | 0.946 | 0.3686 | pass | 13 / 14 | 0.0030 | 0.0024 | 0.819 | 0.334 | 500 |
| `cell08_quadratic_n100` | PNDE | 470 | 0.940 | 0.1765 | pass | 16 / 14 | 0.0056 | 0.0044 | 0.782 | 0.200 | 500 |
| `cell08_quadratic_n100` | TNIE | 473 | 0.946 | 0.3686 | pass | 24 / 3 | -0.0025 | 0.0020 | 0.245 | 0.450 | 500 |
| `cell09_spline_n250` | TE | 479 | 0.958 | 0.8211 | pass | 10 / 11 | 0.0072 | 0.0056 | 0.514 | 0.650 | 500 |
| `cell09_spline_n250` | PNDE | 480 | 0.960 | 0.8728 | pass | 7 / 13 | 0.0051 | 0.0040 | 0.509 | 0.362 | 500 |
| `cell09_spline_n250` | TNIE | 474 | 0.948 | 0.4471 | pass | 20 / 6 | 0.0021 | 0.0017 | 0.201 | 0.666 | 500 |
| `cell10_moderated_n150` | TNIE_W0 | — | — | — | excluded (point-only) | — | 0.0007 | 0.0006 | — | — | 0 |
| `cell10_moderated_n150` | TNIE_W1 | — | — | — | excluded (point-only) | — | -0.0047 | 0.0038 | — | — | 0 |
| `cell10_moderated_n150` | TNIE_difference | 468 | 0.936 | 0.0945 | pass | 19 / 13 | -0.0054 | 0.0044 | 0.704 | 0.328 | 500 |
| `cell11_binary_mediator_n150` | TE | 469 | 0.938 | 0.1309 | pass | 17 / 14 | -0.0081 | 0.0073 | 0.656 | 0.456 | 500 |
| `cell11_binary_mediator_n150` | PNDE | 478 | 0.956 | 0.7591 | pass | 12 / 10 | -0.0120 | 0.0108 | 0.644 | 0.212 | 500 |
| `cell11_binary_mediator_n150` | TNIE | 470 | 0.940 | 0.1765 | pass | 14 / 16 | 0.0039 | 0.0035 | 0.240 | 0.634 | 500 |
| `cell12_mixed_binary_serial_n250` | TE | 472 | 0.944 | 0.2961 | pass | 15 / 13 | 0.0019 | — | 0.238 | 0.372 | 500 |
| `cell12_mixed_binary_serial_n250` | PNDE | 475 | 0.950 | 0.5286 | pass | 13 / 12 | 0.0026 | — | 0.241 | 0.124 | 500 |
| `cell12_mixed_binary_serial_n250` | TNIE | 478 | 0.956 | 0.7591 | pass | 14 / 8 | -0.0007 | — | 0.086 | 0.812 | 500 |
| `cell13_a_path_only_n100` | TE | 472 | 0.944 | 0.2961 | pass | 13 / 15 | 0.0055 | 0.0052 | 0.774 | 0.162 | 500 |
| `cell13_a_path_only_n100` | PNDE | 469 | 0.938 | 0.1309 | pass | 16 / 15 | 0.0079 | 0.0075 | 0.804 | 0.158 | 500 |
| `cell13_a_path_only_n100` | TNIE | 478 | 0.956 | 0.7591 | pass | 14 / 8 | -0.0024 | 0.0023 | 0.239 | 0.044 | 500 |
| `cell14_b_path_only_n100` | TE | 467 | 0.934 | 0.0664 | pass | 16 / 17 | 0.0127 | 0.0105 | 0.869 | 0.186 | 500 |
| `cell14_b_path_only_n100` | PNDE | 469 | 0.938 | 0.1309 | pass | 14 / 17 | 0.0128 | 0.0106 | 0.781 | 0.200 | 500 |
| `cell14_b_path_only_n100` | TNIE | 461 | 0.922 | 0.0046 | pass | 21 / 18 | -0.0001 | 0.0001 | 0.408 | 0.078 | 500 |

In cells 03–05 the fitted model omits the null path, so the TNIE is a structural zero: estimate 0, width 0, always covered. In cells 13 and 14 both paths are fitted, so the TNIE is estimated and its truth is 0. There, a miss and a zero-exclusion are the same event.

## Null gate detail

The TNIE truth is 0 in all five cells. "Excludes 0" counts intervals entirely above or entirely below zero.

| Cell | Paths in the generator (A → M / M → Y) | Fitted model | Intervals excluding 0 | Rate | Wilson 95% | Entirely above 0 / below 0 | Mean width | Within 0.10? |
|---|---|---|---:|---:|---|---:|---:|:---:|
| `cell03_no_a_to_m_n100` | 0 / 0.5 | omits A → M | 0 of 500 | 0.000 | 0.000–0.008 | 0 / 0 | 0.000 | yes |
| `cell04_no_m_to_y_n100` | 0.5 / 0 | omits M → Y | 0 of 500 | 0.000 | 0.000–0.008 | 0 / 0 | 0.000 | yes |
| `cell05_no_mediation_n100` | 0 / 0 | omits M → Y | 0 of 500 | 0.000 | 0.000–0.008 | 0 / 0 | 0.000 | yes |
| `cell13_a_path_only_n100` | 0.5 / 0 | both paths | 22 of 500 | 0.044 | 0.029–0.066 | 8 / 14 | 0.239 | yes |
| `cell14_b_path_only_n100` | 0 / 0.5 | both paths | 39 of 500 | 0.078 | 0.058–0.105 | 18 / 21 | 0.408 | **no** |

- **Cell 14** (A → M truly zero, M → Y = 0.5): 39 of 500 is above the nominal 5%. An exact one-sided binomial test against 5% gives p = 0.0046. The exclusions fall on both sides (18 above zero, 21 below), and the TNIE estimate is unbiased (mean −0.0001) and close to symmetric (sample skewness −0.14). So the intervals are slightly too narrow, not shifted.
- **Cell 13** (M → Y truly zero): 22 of 500 (4.4%), consistent with 5% (p = 0.76 for 22 or more).
- **Cells 03–05:** structural zeros, as in run 1. They cannot produce a false positive.

## Interpretation

- **Bias.** Estimates are essentially unbiased in every cell: at most 0.011 population SD (cell 11 PNDE), or 0.003 probability for the binary outcome. Every mean bias is within 1.7 Monte Carlo SEs of zero.
- **Coverage.** Mean coverage across the 38 gated effects is **94.9%**, or 94.5% excluding the three structural zeros. No effect reached the critical count of 458. Three effects have a one-sided p-value below 0.05 without multiple-comparison adjustment: cell 07 PNDE (461, p = 0.0046), cell 14 TNIE (461, p = 0.0046) and cell 02 TNIE (464, p = 0.020). With 38 effects, about two such values are expected by chance alone.
- **Mixed-null false positives.** The one failure is the null gate, and it comes from cell 14 alone. When the A → M path is truly zero but estimated, and M → Y is strong, the percentile interval for the TNIE excludes zero in about 8% of datasets at N = 100, rather than 5%. The reverse configuration (cell 13) behaves as expected. The Wilson upper bound, 0.1049, is only just above the 0.10 threshold, so the verdict is close. A repeat with a fresh seed gave 32 of 500 ([`null_gate_fix_check.md`](null_gate_fix_check.md)); pooled over both seeds the rate is 7.1% (Wilson 95% 5.7–8.9%).
- **Power** (descriptive). Zero-exclusion rates for non-null TNIEs range from 0.328 (cell 10 difference) and 0.450 (cell 08) to 0.972 (cell 02).

## Comparison with run 1

Run 2 used a new master seed and a different coverage rule. The comparison is descriptive; run 1 is not re-graded.

| Item | Run 1 (200 datasets) | Run 2 (500 datasets) |
|---|---|---|
| Worst continuous bias / SD | 0.0111 | 0.0108 |
| Mean coverage of gated effects | 94.8% (32 effects) | 94.9% (38 effects) |
| Cell 08 TNIE covered | 183 / 200 (91.5%), misses 12 above / 5 below | 473 / 500 (94.6%), misses 24 above / 3 below |
| Cell 11 TNIE covered | 179 / 200 (89.5%), misses 15 above / 6 below | 470 / 500 (94.0%), misses 14 above / 16 below |
| Null gate, worst Wilson upper | 0.0188 (structural zeros only) | 0.1049 (cell 14) |

- Run 1's main finding, that the TNIE intervals of cells 08 and 11 under-cover, **did not replicate**. Both are close to 95% at 500 datasets.
- Cell 08's misses are still one-sided (24 above, 3 below), so its intervals sit slightly too low even though total coverage is near nominal.
- Run 1's null gate passed only because its null cells were structural zeros. Run 2's cells 13 and 14 are the first test of estimated null indirect effects.

## Consequence under the charter

The failure stands as the result of run 2. Under the charter's one-correction rule:
- **Root cause.** The percentile bootstrap interval for the TNIE is slightly too narrow when A → M is truly zero and M → Y is strong, at N = 100.
- **Check before deciding.** Three candidate intervals were compared offline with the percentile interval on the run-2 datasets and on a fresh seed: an expanded percentile interval, estimate ± t × bootstrap SD, and BC. None fixes the false-positive rate without a cost elsewhere ([`null_gate_fix_check.md`](null_gate_fix_check.md)).
- **Decision (owner, 2026-09-27).** No correction is adopted, the one correction is not used, and there is no rerun. Run 2 stands as **FAILED** on the null false zero-exclusion gate. The mixed-null false-positive rate is documented as a known limitation in [`baseline_evidence.md`](baseline_evidence.md#known-limitations). The decision is recorded in the implementation decision log (entry "Task 16 — outcome: null-gate limitation documented (option 2)").
- Comparing several candidate intervals sits uneasily with the charter's "no estimator tournament" rule. Because none was adopted and nothing was rerun, the run-2 verdict was not tuned by that comparison.
