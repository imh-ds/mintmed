# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94`).
- Git commit: `fee1fc4351971f658f519676b8d072cdddcdce3b`.

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
| `platform` | `Windows-10-10.0.26200-SP0` |
| `python` | `3.11.9` |
| `scipy` | `1.17.1` |
| `statsmodels` | `0.14.6` |

## Measured cases

| Cell | N | Repeats | Integration | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |
|---|---:|---:|---|---:|---:|---:|---|---|
| `cell01_linear_n100` | 100 | 2 | gaussian_linear_exact | 4.117 | 4.192 | 165105664 | complete | complete |
| `cell02_linear_n250` | 250 | 2 | gaussian_linear_exact | 4.477 | 4.525 | 167030784 | complete | complete |
| `cell03_no_a_to_m_n100` | 100 | 2 | gaussian_linear_exact | 3.766 | 3.853 | 165126144 | complete | complete |
| `cell04_no_m_to_y_n100` | 100 | 2 | gaussian_linear_exact | 4.039 | 4.063 | 164167680 | complete | complete |
| `cell05_no_mediation_n100` | 100 | 2 | gaussian_linear_exact | 3.875 | 3.936 | 164560896 | complete | complete |
| `cell06_parallel_interaction_n150` | 150 | 2 | sobol_blocked | 27.609 | 27.695 | 182489088 | complete | complete_with_warnings |
| `cell07_serial_three_n200` | 200 | 2 | gaussian_linear_exact | 7.156 | 7.256 | 166576128 | complete | complete_with_warnings |
| `cell08_quadratic_n100` | 100 | 2 | gauss_hermite | 9.242 | 9.330 | 165285888 | complete | complete |
| `cell09_spline_n250` | 250 | 2 | gauss_hermite | 15.703 | 15.960 | 176005120 | complete | complete |
| `cell10_moderated_n150` | 150 | 2 | sobol_blocked | 68.258 | 68.768 | 182280192 | complete | complete |
| `cell11_binary_mediator_n150` | 150 | 2 | exact_binary_mediators | 5.492 | 5.539 | 166146048 | complete | complete |
| `cell12_mixed_binary_serial_n250` | 250 | 2 | gauss_hermite | 10.578 | 10.666 | 179298304 | complete | complete_with_warnings |

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `32862.500`.
- Projected CPU seconds including reruns: `34505.625`.
- Projected CPU hours: `9.585`; budget pass: `True`.

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
