# Mintmed mediation analysis

## Contrast and answer

- Overall status: `complete_with_warnings` (uncertainty `provisional`, warnings `warnings`; result status `warning`).
- Exposure contrast: `0` → `1`.
- Interpretation: `model_standardized`.

| Estimand | Estimate | 95% interval (provisional) | Units | Status | Reason |
| --- | ---: | --- | --- | --- | --- |
| TE | 0.13286794 | not available | outcome_units | ok | not available |
| PNDE | 0.077692027 | not available | outcome_units | ok | not available |
| TNIE | 0.055175916 | not available | outcome_units | ok | not available |

Individual mediator contributions: unavailable (`contribution_cross_mediator_term`; a single outcome block cannot contain multiple mediators (interaction=('M1', 'M2'))).

## Uncertainty

- Bootstrap mode: `quick_diagnostic`.
- Replicates: requested 50, attempted 50, successful 50, failed 0.
- Bootstrap status: `warning`; interval policy: percentile 2.5/97.5 over successful finite values.
- These intervals are provisional quick-diagnostic intervals and are not release evidence.

## Model

- Analysis population: 200 retained of 200 rows; 0 excluded.
- Outcome units: `outcome_units`; outcome family: `gaussian`.
- Arrangement: `parallel`; factorization order: `["M1","M2"]`.
- Scientific edges: `[["A","M1"],["A","M2"],["A","Y"],["M1","Y"],["M2","Y"]]`; factorization predictors are recorded separately.
- Integration: `sobol_blocked` with accepted draw budget `512`.

## Assumptions and exclusions

- observed-variable mediation analysis
- rows are treated as independent observations
- endogenous nodes use supported Gaussian or Bernoulli families
- effects are standardized over retained_analysis_rows
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
| Support | {"A":{"observed_max":2.628857,"observed_min":-2.465694},"M1":{"observed_max":3.782796,"observed_min":-2.875642},"M2":{"observed_max":2.762712,"observed_min":-2.964697},"Y":{"observed_max":4.847294,"observed_min":-3.328146}} |
| Binary counts | {} |
| Warnings | [{"code":"contribution_cross_mediator_term","message":"a single outcome block cannot contain multiple mediators (interaction=('M1', 'M2'))","node":"Y","path":"contributions","status":"warning"}] |
| Integration | {"accepted_draw_budget":512,"diagnostics":{"absolute_tolerance":0.0014243328145543948,"accepted_draw_count":512,"best_max_delta":0.0006044369945489569,"candidate_checks":[{"accepted":true,"doubling_max_delta":0.0002670259221403959,"draw_count":256,"independent_scramble_max_delta":0.0006044369945489569}],"doubling_max_delta":0.0002670259221403959,"independent_scramble_max_delta":0.0006044369945489569,"initial_draw_count":256,"outcome_scale":1.4243328145543948,"required_relative_tolerance":0.0004243649997897831,"status":"ok","tolerance":0.001,"tolerance_scale":"outcome_sd"},"draw_seed":5576091918085075703,"initial_draw_budget":256,"issues":[],"method":"sobol_blocked","status":"ok","tolerance":0.001} |

## Provenance

- specification_hash: `d72781a93b27e4a23e294fc16bf987bdc7ef15620da750f12c3a79adb0aaddb8`
- analysis_hash: `769857de6dac7f2c6bf5e4f343d9e8ade56e3e306d805a402076be1f375ec6d3`
- mintmed_version: `0.1.0`
- python_version: `3.11.16`
- seed: `20260920`
- bootstrap_requested: `50`
- bootstrap_mode: `quick_diagnostic`

## Limitations

- Causal interpretation requires the declared assumptions; otherwise these are model-standardized contrasts.
- An unavailable interval is not a zero effect and is not evidence of a null finding.
- This report does not apply a significance cascade or supply a default proportion-mediated quantity.
