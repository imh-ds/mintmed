---
id: proposal-04
title: Adaptive node specification with information-theoretic inference on the regression skeleton
status: proposal, awaiting collaborator review (not adopted, not scheduled)
date: 2026-09-29
author: claude_code (Sonnet 5.5 session, on behalf of the owner)
audience: reviewing agent / collaborator; then the owner
supersedes: nothing (extends outline/01 section 4 priorities 1 and 4)
relates_to:
  - outline/01_final_methodology_outline.md
  - outline/02_final_implementation_roadmap.md
  - outline/03_review_and_smoke_test_assessment.md
  - outline/feasibility_smoke_2026-09-19.py
  - outline/plan/task-17-comparator-benchmark.md
  - docs/validation/baseline_evidence.md
  - docs/validation/comparator_rule_calibration.md
decision_needed_from_reviewer: feasibility verdict on P1-P4, answers to the questions in section 9
---

# Proposal: make Mintmed adaptive, and give information theory a role inside inference

## 0. How to read this

This is a pitch to a collaborator for review, not a plan to execute. Section 9 lists the questions I want answered. Please challenge the design, especially the parts I flag as risky. If you think the honest verdict is "not worth building", say so and say why.

## 1. Why this proposal exists

While preparing Task 17 (benchmark against R `mediation` and lavaan path models), the owner asked two questions that expose a positioning problem:

1. If curved effects are only handled when the analyst declares them, what does Mintmed offer beyond `mediate()` with a curved formula?
2. Mutual information (MI) was meant to be central to the project. Today it is not.

Both concerns are correct as stated. The evidence:

- **Nonlinearity is declared, not detected.** `TermKind` in `src/mintmed/spec.py:52-57` offers `linear`, `quadratic`, `natural_spline` and `categorical`; the analyst chooses per predictor. If nothing is declared, the fit is linear, i.e. the same model as `mediate()` or lavaan.
- **`mediate()` can already fit a curved single mediator** when given a formula. Task 17 lists cells 08 and 09 as supported for it (`outline/plan/task-17-comparator-benchmark.md`, `stage1.support_matrix`; `docs/validation/comparator_support.md`).
- **Information theory has almost no role.** `ComputationSpec.information` (`src/mintmed/spec.py:196`, default `False`) is parsed and validated but never used to compute anything. Nothing in `src/mintmed/` calls an information measure.
- **This was a written decision, not silent drift.** `outline/01_final_methodology_outline.md` section 1 says the product is "nonlinear model-based mediation with optional information summaries" and that "Mutual information is unsigned; differences of observational MI do not generally identify mediation." Section 4 says: "If an MI-only causal estimator is required instead, this plan does not supply one." Whether the owner saw and accepted that trade at the time is not something I can establish from the repo. The owner now says the expectation was MI-centred. That gap is the reason for this document.
- **The MI-native route is not a good fallback.** The owner reports that earlier benchmarks in the separate `mintnet` package showed the MI-native engine gained little without very large samples. I have not seen those results in this repository, so treat this as owner-reported context, not verified evidence. It is consistent with `outline/01` section 8 (low-hundreds sample sizes, "neither regularization nor MI can guarantee adequate power").

**Consequence for Task 17.** Benchmarking today's Mintmed (fixed declared terms) against `mediation` and lavaan will likely show parity where models are right and only a scope advantage (multiple mediators, binary nodes) elsewhere. That is a weak result and may be what the data say. This proposal asks whether a stronger, defensible design exists before more compute is spent.

## 2. What exists today (the skeleton to keep)

| Layer | File | Fact |
|---|---|---|
| Specification | `src/mintmed/spec.py` | Declared terms; `ComputationSpec` with the unused `information` flag (line 196) and `bootstrap_mode` |
| Design | `src/mintmed/design.py` | `DesignTerm`, `fit_design` (line 288); patsy `cr` natural splines; frozen designs so a bootstrap refit re-derives the basis |
| Node fits | `src/mintmed/models.py` | `fit_node` (line 896): statsmodels OLS (Gaussian) or GLM (Bernoulli). Its docstring says point fits and every bootstrap refit share this one path |
| System / g-formula | `src/mintmed/gformula.py` | `fit_system` (line 384); simulates the mediator distribution and standardizes outcome contrasts |
| Effects | `src/mintmed/effects.py` | TE, pure natural direct effect (PNDE), total natural indirect effect (TNIE) |
| Uncertainty | `src/mintmed/uncertainty.py` | `bootstrap_analysis` (line 533), `_run_replicate` (line 255): participant bootstrap, percentile intervals |
| Evidence | `docs/validation/baseline_evidence.md` | Run 2: coverage passes; null false-positive gate fails at the mixed-null cell (cell 14 TNIE 39/500 = 7.8%) |

