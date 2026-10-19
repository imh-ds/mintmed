# Task 14 runtime pilot

This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.

- Status: `pass`.
- Supported runtime: `>=3.11,<3.12`.
- Source configuration: `configs/comparator_mintmed_cells15_16.yaml` (`a89c00731c7f8adf97e7ba6463d02ece5f47cd9911b13ff30ef75c55035fc3f3`).
- Git commit: `2db6245c7f6935c91918367e6f009a91f0846a37`.

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
| `cell15_a_path_only_n250` | 250 | 2 | gaussian_linear_exact | 5.801 | 5.801 | 183504896 | complete | complete |
| `cell16_b_path_only_n250` | 250 | 2 | gaussian_linear_exact | 5.806 | 5.806 | 183246848 | complete | complete |

## Locked-matrix forecast

- Point fits: `1000`.
- Bootstrap refits: `399000`.
- Complete analyses: `400000`.
- Base CPU seconds: `5803.463`.
- Projected CPU seconds including reruns: `6093.637`.
- Projected CPU hours: `1.693` (aggregate gate pass: `True`).
- Slowest shard: `cell16_b_path_only_n250` at `0.085` wall hours for `50` datasets (shard gate pass: `True`).
- Budget pass: `True`.

Every locked matrix cell is measured directly (no proxy cells), so each cell is forecast from its own integration path. The forecast includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.

## Proxy map

- `cell15_a_path_only_n250` forecasts: `cell15_a_path_only_n250`.
- `cell16_b_path_only_n250` forecasts: `cell16_b_path_only_n250`.

## Handoff

Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.
