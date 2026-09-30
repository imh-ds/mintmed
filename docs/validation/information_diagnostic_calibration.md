# Task 18 information diagnostic: runtime pilot and threshold calibration (T18-S4)

This page records the GitHub runtime pilot, the compute forecast, the calibration-seed run and the warning thresholds matched on it for the Task 18 Phase 1 status-only (C2) diagnostics.

**Calibration results are not evaluation evidence.** Nothing on this page is a gate outcome. The gate (`outline/plan/task-18-…`, `gate_to_phase_2`) is judged only on the evaluation run (seed 20261002) at the thresholds frozen here, after the S5 charter.

- Runner: `src/mintmed/experiments/information_diagnostic.py` and `information_diagnostic_reporting.py`
- Threshold matching: `scripts/calibrate_diagnostic_thresholds.py`
- Tests: `tests/integration/test_information_diagnostic.py`
- Configs: `configs/information_diagnostic_pilot.yaml`, `configs/information_diagnostic_calibration.yaml`, `configs/information_diagnostic_evaluation.yaml` (written, not run)
- Log rows 13 and 14 of [`benchmarks/benchmark_log.md`](../../benchmarks/benchmark_log.md); summaries in `benchmarks/runs/36760113514/` and `benchmarks/runs/36760516354/`

## Runner

For each dataset `generate(mechanism, n, dataset_seed(master, mechanism, n, r))` the runner fits the analyst's base model of the mechanism and runs, at two nodes:

| Node | Formula (base model) | Information arm | Conventional arm |
|---|---|---|---|
| outcome (primary) | `Y ~ A + M + C` (N2, E3: `Y ~ A + I(M ** 2) + C`) | `I(r_Y ; M \| A, C)`: 5-fold cross-fitted residuals, CMIknn with k = max(5, round(0.1 n_a)), joint local permutation (k_perm 5, 199 permutations) | spline in M, A x M, Breusch-Pagan; Holm |
| mediator (secondary) | `M ~ A + C` | `I(r_M ; A \| C)` (binary tested parent) | spline in C, A x C, Breusch-Pagan; Holm |

At the outcome node two information sensitivities also run: in-sample residuals, and k = round(0.2 n_a). Both reuse the primary analysis seed.

- **Analysis seed.** `SeedSequence([master, 1801, code, n, r, node_code])` reduced to one 32-bit integer; tag 1801 keeps it apart from the data stream (tag 1800).
- **Rows.** One row per (mechanism, n, replicate, node) with the information statistic, p-value, status, stratum sizes, stratum estimates, k, tie counts and runtime; the battery's minimum Holm-adjusted p, nominal warning, status, every component's raw and adjusted p and status, and runtime; the two sensitivities (outcome node only); and the node's total runtime.
- **Aggregation.** `COMBINATION_COLUMNS = (mechanism, n, node)`; the aggregator adds `replicate` to its duplicate key. `write_report` refuses an incomplete (mechanism, n, replicate, node) grid.
- **Warning rule** (used for every arm here and in the evaluation): status `ok` and p <= t. An unavailable check never warns and stays in the denominator. The information p is the permutation p `(1 + #{T_null >= T}) / 200`; the conventional p is the battery's minimum Holm-adjusted p.
- **Thresholds are not in the configs.** The runner records p-values only, so the evaluation config did not need to wait for this calibration.

## Runtime pilot (run 36760113514)

Pilot config: seed 20260930 (neither calibration nor evaluation seed), all 9 mechanisms × N ∈ {100, 250, 500} × 4 datasets, full settings. 18 shards (mechanism × `--replicate-block 0of2,1of2`), `with_r=false`, commit `14b1556`. Complete grid, 216 rows, all `ok`.

Mean runtime per dataset on GitHub `ubuntu-latest` (seconds; 36 datasets per cell):

| N | Node | Information (primary) | In-sample sensitivity | k = 0.2 sensitivity | Battery | Node total |
|---:|---|---:|---:|---:|---:|---:|
| 100 | outcome | 0.123 | 0.122 | 0.131 | 0.010 | 0.386 |
| 100 | mediator | 0.116 | — | — | 0.009 | 0.125 |
| 250 | outcome | 0.331 | 0.331 | 0.413 | 0.010 | 1.086 |
| 250 | mediator | 0.406 | — | — | 0.009 | 0.415 |
| 500 | outcome | 0.908 | 0.905 | 1.221 | 0.010 | 3.045 |
| 500 | mediator | 1.268 | — | — | 0.009 | 1.277 |

