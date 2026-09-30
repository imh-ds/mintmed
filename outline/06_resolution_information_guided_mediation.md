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
next_reviewer_action: done 2026-09-29 (reviewer answers and gap follow-ups at the end of this file); Phase 1 plan in outline/plan/task-18-information-diagnostic-calibration.md
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

### Reviewer answers (2026-09-29; for Task 18 charter drafting)

**Overall verdict.** Do not freeze the section 3 residual-CMI rule or the four-arm matrix as an inferential charter yet. The rule is a reasonable *candidate diagnostic*, but omitting C and permuting fitted residuals do not currently support calibrated p-values. A short calibration gate should precede the effect-level study. Retain the owner's settled goal: MI need not be the effect estimate, but an information diagnostic must have a predeclared consequence that improves or qualifies mediation inference.

1. **Do not omit C from the conditioning target.** Fitting C in the mean model does not generally remove its information from estimated residuals. If the C effect is misspecified and C is related to M, `I(r_Y;M|A)` can flag M when the omitted pattern is in C. Conversely, dependence can cancel after marginalizing C: with independent symmetric binary C and M, a residual pattern `r_Y=M*C` depends on M *within each C level* but is independent of M marginally. The target for an M-specific outcome check is `I(r_Y;M|A,C)`; a separate omnibus check may ask whether residuals retain information about `(A,M,C)`, but it cannot attribute the source. Do not describe either as a general causal-path test. Restrict the first pilot to at most one prespecified continuous C and a single mediator, or return `diagnostic_unavailable` when the conditioning dimension exceeds what the pilot validates. The same covariate principle applies to the mediator-node check. Also state the null precisely: raw residual independence requires an additive, identically distributed error assumption, stronger than a correct conditional *mean*. Under a correct mean but heteroskedastic errors, residual MI may properly detect a density defect without implying a biased mean indirect effect.

