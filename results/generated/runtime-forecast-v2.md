# Runtime forecast from measured runtimes

This forecast reuses measured per-dataset runtimes; no analysis was fitted to produce it. It applies the runtime pilot's budget arithmetic: aggregate CPU hours include the targeted-rerun allowance, and each shard runs one cell's replicate block sequentially.

- Status: `pass`.
- Source configuration: `configs/mediation_validation_v2.yaml` (`0f2f738887b2a1669cf8c281e43fb9c258652291a4c50bbed9a009ffaafb953b`).
- Git commit: `b8ac24349f4a18ccd1d247d4ab91c12e82e9f88c`.

## Settings

- Cells: `14`; datasets per cell: `500`; replicate blocks: `10`.
- Targeted-rerun allowance: `0.05`; CPU ceiling: `36.0` hours.
- Reference platform: `github-actions ubuntu-latest`; shard wall ceiling: `4.0` hours.

## Runtime sources

| Kind | Source | SHA-256 | Cells used |
|---|---|---|---:|
| cell_summary | `results/generated/validation-matrix-36296143027/cell_summary.csv` | `ca2faeb1601641bf659c02c90ae20ec4851e2d9c5386ccfb29c6d29d65354923` | 12 |
| pilot_json | `results/generated/pilot-36349462559/runtime-pilot-36349462559/runtime-pilot.json` | `b0a0b10e7c65f2ae5c8a617c81ef8f52f85b790a88e74537c39381ac7dcfb893` | 2 |

## Per-cell forecast

| Cell | CPU s/dataset | Wall s/dataset | Base CPU hours | Shard wall hours | Source |
|---|---:|---:|---:|---:|---|
| `cell01_linear_n100` | 5.268 | 5.268 | 0.732 | 0.077 | cell_summary |
| `cell02_linear_n250` | 5.924 | 5.924 | 0.823 | 0.086 | cell_summary |
| `cell03_no_a_to_m_n100` | 5.776 | 5.776 | 0.802 | 0.084 | cell_summary |
| `cell04_no_m_to_y_n100` | 4.853 | 4.853 | 0.674 | 0.071 | cell_summary |
| `cell05_no_mediation_n100` | 6.905 | 6.905 | 0.959 | 0.101 | cell_summary |
| `cell06_parallel_interaction_n150` | 27.799 | 27.799 | 3.861 | 0.405 | cell_summary |
| `cell07_serial_three_n200` | 10.080 | 10.080 | 1.400 | 0.147 | cell_summary |
| `cell08_quadratic_n100` | 14.747 | 14.747 | 2.048 | 0.215 | cell_summary |
| `cell09_spline_n250` | 21.884 | 21.884 | 3.039 | 0.319 | cell_summary |
| `cell10_moderated_n150` | 75.117 | 75.117 | 10.433 | 1.095 | cell_summary |
| `cell11_binary_mediator_n150` | 9.794 | 9.794 | 1.360 | 0.143 | cell_summary |
| `cell12_mixed_binary_serial_n250` | 12.422 | 12.422 | 1.725 | 0.181 | cell_summary |
| `cell13_a_path_only_n100` | 7.011 | 7.012 | 0.974 | 0.102 | pilot_json |
| `cell14_b_path_only_n100` | 6.896 | 6.896 | 0.958 | 0.101 | pilot_json |

## Matrix forecast

- Shards: `140` (`14` cells x `10` blocks of up to `50` datasets).
- Complete analyses: `2800000`.
- Base CPU hours: `29.788`.
- Projected CPU hours including reruns: `31.278` (aggregate gate pass: `True`).
- Slowest shard: `cell10_moderated_n150` at `1.095` wall hours (shard gate pass: `True`).
- Budget pass: `True`.
