---
id: resolution-06
title: Resolution of the adaptive / information-guided mediation proposal
status: owner-approved direction (2026-09-29); methodology change not yet validated
date: 2026-09-29
author: claude_code (on behalf of the owner)
resolves:
  - outline/04_proposal_adaptive_specification_with_information_inference.md
  - outline/05_response_to_adaptive_information_proposal.md
reopens: outline/01_final_methodology_outline.md section 1 (information optional)
owner_decisions:
  - {id: D1, decision: "Reopen the outline/01 product decision: information theory must have a consequential diagnostic and inferential role, not only optional summaries. MI need not be the effect estimate.", approved: 2026-09-29}
  - {id: D2, decision: "Create a bounded design study (Task 18) that isolates an information-guided rule against a conventional rule on the same candidate models; Task 17 Stage 2 scenarios merge into it.", approved: 2026-09-29}
  - {id: D3, decision: "Task 17 continues with Stage 1 only, judged by the noise-floor calibration of comparator_rule_calibration.md, against the latest lavaan (0.7.2).", approved: 2026-09-29}
relay_task: MINT-57  # Task 18
next_reviewer_action: respond to section 4 (study design) before the Task 18 charter freezes
---

# Resolution: information-guided mediation

## 1. What is settled

| Point | Settled position | Source |
|---|---|---|
| Effect estimate | Signed, standardized TE/PNDE/TNIE in outcome units from fitted node models and the g-formula. MI is not the effect estimate, and no MI-valued effect is pursued now | `05` sections 1-2 |
| Role of information theory | Must change an analysis decision, interpretation or uncertainty assessment. A diagnostic that never changes a decision does not meet the goal | `05` section 2 item 3 |
| Isolation principle | The information rule is compared with a conventional rule using the **same candidate models, data and effect estimator**, so the information criterion is the only difference | `05` sections 5-6 |
| P1 corrections | Exact R0 (linear) endpoint; separate unpenalized linear and penalized nonlinear spaces; explicit residual-variance estimator; integration routing by *fitted* structure (`_is_gaussian_linear`, `src/mintmed/gformula.py:316`, called at lines 407 and 586); selection recorded per bootstrap replicate | `05` sections 3.4-3.5 |
| P2 ladder | Dropped as a separate ladder. Revisit an interaction decision only if the study shows a gap | `05` Q2 |
| P3 | Renamed a conditional-association diagnostic; single-mediator only; not a test of TNIE = 0; own null calibration required; flag, not veto | `05` sections 3.1-3.3, Q5 |
| P4 summaries | Model-dependent point summaries; low priority, may be built independently | `04` P4, `05` Q8 |
| Stop signal | A weak or null advantage at N = 100-250 stops or narrows the information-aware claim; no rescue by new selection rules | `05` Q8, `outline/01` section 11 |

## 2. Point the reviewer raised but did not apply to the proposed rule

`05` warns that an information score that "merely renames a likelihood-ratio or model-selection rule" does not meet the goal. That applies to P2's criterion. Within one parametric family, a held-out log-score is asymptotically equivalent to AIC (Stone, 1977, *JRSS-B* 39:44-47, leave-one-out cross-validation and AIC). A study comparing it with AIC on the same candidates would likely find no difference, by construction.

The same holds for REML/GCV-chosen smoothness versus a log-score-chosen smoothness in a penalized Gaussian family: both score the same likelihood.

The tension, stated plainly:

| Information measure | Strength | Weakness |
|---|---|---|
| **Model-based** (log-score of fitted node models) | Works at N ~ 100-250 | Largely a renamed AIC/LR rule; sees only what the candidate family can express |
| **Model-free** (k-nearest-neighbour conditional MI, KSG-type) | Detects structure outside the candidate family (curvature, interaction, changing variance) | Sample-hungry as dimension grows (`05` section 1: Singh and Poczos 2017; McAllester and Stratos 2020) |

## 3. Resolution: low-dimensional, model-free residual information test with a defined consequence

The information arm uses **model-free** information only where it is feasible: **low-dimensional residual tests**.

**Statistic.** After fitting a node with the current candidate model, estimate the conditional mutual information between that node's residual and its scientific parents, for example for the outcome node:

`I(r_Y ; M | A)` and `I(r_Y ; M, A)` where `r_Y = Y - E_hat[Y | A, M, C]`

