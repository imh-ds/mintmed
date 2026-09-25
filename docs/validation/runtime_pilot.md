# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation.yaml` (`2a86c29394f869921f17f6cafa1a89cfd1bf70b3a141f6129d8ecf45d5a4ea22`).
- Git commit: `b80aeb3e6f6b53e0667c67e717c23da67a6d97b7`.
- GitHub Actions run: `36196715109`.

## Settings

- Pilot repeats: `2`; bootstrap replicates per case: `399`.
- Integration draws: `256`; tolerance: `1e-08`.
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

| Cell | N | Repeats | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |
|---|---:|---:|---:|---:|---:|---|---|
| `cell01_linear_n100` | 100 | 2 | 3.668 | 3.668 | 180072448 | complete | complete |
| `cell02_linear_n250` | 250 | 2 | 4.227 | 4.228 | 181907456 | complete | complete |
| `cell07_serial_three_n200` | 200 | 2 | 6.546 | 6.547 | 181493760 | complete | complete_with_warnings |
| `cell09_spline_n250` | 250 | 2 | 39.080 | 19.693 | 202051584 | complete | complete_with_warnings |
| `cell12_mixed_binary_serial_n250` | 250 | 2 | 12.163 | 6.217 | 196091904 | complete | complete_with_warnings |

All five pilot cases completed. The warning statuses are nonblocking diagnostic warnings; no case was integration-blocked or incomplete.

## Locked-matrix forecast

- Point fits: `2400`.
- Bootstrap refits: `957600`.
- Complete analyses: `960000`.
- Base CPU seconds: `29327.748`.
- Projected CPU seconds including reruns: `30794.136`.
- Projected CPU hours: `8.554`; budget pass: `True`.

The forecast uses the declared conservative proxy map and includes point fits, attempted bootstrap refits, serialization, and the 5% targeted-rerun allowance. This is a runtime boundary, not statistical validation.

## Proxy map

- `cell01_linear_n100` forecasts: `cell01_linear_n100`, `cell03_no_a_to_m_n100`, `cell04_no_m_to_y_n100`, `cell05_no_mediation_n100`.
- `cell02_linear_n250` forecasts: `cell02_linear_n250`.
- `cell07_serial_three_n200` forecasts: `cell06_parallel_interaction_n150`, `cell07_serial_three_n200`.
- `cell09_spline_n250` forecasts: `cell08_quadratic_n100`, `cell09_spline_n250`.
- `cell12_mixed_binary_serial_n250` forecasts: `cell10_moderated_n150`, `cell11_binary_mediator_n150`, `cell12_mixed_binary_serial_n250`.

## Handoff

Task 14 runtime acceptance is complete for the locked methodology boundary. Task 15 remains deferred and may freeze the release charter using this report, the raw JSON artifact, the reference-agreement record, and supported-runtime verification.
