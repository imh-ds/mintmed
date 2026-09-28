# Mintmed benchmark log

Running, append-only log of every benchmark run. Add new rows at the bottom and never rewrite old ones; if a row turns out to be wrong, add a correction row that refers to it.

**Columns:**
- **ID:** the GitHub Actions run ID, or `local-…` for runs on the developer machine.
- **Where:** `GH` means GitHub Actions `ubuntu-latest` with Python 3.11.16. `Local` means Windows 11 with Python 3.11.9 and 16 worker processes; local runs are diagnostic only.
- **Summary files:** for GitHub runs, the small summary artifacts are in [`runs/<ID>/`](runs/). Full artifacts are in git-ignored `results/generated/archive/github/<ID>/` and are fingerprinted in [`manifest.sha256`](manifest.sha256).

## Log

| # | Date | ID | Where | Kind | Commit | Config (hash) | Scope | Compute | Outcome | Record |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-27 | `36285805451` | GH | Runtime pilot (Task 14) | `e93368a` | run 1 (`176be112…`) | 12 cells × 2 repeats × 399 refits | — | **Over budget.** Forecast 23.965 CPU-h against the original 12 CPU-h ceiling. This led to the sharded budget amendment (36 CPU-h, 4 h per shard). | decision log, "Task 14 amendment" |
| 2 | 2026-09-27 | `36293907650` | GH | Runtime pilot (Task 14) | `54c9f30` | run 1 (`176be112…`) | 12 cells × 2 repeats | — | **Pass.** Forecast 20.717 CPU-h of 36; slowest shard 1.159 h of 4. | [`runtime_pilot.md`](../docs/validation/runtime_pilot.md) |
| 3 | 2026-09-27 | `36296143027` | GH | **Validation run 1** (Task 15) | `04cbf2d` | `mediation_validation.yaml` (`176be112…`) | 12 cells × 200 datasets × 399 refits; 48 shards; 2,400 rows | 11.15 CPU-h | **FAIL: coverage gate.** Minimum Wilson lower bound 0.845 against 0.90. The gate was nearly unattainable at 200 datasets. Mean coverage 94.8%; bias, null and availability gates passed. | [`baseline_run1_results.md`](../docs/validation/baseline_run1_results.md) |
| 4 | 2026-09-27 | `local-bc-bca` | Local | Diagnostic: BC/BCa interval check | `a3e9dc5` | run 1 seeds | Cells 11, 08, 01 × 200 datasets (run-1 datasets) | about 40 min wall-clock (16 processes) | BC/BCa add 3–5 covered datasets per 200 and do not reach the gate. **Not adopted.** | [`interval_correction_check.md`](../docs/validation/interval_correction_check.md) |
| 5 | 2026-09-27 | `local-stress` | Local | Stress diagnostics (`--stress-only`) | `a3e9dc5` | run 1 (`176be112…`) | 4 fixtures × 1, N = 50 | seconds | All 4 `complete_with_warnings`. Descriptive only. | [`baseline_evidence.md`](../docs/validation/baseline_evidence.md) |
| 6 | 2026-09-27 | `36349462559` | GH | Runtime pilot (Task 16) | `b8ac243` | `mediation_validation_v2.yaml` (`0f2f7388…`) | Cells 13, 14 × 2 repeats | — | **Pass.** About 7.0 s per dataset. Combined with run 1's measured runtimes, the forecast is 31.28 CPU-h of 36 and the slowest shard 1.10 h of 4. | [`coverage_revalidation_charter.md`](../docs/validation/coverage_revalidation_charter.md) |
| 7 | 2026-09-27 | `36349731184` | GH | **Validation run 2** (Task 16) | `9ff5de6` | `mediation_validation_v2.yaml` (`0f2f7388…`) | 14 cells × 500 datasets × 399 refits; 140 shards; 7,000 rows | 30.30 CPU-h | **FAIL: null false-positive gate.** Wilson upper bound 0.1049 against 0.10; cell 14 TNIE 39/500 = 7.8%. Coverage gate (Option B) **passed**: minimum 461/500 against a critical count of 458, mean 94.9%. Bias and availability gates passed. | [`coverage_revalidation_results.md`](../docs/validation/coverage_revalidation_results.md) |
| 8 | 2026-09-27 | `local-interval-fix` | Local | Diagnostic: null-gate fix check | `b6e2e8c` | v2; seeds 20260927 and 20260928 | Cells 14, 13, 01 (run-2 seed) and 14, 13, 01, 08 (fresh seed) × 500 datasets | about 1.7 h wall-clock (16 processes) | Percentile false positives in cell 14: 39 and 32 per 500 (pooled 7.1%, 95% CI 5.7–8.9%). The expanded percentile barely changes this; t × SD fixes it but costs a lot of power; BC is worse. **None adopted.** | [`null_gate_fix_check.md`](../docs/validation/null_gate_fix_check.md) |

**GitHub validation compute to date:** 41.45 CPU-hours (row 3 plus row 7).

## Artifact retention

GitHub deletes this repository's workflow artifacts after 14 days. For the runs above that is **2026-10-11**. All of their artifacts were downloaded on 2026-09-28 to `results/generated/archive/github/`, and their SHA-256 fingerprints are in [`manifest.sha256`](manifest.sha256). The verification-suite runs `36285800615` and `36293906861`, whose CLI example outputs were archived with them, are not benchmarks and are not logged above.
