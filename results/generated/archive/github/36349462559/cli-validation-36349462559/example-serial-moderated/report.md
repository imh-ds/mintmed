# Mintmed mediation analysis

## Contrast and answer

- Overall status: `complete_with_warnings` (uncertainty `provisional`, warnings `warnings`; result status `warning`).
- Exposure contrast: `0` → `1`.
- Interpretation: `model_standardized`.
- Evaluated at moderator values: `W=0`. The primary effects are standardized over the retained rows with these moderators fixed, not averaged over the observed moderator distribution.

| Estimand | Estimate | 95% interval (provisional) | Units | Status | Reason |
| --- | ---: | --- | --- | --- | --- |
| TE | 0.44665452 | not available | outcome_units | ok | not available |
| PNDE | 0.22540318 | not available | outcome_units | ok | not available |
| TNIE | 0.22125134 | not available | outcome_units | ok | not available |

Individual mediator contributions: unavailable (`contribution_nonparallel`; parallel contributions require no mediator-to-mediator scientific edge (node='M2', parents=('M1',))).

Moderator contrasts:

| Estimand | Source | Moderator | Value | Baseline | Estimate | 95% interval (provisional) | Status | Reason |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| TE | moderator_effect | W | 0 | 0 | 0.44665452 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| PNDE | moderator_effect | W | 0 | 0 | 0.22540318 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| TNIE | moderator_effect | W | 0 | 0 | 0.22125134 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| TE | moderator_difference | W | 0 | 0 | 0 | not available | ok | baseline_reference |
| PNDE | moderator_difference | W | 0 | 0 | 0 | not available | ok | baseline_reference |
| TNIE | moderator_difference | W | 0 | 0 | 0 | not available | ok | baseline_reference |
| TE | moderator_effect | W | 1 | 0 | 0.64187657 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| PNDE | moderator_effect | W | 1 | 0 | 0.22540318 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| TNIE | moderator_effect | W | 1 | 0 | 0.41647339 | not available | ok | bootstrap_interval_not_reported_for_moderator_effect |
| TE | moderator_difference | W | 1 | 0 | 0.19522205 | [-0.19042952, 0.49279479] | warning | quick_diagnostic_provisional |
| PNDE | moderator_difference | W | 1 | 0 | 0 | not available | ok | structurally_zero |
| TNIE | moderator_difference | W | 1 | 0 | 0.19522205 | [-0.19042952, 0.49279479] | warning | quick_diagnostic_provisional |

## Uncertainty

- Bootstrap mode: `quick_diagnostic`.
- Replicates: requested 50, attempted 50, successful 50, failed 0.
- Bootstrap status: `warning`; interval policy: percentile 2.5/97.5 over successful finite values.
- These intervals are provisional quick-diagnostic intervals and are not release evidence.

## Model

- Analysis population: 160 retained of 160 rows; 0 excluded.
- Outcome units: `outcome_units`; outcome family: `gaussian`.
- Arrangement: `sequential`; factorization order: `["M1","M2"]`.
- Scientific edges: `[["A","M1"],["A","M2"],["M1","M2"],["A","Y"],["M1","Y"],["M2","Y"]]`; factorization predictors are recorded separately.
- Integration: `sobol_blocked` with accepted draw budget `512`.

## Assumptions and exclusions

- observed-variable mediation analysis
- rows are treated as independent observations
- endogenous nodes use supported Gaussian or Bernoulli families
- effects are standardized over retained_analysis_rows_with_W=0
- every declared conditional node model is correctly specified
- mediators are factorized in the declared factorization order ['M1', 'M2']; for parallel mediators this order is a modelling choice, not a causal claim
- latent variables, clustered rows, ordinal nodes, and count nodes are unsupported
- effects are model-standardized contrasts, not identified causal effects; a causal reading requires the identification assumptions, which were not declared
- Excluded rows: 0.
- Unsupported features: latent variables, clustered rows, ordinal nodes, count nodes.

## Diagnostics

| Category | Value |
| --- | --- |
| Missingness | {"counts":{},"excluded_rows":0,"policy":"error"} |
| Support | {"A":{"declared_levels":[0,1],"observed_levels":[0,1]},"C":{"observed_max":2.892503,"observed_min":-2.463794},"M1":{"observed_max":3.06336,"observed_min":-2.585188},"M2":{"observed_max":2.804861,"observed_min":-2.131769},"W":{"declared_levels":[0,1],"observed_levels":[0,1]},"Y":{"observed_max":3.657993,"observed_min":-2.450164}} |
| Binary counts | {} |
| Warnings | [{"code":"contribution_nonparallel","message":"parallel contributions require no mediator-to-mediator scientific edge (node='M2', parents=('M1',))","node":"Y","path":"contributions","status":"warning"}] |
| Integration | {"accepted_draw_budget":512,"diagnostics":{"absolute_tolerance":0.0012789128531116825,"accepted_draw_count":512,"best_max_delta":1.1102230246251565e-16,"candidate_checks":[{"accepted":true,"doubling_max_delta":5.551115123125783e-17,"draw_count":256,"independent_scramble_max_delta":1.1102230246251565e-16}],"doubling_max_delta":5.551115123125783e-17,"independent_scramble_max_delta":1.1102230246251565e-16,"initial_draw_count":256,"outcome_scale":1.2789128531116825,"required_relative_tolerance":8.680990435930861e-17,"status":"ok","tolerance":0.001,"tolerance_scale":"outcome_sd"},"draw_seed":6304144867436258770,"initial_draw_budget":256,"issues":[],"method":"sobol_blocked","status":"ok","tolerance":0.001} |

## Provenance

- specification_hash: `13c4befdae0e58f82fc4f4fe79ad33fce332470457afb97790842ef4f660f0be`
- analysis_hash: `0f55eb6238c128b95f7c5e735d0a586cd229921dbb8514bfe8aee20fba5df8f1`
- mintmed_version: `0.1.0`
- python_version: `3.11.16`
- seed: `20260921`
- bootstrap_requested: `50`
- bootstrap_mode: `quick_diagnostic`

## Limitations

- Causal interpretation requires the declared assumptions; otherwise these are model-standardized contrasts.
- An unavailable interval is not a zero effect and is not evidence of a null finding.
- This report does not apply a significance cascade or supply a default proportion-mediated quantity.