**Design principle for this proposal: keep the g-formula, effect definitions and bootstrap unchanged.** They give signed effects in outcome units, which MI cannot. Only the node models (what is fitted) and the model-selection logic (how it is decided) change.

## 3. The proposal in one paragraph

Replace "the analyst declares every term" with "each node is fitted adaptively and the decision to spend flexibility is made by an information-theoretic criterion, inside the same bootstrap". Add a nonparametric conditional-independence (conditional MI style) existence test for the mediation path as a second, assumption-light line of evidence. Keep the signed effect estimation regression-based. Information theory then decides model structure and checks path existence, rather than decorating the output.

## 4. Components

### P1. Adaptive node models (penalized smooths shrinking to linear)

**What.** For each continuous predictor, fit `linear part (unpenalized) + smooth part (penalized)`. The smoothing penalty is chosen from the data. If the data are linear the smooth part is penalized to zero and the fit equals today's linear fit; if curved, it bends. Effective degrees of freedom (edf) are reported per term. For A×M, penalize only the interaction part.

**Where it plugs in.**
- Add a term kind next to `TermKind.NATURAL_SPLINE` (`spec.py:52-57`), e.g. `penalized_smooth`; keep `linear`, `quadratic` and `natural_spline` untouched so the exact-linear reference mode survives (`outline/01` section 8).
- `design.py`: separate the unpenalized linear subspace from the penalized nonlinear subspace with an explicit rank test. `outline/03` section 5.2 records that the smoke script relied on a 1e8 penalty and pseudoinverse tolerances instead; that must not be repeated.
- `models.py`: candidate implementations are statsmodels `GLMGam` with a penalty-weight selector (Gaussian and Bernoulli, so it fits the existing OLS/GLM path), or a small custom penalized least squares. **Reviewer: please check which is viable and whether it supports frozen-basis prediction for counterfactual exposure values.**
- Because `fit_node` is the single fitting path (`models.py:896`), the smoothing choice is repeated in every bootstrap refit at no extra design effort. The cost is runtime.

**Prior art in this repo.** `outline/feasibility_smoke_2026-09-19.py` (`class Node`, line 28; penalty grid at line 54; minimum-LOO or one-SE rule, largest penalty preferred) already prototyped this. `outline/03` section 5 lists its defects: fixed-design LOO rather than full-pipeline LOO (5.1), overlapping basis columns and a non-nested linear endpoint (5.2), approximate residual variance `RSS/(n - tr(H))` that feeds regime means (5.3, 5.4), and timing that excluded most default work (5.5). This is `outline/01` section 4 priority 1, with promotion requirements: "correct the smoke implementation's design/LOO issues; validate full-refit interval behavior and runtime".

### P2. Information-theoretic criterion decides how much flexibility to spend

**What.** Penalized smooths alone give continuous shrinkage but no explicit decision. P2 adds a small ladder and a rule for climbing it:

