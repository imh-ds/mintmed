---
id: response-05
title: Review response to adaptive specification with information inference
status: revised reviewer feedback after owner correction; no methodology change adopted
date: 2026-09-29
responds_to: outline/04_proposal_adaptive_specification_with_information_inference.md
---

# Review response: adaptive specification and information inference

## 1. Corrected verdict after owner clarification

The owner's requirement is a substantive information-theoretic contribution to *determining mediation*, not an ordinary mediation package with MI report decoration. **MI itself does not have to be the effect estimate.** The first version of this response missed the requirement; the second revision overcorrected by making an MI-valued effect the primary target. Neither should be treated as the owner's decision.

The sample-size concern is real but needs a distinction. **Unrestricted estimation of continuous MI/conditional MI** is often sample hungry, particularly as the conditioning set grows. [Research on information estimation](https://proceedings.mlr.press/v70/singh17a.html) finds that nonparametric methods can fail at realistic sample sizes outside very low dimension, while stronger distributional assumptions can reduce data needs at the cost of fragility. A [formal finite-sample limitation](https://proceedings.mlr.press/v108/mcallester20a.html) also rules out strong distribution-free high-confidence MI lower bounds from small samples. That does not mean every information-based *test or model score* needs a huge N: a specified low-dimensional likelihood can yield a score or test at N around 100–250, but the result is model-dependent and its power/calibration must be checked.

The credible near-term question is whether an **information-guided fitting and inference procedure** can find mediation-relevant nonlinear structure or expose a false mediator-path claim more reliably than prespecified terms and ordinary smoothing rules, while the causal effect remains a separately estimated standardized contrast. P1/P2/P3 gesture toward this, but the proposal has not yet established that their information step improves the indirect-effect decision. If the information score merely renames a likelihood-ratio or predictive comparison without changing operating behavior, it does not meet the project's purpose.

An **MI-valued distributional mediated effect** is mathematically possible, but it is not the proposed product direction: it asks a different question, has no automatic efficiency gain over the current mean-effect estimator, and places heavier demands on outcome-density estimation. If the requirement is that *observational MI alone* reveal causal mediation without a causal design or identifying assumptions, I do not know a defensible method that does that.

[Outline/01 section 1](01_final_methodology_outline.md) explicitly makes information optional. That conflicts with the clarified product goal and should be reopened. Task 17 may document the current engine, but parity with R mediation is not evidence for a substantive MI-centered method.

## 2. Proposed role for information theory

The signed, standardized indirect effect remains in outcome units. Information theory should be part of how Mintmed evaluates the *credibility of that effect*, not a post-hoc ornament or a second effect scale. A proposed workflow has three distinct jobs:

1. **Specification diagnostic.** Compare held-out conditional log densities of a prespecified simple node model and a bounded flexible alternative. Ask whether curvature or an interaction changes predictive information enough to matter for the indirect-effect estimate. This must be compared with ordinary smoothing/AIC-style rules using the *same* candidate models.
2. **Path-evidence diagnostic.** For a specified single-mediator structure, evaluate whether A adds information about M given C, and whether M adds information about Y given A,C. Use a calibrated test only where the conditioning/resampling assumptions support it. A known randomized exposure mechanism may help calibrate the first test; the second remains observational unless mediator assignment or stronger assumptions are available. A positive pair of tests does **not** prove a nonzero net indirect effect, and a non-rejection does not prove absence of a path.
3. **Inferential consequence.** Predefine how those diagnostics affect the analysis: model revision, sensitivity status, or a separately validated combined decision rule. Show the signed effect and interval alongside the information evidence and disagreements. A “diagnostic” that never changes a decision, interpretation, or uncertainty assessment does not meet the owner's purpose. Any model selection that affects the effect estimate must be repeated inside the bootstrap, then validated for coverage.

The full and reduced models must remove all terms involving the tested parent, refit transforms inside training folds, and preserve negative held-out score gains. A predictive log-score difference is **model-dependent predictive information**, not unrestricted true CMI unless the relevant conditional densities are estimated correctly. If the result is essentially a familiar likelihood-ratio or model-selection rule with a new name, that alone is not a substantive MI contribution.

The proposal is worth building only if it does something **mediation-relevant** that ordinary prespecified formulas or smoothing rules do not. A locked comparison should test curved and interaction mechanisms, the mixed-null cases, and linear truth at the intended N. Its decisive measures are effect bias, false-positive rate, interval coverage, power, diagnostic calibration, failures, and time. It may fail because the information signal is too weak around N=100 or because simpler rules perform as well. That outcome should stop or narrow the information-aware claim.

### Why an MI-valued effect is not the priority

Published [information-theoretic causal-effect work](https://coleman.ucsd.edu/wp-content/uploads/2020/08/SCXC-Entropy-July2020.pdf) gives legitimate distributional effect measures, but it does not show that they estimate the current signed indirect effect more efficiently. For a binary outcome, an information divergence of the two outcome regimes is another function of their probabilities, so it adds no distribution-only detection capability. For continuous outcomes, distributional effects could reveal variance or shape changes missed by a mean effect, but they require fuller density modeling; the current constant-variance Gaussian mediator nodes cannot represent an exposure-induced variance shift. An MI-valued effect would also need new null-valid uncertainty, because nonnegative plug-in divergence estimates do not inherit the existing percentile-bootstrap test of zero. This is a separate research question, not the route recommended to meet the owner's present goal.

## 3. Changes needed before implementing the proposal's P1–P4

### 3.1 P3's target is not the null TNIE

For a simple linear single-mediator model, tests of the A-to-M and M-to-Y components can form a joint-significance test of a product null. Mintmed's target is broader. With nonlinear outcome functions, exposure-mediator interaction, moderation, serial mediators, or multiple mediator routes, conditional association on component edges is neither necessary nor sufficient for a nonzero *net* TNIE. Real routes can cancel in the standardized contrast. Conditional independence also does not establish a causal arrow or the natural-effect identification assumptions.

The proposed H_a/H_b pair needs a precise conditional distribution for each test. For H_a, one possible target is A ⟂ M | C. For H_b, it is M ⟂ Y | A,C in a single-mediator model. These are association nulls. The scientific edges and nuisance predictors used to factorize correlated parallel mediators must remain distinct, as [outline/01 section 5](01_final_methodology_outline.md) and [outline/02 section 9.1](02_final_implementation_roadmap.md) require. There is no general two-test recipe in the proposal for the joint TNIE of the serial and mixed systems that Mintmed already supports (for example, `cell12_mixed_binary_serial_n250` in `src/mintmed/experiments/mediation_validation.py`).

**Revision:** call P3 a conditional-association diagnostic, restrict its first possible version to a specified single-mediator setting, and remove “path-existence test” and “nonparametric mediation evidence” claims. It cannot serve as the significance test for mean TNIE. It can still contribute inferential insight when its own null is calibrated and its relationship to the effect decision is stated precisely.

### 3.2 P3's validation target contradicts its proposed role

Section 4 proposes a *concordance flag*, not a veto, yet section 7 asks whether P3 reduces the 7.8% mixed-null interval false-positive rate. A flag cannot change that rate: the same TNIE intervals still exclude zero. A veto or combined decision rule could change it, but then it is a new inferential procedure requiring its own type-I-error, power, and coverage assessment. It should not be described as a repair of the existing percentile interval. [Run 2](../docs/validation/coverage_revalidation_results.md) recorded the mixed-null failure, and the owner chose to document it rather than adopt an interval correction.

**Revision:** if P3 remains diagnostic, measure calibration of its own p-values and concordance with intervals, not a reduction in interval false positives. If a combined rule is later desired, specify it and validate it as a separate method.

### 3.3 P3's conditional null calibration remains unresolved

Plain permutation of M can break its dependence on A and C. Residual permutation is generally model-dependent; it is not automatically exact for nonlinear or heteroskedastic conditional distributions. A conditional-randomization or model-X test requires a credible conditional law for the predictor being resampled. For H_a, that may be known under an explicitly randomized exposure assignment; for observational A it must be estimated. For H_b, M|A,C must be known or estimated well enough for the proposed calibration claim. Using the same fitted node model that supplies the mediation estimate is not an assumption-light independent check. See the primary [conditional permutation test paper](https://academic.oup.com/jrsssb/article/82/1/175/7056014).

Running such a diagnostic once on the original sample is conceptually fine if its null calibration is independently established. Repeating it inside every effect bootstrap would not by itself validate the conditional-resampling null. Conversely, leaving it outside the bootstrap is appropriate only while it does not change the effect estimate or interval decision.

### 3.4 P1 touches integration and reporting, not only `fit_node`

The claim that only node models and selection logic change is too narrow. [`fit_system`](../src/mintmed/gformula.py) chooses exact binary, exact Gaussian-linear, Gaussian-Hermite, or Sobol integration using the compiled plan. In particular, `_is_gaussian_linear` checks declared `TermKind`s and interactions. The selected *fitted* structure must govern whether exact linear integration is valid; an adaptive nonlinear fit must never enter an exact-linear route. A penalized fit close to linear may still require the nonlinear numerical route unless an exact R0 model was chosen. Parallel contribution eligibility and fitted-curve reporting also depend on the actual selected terms.

**Revision:** keep the g-formula estimand and regime definitions, but include integration routing, contribution eligibility, diagnostics, serialization, and report provenance in the implementation scope. Record the selected structure and smoothing settings for the point fit and each bootstrap replicate.

### 3.5 The linear endpoint and smoothing estimator need a contract

A finite smoothing penalty normally gives an *approximately* linear fit, not the identical OLS/GLM fit. P1's statement that linear data yield today's linear fit to numerical tolerance needs either an explicit R0 selection or a different acceptance test. Random samples generated from a linear truth can still select curvature. The smoke audit identified overlapping spline and linear columns, a non-exact 1e8-penalty endpoint, fixed-design LOO leakage, and an inadequate Gaussian variance formula. All can recur in a production smooth if its basis and variance estimator are left implicit. Gaussian mediator variance affects nonlinear regime means, not merely standard errors.

**Revision:** define the unpenalized intercept/linear space, the penalized nonlinear space, rank handling, knot/support policy for counterfactual predictions, Gaussian residual-variance estimator, and an exact R0 mode. Test equality to today's reference fit when R0 is *selected*; test linear-truth operating behavior across datasets separately.

## 4. Answers to the proposal's section 9 questions

1. **P1 feasibility with statsmodels.** `GLMGam` is reasonable for a disposable Gaussian/Bernoulli prototype, but not yet a production commitment. Mintmed pins `statsmodels>=0.14,<0.15` in [`pyproject.toml`](../pyproject.toml). The [GAM implementation](https://www.statsmodels.org/v0.14.3/_modules/statsmodels/gam/generalized_additive_model.html) is marked experimental, with core verification concentrated on Gaussian and Poisson cases; [penalty selection](https://www.statsmodels.org/stable/generated/statsmodels.gam.generalized_additive_model.GLMGam.select_penweight.html) can converge to a local optimum. The [frozen smoother API](https://www.statsmodels.org/stable/generated/statsmodels.gam.smooth_basis.BSplines.html) and [prediction API](https://www.statsmodels.org/stable/generated/statsmodels.gam.generalized_additive_model.GLMGamResults.predict.html) make a prototype plausible. Verify Bernoulli predictions, convergence/failures, counterfactual values outside training support, and bootstrap-resample behavior before deciding. A small custom penalized Gaussian least-squares solver is a fallback for Gaussian nodes; do not casually introduce custom logistic IRLS against the maintained-tools decision in outline/01.

2. **Is P2 needed?** The information criterion may be central, but the proposed three-rung ladder is not automatically necessary. A separate smooth-main-effect rung duplicates some of the smoothing penalty's job and adds another selection boundary. Test one bounded information rule against a conventional rule using the same candidate models. Add an interaction decision only if a locked pilot demonstrates value beyond penalization alone. Specify whether R2 means just a linear A×M product or allows nonlinear effect modification; these are different model families. Preserve the analyst's ability to prespecify a scientifically required interaction.

3. **Criterion choice.** Cross-fitted log-score gain is a defensible predictive model-comparison statistic, but neither it nor a one-standard-error rule optimizes indirect-effect bias or inference. Five folds also do not provide five independent observations for an inferential standard error. REML/GCV can choose smoothness, but they do not resolve the estimand mismatch. Pick one bounded rule in advance and let predeclared *indirect-effect* simulation results decide whether to promote it. Do not call the gain estimated true CMI except under additional conditional-density assumptions; [outline/01 section 7](01_final_methodology_outline.md) already states the KL qualification.

4. **Conditional-independence null and bootstrap placement.** No universal null-calibration method among the listed options is justified for all supported Mintmed settings. If pursued, begin with a randomized-exposure single-mediator design where the assignment law is known, state exactly which variable is resampled for each null, and assess calibration on null data-generating mechanisms outside the fitting family. Running once on the original data is suitable for a separate diagnostic. Bootstrap-inside testing is needed only if a future inferential procedure explicitly depends on the test, and would not remove model-X assumptions.

5. **Flag versus veto.** A flag can convey a calibrated diagnostic result but cannot improve the effect interval's false-positive rate. A veto would be a separately named and validated combined rejection rule, with its power loss reported. A non-rejection must not be presented as evidence that mediated influence is absent. Before adding either to a conclusion, specify the inferential consequence and measure whether it helps at the intended N.

6. **Thresholds and six CPU-hours.** Treat six CPU-hours as a hard *pilot stop budget*, not a claim that the pilot is affordable. The stated P3 cost is roughly 2 × 199 × 5 × 2 = 3,980 node fits per dataset before tuning; this is substantial beside 399 bootstrap *system* refits, particularly in a single-mediator case. Predeclare effect bias, mixed-null rejection, interval coverage, power, diagnostic calibration, failures, and runtime versus simple smoothing and fixed-specification comparators. An absolute “coverage ≥93%” criterion alone is weak near a nominal 95% target.

7. **Other outline/smoke concerns.** The most consequential carryovers are basis overlap, the non-exact linear endpoint, variance estimation, and transform leakage in held-out scoring, as identified in [outline/03 section 5](03_review_and_smoke_test_assessment.md). Also preserve the baseline's scientific-edge versus nuisance-predictor distinction, exact linear reference mode, bounded workload, and no automatic claim of small-sample safety.

8. **Should this be attempted now?** A bounded feasibility study of information-guided diagnostics and inference is justified because it matches the clarified goal without requiring MI itself to be the effect. The study should determine whether the information rule adds value over simpler adaptive rules at the intended N. Task 17 can document the existing baseline without serving as the go/no-go gate for the information-aware method. A weak or null advantage at the intended sample sizes is a legitimate stop signal.

## 5. Validation-design corrections

The first validation should use known mean effects and locked model misspecifications: complete null, one absent path with the other real, curved A-to-M or M-to-Y relation, omitted interaction, and linear truth. Compare the information-guided rule with the same candidate models chosen by a conventional rule, plus a prespecified correct model and the existing baseline. Report effect bias, type-I error, interval coverage, power, diagnostic calibration, selection frequency, failures, and runtime at the intended sample sizes. The information rule must earn its computational and inferential cost.

Task 17's [Stage 2 principle](plan/task-17-comparator-benchmark.md) says every method fits the same wrong declared model to the same data. If only `mintmed_adaptive` may recover an omitted quadratic or interaction, that is a *different* comparison. Keep any such comparison clearly separate and do not report superiority over `mediation` from withholding a term it can fit when supplied. Task 17's existing comparison does not isolate the information criterion's added value; the proposed study above must do that.

The existing [bootstrap path](../src/mintmed/uncertainty.py) can refit selected node models. Selection must be repeated in each effect refit; this is necessary but not proof of interval validity. A conditional-information test needs its own null calibration before contributing to an inferential decision. The current percentile effect interval does not calibrate that separate test.

## 6. Recommended revision and sequence

1. Reopen the [outline/01 product decision](01_final_methodology_outline.md): information must have a consequential diagnostic and inferential role. Do not force an MI-valued effect to satisfy that requirement.
2. Run a bounded design study. Specify one information-guided model/test rule, its calibrated null where applicable, and the conventional rule it must beat. Use the same candidate node families, data, and effect estimator in both arms so the information criterion is the isolated difference. Predeclare effect-level thresholds and the cost stop.
3. Include null, mixed-null, curved, interaction, and linear-truth cases at the intended sample sizes. If the information rule does not materially improve mediated-effect decisions without unacceptable coverage or runtime cost, do not promote it merely because its score has an information-theoretic interpretation.
4. Specify how each information diagnostic changes the analysis or interpretation. If it never changes a decision and does not improve effect-level operating behavior, it is not enough to justify an information-aware product claim.
5. Treat P3 as a separate conditional-association diagnostic until its calibration and relationship to the mediated-effect decision are established. Task 17 may proceed for baseline documentation but should not consume the decision budget for the information-centered product.

The claim, **if validation succeeds**, is that an information-guided procedure makes better mediation-relevant diagnostic and inferential decisions at realistic N, while retaining an interpretable signed effect estimate. That claim is not established today.

## 7. Evidence limits

This response is based on repository source, the existing methodology and validation reports, and the primary research linked above. No new fit, simulation, timing run, or comparison with R was performed for this review. The proposed information-aware workflow is a testable research hypothesis, not a demonstrated improvement. The separate `mintnet` benchmark mentioned in the proposal remains owner-reported context, not verified repository evidence.
