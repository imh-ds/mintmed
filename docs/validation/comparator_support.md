# Task 17 comparator support and estimand mapping (T17-S4)

## Scope

This document records, for every validation cell and each R comparator,
the model fitted, how its output maps to Mintmed's estimands, or why the cell
cannot be estimated. It covers Stage 1 of Task 17, where all tools fit correctly
specified models to the exact datasets Mintmed analysed. The runners are:

- `benchmarks/comparators/r/run_mediation.R`: `mediation::mediate()` 4.5.1.
- `benchmarks/comparators/r/run_lavaan.R`: lavaan 0.6-21, used only as an
  observed-variable path model (`sem()` on measured variables, labelled
  regressions and `:=` defined parameters). It has no latent variables and no
  measurement model.
- `src/mintmed/experiments/comparator_benchmark.py`: the shardable Python
  wrapper. It exports the datasets, calls the runners and writes the raw
  rows. `comparator_benchmark_reporting.py` summarises them and compares them
  with Mintmed.

The support matrix, with the reason for each cell that cannot be estimated,
lives in one file: `benchmarks/comparators/support_matrix.json`. Both the
R runners and the Python module read it. A test checks it against the plan.

## Datasets, seeds and determinism

- The datasets come from `scripts/export_validation_datasets.py`, using
  `configs/mediation_validation_v3.yaml`.
  - Cells 01–14 are exactly the run-2 datasets.
  - Cells 15 and 16 are N = 250 copies of cells 13 and 14.
  - Each CSV is written with `%.17g` and read with R's `read.csv`. The
    values are the same bits Mintmed analysed.
- **Seed rule.** The manifest stores `analysis_seed` as a decimal string,
  because it is an unsigned 64-bit integer above 2^53.
  - R computes `analysis_seed mod 2147483647` digit by digit. Each
    intermediate value stays below 10 × 2^31, so it is exact in a double.
  - R calls `set.seed()` with that value, after fixing
    `RNGkind("Mersenne-Twister", "Inversion", "Rejection")`.
  - It does this immediately before every `mediate()` or `sem()` call: once
    per mode, and once per moderator level in cell 10.
  - The Python equivalent is `int(analysis_seed) % 2147483647`. It is stored as
    `r_seed` in every row, and a test checks that R and Python agree.
- **Determinism.** Rerunning a runner on the same manifest gives byte-identical
  rows apart from `runtime_seconds`. `tests/integration/test_comparator_r_runners.py`
  checks this.
- **Failures.** Errors and warnings are caught for each dataset and become
  statuses:
  - `ok`;
  - `ok_warnings`, with the warning text kept;
  - `error`;
  - `not_estimable`.

  A failing R process becomes `runner_failed` rows in Python. A missing
  mode or effect becomes a `missing_output` record. No row is dropped and no value is
  imputed.

## Modes

| Tool | Mode | Settings | Point estimate | Interval |
|---|---|---|---|---|
| mediation | primary | `boot = TRUE, sims = 399, boot.ci.type = "perc"` | original-sample `med.fun` (see below) | percentile of 399 nonparametric bootstrap refits, `quantile` type 7 |
| mediation | secondary (descriptive) | package default quasi-Bayesian, `sims = 1000` | mean of the 1000 simulated effects | percentile of the simulations |
| lavaan | primary | `sem(se = "bootstrap", bootstrap = 399)`, `parameterEstimates(boot.ci.type = "perc")` | ML estimate on the original sample | percentile of 399 bootstrap refits |
| lavaan | secondary (descriptive) | `sem()` defaults | ML estimate | normal-theory 95% interval, delta-method SE |

The primary bootstrap count comes from the config's `bootstrap_replicates`, which is 399, the same number of refits Mintmed uses.
Lowering it (as the tests do with `--boot-sims`) is recorded in every row's
provenance and flagged in the report.

## How `mediate()` computes its point estimate with `boot = TRUE`

Confirmed from the mediation 4.5.1 source (`mediate()` and the internal `med.fun`):

1. **Bootstrap draws.** The bootstrap draws come from
   `boot::boot(data = y.data, statistic = med.fun, R = sims)`.
   - `boot` generates all resample indices first.
   - It then evaluates `med.fun` on the original data (`t0`, not used by
     `mediate`).
   - Then it runs the `sims` refits.
