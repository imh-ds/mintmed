# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94`).
- Git commit: `54c9f30bc7e5963e77058c44a3e02304e7015be9`.

## Settings

- Pilot repeats: `2`; bootstrap replicates per case: `399`.
- Integration draws: `256`; tolerance: `0.001`.
- Targeted-rerun allowance: `0.05`; CPU ceiling: `36.0` hours.
- Reference platform: `github-actions ubuntu-latest`; shard layout: `12` cells x `4` replicate blocks; shard wall ceiling: `4.0` hours.

## Environment

| Component | Value |
|---|---|
| `mintmed` | `0.1.0` |
| `numpy` | `2.4.6` |
| `pandas` | `3.0.6` |
| `patsy` | `1.0.3` |
| `platform` | `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39` |
| `python` | `3.11.16` |
| `scipy` | `1.17.1` |
| `statsmodels` | `0.14.6` |

## Measured cases

| Cell | N | Repeats | Integration | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |
|---|---:|---:|---|---:|---:|---:|---|---|
| `cell01_linear_n100` | 100 | 2 | gaussian_linear_exact | 6.773 | 6.773 | 180875264 | complete | complete |
| `cell02_linear_n250` | 250 | 2 | gaussian_linear_exact | 7.184 | 7.184 | 182333440 | complete | complete |
| `cell03_no_a_to_m_n100` | 100 | 2 | gaussian_linear_exact | 6.041 | 6.041 | 181047296 | complete | complete |
| `cell04_no_m_to_y_n100` | 100 | 2 | gaussian_linear_exact | 6.280 | 6.280 | 180588544 | complete | complete |
| `cell05_no_mediation_n100` | 100 | 2 | gaussian_linear_exact | 6.271 | 6.271 | 180830208 | complete | complete |
| `cell06_parallel_interaction_n150` | 150 | 2 | sobol_blocked | 59.870 | 30.171 | 201609216 | complete | complete_with_warnings |
| `cell07_serial_three_n200` | 200 | 2 | gaussian_linear_exact | 12.013 | 12.015 | 182607872 | complete | complete_with_warnings |
| `cell08_quadratic_n100` | 100 | 2 | gauss_hermite | 14.813 | 14.818 | 182726656 | complete | complete |
| `cell09_spline_n250` | 250 | 2 | gauss_hermite | 42.245 | 21.403 | 202399744 | complete | complete |
| `cell10_moderated_n150` | 150 | 2 | sobol_blocked | 158.349 | 79.442 | 200564736 | complete | complete |
| `cell11_binary_mediator_n150` | 150 | 2 | exact_binary_mediators | 9.330 | 9.331 | 181518336 | complete | complete |
| `cell12_mixed_binary_serial_n250` | 250 | 2 | gauss_hermite | 25.978 | 13.270 | 196665344 | complete | complete_with_warnings |

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `71029.116`.
- Projected CPU seconds including reruns: `74580.571`.
- Projected CPU hours: `20.717` (aggregate gate pass: `True`).
- Slowest shard: `cell10_moderated_n150` at `1.159` wall hours for `50` datasets (shard gate pass: `True`).
- Budget pass: `True`.

Every locked matrix cell is measured directly (no proxy cells), so each cell is forecast from its own integration path. The forecast includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.

## Proxy map

- `cell01_linear_n100` forecasts: `cell01_linear_n100`.
- `cell02_linear_n250` forecasts: `cell02_linear_n250`.
- `cell03_no_a_to_m_n100` forecasts: `cell03_no_a_to_m_n100`.
- `cell04_no_m_to_y_n100` forecasts: `cell04_no_m_to_y_n100`.
- `cell05_no_mediation_n100` forecasts: `cell05_no_mediation_n100`.
- `cell06_parallel_interaction_n150` forecasts: `cell06_parallel_interaction_n150`.
- `cell07_serial_three_n200` forecasts: `cell07_serial_three_n200`.
- `cell08_quadratic_n100` forecasts: `cell08_quadratic_n100`.
- `cell09_spline_n250` forecasts: `cell09_spline_n250`.
- `cell10_moderated_n150` forecasts: `cell10_moderated_n150`.
- `cell11_binary_mediator_n150` forecasts: `cell11_binary_mediator_n150`.
- `cell12_mixed_binary_serial_n250` forecasts: `cell12_mixed_binary_serial_n250`.

## Handoff

Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.