- One to two conditioning dimensions, where kNN estimators are known to be usable at modest N.
- Covariates C enter through the fitted model; they are not added to the MI conditioning set in the first version. The reviewer should confirm or reject this simplification.
- Under a correctly specified mean model with independent errors, the residual carries no information about the parents; curvature, an omitted interaction, or variance that depends on a parent all leave information that AIC on the *same* candidates cannot see if no candidate expresses it.

**Calibration.** Residual permutation against the parents is closer to valid here than in P3, because the null is "residual independent of parents", not a conditional-independence null on raw variables. It is still model-dependent (residuals are estimated), so calibration must be measured on null mechanisms outside the fitting family (`05` Q4). Budget: a fixed permutation count, run once on the original data for the diagnostic.

**Consequence (what makes it count).** Predeclared, one of:

- **C1 model revision:** when the test rejects, expand the node to the next candidate (penalized smooth, then the linear A x M product) and refit. Because this changes the estimate, the whole rule is repeated inside every bootstrap replicate (`src/mintmed/uncertainty.py`, `_run_replicate`, line 255).
- **C2 status:** when the test still rejects after the largest candidate, the effect is reported with status `specification_unresolved`, and the interval carries that label.

**Comparison arm.** The same candidate ladder, moved by AIC (or REML for smoothness), also inside the bootstrap. If the information arm only matches the AIC arm, the information claim is not supported.

## 4. Task 18 study design (for reviewer response before the charter freezes)

| Element | Proposal |
|---|---|
| Arms | (a) fixed declared terms (today's baseline); (b) correct model prespecified (oracle); (c) conventional rule: AIC/REML ladder; (d) information rule: residual kNN-CMI test, consequences C1 and C2 |
| Mechanisms | complete null; mixed null (one path absent); curved A->M; curved M->Y; omitted A x M interaction; linear truth; heteroskedastic errors (variance depends on A) |
| Sample sizes | N = 100 and 250 |
| Measures | TNIE/PNDE bias; interval coverage; false-positive rate in null and mixed-null; power; width; selection frequency by arm; diagnostic calibration (p-value uniformity under null mechanisms); status C2 frequency; failures in the denominator; runtime |
| Decisive comparison | (d) versus (c), paired on the same datasets, with predeclared thresholds and confidence bounds (not an absolute "coverage >= 93%") |
| Pilot | Phase A: prototype of (c) and (d) for Gaussian nodes only; runtime pilot on 4 mechanisms, hard stop at 6 aggregate CPU-hours; forecast before any matrix |
| Stop rule | If (d) does not materially beat (c) on a predeclared effect-level measure without unacceptable coverage or runtime cost, stop and narrow the claim |
| Task 17 overlap | Task 17 Stage 2 (omitted quadratic, omitted interaction, heavy tails, heteroskedastic, unmeasured confounder) folds into these mechanisms. Matched-misspecification against R `mediation` and lavaan stays as a separately labelled comparison and is not used to claim superiority by withholding a formula (`05` section 5) |

Engineering prerequisites from `05` section 3.4-3.5 (fitted-structure-aware integration, exact R0 endpoint, variance estimator, basis contract) apply to arms (c) and (d) alike.

## 5. Task 17 changes

- **Stage 1 continues** (S7-S9): charter, GitHub run, report. It documents the current engine and provides the baseline arm; it is not the go/no-go gate for the information-aware method (`05` section 6 item 5).
- **Comparison rules judged by the noise floor** (`docs/validation/comparator_rule_calibration.md`, "Recommendation for the Stage 1 charter"): decision agreement judged on excess disagreement beyond a mediate-versus-mediate reseeded noise floor (<= 5 pp negligible, <= 10 pp tolerable); zero opposite-sign significant pairs as a primary rule; sign agreement, coverage loss and false-positive excess judged on observed values with bounds reported; power, width and bias keep the upper-bound judgement.
- **lavaan 0.7.2** (current CRAN), replacing the 0.6.21 pin (`benchmarks/comparators/r/pins.R`).
- **Stage 2 (S10, S11)** merges into Task 18. S12 publishes Stage 1 only.

## 6. Open for the reviewer

1. Is excluding C from the MI conditioning set acceptable, or does it make the residual test miss covariate-driven misspecification that matters for TNIE?
2. Which kNN-CMI estimator and neighbour count for N = 100-250, and is residual permutation adequately calibrated when residuals come from a flexible fit (estimated-residual effect)?
3. Is C1 (revise and refit inside the bootstrap) the right consequence, or should the study test C2 only first because it does not change the estimate?
4. Should heteroskedastic errors be in scope, given constant-variance nodes cannot represent it (`05` section 2): C2 would be the only possible response.