2. **Reported estimates.** The reported `d1`, `d0`, `z1` and `z0` come from a
   separate call, `med.fun(y.data, index = 1:n, m.data)`, on the original rows
   **after** the bootstrap. They are **not** the mean of the bootstrap draws.
   `tau.coef` is `(d1 + d0 + z1 + z0) / 2`.
3. **What `med.fun` computes.** Inside `med.fun`, the mediator is simulated
   once per observation, and the effects are the sample means of the
   predicted outcome contrasts.
   - For an `lm` mediator it uses the predicted mean plus one
     `rnorm(n, 0, sigma)` draw. The same draw is shared by `M(1)` and `M(0)`.
   - For a binomial `glm` mediator it takes one `rbinom` draw for each
     treatment level.

   The percentile interval uses `quantile(type = 7)` of the `sims` bootstrap
   draws.

Consequences:

- **Outcome linear in M** (cells 01–05, 10, 13–16). The shared error cancels
  in every contrast, so the primary-mode point estimate is exact: it equals
  the OLS path product. The runner tests check this to 1e-10.
- **Outcome nonlinear in M, or a binary mediator** (cells 08, 09, 11). The point
  estimate carries Monte Carlo error from that single set of `n` draws.
  - The error does not shrink with `sims`. It shrinks only with `n`.
  - Mintmed integrates exactly: Gauss–Hermite quadrature for cells 08 and 09,
    and exact enumeration of the binary mediator for cell 11.
  - The size of this error is quantified below.
- **Quasi-Bayesian mode.** Point estimates are averages over parameter draws,
  so they carry simulation error in every cell.

## Model frames: a documented runner adjustment

`mediate()` reads the treatment and mediator columns from
`model.frame(model.m)` and `model.frame(model.y)`. It also re-evaluates each model's call on resampled model
frames. Mintmed's own specifications break this in three situations:

- **Reduced specifications (cells 03–05).** The mediator model omits `A` (cells 03 and 05), or the outcome model omits
  `M` (cells 04 and 05). Called directly, `mediate()` stops with
  `undefined columns selected`. This was verified on cells 03 and 04.
- **Transformed mediator terms (cells 08 and 09).** The frame holds `I(M^2)` or `ns(M, df = 3)`
  but not `M`, so `mediate()` stops with the same error. Worse, the refits
  cannot find the raw `M` column.
- **Quasi-Bayesian mode with a transformed term.** `mediate()` calls
  `model.matrix(terms(model.y), data = frame)`. If the frame keeps its `terms`
  attribute, `model.matrix` reuses the stale basis columns evaluated at the
  observed `M`, instead of the simulated `M`.
  - This silently returned **TNIE = 0** in cells 08 and 09 during development.
  - It is a pitfall for users as well: `Y ~ A + C + M + I(M^2)` runs without
    error, but the quasi-Bayesian ACME ignores the quadratic part.

The runner therefore appends any missing raw dataset columns to each fitted
model's stored frame (`fit$model`). When the frame contains a transformed term,
it also drops the frame's `terms` attribute, so `model.matrix` re-evaluates the
term, with the fit's stored knots, from the simulated `M`.

- The fitted coefficients are untouched.
- The appended columns never enter a formula.
- `predict()` (used in bootstrap mode) is unaffected.
- The formula is spliced into each model call, so `mediate()` can refit the
  model on resampled data.
- Every row records the adjustment in its `model` field. For example: "raw columns
  appended to model frames: Y,M; terms attribute dropped from frames with
  transformed terms".

With this adjustment, `mediate()` returns TNIE = 0 exactly, with interval
[0, 0], in cells 03–05 in both modes, because `M` does not depend on `A`, or `Y`
does not depend on `M`. This matches Mintmed, which also reports 0 with
[0, 0]. TE and PNDE equal the direct coefficient there.

## Cell-by-cell support and fitted models

The fitted node models are generated from each cell's exported `cell.json` (Mintmed's compiled spec).
There are no hand-written per-cell formulas.

- **Formula terms.** The R formula builder in `common.R` maps:
  - `linear` to `x`;
  - `quadratic` to `I(x^2)` alone;
  - `natural_spline` to `ns(x, df)`;
  - interactions to `x:z`.
- **Families.** Gaussian nodes are fitted by `lm` in mediate, and by ML
  regression in lavaan. Bernoulli nodes are fitted by
  `glm(binomial("logit"))`.
