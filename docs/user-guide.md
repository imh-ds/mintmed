# Mintmed user guide

Mintmed estimates natural direct and indirect effects for **observed-variable** mediation models. You declare every node model explicitly, and Mintmed evaluates the effects with a model-standardized g-formula. This guide explains how to run an analysis and how to read its results.

> **Research beta.** Mintmed was checked only on the 14 simulation designs in [`validation/baseline_evidence.md`](validation/baseline_evidence.md), in two pre-registered runs fixed by [`validation/baseline_release_charter.md`](validation/baseline_release_charter.md) and [`validation/coverage_revalidation_charter.md`](validation/coverage_revalidation_charter.md). **Neither run fully passed.**
> - In all 14 designs, the point estimates were essentially unbiased.
> - **Run 1** failed its interval coverage check. Coverage averaged 94.8%, but the check was nearly impossible to pass at 200 datasets per design.
> - **Run 2** (500 datasets per design) passed its coverage check, with coverage averaging 94.9%, but **failed its check for false indirect effects**: in one mixed-null design, indirect-effect intervals excluded zero too often. See [Uncertainty](#uncertainty).
> - Designs outside the 14 run, but are **not validated**. See [What Mintmed does not do](#what-mintmed-does-not-do).

## Installation

Mintmed requires Python 3.11.

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install .
```

## Running the examples

Each example folder contains a CSV file and a YAML specification.

```powershell
mintmed --data examples/single/data.csv --spec examples/single/analysis.yaml --output results/single
mintmed --data examples/parallel/data.csv --spec examples/parallel/analysis.yaml --output results/parallel
mintmed --data examples/serial_moderated/data.csv --spec examples/serial_moderated/analysis.yaml --output results/serial_moderated
```

| Example | What it shows |
|---|---|
| `single` | One mediator with a categorical binary exposure. |
| `parallel` | Two correlated parallel mediators, with a smooth (spline) term and an interaction in the outcome model. |
| `serial_moderated` | Two serial mediators, with a binary moderator evaluated at W = 0 and W = 1. |

All three use `quick_diagnostic` bootstrap mode, so their intervals are **provisional** (see [Uncertainty](#uncertainty)).

### Outputs

Each run writes four files to the output folder:

| File | Contents |
|---|---|
| `analysis.json` | The full versioned result: effects, intervals, diagnostics, hashes and provenance. |
| `effects.csv` | One row per effect, with its interval, status, reason and moderator conditioning (`evaluated_at`). |
| `bootstrap.csv` | One row per bootstrap replicate. Participant row identifiers are never written. |
| `report.md` | A readable report of the answer, uncertainty, model, assumptions, diagnostics and limitations. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | The analysis ran. The overall status is `complete`, `complete_with_warnings` or `point_only`. If requested intervals were unavailable, the CLI also writes a note to stderr. |
| `1` | The analysis failed with a structured status, such as invalid data, a failed fit or unresolved integration. The four files are still written. |
| `2` | The input, specification or output location was unusable. No analysis ran. |

## Declaring an analysis

A specification declares every variable, node model, scientific edge and contrast. Nothing is inferred from the data. The main sections are:

| Section | What it declares |
|---|---|
| `exposure` | Name and type. A `binary` exposure needs levels `[0, 1]`; a categorical one needs its levels. Also declares the reference and comparison values. |
| `mediators` | One to four mediators, each `continuous` with the `gaussian` family or `binary` with the `bernoulli` family. |
| `outcome` | The outcome, `continuous`/`gaussian` or `binary`/`bernoulli`. |
| `mediator_order` | The order in which mediators are factorized. |
| `arrangement` | `parallel` or `sequential`. |
| `baseline` | Pre-exposure covariates. |
| `moderators` | Pre-exposure moderators. |
| `participant_id` | Optional. A categorical column that must be unique per row. |
| `scientific_edges` | The declared causal graph. Mediator-to-mediator edges must follow `mediator_order` and are not allowed in a parallel arrangement. |
| `models` | For each mediator and the outcome: `intercept: true`, the `terms` and the `interactions`. |
| `contrast` | Optional moderator settings and the interpretation (see below). |
| `missing` | `error` or `complete_case`. |
| `computation` | `seed`, `bootstrap`, `bootstrap_mode`, `integration_draws`, `integration_tolerance`, `max_seconds` and `memory_budget_mb`. |

### Terms

Each term has a basis:

| Basis | Use for | Notes |
|---|---|---|
| `linear` | Continuous predictors, or 0/1 binary predictors | |
| `quadratic` | Continuous predictors | Adds the squared term only. |
| `natural_spline` | Continuous predictors | Requires `df: 3`. |
| `categorical` | Categorical predictors | Required for categorical predictors; a numeric code is not evidence that a variable is continuous. Not allowed on continuous predictors. |

Both members of an interaction must also be declared as main terms on the same node.

### Contrast

- **Exposure contrast.** Every effect compares exposure `comparison` with exposure `reference`.
- **Moderator baseline.** `contrast.moderator_values` fixes the moderator values that the primary effects are standardized at.
- **Moderator evaluation values.** `contrast.moderator_evaluation` lists the values each moderator is compared at, for example `{age: [30, 40, 50]}`. Without it, moderators with declared levels are compared at those levels, and continuous moderators are not compared at all.
- **Interpretation.** `contrast.interpretation`, or the top-level `interpretation`, sets how effects may be read (see below). If you declare both, they must agree.

## Reading the effects

### The natural-effect convention

Let `μ_ab` be the mean outcome with the outcome set at exposure `a` and the mediators at their exposure-`b` distribution, standardized over the retained rows. Then:

- **Total effect:** `TE = μ11 − μ00`
- **Pure natural direct effect:** `PNDE = μ10 − μ00`
- **Total natural indirect effect:** `TNIE = μ11 − μ10`

`TE = PNDE + TNIE` holds exactly. Mintmed never clips effects or reports a proportion mediated. A statistically significant total effect is **not** required before indirect effects are reported.

### Units

- A **continuous** outcome's effects are in its **original units**.
- A **binary** outcome's effects are **probability differences** (risk differences), in the `probability_difference` units.

### Moderator conditioning

When moderator values are declared, the primary effects are evaluated with those moderators fixed. They are **not** averaged over the observed moderator distribution. The report says "Evaluated at moderator values: W=0", and `effects.csv` fills `evaluated_at`.

Moderator rows compare each evaluation value with the baseline:
- The baseline compared with itself has reason `baseline_reference` and no interval.
- A difference that is zero by construction has reason `structurally_zero` and no interval.

### Interpretation

- **`model_standardized` (the default).** Effects are model-standardized contrasts under your declared models. They are **not** identified causal effects.
- **`assumption_based_causal`.** Effects may be read causally only under the identification assumptions, which the report lists in full:
  - consistency;
  - positivity;
  - no interference;
  - no unmeasured exposure–outcome, exposure–mediator or mediator–outcome confounding;
  - no exposure-induced mediator–outcome confounders;
  - temporal ordering;
  - cross-world independence;
  - no measurement error.

  None of these can be tested from the data.

**Both modes** also assume correctly specified node models. For parallel mediators, the factorization order is a modelling choice, not a causal claim.

## Uncertainty

Intervals come from a participant bootstrap. Every node is refitted on each resample, and each interval is the 2.5–97.5 percentile range of the successful replicates.

- **`standard` mode.** Requires **at least 200** replicates; with fewer, intervals are withheld (`bootstrap_too_few_replicates`).
  - Below 400 replicates, every replicate must succeed.
  - From 400 up, at least 390 must succeed and at most 1% may fail.
  - Use 999 replicates for reported results.
- **`quick_diagnostic` mode.** Every interval is **provisional**. It is labelled `quick_diagnostic_provisional` and is not inferential evidence.
- **Optional outputs.** Parallel contributions and moderator differences are withheld individually when they are unavailable. They never remove the primary intervals.

**Known limitation: false indirect effects in mixed-null designs.** When the exposure → mediator path is truly zero but included in the model, and the mediator → outcome path is strong, the TNIE interval excludes zero too often. In validation (N = 100, mediator → outcome coefficient 0.5):
- the interval excluded zero in 39 of 500 datasets (7.8%), and in 32 of 500 with a fresh seed; the pooled rate was 7.1% (95% interval 5.7–8.9%), instead of 5%;
- the reverse case, a real exposure → mediator path and a truly zero mediator → outcome path, stayed near 5% (4.4%).

So in designs like this, about 6–8% of truly null indirect effects will look significant, not 5%. Of the alternative intervals checked, only one reduced the rate, and it cost a large loss of power in ordinary designs, so Mintmed keeps the percentile interval. Larger samples have not been checked. Details are in [`validation/baseline_evidence.md`](validation/baseline_evidence.md#known-limitations).

**Skewed indirect effects.** Run 1 suggested that TNIE intervals under-cover with a quadratic outcome or a binary mediator (91.5% and 89.5%). Run 2, with 500 datasets per design, did not confirm this (94.6% and 94.0%). With the quadratic outcome, the misses still fell mostly on one side: when the interval missed, it usually lay below the true indirect effect.

`analysis.json` and the report record two state fields alongside `overall_status`:

| Field | Values |
|---|---|
| `uncertainty_state` | `not_requested`, `complete`, `provisional`, `unavailable`, `incomplete`, or `not_run` if the analysis failed |
| `warning_state` | `none` or `warnings` |

## Warnings and failure statuses

Warnings are listed in `analysis.json` and in the report:

| Warning | Condition |
|---|---|
| `small_sample` | Fewer than 100 retained rows. |
| `sparse_binary_events` | A binary node has fewer than 5 events or non-events. |
| `low_observations_per_parameter` | A node has fewer than 10 observations per parameter, or, for a Bernoulli node, fewer than 10 minority events per parameter. |
| `edge_without_term` | A declared edge has no matching term on the target node. |

**Failures** are reported as explicit statuses, not as missing numbers:
- `invalid_specification`
- `invalid_data`
- `unsupported_analysis`
- `fit_failed`
- `integration_unresolved`: numerical integration did not reach the tolerance. `integration_tolerance` is relative to the outcome standard deviation, and the default `1e-3` suits almost all analyses.
- `incomplete`: the time limit stopped the bootstrap.

An unavailable interval is never evidence of a null effect.

## Missing data

- **`missing: error`** stops if any analysis column has a missing value.
- **`missing: complete_case`** drops incomplete rows. Effects then describe the **complete-case population**, which differs from the full sample unless the data are missing completely at random. The report states how many rows were excluded and which columns they were missing.

## What Mintmed does not do

**Supported inputs:**
- observed scale scores, including tied or discrete-looking continuous scores;
- Gaussian and Bernoulli nodes;
- one to four mediators;
- independent participant rows.

**Checked by simulation:** only the 14 cells in the evidence report. Neither pre-registered run fully passed: run 1 failed its coverage check, and run 2 failed its check for false indirect effects in mixed-null designs (see above).

**Not validated:**
- four-mediator inference;
- continuous exposures;
- continuous moderators;
- categorical predictors with more than two levels;
- individual parallel contributions;
- samples below 100.

**Not supported:**
- repeated, clustered or multilevel rows;
- latent variables and measurement models;
- ordinal and count nodes;
- automatic term or smoothness selection.
