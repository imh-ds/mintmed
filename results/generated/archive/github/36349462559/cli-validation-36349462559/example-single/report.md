# Mintmed mediation analysis

## Contrast and answer

- Overall status: `complete_with_warnings` (uncertainty `provisional`, warnings `none`; result status `warning`).
- Exposure contrast: `0` → `1`.
- Interpretation: `model_standardized`.

| Estimand | Estimate | 95% interval (provisional) | Units | Status | Reason |
| --- | ---: | --- | --- | --- | --- |
| TE | 0.39387079 | not available | outcome_units | ok | not available |
| PNDE | 0.10533412 | not available | outcome_units | ok | not available |
| TNIE | 0.28853666 | not available | outcome_units | ok | not available |

## Uncertainty

- Bootstrap mode: `quick_diagnostic`.
- Replicates: requested 50, attempted 50, successful 50, failed 0.
- Bootstrap status: `warning`; interval policy: percentile 2.5/97.5 over successful finite values.
- These intervals are provisional quick-diagnostic intervals and are not release evidence.

## Model

- Analysis population: 150 retained of 150 rows; 0 excluded.
- Outcome units: `outcome_units`; outcome family: `gaussian`.
- Arrangement: `parallel`; factorization order: `["M"]`.
- Scientific edges: `[["A","M"],["A","Y"],["M","Y"]]`; factorization predictors are recorded separately.
- Integration: `gauss_hermite` with accepted draw budget `0`.

## Assumptions and exclusions

- observed-variable mediation analysis
- rows are treated as independent observations
- endogenous nodes use supported Gaussian or Bernoulli families
- effects are standardized over retained_analysis_rows
- every declared conditional node model is correctly specified
- mediators are factorized in the declared factorization order ['M']; for parallel mediators this order is a modelling choice, not a causal claim
- latent variables, clustered rows, ordinal nodes, and count nodes are unsupported
- effects are model-standardized contrasts, not identified causal effects; a causal reading requires the identification assumptions, which were not declared
- Excluded rows: 0.
- Unsupported features: latent variables, clustered rows, ordinal nodes, count nodes.

## Diagnostics

| Category | Value |
| --- | --- |
| Missingness | {"counts":{},"excluded_rows":0,"policy":"error"} |
| Support | {"A":{"declared_levels":[0,1],"observed_levels":[0,1]},"M":{"observed_max":3.387056,"observed_min":-2.41414},"Y":{"observed_max":2.869818,"observed_min":-2.093436}} |
| Binary counts | {} |
| Warnings | [] |
| Integration | {"accepted_draw_budget":0,"diagnostics":{"absolute_tolerance":0.001073141226675389,"accepted_draw_count":0,"check_order":32,"hermite_order_delta":6.453171330633722e-16,"outcome_scale":1.073141226675389,"quadrature_order":64,"status":"ok","tolerance":0.001,"tolerance_scale":"outcome_sd"},"draw_seed":null,"initial_draw_budget":256,"issues":[],"method":"gauss_hermite","status":"ok","tolerance":0.001} |

## Provenance

- specification_hash: `8cf616ce87bde202e708aa55567bd2a1106bcbe7fb1a61b197b78d5c24fe7b47`
- analysis_hash: `681080e5170c7889de6fbe1c5d94e49e69483824ee44f09bdc754aa15d448fa3`
- mintmed_version: `0.1.0`
- python_version: `3.11.16`
- seed: `20260919`
- bootstrap_requested: `50`
- bootstrap_mode: `quick_diagnostic`

## Limitations

- Causal interpretation requires the declared assumptions; otherwise these are model-standardized contrasts.
- An unavailable interval is not a zero effect and is not evidence of a null finding.
- This report does not apply a significance cascade or supply a default proportion-mediated quantity.