2. **No production estimator or neighbour count is justified yet; use a frozen pilot candidate.** For a continuous Gaussian outcome and continuous mediator with binary A, stratify by A rather than feed its 0/1 codes into a continuous-only kNN-CMI estimator. Within each stratum, use the continuous-data CMI kNN statistic with *local* permutation described by [Runge (2018)](https://proceedings.mlr.press/v84/runge18a.html) for `I(r_Y;M|C)`. As an engineering pilot setting, predeclare `k_CMI = max(5, round(0.1*n_stratum))` and `k_perm = 5`, with `0.2*n_stratum` as a sensitivity setting; these come from that paper's rule of thumb, **not** from validation of Mintmed residuals at N=100–250. Record effective stratum N and ties; if a stratum is too small, return unavailable rather than silently pool or jitter. Mixed discrete/continuous nodes need a separately validated method; [mixed-data CMI work](https://pmc.ncbi.nlm.nih.gov/articles/PMC9498172/) does not validate this proposed pipeline automatically.

   **Ordinary permutation of the fitted residuals is not adequately justified.** Same-sample residuals inherit leverage and fitted-model constraints; cross-fitted residuals reduce one overfitting mechanism but are still not generally exchangeable. Heteroskedasticity also breaks global exchangeability. Runge's calibration result concerns a test on observed continuous variables with its own local permutation scheme, not residuals generated by a selected smooth model. Prototype the *entire* fit → residual → CMI → resampling procedure under prespecified null mechanisms, including linear truth, correctly specified curved truth, C-only misspecification, ties and heteroskedastic errors. Refit any model selection within each null resample where the null-generating scheme permits it. Report empirical rejection rates and power before treating its p-value as inferential; if this cannot be calibrated within the budget, use the statistic only as an exploratory model check. A fixed 199-resample count is a runtime choice, not a calibration argument.

3. **Test C2 before C1.** A status-only pilot can measure whether the information diagnostic is calibrated and whether its warnings identify consequential model defects, without adding selection uncertainty to TNIE. For this pilot, label a failed check on the current model `model_check_failed`; reserve `specification_unresolved` for a failure *after* all prespecified candidates have been tried. Continue to show the effect and interval with a model-dependence warning rather than asserting that the TNIE is zero or suppressing its interval automatically. Predeclare a gate for advancing to C1: acceptable false-warning rate under correctly specified models, useful detection of effect-relevant misspecification, and manageable runtime. Only then evaluate C1 as a distinct estimator, with every promotion and smoothness choice rerun inside each bootstrap replicate. The original section 4 comparison of arm (d) against arm (c) is an appropriate later test, but a C2-only study cannot claim reduced TNIE bias or improved coverage because it does not alter the fit.

4. **Keep heteroskedasticity as an out-of-family stress case, not a C1 success target.** The current [`GaussianNode`](../src/mintmed/models.py) samples with one fitted `sigma`, so neither a smooth mean nor an A×M mean interaction repairs variance dependence. Separate (a) outcome-error variance varying with A/M from (b) mediator variance varying with A. In (a), the signed mean effect may remain correct even when residual MI rejects, so score C2's ability to distinguish a density warning from an effect error. In (b), a nonlinear outcome can make the wrong mediator distribution bias TNIE; C2 should flag that the model family cannot resolve the effect. Do not score C1 as failing to fix a mechanism its candidate set excludes. An independent heavy-tailed residual with constant variance is another useful negative control: residual-parent MI can be zero despite a wrong Gaussian density, showing this test is not a comprehensive goodness-of-fit check. If later work adds a location-scale candidate, validate that as a separate extension.

**Additional correction for section 2.** Stone's AIC result concerns asymptotic equivalence to leave-one-out cross-validation under regularity conditions; it does not make five-fold held-out scoring, AIC, REML and GCV identical in finite samples or under penalized selection. Keep the conventional arm, but do not claim equivalence “by construction.” The decisive test is whether the information arm improves effect-level operating behavior on paired datasets. The proposed residual test may detect departures outside the shared candidate ladder, yet C1 cannot repair such departures; that is why C2 calibration must come first.

### Follow-up answers to the three charter gaps

1. **Add a conventional C2 diagnostic arm.** Use the *same fitted base-model specification, rows, covariate information, and target node* for the information check and a prespecified conventional lack-of-fit battery; share cross-fit splits where valid for both tests. For Gaussian nodes, a fair battery includes a low-degree spline/interaction score or partial-F test for omitted mean structure and a [Breusch–Pagan-type variance test](https://opus.lib.uts.edu.au/handle/10453/13901) for variance structure. Include the same candidate mean terms that C1 would offer; a generic RESET test alone can miss a mediator-specific interaction or U-shaped relation and would be an artificially weak comparator. Return **one conventional warning** if any prespecified component rejects, with multiplicity handled by a fixed procedure such as Holm adjustment. Calibrate any threshold matching on a separate seed and freeze it before evaluation; compare warnings at the same empirical false-warning rate, and report separate components so the kind of detected defect remains clear. Measure whether either warning predicts *effect-relevant* bias or undercoverage; raw rejection power alone is insufficient. This C2 comparison isolates the diagnostic from the later AIC-versus-information *model revision* comparison.

2. **Use one exposure-stratified CMI statistic and one p-value.** The proposed identity is correct for a binary A: `I(r;M|A,C) = sum_a P(A=a) I(r;M|C,A=a)`. Predeclare `w_a=n_a/n` over retained rows for the observational diagnostic target, freeze those weights across null resamples, and calculate `T=sum_a w_a*T_a`. In each null replicate, perform the local C-preserving permutation *within both A strata*, recompute both `T_a`, and combine them into one `T`; compare the observed T with this joint null distribution for **one p-value**. Do not test each stratum separately and combine two p-values. Show the stratum estimates and sizes as diagnostics, preserving negative finite-sample CMI estimates rather than clipping them. If the study wants equal-stratum weights instead, state that different target before running it. These mechanics do **not** cure the estimated-residual calibration problem in answer 2 above; the whole procedure still needs the empirical null study. [Runge's local-permutation test](https://proceedings.mlr.press/v84/runge18a.html) is a starting statistic, not a proof for fitted residuals.

3. **Add N=500 to the diagnostic calibration, not automatically to the full bootstrap matrix.** Predeclare N in `{100,250,500}` for the C2-only null/power study, with the same generating mechanisms, covariate dimension, diagnostic comparators, permutation count, and analysis rule at each N. Report per-N group sizes, false-warning rates with uncertainty, power against effect-relevant and variance-only departures, and runtime. N=500 answers *when* the diagnostic starts to be useful. Success only at N=500 would support a narrower sample-size claim; it would not establish the owner's low-hundreds use case or justify C1 at N=100. Forecast diagnostic cost separately before adding N=500, and keep the full 399-bootstrap effect-level comparison gated on C2 calibration and a new measured runtime forecast.