| Rung | Node model |
|---|---|
| R0 | linear (today's exact reference) |
| R1 | + penalized smooth main effects |
| R2 | + exposure×mediator interaction (a fixed candidate set, no interaction search, per `outline/01` section 3) |

Climb a rung only if the **cross-fitted held-out log-score gain** exceeds a one-standard-error margin. That statistic is the `predictive_log_score_gain_nats` of `outline/02` section 9.1: five fixed folds, transforms refitted within training folds, negative values preserved. It is information-theoretic (a difference of expected log densities, equal to true CMI minus KL error terms, as `outline/01` section 7 states precisely). It needs no permutation.

**Design fork for the reviewer.** If P1's penalization already shrinks correctly, P2 may be redundant for main effects and only earn its place for the interaction rung. Alternatively P2 could replace P1's smoothing-parameter selection with a log-score criterion. I lean towards: P1 for smooth main effects, P2 only for the interaction decision. Tell me if you disagree.

**Selection must sit inside the bootstrap.** Each replicate re-runs the ladder. Otherwise intervals ignore selection uncertainty and will under-cover; run 2's null-gate failure (`docs/validation/baseline_evidence.md`, "Known limitations") shows the current procedure already has little slack there. The trade is cost: a ladder multiplies fits per replicate. `outline/03` section 5.5 estimated that the smoke design's full default work implied about 6.7 million bootstrap refits for its stage 11A, which is why the baseline dropped it. P2 must be priced before adoption (section 7).

**Caution recorded in the repo.** `outline/01` section 8: "Selection aimed at prediction is not guaranteed to optimize an indirect effect or its interval." The validation plan below therefore tests interval behaviour directly.

### P3. Nonparametric existence test for the indirect path

**What.** A conditional-independence test that does not assume linearity, reported next to the interval:

- H_a: is M informative about A (given covariates C)?
- H_b: is Y informative about M (given A, C)?
- Statistic: cross-fitted log-score gain of the flexible model over the reduced model that drops the variable (P2's statistic, removing the parent's main effect and every term involving it, as `outline/02` section 9.1 specifies).
- Calibration: a permutation or residual-resampling null. **Conditional permutation with continuous covariates is delicate** (a plain permutation of M breaks the M–C link and can misstate the null). Options: permute within covariate-model residuals, or a model-X style resample from the fitted M|A,C model. Reviewer, please advise.
- Combine as a joint-significance (intersection) test, and say plainly that it is conservative for the product null.

**Cost control.** Run it once on the original sample, not inside every bootstrap replicate. Rough budget: 2 tests × about 199 permutations × 5 folds × 2 fits is about 4,000 node fits, small next to 399 bootstrap system refits. `outline/02` section 9.1 rules out default permutation tests and a bootstrap for every information score for cost reasons; running once on the original data respects that concern but does reverse the "no default" stance, so that is a decision, not a detail.

**Use.** First as a concordance flag ("interval excludes zero but the existence test does not", or the reverse), not a veto. A veto changes the coverage claim and would need its own validation.

**Why it might matter.** Run 2 found about 7% false positives in a mixed-null cell (one path real, one absent) at N = 100 (`docs/validation/null_gate_fix_check.md`; `docs/validation/coverage_revalidation_results.md`). Fixes tested on the interval side were not worthwhile. An independent test of path existence attacks the same problem from the structure side. It may not help; the pilot decides.

### P4. Descriptive information summaries (already specified, low risk)

`predictive_log_score_gain_nats` per declared edge and the regime Jensen–Shannon summary (`outline/02` section 9.2, `outline/01` section 7). Point summaries only, labelled model-dependent and unsigned. This gives users a nonlinear-robust "how much does this arrow matter" alongside the signed effect. Not on the critical path.

## 5. What this does and does not claim

- **Claims we could support if the pilot passes:** Mintmed finds curvature and interactions without being told where they are, keeps intervals honest after that selection, and reports a nonparametric path-existence check.
- **Does not claim:** MI estimates the effect; MI-based methods have better power; automatic safe nonlinearity in general. `outline/01` section 4 already forbids "advertise automatic safe nonlinearity selection" before validation.
- **Sample-size honesty.** The residual and log-score tests inherit the same small-sample weakness that reportedly hurt the MI-native engine. At small N the ladder may stay at R0. That is acceptable (it falls back to today's behaviour), but the benefit disappears there. The pilot must report the N at which each rung is reliably chosen.

## 6. Conflicts with existing decisions (please rule on each)

| Existing decision | Source | This proposal | Proposed handling |
|---|---|---|---|
| Baseline uses prespecified terms; auto smooths optional | `outline/01` sections 2, 4 (priority 1) | Promotes it to a candidate default | Opt-in mode first; baseline and exact linear reference mode unchanged |
| "Avoid selection/test cascades" | `outline/01` section 2, small-sample row | P2 is a selection ladder | Only inside the bootstrap; deterministic criterion; measured on interval coverage |
| No default permutation tests | `outline/02` section 9.1 | P3 uses permutations once on original data | Explicit, budgeted exception; reported as flag, not veto |
| Information companion is priority 4 | `outline/01` section 4 | Raised to priority with P1 | Reordering needs owner approval |
| Do not change the estimator during Task 17 | `outline/plan/task-17-comparator-benchmark.md`, non-goals | Changes the node fits | Separate task; Task 17 stays the baseline comparison |
| One targeted correction, no estimator tournaments | `outline/01` section 11 | Two designs (P1 only vs P1+P2) | Predeclare the fork; do not run open-ended comparisons |

## 7. Validation plan (reuses Task 17 machinery)

Reuse, do not rebuild: `src/mintmed/experiments/mediation_validation.py` (cells and truth), `comparator_benchmark.py` (paired reporting with R `mediation` and lavaan), `scripts/export_validation_datasets.py`, `benchmarks/benchmark_log.md`, and the decision rules in `docs/validation/comparator_rule_calibration.md` once the owner settles them. Add `mintmed_adaptive` as a fourth method next to `mintmed`, `mediation` and lavaan.

**Phase A: prototype and cost (before any large run).**
1. Implement P1 behind an opt-in flag; unit-test that linear data give the linear fit to numerical tolerance (analogue of `tests/integration/test_reference_agreement.py`).
2. Runtime pilot with `scripts/run_runtime_pilot.py` on the curved cells (08, 09), a linear cell (01) and the mixed-null cell (14). Forecast full cost before dispatch, as in `docs/validation/runtime_pilot.md`.
3. Cap: 6 aggregate CPU-hours for the pilot, under the 12-hour matrix budget in `outline/01` section 11.

**Phase B: three questions, each with a pre-declared threshold.**

| Question | Cells | Pass condition (draft, reviewer to adjust) |
|---|---|---|
| Cost of unneeded flexibility | linear cells 01–05, 13–16 | coverage loss vs. fixed-term Mintmed <= 2.5 pp; width ratio <= 1.10; no new false-positive excess |
| Benefit when the analyst is wrong | Stage 2 scenarios: omitted quadratic, omitted A×M interaction | bias reduced materially versus `mediation`, lavaan and fixed Mintmed on the same data; coverage >= 93% |
| Does P3 help the mixed-null caveat? | cells 13–16 | false-positive rate at N = 100 reduced from 7.8% with power loss <= 5 pp |

Add one new Stage 2 scenario, "unneeded flexibility" (linear truth, adaptive model offered), so the price of flexibility is measured rather than assumed. I raised this to the owner before; it is still undecided.

**Stopping rules (from `outline/01` section 11).** One targeted correction and one affected-case rerun. If P1 fails the cost question, or fails the benefit question, stop and narrow the claim. Do not add new selection rules to rescue it.

## 8. Risks I see, ranked

1. **Post-selection coverage.** Selection inside the bootstrap should give roughly honest intervals but is not guaranteed. This is the main way P2 could hurt. Run 2 already shows the current interval has a known 7–8% false-positive weakness in one cell.
2. **Runtime.** Penalized fits with smoothing search multiplied by 399 refits, times a ladder. Could be an order of magnitude slower than today.
3. **P3 null calibration.** Conditional permutation with continuous covariates is easy to get subtly wrong. A wrongly calibrated test would give false assurance.
4. **Small-N inertness.** At N = 100 the criteria may rarely leave R0, so the benefit only appears at larger N.
5. **Positioning.** Even if everything works, the honest headline may be "an automatic, assumption-flexible mediation estimator that matches standard tools when the model is right and degrades less when it is wrong". That is a solid but modest claim, and it must be earned by Stage 2.

## 9. Questions for the reviewer

1. Is P1 feasible with statsmodels (`GLMGam` or similar) under our frozen-design contract (`design.py`) and Bernoulli nodes? If not, what is the least-risky custom route?
2. Is P2 needed on top of P1, or does penalization make the ladder redundant for main effects? Should the interaction rung be a penalized term instead of a ladder step?
3. Is the cross-fitted log-score gain the right criterion, or would REML/GCV plus an explicit interaction test be more defensible for indirect-effect inference?
4. What is a correctly calibrated conditional-independence null for P3 with continuous covariates: model-X resampling, residual permutation, or something else? Is once-on-original-data acceptable, or is a bootstrap-inside version needed to say anything about coverage?
5. Concordance flag versus veto for P3: any argument for a veto that survives the coverage concern?
6. Are the Phase B thresholds sensible, and is 6 CPU-hours a realistic pilot cap given the runtime issue in risk 2?
7. Does anything in `outline/01`–`03` make this proposal inadvisable that I have not cited? In particular, does the smoke audit (`outline/03` section 5) contain a defect that would carry over into P1 unnoticed?
8. Should any of this be attempted, or is the better course to finish Task 17 as scoped (baseline comparison, plus the misspecification stage) and accept a scope-only advantage?

## 10. Proposed next steps if the reviewer agrees

1. The owner approves creating a Relay task for Phase A (task creation needs owner approval under the project's instructions), with dates chosen by the owner.
2. Pause Task 17 step S7 (the Stage 1 charter) until the owner settles how the comparison rules are judged and whether to include `mintmed_adaptive`; the finished Task 17 harness (S1–S6) is reusable unchanged.
3. Implement P1 in an opt-in mode; run Phase A; decide go/no-go against the Phase B thresholds.
4. Record the outcome, positive or negative, in `outline/decision_log/2026-09-19-mintmed-implementation-decisions.md` and `benchmarks/benchmark_log.md`.

## 11. Provenance and limits of this document

- Written from the repo files cited above and the owner's stated goals. I have not run any new experiment for it, and no number here is new evidence.
- Owner-reported, not verified here: the `mintnet` MI-native benchmark outcome.
- The cost figure for P3 is a back-of-envelope estimate, not a measurement.
