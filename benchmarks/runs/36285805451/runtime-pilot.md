# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `over_budget`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94`).
- Git commit: `e93368a5ea03d3f9fd1b5179adbf1175397ffe85`.

## Settings

- Pilot repeats: `2`; bootstrap replicates per case: `399`.
- Integration draws: `256`; tolerance: `0.001`.
- Targeted-rerun allowance: `0.05`; CPU ceiling: `12.0` hours.

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
| `cell01_linear_n100` | 100 | 2 | gaussian_linear_exact | 8.047 | 7.942 | 182398976 | complete | complete |
| `cell02_linear_n250` | 250 | 2 | gaussian_linear_exact | 8.464 | 8.358 | 183992320 | complete | complete |
| `cell03_no_a_to_m_n100` | 100 | 2 | gaussian_linear_exact | 7.249 | 7.143 | 182239232 | complete | complete |
| `cell04_no_m_to_y_n100` | 100 | 2 | gaussian_linear_exact | 7.414 | 7.308 | 182415360 | complete | complete |
| `cell05_no_mediation_n100` | 100 | 2 | gaussian_linear_exact | 7.437 | 7.331 | 182300672 | complete | complete |
| `cell06_parallel_interaction_n150` | 150 | 2 | sobol_blocked | 60.475 | 30.443 | 203509760 | complete | complete_with_warnings |
| `cell07_serial_three_n200` | 200 | 2 | gaussian_linear_exact | 13.981 | 13.878 | 183496704 | complete | complete_with_warnings |
| `cell08_quadratic_n100` | 100 | 2 | gauss_hermite | 34.248 | 17.245 | 184201216 | complete | complete |
| `cell09_spline_n250` | 250 | 2 | gauss_hermite | 48.365 | 24.461 | 201662464 | complete | complete |
| `cell10_moderated_n150` | 150 | 2 | sobol_blocked | 165.269 | 82.880 | 202285056 | complete | complete |
| `cell11_binary_mediator_n150` | 150 | 2 | exact_binary_mediators | 20.583 | 10.483 | 182988800 | complete | complete |
| `cell12_mixed_binary_serial_n250` | 250 | 2 | gauss_hermite | 29.296 | 14.919 | 195809280 | complete | complete_with_warnings |

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `82165.671`.
- Projected CPU seconds including reruns: `86273.955`.
- Projected CPU hours: `23.965`; budget pass: `False`.

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
