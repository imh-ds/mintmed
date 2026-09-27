# Baseline validation — run 1 results (failed coverage gate)

This file permanently records the **first** full execution of the validation matrix fixed by [`baseline_release_charter.md`](baseline_release_charter.md). It is kept as-is. Any corrected run is reported separately, alongside it, and never replaces it.

**Verdict: FAIL.** The pre-registered coverage gate failed, and all other gates passed.

## Run identity

| Item | Value |
|---|---|
| Workflow | `.github/workflows/sharded_benchmark.yml`, run `36296143027` |
| Dispatched commit | `04cbf2d` (the charter commit) |
| When | 2026-09-27, 05:04–06:26 UTC |
| Platform | GitHub Actions `ubuntu-latest`, Python 3.11.16 |
| Layout | 48 shards: 12 cells × `--replicate-block 0of4…3of4` |
| Configuration hash | `176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94` (single hash across all rows) |
| Grid | 2,400 of 2,400 expected rows, 0 duplicates, 0 missing |
| Total shard runtime | 40,130 s (11.1 h summed across shards) |
| Artifacts | GitHub artifact `aggregated-benchmark` from run `36296143027`, plus a local copy in `results/generated/validation-matrix-36296143027/` (git-ignored) |

Every analysis finished `complete` (1,800) or `complete_with_warnings` (600), with no fit or integration failures and no interval withheld by failed refits.

## Gates

| Gate | Observed | Threshold | Passed |
|---|---:|---:|:---:|
| `binary_abs_bias_probability` | 0.0060 | 0.02 | yes |
| `continuous_abs_bias_sd` | 0.0111 | 0.05 | yes |
| `coverage_wilson_lower` | 0.8448 | 0.9 | **no** |
| `null_false_zero_wilson_upper` | 0.0188 | 0.1 | yes |
| `unavailable_or_fatal_max` | 0.0000 | 0.01 | yes |

The coverage gate requires the 95% Wilson lower bound of full-denominator coverage to be at least 0.90 for **every** gated effect. With 200 datasets, that means at least **189 of 200** intervals must contain the truth. **16 of 32** gated effects fell short.

## Per-cell results

"Covered / 200" and "Coverage" use the full denominator, in which a missing interval counts as a miss. No intervals were missing in this run. Cell 10's direct moderator effects are point-only by contract and excluded from the gates.