The slowest primary outcome-node information check at N = 500 took 1.24 s (runtime gate threshold: 10 s; the gate is judged on the evaluation run). Shard runtime totalled 228.4 s, i.e. **6.35 s per mechanism-replicate** (three N, both nodes, all checks). Shard jobs took 31-54 s wall-clock each, so the planning allowance of 120 s per shard is generous.

## Forecast

Formula: `(datasets × 6.345 s + shards × 120 s) × 1.05`, in shard CPU-hours (one GitHub job = one CPU-hour per hour, as in earlier rows of the log).

| Run | Datasets (mechanism-replicates) | Shards | Compute | Overhead | Forecast | Cap |
|---|---:|---:|---:|---:|---:|---:|
| (a) calibration, seed 20261001 | 9 × 200 = 1,800 | 18 (mechanism × 2 blocks of 100) | 3.17 h | 0.60 h | **3.96 CPU-h** | 12 |
| (b) evaluation, seed 20261002 | 9 × 500 = 4,500 | 45 (mechanism × 5 blocks of 100) | 7.93 h | 1.50 h | **9.90 CPU-h** | 24 |

The calibration run measured 6.70 s per mechanism-replicate (5% above the pilot). Re-forecast with that figure, the evaluation run is **10.37 CPU-h** with 45 shards (about 11-12 minutes each), well under the 24 CPU-h cap. Dispatch for the evaluation (S6, after the charter): `dim1_flag=--mechanism` with the 9 ids, `dim2_flag=--replicate-block`, `dim2_values=0of5,1of5,2of5,3of5,4of5`, `with_r=false`.

## Calibration run (run 36760516354)

- Config `configs/information_diagnostic_calibration.yaml` (hash `684093b1…`), seed 20261001, 200 datasets per mechanism and N, commit `8044f9d`.
- 18 shards; 10,800 rows; complete grid; every information check, sensitivity and battery `ok` (no `diagnostic_unavailable`; the smallest A stratum was 32 at N = 100).
- 3.35 CPU-h of shard runtime (3.54 job-hours including plan and aggregate), against a forecast of 3.96.
- No zero-radius (tie) points occurred at the outcome node, including N3: the cross-fitted residuals are not tied even when Y and M are 7-point scores.

### Threshold rule

For each arm and node and each grid value t ∈ {0.001, 0.002, …, 0.200}, the false-warning rate is computed on each effect-correct null mechanism (N1-N4) at each N (12 cells of 200 datasets). The **frozen threshold is the largest t whose false-warning rate is <= 0.05 in every one of the 12 cells.** This refines the plan's pooled rule, because pooling would let a single null mechanism exceed 0.05. Reported descriptively: the pooled-rule threshold (the rate pooled over the 12 cells <= 0.05), per-N thresholds (the frozen rule at one N) and the binding cell.

### Frozen thresholds

| Arm | Node | Frozen t | Effective cut on the attainable p-values | Binding cell (rate at the next grid t) | Pooled-rule t | Per-N t (100 / 250 / 500) | Mean null rate at frozen t |
|---|---|---:|---|---|---:|---|---:|
| information | outcome | **0.039** | p <= 0.035 (at most 6 null T >= T_obs) | N2, N = 100 (0.055 at 0.040) | 0.069 | 0.039 / 0.064 / 0.044 | 0.026 |
| conventional | outcome | **0.029** | continuous | N2, N = 500 (0.055 at 0.030) | 0.053 | 0.035 / 0.039 / 0.029 | 0.025 |
| information, in-sample residuals | outcome | 0.044 | p <= 0.040 | N2, N = 100 (0.055 at 0.045) | 0.069 | 0.044 / 0.054 / 0.049 | — |
| information, k = 0.2 | outcome | 0.039 | p <= 0.035 | N2, N = 500 (0.055 at 0.040) | 0.069 | 0.064 / 0.054 / 0.039 | — |
| information | mediator | **0.064** | p <= 0.060 | N4, N = 100 (0.055 at 0.065) | 0.099 | 0.064 / 0.084 / 0.074 | 0.032 |
| conventional | mediator | **0.026** | continuous | N2, N = 250 (0.055 at 0.027) | 0.050 | 0.048 / 0.026 / 0.032 | 0.028 |

