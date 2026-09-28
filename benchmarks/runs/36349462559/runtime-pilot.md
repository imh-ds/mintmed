# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/mediation_validation_v2.yaml` (`0f2f738887b2a1669cf8c281e43fb9c258652291a4c50bbed9a009ffaafb953b`).
- Git commit: `b8ac24349f4a18ccd1d247d4ab91c12e82e9f88c`.

## Settings

- Pilot repeats: `2`; bootstrap replicates per case: `399`.
- Integration draws: `256`; tolerance: `0.001`.
- Targeted-rerun allowance: `0.05`; CPU ceiling: `36.0` hours.
- Reference platform: `github-actions ubuntu-latest`; shard layout: `2` cells x `10` replicate blocks; shard wall ceiling: `4.0` hours.

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
| `cell13_a_path_only_n100` | 100 | 2 | gaussian_linear_exact | 7.011 | 7.012 | 181907456 | complete | complete |
| `cell14_b_path_only_n100` | 100 | 2 | gaussian_linear_exact | 6.896 | 6.896 | 181780480 | complete | complete |

## Locked-matrix forecast

- Point fits: `1000`.
- Bootstrap refits: `399000`.
- Complete analyses: `400000`.
- Base CPU seconds: `6953.570`.
- Projected CPU seconds including reruns: `7301.248`.
- Projected CPU hours: `2.028` (aggregate gate pass: `True`).
- Slowest shard: `cell13_a_path_only_n100` at `0.102` wall hours for `50` datasets (shard gate pass: `True`).
- Budget pass: `True`.

Every locked matrix cell is measured directly (no proxy cells), so each cell is forecast from its own integration path. The forecast includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.

## Proxy map

- `cell13_a_path_only_n100` forecasts: `cell13_a_path_only_n100`.
- `cell14_b_path_only_n100` forecasts: `cell14_b_path_only_n100`.

## Handoff

Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.