| Cell | Effect | Covered / 200 | Coverage | Wilson lower | Gate | Mean bias | Bias / SD | Mean width | Zero-exclusion | Available intervals |
|---|---|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| `cell01_linear_n100` | PNDE | 187 | 0.935 | 0.892 | **fail** | 0.0021 | 0.0017 | 0.792 | 0.150 | 200 |
| `cell01_linear_n100` | TE | 191 | 0.955 | 0.917 | pass | 0.0004 | 0.0003 | 0.864 | 0.535 | 200 |
| `cell01_linear_n100` | TNIE | 186 | 0.930 | 0.886 | **fail** | -0.0017 | 0.0013 | 0.443 | 0.670 | 200 |
| `cell02_linear_n250` | PNDE | 193 | 0.965 | 0.930 | pass | 0.0047 | 0.0038 | 0.508 | 0.315 | 200 |
| `cell02_linear_n250` | TE | 186 | 0.930 | 0.886 | **fail** | 0.0049 | 0.0040 | 0.552 | 0.895 | 200 |
| `cell02_linear_n250` | TNIE | 193 | 0.965 | 0.930 | pass | 0.0003 | 0.0002 | 0.279 | 0.975 | 200 |
| `cell03_no_a_to_m_n100` | PNDE | 186 | 0.930 | 0.886 | **fail** | 0.0134 | 0.0111 | 0.782 | 0.175 | 200 |
| `cell03_no_a_to_m_n100` | TE | 186 | 0.930 | 0.886 | **fail** | 0.0134 | 0.0111 | 0.782 | 0.175 | 200 |
| `cell03_no_a_to_m_n100` | TNIE | 200 | 1.000 | 0.981 | pass | 0.0000 | 0.0000 | 0.000 | 0.000 | 200 |
| `cell04_no_m_to_y_n100` | PNDE | 188 | 0.940 | 0.898 | **fail** | 0.0028 | 0.0026 | 0.768 | 0.190 | 200 |
| `cell04_no_m_to_y_n100` | TE | 188 | 0.940 | 0.898 | **fail** | 0.0028 | 0.0026 | 0.768 | 0.190 | 200 |
| `cell04_no_m_to_y_n100` | TNIE | 200 | 1.000 | 0.981 | pass | 0.0000 | 0.0000 | 0.000 | 0.000 | 200 |
| `cell05_no_mediation_n100` | PNDE | 195 | 0.975 | 0.943 | pass | 0.0104 | 0.0099 | 0.775 | 0.180 | 200 |
| `cell05_no_mediation_n100` | TE | 195 | 0.975 | 0.943 | pass | 0.0104 | 0.0099 | 0.775 | 0.180 | 200 |
| `cell05_no_mediation_n100` | TNIE | 200 | 1.000 | 0.981 | pass | 0.0000 | 0.0000 | 0.000 | 0.000 | 200 |
| `cell06_parallel_interaction_n150` | TNIE | 189 | 0.945 | 0.904 | pass | -0.0011 | 0.0008 | 0.516 | 0.905 | 200 |
| `cell07_serial_three_n200` | PNDE | 188 | 0.940 | 0.898 | **fail** | 0.0063 | 0.0045 | 0.576 | 0.300 | 200 |
| `cell07_serial_three_n200` | TE | 185 | 0.925 | 0.880 | **fail** | 0.0015 | 0.0010 | 0.669 | 0.895 | 200 |
| `cell07_serial_three_n200` | TNIE | 191 | 0.955 | 0.917 | pass | -0.0048 | 0.0034 | 0.427 | 0.925 | 200 |
| `cell08_quadratic_n100` | PNDE | 190 | 0.950 | 0.910 | pass | 0.0007 | 0.0006 | 0.779 | 0.170 | 200 |
| `cell08_quadratic_n100` | TE | 191 | 0.955 | 0.917 | pass | -0.0032 | 0.0025 | 0.815 | 0.280 | 200 |
| `cell08_quadratic_n100` | TNIE | 183 | 0.915 | 0.868 | **fail** | -0.0040 | 0.0031 | 0.247 | 0.445 | 200 |
| `cell09_spline_n250` | PNDE | 191 | 0.955 | 0.917 | pass | -0.0008 | 0.0006 | 0.511 | 0.360 | 200 |
| `cell09_spline_n250` | TE | 188 | 0.940 | 0.898 | **fail** | 0.0021 | 0.0017 | 0.516 | 0.645 | 200 |
| `cell09_spline_n250` | TNIE | 187 | 0.935 | 0.892 | **fail** | 0.0029 | 0.0023 | 0.199 | 0.635 | 200 |
| `cell10_moderated_n150` | TNIE_W0 | — | — | — | excluded | -0.0047 | 0.0038 | — | 0.000 | 0 |
| `cell10_moderated_n150` | TNIE_W1 | — | — | — | excluded | -0.0065 | 0.0053 | — | 0.000 | 0 |
| `cell10_moderated_n150` | TNIE_difference | 187 | 0.935 | 0.892 | **fail** | -0.0019 | 0.0015 | 0.701 | 0.360 | 200 |
| `cell11_binary_mediator_n150` | PNDE | 188 | 0.940 | 0.898 | **fail** | 0.0017 | 0.0015 | 0.646 | 0.220 | 200 |
| `cell11_binary_mediator_n150` | TE | 189 | 0.945 | 0.904 | pass | -0.0006 | 0.0006 | 0.658 | 0.505 | 200 |
| `cell11_binary_mediator_n150` | TNIE | 179 | 0.895 | 0.845 | **fail** | -0.0023 | 0.0021 | 0.235 | 0.580 | 200 |
| `cell12_mixed_binary_serial_n250` | PNDE | 186 | 0.930 | 0.886 | **fail** | -0.0046 | — | 0.240 | 0.110 | 200 |
| `cell12_mixed_binary_serial_n250` | TE | 189 | 0.945 | 0.904 | pass | -0.0060 | — | 0.239 | 0.325 | 200 |
| `cell12_mixed_binary_serial_n250` | TNIE | 193 | 0.965 | 0.930 | pass | -0.0014 | — | 0.087 | 0.800 | 200 |


## Interpretation

- **Bias.** Estimates are essentially unbiased in every cell: at most 0.011 population SD, or 0.006 probability for the binary outcome.
- **Null cells.** The false zero-exclusion rate is 0 for the null TNIE in cells 03, 04 and 05.
- **Coverage.** Mean coverage across the 32 gated effects is **94.8%**, close to nominal.
- **Why the coverage gate failed** (analysis after the run):
  - If every interval covered exactly 95%, each effect would pass the gate with probability about 0.70. All 32 would pass with probability about 1 × 10⁻⁵, treating them as independent.
  - At a true 94%, the chance falls to about 1 × 10⁻¹¹.
  - As pre-registered, the gate is therefore effectively unattainable at 200 datasets per cell, even for well-calibrated intervals. Most failures are 185–188 of 200.
- **Genuine undercoverage.** Two effects miss more than chance explains:
  - **Cell 11 TNIE** (binary mediator, N = 150): 179 of 200, p ≈ 0.001 if true coverage were 95%.
  - **Cell 08 TNIE** (quadratic outcome, N = 100): 183 of 200, p ≈ 0.02.
  In both, the sampling distribution of the indirect effect is skewed (skewness 0.57 and 1.42). The misses are one-sided: in cell 11 the truth lay above the interval 15 times and below it 6 times, and the intervals were about 9% narrower than ideal. Across all gated effects the median interval width is 99% of ideal. This is the known weakness of the plain percentile bootstrap for skewed indirect effects.

## Consequence under the charter

The failure stands as the result of run 1. Under the charter's one-correction rule:
- the single targeted correction under investigation is a bias-corrected bootstrap interval (BC or BCa), aimed at the skewed indirect effects;
- any rerun is reported next to this record, with this record unchanged.

Separately, the coverage gate is miscalibrated for 200 datasets. That is recorded as a lesson for the **next** validation plan. This run is **not** re-graded with a different rule.