The information p-values lie on the grid k/200, so any t in [0.035, 0.040) gives the same warnings as 0.035. For the charter the information thresholds can equally be stated as 0.035 (outcome) and 0.060 (mediator).

At the nominal 0.05, the pooled null rates were: outcome node information 0.040, conventional 0.046; mediator node information 0.028, conventional 0.050. The largest single null cell at nominal 0.05 was information N3 at N = 500 (15/200 = 0.075) and conventional N2 at N = 250, mediator node (18/200 = 0.090).

### Warning rates at the frozen thresholds (descriptive)

Count of warnings out of 200 datasets, with Wilson 95% intervals in the machine-readable file `benchmarks/runs/36760516354/rates_at_frozen_thresholds.csv` (and in `threshold_report.md` there).

**Outcome node** (information t = 0.039, conventional t = 0.029):

| Mechanism | Category | Information N=100 | N=250 | N=500 | Conventional N=100 | N=250 | N=500 |
|---|---|---:|---:|---:|---:|---:|---:|
| N1_linear | null | 5 | 3 | 5 | 9 | 4 | 5 |
| N2_curved_declared | null | 10 | 5 | 3 | 3 | 5 | 10 |
| N3_ties | null | 7 | 6 | 5 | 2 | 1 | 3 |
| N4_heavy_tail | null | 4 | 5 | 5 | 5 | 5 | 7 |
| A1_c_only | attribution | 3 (0.015) | 2 (0.010) | 3 (0.015) | 30 (0.150 [0.107, 0.206]) | 56 (0.280 [0.222, 0.346]) | 98 (0.490 [0.422, 0.559]) |
| V1_outcome_variance | density only | 5 (0.025) | 6 (0.030) | 5 (0.025) | 132 (0.660 [0.592, 0.722]) | 200 (1.000 [0.981, 1.000]) | 200 (1.000 [0.981, 1.000]) |
| E1_omitted_quadratic | effect relevant | 18 (0.090 [0.058, 0.138]) | 59 (0.295 [0.236, 0.362]) | 133 (0.665 [0.597, 0.727]) | 105 (0.525 [0.456, 0.593]) | 190 (0.950 [0.910, 0.973]) | 200 (1.000 [0.981, 1.000]) |
| E2_omitted_interaction | effect relevant | 18 (0.090 [0.058, 0.138]) | 50 (0.250 [0.195, 0.314]) | 106 (0.530 [0.461, 0.598]) | 58 (0.290 [0.232, 0.356]) | 156 (0.780 [0.718, 0.832]) | 195 (0.975 [0.943, 0.989]) |
| E3_mediator_variance | effect relevant | 6 (0.030) | 6 (0.030) | 4 (0.020) | 5 (0.025) | 4 (0.020) | 11 (0.055) |

Outcome-node sensitivities at their own frozen thresholds, effect-relevant detection (N = 100 / 250 / 500): in-sample residuals E1 21 / 65 / 134, E2 22 / 56 / 108; k = 0.2 E1 21 / 71 / 137, E2 29 / 64 / 131. Neither warns on A1 or V1 above 8/200.

**Mediator node** (information t = 0.064, conventional t = 0.026):

| Mechanism | Information N=100 | N=250 | N=500 | Conventional N=100 | N=250 | N=500 |
|---|---:|---:|---:|---:|---:|---:|
| N1-N4, A1, V1, E1, E2 (all 8) | 2-10 | 3-12 | 1-10 | 1-6 | 2-10 | 4-9 |
| E3_mediator_variance | 26 (0.130 [0.090, 0.184]) | 92 (0.460 [0.392, 0.529]) | 161 (0.805 [0.745, 0.854]) | 47 (0.235 [0.182, 0.298]) | 184 (0.920 [0.874, 0.950]) | 200 (1.000 [0.981, 1.000]) |

The mediator node is correctly specified for every mechanism except E3, so all mediator-node warnings outside E3 are false warnings of that node. The range column gives the smallest and largest counts over the eight mechanisms.