- **Covariates.** The covariate `C` is included wherever Mintmed includes it. It is a
  regressor in the Y node in every cell, and in the M node in every cell except 06.
- **Effects.** Effects are averaged over the empirical covariate
  distribution, as Mintmed's model-standardised contrasts are.

| Cell | Mintmed fitted spec | `mediate()` | lavaan path model |
|---|---|---|---|
| 01 linear N=100, 02 linear N=250 | `M ~ A + C`; `Y ~ A + C + M` | supported; TNIE = d1, PNDE = z0, TE = tau.coef | supported; `M ~ M__A*A + M__C*C; Y ~ Y__A*A + Y__C*C + Y__M*M; TNIE := M__A*Y__M; PNDE := Y__A; TE := Y__A + M__A*Y__M` |
| 03 no A→M | `M ~ C`; `Y ~ A + C + M` | supported; TNIE is a structural 0 (see above) | supported; `M ~ M__C*C; Y ~ Y__A*A + Y__C*C + Y__M*M`; TNIE is a structural zero reported as 0 with [0, 0] (no A→M→Y path); `PNDE := Y__A; TE := Y__A` |
| 04 no M→Y | `M ~ A + C`; `Y ~ A + C` | supported; TNIE is a structural 0 | supported; `M ~ M__A*A + M__C*C; Y ~ Y__A*A + Y__C*C`; TNIE is a structural zero; `PNDE := Y__A; TE := Y__A` |
| 05 no mediation | `M ~ C`; `Y ~ A + C` | supported; TNIE is a structural 0 | supported; `M ~ M__C*C; Y ~ Y__A*A + Y__C*C`; TNIE is a structural zero; `PNDE := Y__A; TE := Y__A` |
| 06 parallel with M1×M2 | `M1 ~ A`; `M2 ~ A`; `Y ~ A + C + M1 + M2 + M1:M2` | **not estimable**: the joint TNIE of two interacting parallel mediators is outside `mediate()`'s single-mediator design | **not estimable**: the outcome is nonlinear in the mediators (M1×M2), so natural effects are not path products |
| 07 three serial | `M1 ~ A + C`; `M2 ~ A + M1 + C`; `M3 ~ A + M2 + C`; `Y ~ A + M1 + M2 + M3 + C` | **not estimable**: three serial mediators | supported; four labelled regressions. `TNIE :=` the sum of the six A→…→Y path products: `M1__A*M2__M1*M3__M2*Y__M3 + M1__A*M2__M1*Y__M2 + M1__A*Y__M1 + M2__A*M3__M2*Y__M3 + M2__A*Y__M2 + M3__A*Y__M3`; `PNDE := Y__A`; `TE := PNDE + TNIE` |
| 08 quadratic | `M ~ A + C`; `Y ~ A + C + I(M^2)` (no linear M) | supported with `Y ~ A + C + I(M^2)`; point estimate has Monte Carlo error | **not estimable**: nonlinear in M |
| 09 spline | `M ~ A + C`; `Y ~ A + C + cr(M, df=3, constraints="center")` | supported with `Y ~ A + C + ns(M, df = 3)`: the same function space as Mintmed's basis (below); point estimate has Monte Carlo error | **not estimable**: nonlinear in M |
| 10 moderated | `M ~ A + W + C + W:A`; `Y ~ A + W + C + M + W:M` | supported (see below) | supported (see below) |
| 11 binary mediator | `M ~ A + C` (logit); `Y ~ A + M + C` | supported, `glm(binomial("logit"))` mediator; point estimate has Monte Carlo error from Bernoulli draws | **not estimable**: lavaan's probit latent-response effects are a different estimand |
| 12 binary serial | `M1 ~ A + C` (logit); `M2 ~ A + M1 + C`; `Y ~ A + M1 + M2 + C` (logit) | **not estimable**: two serial mediators | **not estimable**: binary nodes |
| 13–16 mixed null | `M ~ A + C`; `Y ~ A + C + M` (both paths fitted, one is zero in the generator) | supported, as in cell 01 | supported, as in cell 01 |

Label convention in lavaan: `<response>__<regressor>`, so `Y__M` is the
M→Y coefficient.

### Cell 09: spline basis decision

**Decision:** reproduce Mintmed's basis in R, rather than use a merely comparable one.

Mintmed fits patsy's `cr(M, df=3, constraints="center")`. This is a natural
cubic regression spline with four knots:

