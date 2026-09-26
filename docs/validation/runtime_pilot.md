# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94`).
- Git commit: `78a237ae7cb51897dc879584c153a2e160974995`.

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
| `cell01_linear_n100` | 100 | 2 | gaussian_linear_exact | 4.539 | 4.620 | 165216256 | complete | complete |
| `cell02_linear_n250` | 250 | 2 | gaussian_linear_exact | 5.000 | 5.065 | 166912000 | complete | complete |
| `cell03_no_a_to_m_n100` | 100 | 2 | gaussian_linear_exact | 4.102 | 4.208 | 164855808 | complete | complete |
| `cell04_no_m_to_y_n100` | 100 | 2 | gaussian_linear_exact | 4.250 | 4.368 | 164749312 | complete | complete |
| `cell05_no_mediation_n100` | 100 | 2 | gaussian_linear_exact | 4.180 | 4.254 | 165388288 | complete | complete |
| `cell06_parallel_interaction_n150` | 150 | 2 | sobol_blocked | 27.570 | 27.985 | 182276096 | complete | complete_with_warnings |
| `cell07_serial_three_n200` | 200 | 2 | gaussian_linear_exact | 7.883 | 8.084 | 166768640 | complete | complete_with_warnings |
| `cell08_quadratic_n100` | 100 | 2 | gauss_hermite | 10.367 | 10.626 | 165838848 | complete | complete |
| `cell09_spline_n250` | 250 | 2 | gauss_hermite | 17.883 | 18.216 | 175411200 | complete | complete |
| `cell10_moderated_n150` | 150 | 2 | sobol_blocked | 81.148 | 81.320 | 181829632 | complete | complete |
| `cell11_binary_mediator_n150` | 150 | 2 | exact_binary_mediators | 6.945 | 7.016 | 166641664 | complete | complete |
| `cell12_mixed_binary_serial_n250` | 250 | 2 | gauss_hermite | 12.969 | 13.090 | 179208192 | complete | complete_with_warnings |

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `37367.188`.
- Projected CPU seconds including reruns: `39235.547`.
- Projected CPU hours: `10.899`; budget pass: `True`.

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