### Which conventional component warns (outcome node, adjusted p <= 0.029; share of 200 datasets at N = 100 / 250 / 500)

| Mechanism | Spline in M | A x M | Breusch-Pagan |
|---|---|---|---|
| A1_c_only | 0.11 / 0.23 / 0.48 | 0.03 / 0.03 / 0.04 | 0.02 / 0.05 / 0.05 |
| V1_outcome_variance | 0.01 / 0.03 / 0.01 | 0.02 / 0.03 / 0.02 | 0.66 / 1.00 / 1.00 |
| E1_omitted_quadratic | 0.51 / 0.95 / 1.00 | 0.11 / 0.29 / 0.43 | 0.10 / 0.26 / 0.42 |
| E2_omitted_interaction | 0.03 / 0.12 / 0.13 | 0.28 / 0.77 / 0.98 | 0.01 / 0.01 / 0.00 |

At the mediator node under E3 the Breusch-Pagan component carries the battery (0.21 / 0.92 / 1.00).

## Observations and calibration caveats

These are descriptive and are recorded so the S5 charter can take them into account. They are not gate results.

1. **The frozen thresholds are driven by the worst of 12 noisy cells.** With 200 datasets a cell's rate has a standard error of about 0.015, and the maximum over 12 cells sits well above their mean. The every-cell rule therefore pulls every threshold below nominal. The mean null rate at the frozen thresholds is about 0.025-0.03 for all four primary arm-node pairs, so both arms are matched at similar (conservative) empirical rates. In every arm the binding cell is N2 or N4, not N3: at the outcome node the information check was **not** noticeably conservative under N3 in this run (at nominal 0.05: 9, 9 and 15 of 200), unlike the S2 observation on rounded Y.
2. **The thresholds are imprecise.** A single dataset in the binding cell moves the frozen t (for example, the information outcome threshold would be 0.064 at N = 250 alone and 0.039 overall). On 500 evaluation datasets, true null rates of about 0.03 would give Wilson upper bounds of about 0.05, well inside the plan's 0.08 calibration gate, but this is a projection, not evidence.
3. **The conventional battery detects E1 and E2 far more often than the information check at matched thresholds**, at every N. E1 at N = 250: 190 against 59 of 200; E2 at N = 250: 156 against 50. The same holds for both sensitivities and at the mediator node for E3 (184 against 92 at N = 250). The planned added-value comparison uses the evaluation run and paired intervals; on these calibration data the information arm would not show added detection on any effect-relevant mechanism.
4. **The information check is specific where the battery is not.** It hardly warns under A1 (at most 3/200) or V1 (at most 6/200), while the battery warns under A1 (15-49%, through the spline in M, because C is correlated with M and the omitted C² leaks into the M spline) and under V1 (66-100%, through Breusch-Pagan). V1 warnings are density warnings, scored separately, and A1 warnings are attribution failures of an M-specific check. The information check's stratification by A with rank-transformed residuals makes it insensitive to a variance that depends only on A, so V1 cannot be detected by design.
5. **Neither arm flags E3 at the outcome node**, as expected: its defect is the mediator variance, which only the mediator-node checks can see.
6. **Runtime is well inside the gate**: the primary outcome-node information check took 0.91 s on average at N = 500 on GitHub (pilot), maximum 1.24 s.

## Reproduction

```bash
# pilot (run 36760113514) and calibration (run 36760516354): sharded_benchmark.yml with
#   runner_module=mintmed.experiments.information_diagnostic
#   config=configs/information_diagnostic_{pilot,calibration}.yaml
#   dim1_flag=--mechanism dim1_values=<9 ids>  dim2_flag=--replicate-block dim2_values=0of2,1of2  with_r=false
gh run download 36760516354 -D results/generated/archive/github/36760516354
python scripts/calibrate_diagnostic_thresholds.py \
  --raw results/generated/archive/github/36760516354/aggregated-benchmark/raw_metrics.csv \
  --config configs/information_diagnostic_calibration.yaml \
  --output results/generated/information_diagnostic_calibration/36760516354
```

The threshold matching is deterministic; a second run reproduced `thresholds.json` and `false_warning_curves.csv` byte for byte.