- the two boundary knots at min(M) and max(M);
- two inner knots at the 1/3 and 2/3 quantiles of M (NumPy's linear
  interpolation, which is R's `quantile` type 7);
- a sum-to-zero centring constraint.

The fitted model has an intercept, so the centred basis plus the intercept
spans the full natural cubic spline space on those knots. That space has
dimension 4. The curve is cubic between the knots and linear beyond the
boundary knots. Probing patsy confirmed the linear extrapolation beyond max(M).

`splines::ns(M, df = 3)` places its knots in exactly the same positions:

- inner knots at `quantile(M, c(1/3, 2/3))`, type 7;
- boundary knots at `range(M)`.

Together with the intercept, it spans the same space, with linear
extrapolation. The two bases are different parametrisations of the same fitted
function, so fitted values and counterfactual predictions are identical.

- `test_r_natural_spline_spans_patsy_cr_basis` checks this on cell 09,
  replicate 0. The fitted values, and predictions at median(M), min(M) − 1 and
  max(M) + 1.5, agree to 1e-9.
- As in Mintmed, the knots are recomputed from each bootstrap resample.
  `mediate()` refits `ns(M, df = 3)` on the resample, and `predict()` uses
  that fit's stored knots.

### Cell 10: conditional indirect effects at W = 0 and W = 1

Mintmed reports three effects for cell 10:

- `TNIE_W0` and `TNIE_W1`: point estimates only. Mintmed withholds their
  intervals, so they carry no interval in its metrics.
- `TNIE_difference = TNIE_W1 − TNIE_W0`: with a bootstrap interval.

How each tool computes them:

- **mediate.** Two calls, with `covariates = list(W = 0)` and
  `list(W = 1)`, each preceded by the same `set.seed`.
  - `boot::boot` draws all resample indices before any statistic, so the two
    calls use identical resamples. In quasi-Bayesian mode, they use identical
    parameter draws.
  - `TNIE_difference` is `d1(W=1) − d1(W=0)`. Its percentile interval comes
    from the per-draw paired differences.
  - The runner verifies the pairing. The outcome model has no A×W term, so
    the `z0` draws do not depend on W and must agree across the two calls,
    to 1e-9 relative. If they do not, the difference is reported as an `error`.
  - `mediation::test.modmed()` is not used; the difference is formed from the
    two calls' own draws.
- **lavaan.**
  - The runner adds observed product columns: `W_x_A = W·A` for the M
    equation and `W_x_M = W·M` for the Y equation.
  - The defined parameters are:
    - `TNIE_W0 := M__A*Y__M`;
    - `TNIE_W1 := (M__A + 1*M__W_x_A)*(Y__M + 1*Y__W_x_M)`;
    - `TNIE_difference := TNIE_W1 − TNIE_W0`, written out.

  lavaan treats the product columns as exogenous observed covariates. Every
  node's regression is still fitted separately, so the coefficients equal OLS.
  (The joint model is not saturated: M is not regressed on `W_x_M`. That
  affects the fit statistics only.)

Both tools also report intervals for `TNIE_W0` and `TNIE_W1`. The paired
comparison with Mintmed judges those two effects on bias only: interval-based
checks are "not applicable" because Mintmed has no interval for them.

## Known differences from Mintmed

1. **lavaan ML versus OLS.** lavaan's regression coefficients in these
   recursive, observed-variable models equal the OLS coefficients, because
   the likelihood factorises by node. Its ML residual variances divide by N
   rather than N − p, which changes no coefficient or effect. The
   delta-method secondary intervals use ML standard errors.
2. **`mediate()` Monte Carlo point estimates.** These carry Monte Carlo error
   in cells 08, 09 and 11 in bootstrap mode, and in every cell in
   quasi-Bayesian mode. Mintmed integrates these cells exactly. Measured on
   replicate 0 (numbers in the next section).
3. **Bootstrap resamples differ.** Each tool draws its own resamples from its
   own RNG, so intervals are compared by their operating characteristics over
   500 datasets, not interval by interval. Point estimates are compared
   directly.
4. **Quantile definitions.** mediate uses R's `quantile` type 7. lavaan uses its own
   percentile computation. These differences are negligible at 399 draws.
5. **TE in mediate** is `tau.coef = (d1 + d0 + z1 + z0) / 2`. With no A×M term,
   `d0 = d1` and `z1 = z0` draw by draw, so it equals `d1 + z0`.

## Monte Carlo error of `mediate()` point estimates

Replicate 0 of each cell, with the runner's model-frame handling. Each entry is
the standard deviation of the TNIE point estimate across RNG seeds, on one fixed dataset:

- bootstrap mode: 400 seeds with `sims = 2`, and 20 seeds with `sims = 399`
  (the point estimate does not depend on `sims`);
- quasi-Bayesian mode: 100 seeds with `sims = 1000`.

| Cell | Mintmed TNIE (exact integration) | mediate boot: mean over 400 seeds | boot SD (`sims` 2 / 399) | QB mean | QB SD |
|---|---:|---:|---:|---:|---:|
| 01 linear | 0.277650 | 0.277650 | 3e-18 / 0 (exact) | 0.27750 | 0.0037 |
| 08 quadratic | 0.037281 | 0.03887 | 0.0188 / 0.0147 | 0.03736 | 0.0013 |
| 09 spline | 0.027696 | 0.02799 | 0.0340 / 0.0303 | 0.02803 | 0.0017 |
| 11 binary mediator | 0.236817 | 0.23637 | 0.0432 / 0.0442 | 0.23293 | 0.0028 |

Reading the table:

- **Bootstrap-mode point estimates are unbiased for Mintmed's value.** In cells 08, 09 and 11, the mean over
  seeds agrees with Mintmed's value within its Monte Carlo SE (SD / 20).
- **But one run is noisy.**
  - The seed-to-seed SD is about 0.015–0.019 for cell 08 (TNIE truth 0.10).
  - It is about 0.03 for cell 09 (truth 0.10) and about 0.044 for cell 11
    (truth about 0.21).
  - This noise does not shrink with `sims`, because it comes from the single
    set of `n` mediator draws.
  - It inflates mediate's RMSE and bias MC SE in these cells relative to Mintmed. It
    also adds noise to point-estimate sign agreement, though not to the
    expected bias. The bootstrap draws carry the same kind of noise, which widens the
    percentile intervals.
- **PNDE has no such noise.** The direct effect `z0` is exact in bootstrap
  mode (SD 0) in all four cells, because the outcome models have no A×M term.
- **The quasi-Bayesian point is an average over 1000 parameter draws.** Its seed-to-seed SD is
  0.001–0.004.
  - In cell 11 its mean (0.2329) differs from the plug-in value (0.2368) by
    more than Monte Carlo error.
  - This is expected: averaging a nonlinear (logit) effect over parameter
    uncertainty is not the plug-in estimate.

Timing note: a quasi-Bayesian run with `ns()` is slow (cell 09: about 8.6 s per
dataset), because `model.matrix` rebuilds the spline basis for each draw.

## Harness check against Mintmed run 2 (cell 01, replicates 0–9)

Run locally on 2026-09-28 with full settings: 399 bootstrap refits and 1000
quasi-Bayesian simulations. The comparison uses Mintmed's run-2 point estimates
(GitHub run 36349731184), on the same 10 datasets.

| Tool / mode | max \|Δ TNIE\| | max \|Δ PNDE\| | max \|Δ TE\| |
|---|---:|---:|---:|
| lavaan primary and secondary | 3.3e-16 | 4.5e-16 | 4.7e-16 |
| mediate primary (bootstrap) | 3.3e-16 | 3.7e-16 | 6.7e-16 |
| mediate secondary (quasi-Bayesian) | 5.4e-3 (mean 1.9e-3, SD 2.4e-3) | 1.3e-2 | 1.5e-2 |

- **lavaan and bootstrap-mode mediate** agree with Mintmed to floating-point
  rounding (below 1e-15).
- **Quasi-Bayesian mediate** differs by simulation error of the size measured above: SD
  0.0037 for TNIE and 0.0066 for PNDE on one dataset.
- **Cell 10 (moderated), replicate 0.** Both tools reproduce Mintmed's
  `TNIE_W0`, `TNIE_W1` and `TNIE_difference` to about 1e-15.

**Harness tolerances (T17-S5).** They are declared in
`comparator_benchmark.py`:

- `EXACT_POINT_TOLERANCE = 1e-8`: lavaan in both modes, and bootstrap-mode
  mediate in the linear-in-M cells.
- `QUASI_BAYES_TOLERANCE_MULTIPLIER = 5`: five times the quasi-Bayesian
  point's Monte Carlo SE, estimated as the percentile-interval width / 3.92 /
  √sims.
- For cells 08, 09 and 11: a 200-seed average of the bootstrap-mode point
  must lie within 4 SE of Mintmed. PNDE there must be exact.

`tests/integration/test_comparator_harness.py` enforces them on replicates
0–4 of every all-linear cell. It compares against Mintmed recomputed on the
exported datasets.

Local run on 2026-09-28:

| Check | Result |
|---|---|
| lavaan, both modes | max \|Δ\| 1.1e-15 |
| mediate bootstrap mode | max \|Δ\| 2.4e-15 |
| mediate quasi-Bayesian mode | largest \|Δ\| / tolerance 0.70 |

Seed averages on replicate 0 (a harness check, not a verdict):

| Cell | Seed-average TNIE − Mintmed | Tolerance |
|---|---:|---:|
| 08 | +0.0014 | 0.0054 |
| 09 | −0.0016 | 0.0088 |
| 11 | −0.0009 | 0.0120 |

The fresh Mintmed points also match the stored run-2 rows, within 1e-8. The CI job
`r-comparators-env` runs these tests with `MINTMED_REQUIRE_R=1`, so they
cannot skip there.

The feasibility of the Stage 1 comparison rules is calibrated separately in
`comparator_rule_calibration.md`.

## Runtime

Measured locally with full settings on replicate 0 of every cell: Windows 11,
R 4.6.0, one process per tool. One extra R process was running at the same
time, so the times are indicative. The numbers are elapsed seconds per dataset.

| Cells | mediate primary | mediate QB | lavaan primary | lavaan delta |
|---|---:|---:|---:|---:|
| 01–05, 13–16 (single mediator, N = 100–250) | 1.6–2.9 | 2.6–3.1 | 9.7–13.2 | 0.06–0.08 |
| 07 serial three | n/e | n/e | 14.0 | 0.07 |
| 08 quadratic | 3.0 | 4.5 | n/e | n/e |
| 09 spline | 5.0 | 8.6 | n/e | n/e |
| 10 moderated (two conditional calls) | 6.5 | 6.4 | 14.4 | 0.06 |
| 11 binary mediator | 3.1 | 2.7 | n/e | n/e |

`n/e` means the cell is not estimable by that tool.

Over 500 datasets per cell, the total is about **32 CPU-hours**:

| Tool / mode | CPU-hours |
|---|---:|
| mediate primary | 5.8 |
| mediate quasi-Bayesian | 6.5 |
| lavaan bootstrap | 19.7 |
| lavaan delta method | 0.1 |

- lavaan's 399 ML refits (about 33 ms each) dominate the total.
- GitHub `ubuntu-latest` runners may be slower, so the forecast for the charter (T17-S7) should come from
  a GitHub pilot.
- Sharded 16 cells × 4 replicate blocks, with both tools in each shard, the
  longest shard (cell 10: both mediate modes plus both lavaan modes) is about
  125 datasets × 27 s, or about 1 hour.

## Paired comparison rules as implemented

`comparator_benchmark_reporting.py` applies `stage1.comparison_rules` to each
comparator's primary mode. The interpretation choices below are to be
confirmed when the Stage 1 charter is frozen (T17-S7):

- **Primary agreement rates** are judged on their lower Wilson bound (`tier`).
  - `tier_primary_on_point` also reports the tier with the observed rates.
  - The reason: a Wilson lower bound of 0.99 needs about 380 significant pairs
    even with perfect sign agreement. That is unattainable for effects with
    low power.
- **Guardrail losses** are judged on the upper bound of a paired percentile
  bootstrap interval. It uses 2000 joint resamples of the datasets, with a
  seed derived from the tool, cell and effect.
- **A missing interval** counts as a decision disagreement and as
  noncoverage.
- **Sign agreement** requires equal point-estimate signs on the datasets
  where either method's interval excludes zero.
- **Tolerable tier.** Limits that the tolerable tier does not list (sign
  agreement, bias excess) keep their negligible values. `coverage_abs_min`
  applies to Mintmed's coverage point estimate.
- **Checks that do not apply** do not affect the tier. Examples: the interval
  checks for cell 10's point-only `TNIE_W0` and `TNIE_W1`, and the width ratio of a structural
  zero.
