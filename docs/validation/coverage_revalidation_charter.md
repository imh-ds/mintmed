# Mintmed coverage revalidation charter (run 2)

This charter fixes the second validation run (Task 16) **before** it is dispatched. After dispatch it is immutable, apart from the single documented correction allowed in [One-correction rule](#one-correction-rule). If a permitted rerun happens, the original artifacts are kept alongside the new ones.

Run 2 exists because run 1 could not settle whether Mintmed's intervals are calibrated. Its coverage gate required at least 189 of 200 intervals to cover for every effect, which a perfectly calibrated method passes with probability about 1 × 10⁻⁵ across 32 effects ([`baseline_run1_results.md`](baseline_run1_results.md)). The one allowed correction, a BC or BCa interval, was checked and not adopted ([`interval_correction_check.md`](interval_correction_check.md)). Run 2 repeats the 12-cell design at 500 datasets per cell, adds two mixed-null cells, and applies a coverage rule that a calibrated method can pass. The main hypothesis under test is run 1's finding that the TNIE intervals of cells 08 and 11 under-cover.

## Relation to run 1

- **Run 1 is not re-graded.** It remains the failed Task 15 result under its own charter ([`baseline_release_charter.md`](baseline_release_charter.md)), and its record is unchanged.
- Run 2 is reported **alongside** run 1, in `coverage_revalidation_results.md` and a new section of `baseline_evidence.md`.
- The run-1 coverage gate (`coverage_wilson_lower`) does not apply to run 2. The rule below does not apply to run 1.

## Identity

| Item | Value |
|---|---|
| Configuration file | `configs/mediation_validation_v2.yaml` (experiment `mintmed_coverage_revalidation`) |
| File SHA-256 (committed LF bytes) | `6e82d246fad48e89bc2923007c82ff8869ac18dad3c0adbd1a5ec64de6f33f75` |
| Canonical configuration hash (`load_config(...).config_hash`) | `0f2f738887b2a1669cf8c281e43fb9c258652291a4c50bbed9a009ffaafb953b` (run 1: `176be112…`) |
| Code commit | The commit that adds this charter. Its parent, `b8ac243`, is the last code change. The dispatched SHA is recorded in `coverage_revalidation_results.md`. |
| Estimator under test | The current percentile participant bootstrap. No estimator or interval code (`src/mintmed` outside `experiments/`) has changed since run 1's dispatched commit `04cbf2d`. |
| Runner | `python -m mintmed.experiments.mediation_validation` (Python 3.11, GitHub Actions `ubuntu-latest`) |
| Execution | `.github/workflows/sharded_benchmark.yml` with `config: configs/mediation_validation_v2.yaml`. Dimension 1 is `--cell-id` (the 14 cells). Dimension 2 is `--replicate-block` (`0of10,1of10,…,9of10`, 50 datasets each). That makes 140 shards, which `scripts/aggregate_shards.py` combines into 7,000 expected rows. |

Shard count, shard order and artifact location play no part in seed derivation. Each dataset's seeds depend only on the master seed, the cell ordinal and the replicate (see [Computation](#computation)).

## Design

- **Scale:** 14 cells × 500 datasets × 399 standard participant-bootstrap refits per dataset. That is 7,000 point analyses and 2,793,000 bootstrap refits.
- **Master seed:** `20260927`. It is new, so no run-1 dataset (master seed `20260919`) is reused.
- **Exposure:** binary `A` with balanced 0/1 assignment (the first two rows are 0 and 1, and the rest are shuffled), compared from **0 to 1**.
- **Covariate:** `C ~ N(0, 1)`. Every error term is an independent `N(0, 1)` unless stated.
- **Moderator:** in cell 10, `W` is binary and balanced. It is standardized at the baseline `W = 0` and contrasted at `W = 1`.
- **Integration:** 256 starting draws, tolerance `1e-3`; per-analysis limits 600 s and 1,024 MB.
- **Stress fixtures:** unchanged from run 1 and descriptive only (see the envelope below).

### Cells and truths

Cells 01–12 are run 1's cells with the same generators, fitted models, truths and sample sizes. Cells 13 and 14 are new.

The truths are population values computed from the generating equations, never from generated samples. Continuous effects are in outcome units, and cell 12's are probability differences. "Pop. SD" is the population outcome SD used by the bias gate; it is closed form, or 64-point Hermite quadrature for cell 11.

| Cell | N | Generating equations | Metrics | Truth (TE / PNDE / TNIE) | Truth method | Pop. SD |
|---|---:|---|---|---|---|---:|
| `cell01_linear_n100` | 100 | `M = 0.5A + 0.3C + e`; `Y = 0.2A + 0.5M + 0.3C + e` | TE, PNDE, TNIE | 0.45 / 0.20 / 0.25 | closed form | 1.226020 |
| `cell02_linear_n250` | 250 | as cell 01 | TE, PNDE, TNIE | 0.45 / 0.20 / 0.25 | closed form | 1.226020 |
| `cell03_no_a_to_m_n100` | 100 | `M = 0.3C + e`; `Y` as cell 01 | TE, PNDE, TNIE | 0.20 / 0.20 / 0 | closed form | 1.209339 |
| `cell04_no_m_to_y_n100` | 100 | `M = 0.5A + 0.3C + e`; `Y = 0.2A + 0.3C + e` | TE, PNDE, TNIE | 0.20 / 0.20 / 0 | closed form | 1.048809 |
| `cell05_no_mediation_n100` | 100 | `M = 0.3C + e`; `Y = 0.2A + 0.3C + e` | TE, PNDE, TNIE | 0.20 / 0.20 / 0 | closed form | 1.048809 |
| `cell06_parallel_interaction_n150` | 150 | `M1 = 0.5A + e1`, `M2 = 0.4A + e2`, `corr(e1, e2) = 0.4`; `Y = 0.2A + 0.4M1 + 0.4M2 + 0.2M1M2 + 0.3C + e` | joint TNIE | — / — / 0.40 | closed form | 1.336638 |
| `cell07_serial_three_n200` | 200 | `M1 = 0.5A + 0.3C + e`; `M2 = 0.2A + 0.5M1 + 0.3C + e`; `M3 = 0.2A + 0.5M2 + 0.3C + e`; `Y = 0.2A + 0.2M1 + 0.2M2 + 0.4M3 + 0.3C + e` | TE, PNDE, TNIE | 0.56 / 0.20 / 0.36 | closed form | 1.412091 |
| `cell08_quadratic_n100` | 100 | `M = 0.5A + 0.3C + e`; `Y = 0.2A + 0.4M² + 0.3C + e`; outcome term quadratic | TE, PNDE, TNIE | 0.30 / 0.20 / 0.10 | closed form | 1.271177 |
| `cell09_spline_n250` | 250 | as cell 08; outcome term natural spline, df = 3 | TE, PNDE, TNIE | 0.30 / 0.20 / 0.10 | closed form | 1.271177 |
| `cell10_moderated_n150` | 150 | `M = (0.3 + 0.3W)A + 0.2W + 0.3C + e`; `Y = 0.2A + (0.3 + 0.3W)M + 0.2W + 0.3C + e` | TNIE at W=0, TNIE at W=1, paired W1 − W0 difference | TNIE 0.09 (W=0), 0.36 (W=1); difference 0.27 | closed form | 1.231957 |
| `cell11_binary_mediator_n150` | 150 | `M ~ Bernoulli(expit(−0.4 + 0.8A + 0.3C))`; `Y = 0.2A + 0.6M + 0.3C + e` | TE, PNDE, TNIE | 0.315967 / 0.20 / 0.115967 | 64-pt Hermite | 1.107722 |
| `cell12_mixed_binary_serial_n250` | 250 | `M1 ~ Bernoulli(expit(−0.4 + 0.8A + 0.3C))`; `M2 = 0.3A + 0.5M1 + 0.3C + e`; `Y ~ Bernoulli(expit(−0.5 + 0.2A + 0.4M1 + 0.4M2 + 0.3C))` | TE, PNDE, TNIE | 0.098818 / 0.044991 / 0.053828 | 64-pt Hermite | — (binary) |
| `cell13_a_path_only_n100` | 100 | `M = 0.5A + 0.3C + e`; `Y = 0.2A + 0.0M + 0.3C + e` | TE, PNDE, TNIE | 0.20 / 0.20 / 0 | closed form | 1.048809 |
| `cell14_b_path_only_n100` | 100 | `M = 0.0A + 0.3C + e`; `Y = 0.2A + 0.5M + 0.3C + e` | TE, PNDE, TNIE | 0.20 / 0.20 / 0 | closed form | 1.209339 |

**Fitted models of the null cells.**
- In cells 03–05 the fitted model **omits** a null path: cell 03 fits `M ~ C`; cells 04 and 05 fit `Y ~ A + C`. The TNIE is then a structural zero, with a zero-width interval at 0.
- Cells 13 and 14 fit **both** paths, `M ~ A + C` and `Y ~ A + M + C`, although one of them is zero in the generator. Their TNIE is therefore estimated, and a false indirect effect is possible. These cells test false positives when the A → M path is real and M → Y is zero (cell 13), and the reverse (cell 14).

### Estimands

The estimands are the natural effects for the exposure contrast 0 → 1:
- `TE = μ11 − μ00`
- `PNDE = μ10 − μ00`
- `TNIE = μ11 − μ10`

Here `μ_ab` is the model-standardized mean outcome with the outcome at exposure `a` and the mediators at their exposure-`b` distributions, standardized over the retained rows. Cell 6's metric is the joint TNIE. Cell 10's primary effects are conditional on `W = 0`. There is no proportion mediated and no clipping.

## Computation

Unchanged from run 1 apart from the master seed:
- **Seeds.** `numpy.random.SeedSequence([20260927, 1300, stream, cell_ordinal, replicate])`, with stream 1 for data and stream 2 for analysis (`seed_pair` in `mediation_validation.py`). Cell ordinals are 1–14 as in the table; replicates are 0–499.
- **Integration routing and tolerance.** Tolerance is `1e-3 × retained outcome SD`. The route is chosen from the fitted model:
  - exact binary enumeration when every mediator is Bernoulli;
  - exact linear propagation for all-linear Gaussian systems;
  - 64-point Gauss–Hermite with a measured order-64 against order-32 check;
  - otherwise blocked scrambled Sobol. It starts at 256 draws and doubles to at most 4,096 until the independent-scramble and doubling deltas are within tolerance. If they never are, the result is `integration_unresolved`.
- **Bootstrap.** Participant resampling with full Statsmodels refits of every node (OLS/GLM only, no custom IRLS). Bootstrap refits reuse the point analysis's accepted draw budget or quadrature order. Intervals are percentile 2.5/97.5 over successful finite values.
- **Interval rule: zero failures.** 399 is fewer than 400, so a dataset's intervals are withheld if any refit fails. Optional outputs that are missing in any replicate are withheld independently.

## Denominators and gates

- **Denominators.** Every expected `(cell_id, replicate)` combination counts. A fatal fit, integration failure or unavailable interval stays in the attempted denominator. **A missing interval counts as a miss** in the gated coverage count.
- **Eligibility.** Cell 10's direct moderator effects (TNIE at W=0 and at W=1) are point-only by contract and are excluded from the interval gates. Its paired difference is gated.

### Coverage gate: exact binomial with Bonferroni adjustment

For each coverage-eligible cell-metric, with `n = 500` datasets and `k` eligible cell-metrics:

```text
covered  = number of the n datasets whose interval contains the truth (missing interval = miss)
p_value  = BinomialCDF(covered; n, 0.95)          # one-sided, lower tail
fail     = p_value <= 0.05 / k
gate     = pass only if no cell-metric fails
```

- **k = 38.** Cells 01–05, 07–09 and 11–14 contribute TE, PNDE and TNIE (12 × 3 = 36); cell 06 contributes its joint TNIE (1); cell 10 contributes its paired difference (1). Cell 10's TNIE_W0 and TNIE_W1 are excluded. The structural-zero TNIEs of cells 03–05 are included, as in run 1. The code derives k from the eligible rows of the aggregated results; it is not hard-coded.
- **Per-effect level:** `0.05 / 38 = 0.0013158`.
- **Critical count: 458 of 500** (91.6%), from `coverage_critical_count(500, 38, 0.95, 0.05)`. An effect fails if 458 or fewer of its 500 intervals contain the truth: `BinomialCDF(458; 500, 0.95) = 0.00086`, while `BinomialCDF(459; 500, 0.95) = 0.00155`.
- **Operating characteristics** (scipy `binom`, treating effects as independent):

  | True coverage of an effect | Probability that effect fails |
  |---:|---:|
  | 0.95 | 0.00086 |
  | 0.94 | 0.019 |
  | 0.93 | 0.129 |
  | 0.92 | 0.394 |
  | 0.90 | 0.900 |

  If every effect covers at exactly 95%, all 38 pass with probability **0.968**, so the family-wise false-failure rate is 0.032.
- **Descriptive only:** the 95% Wilson interval of full-denominator coverage, available-only coverage, and the miss sides (truth above or below the interval). They play no part in the verdict.
- **One-sided.** The rule fails only undercoverage. Overcoverage is reported but never fails the gate.

### All gates

All fixed before dispatch. The non-coverage thresholds are unchanged from run 1.

| Gate | Rule |
|---|---|
| Continuous bias | `|mean(estimate − truth)| / population SD ≤ 0.05` for every continuous cell-metric |
| Binary bias | `|mean(estimate − truth)| ≤ 0.02` probability units (cell 12) |
| Coverage (`coverage_exact_binomial_bonferroni`) | No eligible cell-metric has `BinomialCDF(covered; 500, 0.95) ≤ 0.05 / 38`, i.e. every one covers at least 459 of 500 |
| Null false zero-exclusion | 95% Wilson upper bound of the TNIE zero-exclusion rate `≤ 0.10` in cells 03, 04, 05, 13 and 14 |
| Unavailable or fatal | `≤ 1%` of rows for every eligible cell-metric |

Power (the zero-exclusion rate in non-null cells) is reported descriptively and is **not** a gate. The complete grid (every combination exactly once, one configuration hash) is a precondition for every gate.

### Caveat for the mixed-null cells

In cells 13 and 14 the TNIE is a product of two path effects, one of which is truly zero. The sampling distribution of such a product is sharply peaked at zero, and percentile intervals for it tend to be conservative. Their coverage of the true value 0 may therefore sit above 95%. That is expected and does not fail the one-sided coverage rule. The informative results for these cells are the false zero-exclusion rate (gated) and the TE and PNDE coverage.

## Runtime budget

The Task 14 budget as amended on 2026-09-27 (decision log, "Task 14 amendment — sharded runtime budget") applies. On GitHub Actions `ubuntu-latest`:
- at most **36 aggregate CPU-hours**, including a 5% rerun allowance;
- no shard projected over **4 wall-clock hours**.

**Forecast basis.** Cells 01–12 use run 1's measured per-cell runtimes on GitHub Actions (run `36296143027`), scaled from 200 to 500 datasets. Cells 13 and 14 use a GitHub pilot of those two cells.

**Forecast** (`scripts/run_runtime_pilot.py --forecast-only`, v2 config, 500 datasets, 10 replicate blocks):

| Item | Value |
|---|---|
| Cell 13 / cell 14 pilot | GitHub run `36349462559`, 2 repeats each, both `complete`; median about 7.0 s and 6.9 s per dataset (`gaussian_linear_exact`) |
| Shards | 140 (14 cells × 10 blocks of 50 datasets) |
| Base compute | 29.79 CPU-hours |
| With the 5% rerun allowance | **31.28 CPU-hours** of 36 (pass) |
| Slowest shard | `cell10_moderated_n150`, **1.10 wall-clock hours** of 4, including the 5% allowance (pass) |

The forecast is a runtime boundary, not statistical evidence.

## One-correction rule

If any gate fails:
- identify **one** root cause;
- make **one** targeted correction;
- rerun only the affected cells, within the runtime budget.

There will be no estimator tournament, no new feature, no grid expansion and no change to the inferential denominator. A failure that persists after that correction narrows the supported envelope or postpones the feature, and is documented as a limitation. Missing or duplicate rows block publication until resolved. They are never filled with summary statistics.

## Supported and unvalidated envelope

**Validation target.** Observed-variable mediation with independent participant rows, and a binary exposure contrast. Nodes are Gaussian or Bernoulli. The estimator under test is the current percentile participant bootstrap, unchanged from run 1. The exact structures are those of the 14 cells:
- one mediator: linear, quadratic or natural-spline outcome;
- one mediator with both paths fitted but one truly zero (mixed-null, cells 13 and 14);
- two correlated parallel mediators with an M1 × M2 interaction;
- three serial Gaussian mediators;
- a binary moderator of the A → M and M → Y paths;
- a binary mediator with a Gaussian outcome;
- binary and Gaussian serial mediators with a binary outcome.

Sample sizes range from 100 to 250.

**Unvalidated.** The package runs these but this matrix does not validate them:
- four-mediator inference;
- continuous exposures;
- continuous moderators and declared moderator evaluation values;
- categorical predictors with more than two levels;
- individual parallel contributions;
- the `assumption_based_causal` interpretation, which rests on untestable assumptions;
- samples below 100.

**Unsupported.** Repeated or multilevel rows, latent measurement, ordinal and count nodes, and automatic term selection.

**Stress diagnostics.** The configured N = 50 stress fixtures (tied score, sparse events, missingness, opposing paths) are run separately with `--stress-only`. They are reported descriptively and are outside every inferential denominator and gate.
