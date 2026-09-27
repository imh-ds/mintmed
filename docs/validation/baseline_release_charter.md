# Mintmed baseline release charter

This charter fixes the full validation run (Task 15) **before** it is dispatched. After dispatch it is immutable, apart from the single documented correction allowed in [One-correction rule](#one-correction-rule). If a permitted rerun happens, the original artifacts are kept alongside the new ones.

## Identity

| Item | Value |
|---|---|
| Configuration file | `configs/mediation_validation.yaml` |
| File SHA-256 (committed LF bytes) | `fa1e8486d30364db23812c9bd8654c720cd6aa04cc823d105b22e626caf96eb7` |
| Canonical configuration hash (`load_config(...).config_hash`) | `176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94` |
| Code commit | The commit that adds this charter. Its parent, `c256c47`, is the last code/documentation change. The dispatched SHA is recorded in `baseline_evidence.md`. |
| Runner | `python -m mintmed.experiments.mediation_validation` (Python 3.11, GitHub Actions `ubuntu-latest`) |
| Execution | `.github/workflows/sharded_benchmark.yml`. Dimension 1 is `--cell-id` (12 cells). Dimension 2 is `--replicate-block` (`0of4,1of4,2of4,3of4`). That makes 48 shards, which `scripts/aggregate_shards.py` combines. |

Shard count, shard order and artifact location play no part in seed derivation. Each dataset's seeds depend only on the master seed, the cell and the replicate (see [Seeds](#seeds)).

## Design

- **Scale:** 12 cells × 200 datasets × 399 standard participant-bootstrap refits per dataset. That is 2,400 point analyses and 957,600 bootstrap refits.
- **Exposure:** binary `A` with balanced 0/1 assignment (the first two rows are 0 and 1, and the rest are shuffled), compared from **0 to 1**.
- **Covariate:** `C ~ N(0, 1)`. Every error term is an independent `N(0, 1)` unless stated.
- **Moderator:** in cell 10, `W` is binary and balanced. It is standardized at the baseline `W = 0` and contrasted at `W = 1`.

### Cells and truths

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

### Estimands

The estimands are the natural effects for the exposure contrast 0 → 1:
- `TE = μ11 − μ00`
- `PNDE = μ10 − μ00`
- `TNIE = μ11 − μ10`

Here `μ_ab` is the model-standardized mean outcome with the outcome at exposure `a` and the mediators at their exposure-`b` distributions, standardized over the retained rows. Cell 6's metric is the joint TNIE. Cell 10's primary effects are conditional on `W = 0`. There is no proportion mediated and no clipping.

## Computation

- **Seeds.** `numpy.random.SeedSequence([20260919, 1300, stream, cell_ordinal, replicate])`, with stream 1 for data and stream 2 for analysis.
- **Integration routing and tolerance.** Tolerance is `1e-3 × retained outcome SD`. The route is chosen from the fitted model:
  - exact binary enumeration when every mediator is Bernoulli;
  - exact linear propagation for all-linear Gaussian systems;
  - 64-point Gauss–Hermite with a measured order-64 against order-32 check;
  - otherwise blocked scrambled Sobol. It starts at 256 draws and doubles to at most 4,096 until the independent-scramble and doubling deltas are within tolerance. If they never are, the result is `integration_unresolved`.
- **Bootstrap.** Participant resampling with full Statsmodels refits of every node (OLS/GLM only, no custom IRLS). Bootstrap refits reuse the point analysis's accepted draw budget or quadrature order. Intervals are percentile 2.5/97.5 over successful finite values.
- **Interval rule: zero failures.** 399 is fewer than 400, so a dataset's intervals are withheld if any refit fails. Optional outputs that are missing in any replicate are withheld independently.

## Denominators and gates

- **Denominators.** Every expected `(cell_id, replicate)` combination counts. A fatal fit, integration failure or unavailable interval stays in the attempted denominator. **A missing interval counts as noncoverage** in the primary coverage figure. Available-only coverage is reported separately and descriptively.
- **Eligibility.** Cell 10's direct moderator effects (TNIE at W=0 and at W=1) are point-only by contract and are excluded from the interval gates. Its paired difference is gated.

The gates, all fixed before dispatch:

| Gate | Rule |
|---|---|
| Continuous bias | `|mean(estimate − truth)| / population SD ≤ 0.05` for every continuous cell-metric |
| Binary bias | `|mean(estimate − truth)| ≤ 0.02` probability units (cell 12) |
| Coverage | 95% Wilson lower bound of full-denominator coverage `≥ 0.90` for every eligible cell-metric |
| Null false zero-exclusion | 95% Wilson upper bound of the TNIE zero-exclusion rate `≤ 0.10` in cells 03, 04 and 05 |
| Unavailable or fatal | `≤ 1%` of rows for every eligible cell-metric |

Power (the zero-exclusion rate in non-null cells) is reported descriptively and is **not** a gate. The complete grid (every combination exactly once, one configuration hash) is a precondition for every gate.

## Runtime budget

The Task 14 budget as amended on 2026-09-27 (decision log, "Task 14 amendment — sharded runtime budget") applies. On GitHub Actions `ubuntu-latest`:
- at most **36 aggregate CPU-hours**, including a 5% rerun allowance;
- no shard projected over **4 wall-clock hours**.

The accepted pilot (run `36293907650`) forecast 20.717 CPU-hours, with the slowest shard at 1.159 hours.

## One-correction rule

If any gate fails:
- identify **one** root cause;
- make **one** targeted correction;
- rerun only the affected cells, within the runtime budget.

There will be no estimator tournament, no new feature, no grid expansion and no change to the inferential denominator. A failure that persists after that correction narrows the supported envelope or postpones the feature, and is documented as a limitation. Missing or duplicate rows block publication until resolved. They are never filled with summary statistics.

## Supported and unvalidated envelope

**Validation target.** Observed-variable mediation with independent participant rows, and a binary exposure contrast. Nodes are Gaussian or Bernoulli. The exact structures are those of the 12 cells:
- one mediator: linear, quadratic or natural-spline outcome;
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
