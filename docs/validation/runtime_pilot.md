# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `blocked`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`2a86c29394f869921f17f6cafa1a89cfd1bf70b3a141f6129d8ecf45d5a4ea22`).
- Git commit: `8911b09f7ae0f17099a6220678e8cdc465701e5b`.

## Settings

- Pilot repeats: `1`; bootstrap replicates per case: `399`.
- Integration draws: `256`; tolerance: `1e-08`.
- Targeted-rerun allowance: `0.05`; CPU ceiling: `12.0` hours.

## Environment

| Component | Value |
|---|---|
| `mintmed` | `0.1.0` |
| `numpy` | `2.5.1` |
| `pandas` | `3.0.3` |
| `patsy` | `1.0.3` |
| `platform` | `Windows-11-10.0.26200-SP0` |
| `python` | `3.12.14` |
| `scipy` | `1.18.0` |
| `statsmodels` | `0.14.6` |

## Measured cases

| Cell | N | Repeats | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |
|---|---:|---:|---:|---:|---:|---|---|
| `cell01_linear_n100` | 100 | 1 | 11.406 | 11.666 | 163782656 | complete | complete |
| `cell02_linear_n250` | 250 | 1 | 12.266 | 12.425 | 165810176 | complete | complete |
| `cell07_serial_three_n200` | 200 | 1 | 554.203 | 582.916 | 193593344 | complete | complete_with_warnings |
| `cell09_spline_n250` | 250 | 1 | 50.672 | 55.201 | 464801792 | blocked | integration_unresolved |
| `cell12_mixed_binary_serial_n250` | 250 | 1 | 121.641 | 128.049 | 431636480 | blocked | integration_unresolved |

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `blocked`.
- Projected CPU seconds including reruns: `blocked`.
- Projected CPU hours: `blocked`; budget pass: `False`.

The forecast uses the declared conservative proxy map and includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.

## Proxy map

- `cell01_linear_n100` forecasts: `cell01_linear_n100`, `cell03_no_a_to_m_n100`, `cell04_no_m_to_y_n100`, `cell05_no_mediation_n100`.
- `cell02_linear_n250` forecasts: `cell02_linear_n250`.
- `cell07_serial_three_n200` forecasts: `cell06_parallel_interaction_n150`, `cell07_serial_three_n200`.
- `cell09_spline_n250` forecasts: `cell08_quadratic_n100`, `cell09_spline_n250`.
- `cell12_mixed_binary_serial_n250` forecasts: `cell10_moderated_n150`, `cell11_binary_mediator_n150`, `cell12_mixed_binary_serial_n250`.

## Handoff

Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.
