# Task 17 Stage 1 comparator charter

This charter fixes the Stage 1 comparator run (T17-S8) **before** it is dispatched. After dispatch it is immutable, apart from the single documented correction allowed in [One-correction rule](#one-correction-rule). If a permitted rerun happens, the original artifacts are kept alongside the new ones.

Stage 1 asks whether Mintmed's current estimator is as good as the standard tools **when every tool fits the correctly specified model to the same datasets**. The comparators are R `mediation::mediate()` and lavaan used purely as an observed-variable path model. Stage 2 (misspecification) is not part of Task 17: it was merged into Task 18 (owner decisions D2/D3, 2026-09-29), and this charter does not design it.

## Relation to earlier runs

- **Runs 1 and 2 are not re-graded.** Mintmed's run-2 rows (GitHub run `36349731184`) are reused unchanged as Mintmed's results for cells 01–14. Mintmed's validation gates are not re-applied in Stage 1.
- **Mintmed's estimator does not change.** The estimator under test is the current percentile participant bootstrap (399 refits), unchanged since run 1's dispatched commit `04cbf2d`.
- **Not a tournament.** No "winner" is declared. Each cell-effect gets a pre-registered verdict (negligible, tolerable or substantive difference) against the rules below, and cells a comparator cannot estimate are reported as not estimable with the reason.
- The limits are the owner-confirmed `stage1.comparison_rules` (2026-09-28). What each limit is judged on follows the owner-approved noise-floor judging (2026-09-29), recommended by the pre-charter calibration [`comparator_rule_calibration.md`](comparator_rule_calibration.md). The calibration used a separate seed and none of the evaluation datasets.

## Identity

| Item | Value |
|---|---|
| Comparator configuration | `configs/mediation_validation_v3.yaml` (experiment `mintmed_comparator_benchmark`) |
| File SHA-256 (committed LF bytes) | `2f4a83361b2c77f7cb0496cdecb9b79cd410c849ce4ada453b5f6561a6b9a014` |
| Canonical configuration hash (`load_config(...).config_hash`) | `e6dc06ede1b1332056f41208654c55e2d217f021a82fbaa227e749ada5a4faf3` |
| Mintmed configuration for cells 15 and 16 | `configs/comparator_mintmed_cells15_16.yaml` (experiment `mintmed_comparator_benchmark_mintmed`); file SHA-256 `088bb84810f52f55cfd02b2afcbcadfa4b8516976ded0d5a714b3b7c9accdf33`; config hash `a89c00731c7f8adf97e7ba6463d02ece5f47cd9911b13ff30ef75c55035fc3f3`. Same master seed, replicates and analysis settings as v3, restricted to cells 15 and 16 (a test checks this). |
| Mintmed reference for cells 01–14 | Run 2, `results/generated/archive/github/36349731184/aggregated-benchmark/raw_metrics.csv`, SHA-256 `b703847449c3c4c56b23ac0769685a3cb04d14bd63567ed2d84b949091247fbc` (12,106,089 bytes; config `mediation_validation_v2.yaml`, hash `0f2f7388…`, same master seed) |
| Support matrix | `benchmarks/comparators/support_matrix.json`, SHA-256 `c0be3171e9bf8ec74d6166c527a41c16b451bfb4fc954479c893384e3099902f` |
| Code commit | The commit that adds this charter. The dispatched SHA is recorded in `comparator_results.md` and in the benchmark log. |
| Runners | `python -m mintmed.experiments.comparator_benchmark` (R comparators and the noise-floor rerun) and `python -m mintmed.experiments.mediation_validation` (Mintmed, cells 15 and 16), Python 3.11 on GitHub Actions `ubuntu-latest` |
| Execution | `.github/workflows/sharded_benchmark.yml`; see [Shard layout and dispatch](#shard-layout-and-dispatch) |

Every comparator row carries the configuration hash, the data and analysis seeds, the R seed, the settings and the SHA-256 of every runner script; every row that ran R also carries the SHA-256 of the exported dataset and the R environment. No file under `src/mintmed` outside `experiments/` has changed since `04cbf2d`.

## Datasets and seeds

- **Master seed `20260927`**, the run-2 seed. 16 cells × 500 datasets.
- Each dataset's seeds are `numpy.random.SeedSequence([20260927, 1300, stream, cell_ordinal, replicate])`, stream 1 for data and 2 for analysis (`seed_pair`). Cell ordinals 1–16, replicates 0–499. Shard count, shard order and artifact location play no part.
- **Cells 01–14 are exactly the run-2 datasets.** Cells 15 and 16 (`cell15_a_path_only_n250`, `cell16_b_path_only_n250`) are N = 250 copies of cells 13 and 14. The cells, generating equations and truths are those of [`coverage_revalidation_charter.md`](coverage_revalidation_charter.md#cells-and-truths); cells 15 and 16 share the truths of 13 and 14 (TE 0.20, PNDE 0.20, TNIE 0).
- `scripts/export_validation_datasets.py` writes the exact datasets Mintmed analysed (`%.17g`, read back bit-for-bit by R). Each row records the dataset's SHA-256.
- **R seeds.** The comparators call `set.seed(analysis_seed mod 2147483647)` with `RNGkind("Mersenne-Twister", "Inversion", "Rejection")` immediately before every `mediate()` or `sem()` call. The noise-floor rerun uses `(analysis_seed + 1000000007) mod 2147483647` (see below). The modulus arithmetic is exact in both R and Python, and tests check that they agree.

## Tools and modes

The R environment is R 4.6.x (`r-lib/actions/setup-r@v2`, `r-version: "4.6"`) with packages from the Posit Package Manager CRAN snapshot of **2026-09-28** (`benchmarks/comparators/r/pins.R`). `install_packages.R` asserts **mediation 4.5.1, lavaan 0.7-2 and jsonlite 2.0.0** and fails the shard otherwise; `versions.R` records the versions of their direct dependencies in every row.

| Tool id | What | Mode | Settings | Role |
|---|---|---|---|---|
| `mintmed` | Mintmed | primary | percentile participant bootstrap, 399 refits | reference arm |
| `mediation` | `mediation::mediate()` | primary | `boot = TRUE, sims = 399, boot.ci.type = "perc"` | **judged** |
| `mediation` | | secondary | package default quasi-Bayesian, `sims = 1000` | descriptive only |
| `lavaan` | `lavaan::sem()` on observed variables | primary | `se = "bootstrap", bootstrap = 399`, `parameterEstimates(boot.ci.type = "perc")` | **judged** |
| `lavaan` | | secondary | package defaults (delta-method SEs, normal-theory interval) | descriptive only |
| `mediation_reseed` | `mediate()` rerun | primary only | as `mediation` primary, R seed `(analysis_seed + 1000000007) mod 2147483647` | noise floor only; never compared with Mintmed |

Estimand map: `mediate()` TNIE = `d1`, PNDE = `z0`, TE = `tau.coef`; lavaan TNIE = the defined sum of path products, PNDE = the direct path, TE = direct + indirect. Cell 10 reports the conditional TNIE at W = 0 and W = 1 and their paired difference. The fitted models and every documented runner adjustment are in [`comparator_support.md`](comparator_support.md). Settings that differ from this table (for example fewer bootstrap refits) are recorded in every row and flagged in the report; such a run is not a Stage 1 run.

### The noise-floor rerun

Two runs of the same 399-refit percentile bootstrap disagree about whether an interval excludes zero on about 5% of datasets, from bootstrap Monte Carlo error alone (calibration: 67 of 1,300 pairs, floor 0.948). An absolute agreement limit of 0.95 therefore fails methods that agree by construction. The run measures this floor directly:

- `mediation_reseed` runs `run_mediation.R --modes primary --tool-id mediation_reseed --seed-offset 1000000007` on the same datasets. Only the R seed changes, so its bootstrap resamples (and, in cells 08, 09 and 11, its simulated mediator values) are independent of the `mediation` run's.
- It has `mediate()`'s support matrix and writes one row per `(tool, cell_id, replicate)` like the other tools; cells `mediate()` cannot estimate get explicit `not_estimable` rows.
- **Per-dataset floor indicator:** 1 when both `mediation` and `mediation_reseed` have an interval and their decisions (excludes zero above, excludes zero below, includes zero) differ, else 0. A missing interval never counts, so a failed rerun cannot raise the floor.
- **The same cell-effect floor applies to both comparators.** In the cells lavaan supports, lavaan and `mediate()` fit the same estimator (identical point estimates to < 1e-8 in cells 01–05, 10, 13–16), so the `mediate()` floor is the floor of two 399-refit percentile bootstraps of that estimator.
- **Cell 07 (lavaan only) has no measured floor.** `mediate()` cannot estimate it, so its floor is taken as **zero**. That can only make its decision verdict stricter (a genuinely agreeing pair is then expected to be `tolerable` on this check rather than `negligible`); it is marked `none` in the report.

## Support matrix

N/A is reported, never imputed. The reasons are those of `support_matrix.json`.

| Cell | `mediation` (and `mediation_reseed`) | `lavaan` |
|---|---|---|
| 01 linear N=100, 02 linear N=250 | yes | yes |
| 03 no A→M, 04 no M→Y, 05 no mediation (structural-zero TNIE) | yes | yes |
| 06 parallel mediators with M1×M2 | no: joint TNIE of two interacting parallel mediators is outside `mediate()`'s single-mediator design | no: outcome nonlinear in the mediators, natural effects are not path products |
| 07 three serial mediators | no: three serial mediators | yes |
| 08 quadratic outcome | yes | no: outcome nonlinear in M |
| 09 natural-spline outcome | yes | no: outcome nonlinear in M |
| 10 moderated (binary W) | yes (two conditional calls, shared seed) | yes |
| 11 binary mediator | yes | no: lavaan's probit latent-response effects are a different estimand |
| 12 binary mediator and outcome, serial | no: two serial mediators | no: probit latent-response estimand |
| 13, 15 A-path only (N = 100, 250) | yes | yes |
| 14, 16 B-path only (N = 100, 250) | yes | yes |

**Judged units.** A cell-effect is judged for a comparator when both Mintmed and that comparator estimate it: `mediation` 13 cells, 39 cell-effects; `lavaan` 11 cells, 33 cell-effects. Cell 10's `TNIE_W0` and `TNIE_W1` are point-only in Mintmed, so only their bias check applies. Cells 06 and 12 are estimated by Mintmed alone and are reported as such.

## Metrics

**Per tool, mode, cell and effect** (every attempted dataset is the denominator; a missing interval counts as a miss): bias, bias Monte Carlo SE, RMSE, bias in population-SD units, coverage with its 95% Wilson interval, mean interval width, zero exclusion with its Wilson interval (power, or false positives for the null TNIE of cells 03–05 and 13–16), failure rate (rows without a finite estimate), warning rows and runtime.

**Paired with Mintmed, per comparator primary mode and cell-effect** (same datasets, joined by replicate):

| Quantity | Definition |
|---|---|
| Decision disagreement (pp) | % of datasets where Mintmed and the comparator reach different decisions (excludes zero above / below / includes zero). A missing interval on either side counts as a disagreement. |
| Noise floor (pp) | % of datasets where `mediation` and `mediation_reseed` disagree (both intervals available) |
| Excess disagreement (pp) | disagreement − floor, on the datasets present in all three runs, with a paired percentile bootstrap interval |
| Opposite-sign significant pairs | count of datasets where both intervals exclude zero on opposite sides |
| Sign agreement | share of datasets with equal point-estimate signs among those where either interval excludes zero; reported with the number of such pairs and its Wilson lower bound |
| Bias excess (SD) | (\|Mintmed mean bias\| − \|comparator mean bias\|) / population outcome SD |
| Coverage loss (pp) | comparator coverage − Mintmed coverage |
| False-positive excess (pp) | Mintmed zero exclusion − comparator zero exclusion (null effects only) |
| Power loss (pp) | comparator zero exclusion − Mintmed zero exclusion (non-null effects) |
| Width ratio | Mintmed mean width / comparator mean width (datasets where both have an interval) |

Every interval is a paired percentile bootstrap: 2,000 joint resamples of the datasets, seed `SeedSequence([20260928, crc32("tool|cell|effect|metric")])`. The code is `comparator_benchmark_reporting.py` (`paired_comparison`, `noise_floor_frame`, `classify_charter_tier`).

## Comparison rules

Frozen as `CHARTER_RULES` in `comparator_benchmark_reporting.py`; a test pins the values.

| Check | Judged on | Negligible | Tolerable |
|---|---|---|---|
| Excess decision disagreement over the noise floor | upper bound of the paired 95% interval | ≤ 5 pp | ≤ 10 pp |
| Pairs significant in opposite directions | observed count | 0 | 0 |
| Sign agreement when either is significant | observed rate (Wilson lower bound and pair count reported) | ≥ 0.99 | ≥ 0.99 |
| Coverage loss | observed value **and** upper bound | point ≤ 2.5 pp and upper ≤ 5 pp | upper ≤ 5 pp and Mintmed coverage ≥ 0.90 |
| False-positive excess (null effects) | observed value (upper bound reported) | ≤ 2.0 pp | ≤ 3.0 pp |
| Power loss (non-null effects) | upper bound | ≤ 5 pp | ≤ 10 pp |
| Width ratio | upper bound | ≤ 1.10 | ≤ 1.25 |
| Bias excess | upper bound | ≤ 0.02 SD | ≤ 0.02 SD |

- **Tier.** `negligible` if no negligible-column check fails; otherwise `tolerable` if no tolerable-column check fails; otherwise `substantive`. A check that cannot be computed (a point-only effect, the width ratio of a structural zero) is not applicable and does not affect the tier.
- **Any pair significant in opposite directions makes the cell-effect substantive.** This is the directional check that decision agreement exists to protect.
- Sign agreement and bias excess have no tolerable relaxation in the plan and keep their negligible limits.
- Values are compared with their limits with a slack of 1e-9, so a count exactly at a limit (for example 10 of 500 = 2.0 pp) is not failed by floating-point rounding.
- **Direction.** The guardrails measure Mintmed's loss only: a comparator that is worse than Mintmed gives a negative loss (or a width ratio below 1), which always passes. Decision disagreement and opposite-sign pairs are symmetric and fail in either direction.
- **Descriptive only:** the secondary modes, the original T17-S3 judging (column `tier_s3_rules`), and all Wilson and bootstrap bounds not named above.
- **The mixed-null question** (does the ~7% false-positive rate of cells 13–14 at N = 100 appear in the comparators, and does it shrink at N = 250 in cells 15–16) is answered descriptively: each tool's false-positive rate with its Wilson interval, per cell, next to the paired excess.

### What the verdicts can and cannot say

- The calibration's operating characteristics at n = 500 per cell-effect: a genuinely agreeing pair passes the excess-disagreement rule with probability about 0.94 and fails the negligible limit when the true excess is 5 pp with probability about 0.975; the coverage rule passes an agreeing pair with probability about 0.999 and fails a true 5 pp loss with probability 0.999; the false-positive rule passes an agreeing pair with probability 0.99, fails a true 3 pp excess with probability 0.87; power, width and bias pass an agreeing pair with probability ≥ 0.998.
- **No multiplicity adjustment.** The verdicts are per cell-effect. Among the 68 cell-effects with an applicable decision check (37 for `mediation`, 31 for `lavaan`), up to about 4 genuinely agreeing ones are expected to be labelled `tolerable` by the excess-disagreement rule alone. A single `tolerable` is therefore not by itself evidence of a difference; the report shows the values and bounds behind every verdict. A `substantive` verdict is documented as a limitation.
- **Cells 08, 09 and 11.** There `mediate()`'s point estimate carries Monte Carlo error that its rerun redraws, so the `mediate()`-vs-rerun floor contains that error twice, while Mintmed-vs-`mediate()` contains it once. The floor may therefore be higher than the floor of two exact-point methods, which makes the decision check more lenient in those cells. The coverage, power, width and bias checks are unaffected. The report shows the floor next to the raw disagreement so the reader can see it.

### Interpretation choices made when freezing

Where the owner decision, the plan and the calibration's recommendation left a detail open, the charter takes the calibration's recommendation or the stricter reading:

1. **Tolerable coverage** is judged on the upper bound (≤ 5 pp) plus Mintmed coverage ≥ 0.90, as the calibration recommends, not on the observed loss.
2. **Opposite-sign pairs:** zero is required (owner decision), not the calibration's "at most 1% of pairs".
3. **Sign agreement** keeps 0.99 in the tolerable tier, because the plan lists no tolerable relaxation.
4. **Cell 07 for lavaan** uses a zero floor (no `mediate()` rerun is possible there), which is stricter.
5. **Noise floor with a missing interval** does not count as a disagreement, which cannot loosen the rule.
6. **Tool id** of the rerun is `mediation_reseed`, consistent with the code's tool ids `mediation` and `lavaan` (the plan's `r_mediation`, `r_lavaan`).

## Denominators and completeness

- **Complete grid.** The comparator run has one row for every `(tool, cell_id, replicate)`: 3 tools × 16 cells × 500 = **24,000 rows** (`expected_combinations`), including explicit `not_estimable` rows. The Mintmed run for cells 15 and 16 has 2 × 500 = **1,000 rows**. `scripts/aggregate_shards.py` refuses a missing, duplicated or mixed-configuration shard.
- A comparator dataset-level `error` is a result: it stays in the denominator, counts as a decision disagreement and as noncoverage in the paired rules, and is reported in the comparator's failure rate. Mintmed's missing intervals are treated the same way.

## Runtime forecast

The Task 14 budget as amended on 2026-09-27 applies. On GitHub Actions `ubuntu-latest`: at most **36 aggregate CPU-hours**, including a 5% rerun allowance, and no shard projected over **4 wall-clock hours**.

**Pilots** (commit `2db6245`, both on 2026-09-29, both `success`):

- **R comparators and the noise-floor rerun:** GitHub run `36634980627`, `configs/comparator_pilot.yaml` (hash `e07447b6…`). It used the pre-charter calibration seed `20260929`, so no evaluation dataset was analysed. 6 cells × 3 tools × 5 datasets, one shard per cell and tool (18 shards), full settings (399 refits, 1000 quasi-Bayesian simulations). The R environment was R 4.6.1 with mediation 4.5.1, lavaan 0.7-2 and jsonlite 2.0.0 (`pins_match: true`), OpenBLAS. All 90 rows were `ok` or `not_estimable`; no error, warning, `runner_failed` or `missing_output`.
- **Mintmed cells 15 and 16:** runtime pilot in GitHub run `36634984823` (`verification.yml`, `run_pilot`), `configs/comparator_mintmed_cells15_16.yaml`, 2 repeats per cell, both `complete` (`gaussian_linear_exact`).

**Measured seconds per dataset** (median of 5; the row runtime, i.e. model fits plus every mode the tool runs):

| Cell | `mediation` (primary + quasi-Bayesian) | `lavaan` (bootstrap + delta) | `mediation_reseed` (primary) | Mintmed |
|---|---:|---:|---:|---:|
| 02 linear N=250 | 3.28 (1.57 + 1.71) | 8.74 (8.70 + 0.05) | 2.30 | — |
| 07 serial three N=200 | n/e | 9.21 | n/e | — |
| 09 spline N=250 | 11.20 (4.19 + 6.98) | n/e | 3.94 | — |
| 10 moderated N=150 | 10.49 (5.10 + 5.39) | 9.55 | 4.62 | — |
| 11 binary mediator N=150 | 3.27 | n/e | 2.48 | — |
| 16 B-path only N=250 | 4.44 | 6.47 | 2.27 | 5.81 |
| 15 A-path only N=250 | — | — | — | 5.80 |

The largest single-dataset time was at most 21% above the median in every cell. The reseed's primary mode is somewhat slower than `mediation`'s own primary mode in the same cell (for example 2.30 s against 1.57 s in cell 02); the forecast uses each tool's own measurement.

**Unpiloted cells use a piloted proxy that is at least as expensive**: the N = 100 single-mediator cells (01, 03–05, 13, 14) and cell 15 use cell 16 for `mediation`, cell 02 for `lavaan` and `mediation_reseed` (the slower of cells 02 and 16 for each tool); cell 08 (quadratic, N = 100) uses cell 09 (spline, N = 250). This overstates the cost of the N = 100 cells.

**Per-shard overhead.** Job duration minus the shard's own runtime was 64–117 s in the pilot (median about 85 s: checkout, `pip install`, R setup and package restore or install, dataset export). The forecast charges **120 s per shard**, the largest observed, also for the 8 shards of cells 06 and 12 that only write `not_estimable` rows and for the Mintmed shards.

**Forecast** (500 datasets per cell; layout in the next section):

| Item | CPU-hours |
|---|---:|
| `mediation`, 13 cells, both modes | 10.41 |
| `lavaan`, 11 cells, both modes | 13.22 |
| `mediation_reseed`, 13 cells, primary mode | 4.95 |
| Mintmed, cells 15 and 16 (runtime pilot base) | 1.61 |
| **Compute** | **30.18** |
| Compute with the 5% rerun allowance | 31.69 |
| Shard overhead, 74 shards × 120 s, with 5% | 2.59 |
| **Total** | **34.28 of 36 (pass)** |
| Slowest shard | `cell10_moderated_n150`: 125 datasets × 24.66 s + 120 s, with 5%: **0.93 wall-clock hours of 4 (pass)** |

- **Wall-clock time.** The pilot ran up to 18 shard jobs at once. At about 20 concurrent jobs the 74 shards take at least about 1.7 hours (total ÷ 20); allow 2–3.5 hours for queueing.
- **Margin.** The forecast has 1.7 CPU-hours of margin before the ceiling, after conservative proxies and overhead. A lavaan noise-floor rerun for cell 07 (not planned) would add about 1.3 CPU-hours (500 × 9.16 s primary mode).
- The forecast is a runtime boundary, not statistical evidence. The pilot's own estimates are 5 calibration-seed datasets per cell and are not results.

## Shard layout and dispatch

Two dispatches of `.github/workflows/sharded_benchmark.yml`, from the commit that adds this charter (or a later commit that changes nothing under `src/`, `scripts/`, `benchmarks/comparators/`, `configs/` or `.github/`). Shard order and count do not affect any seed.

**1. R comparators and the noise-floor rerun: 64 shards, 24,000 rows.** Dimension 1 is `--cell-id` (all 16 cells), dimension 2 is `--replicate-block` (`0of4`–`3of4`, 125 datasets each). Every shard runs all three tools (`--tool all`, the default) for its cell and block, so the 8 shards of cells 06 and 12 only write `not_estimable` rows.

```bash
gh workflow run sharded_benchmark.yml --ref <charter-commit> \
  -f runner_module=mintmed.experiments.comparator_benchmark \
  -f config=configs/mediation_validation_v3.yaml \
  -f dim1_flag=--cell-id \
  -f dim1_values=cell01_linear_n100,cell02_linear_n250,cell03_no_a_to_m_n100,cell04_no_m_to_y_n100,cell05_no_mediation_n100,cell06_parallel_interaction_n150,cell07_serial_three_n200,cell08_quadratic_n100,cell09_spline_n250,cell10_moderated_n150,cell11_binary_mediator_n150,cell12_mixed_binary_serial_n250,cell13_a_path_only_n100,cell14_b_path_only_n100,cell15_a_path_only_n250,cell16_b_path_only_n250 \
  -f dim2_flag=--replicate-block -f dim2_values=0of4,1of4,2of4,3of4 \
  -f with_r=true
```

**2. Mintmed, cells 15 and 16: 10 shards, 1,000 rows.** Dimension 1 is `--cell-id` (cells 15 and 16), dimension 2 is `--replicate-block` (`0of5`–`4of5`, 100 datasets each), without R.

```bash
gh workflow run sharded_benchmark.yml --ref <charter-commit> \
  -f runner_module=mintmed.experiments.mediation_validation \
  -f config=configs/comparator_mintmed_cells15_16.yaml \
  -f dim1_flag=--cell-id -f dim1_values=cell15_a_path_only_n250,cell16_b_path_only_n250 \
  -f dim2_flag=--replicate-block -f dim2_values=0of5,1of5,2of5,3of5,4of5 \
  -f with_r=false
```

The aggregate job of each dispatch checks the complete grid and writes the per-tool summaries. The paired comparison with Mintmed is made after archiving (see [Archiving](#archiving)).

## What counts as a failed run

A run is **failed** (an infrastructure failure, not a result) if any of these hold:

- a shard job fails, is cancelled or times out, or the aggregate job fails (missing, duplicated or mixed-configuration rows);
- any row has status `runner_failed`, or any record `missing_output`;
- `install_packages.R` or `versions.R` reports versions other than R 4.6.x, mediation 4.5.1, lavaan 0.7-2 and jsonlite 2.0.0, or any row's settings differ from this charter (399 bootstrap refits, 1000 quasi-Bayesian simulations, seed offsets 0 and 1000000007);
- a configuration hash differs from the Identity table.

A failed run is re-dispatched **unchanged** from the same commit (the outputs are deterministic apart from runtimes). This is not the one correction. Both runs are logged in the benchmark log, and the failed run's artifacts are archived too. Dataset-level `error` statuses of a comparator, and any tier, are results, never grounds for a rerun.

## One-correction rule

If a Stage 1 result is traced to an error in the **harness** (estimand mapping, fitted model, data transfer or seed handling of a comparator runner, or the reporting code):

- identify **one** root cause;
- make **one** targeted correction;
- rerun only the affected tools and cells, within the runtime budget.

There will be no estimator tournament, no change to Mintmed's estimator, no new feature, no grid expansion, no change to the limits or to what they are judged on, and no change to the inferential denominator. A difference that persists after that correction, or any `substantive` verdict, is documented as a limitation. Missing or duplicate rows block publication until resolved; they are never filled with summary statistics.

## Archiving

As soon as each run finishes, successful or not:

1. Download **all** artifacts immediately (GitHub keeps them 14 days):

   ```bash
   gh run download <run-id> -D results/generated/archive/github/<run-id>
   ```

2. Copy the small summaries (`summary.json`, `report.md`, `comparator_summary.csv` or `cell_summary.csv`, `metadata.json`, `resolved_config.yaml`) from the aggregated artifact to `benchmarks/runs/<run-id>/`.
3. Add the SHA-256, path and size of every downloaded file to `benchmarks/manifest.sha256`.
4. Append a row to `benchmarks/benchmark_log.md` with the date, run ID, commit, configuration hash, scope, compute and outcome.

The paired comparison is then produced locally, without refitting anything:

```bash
python -m mintmed.experiments.comparator_benchmark_reporting \
    --raw results/generated/archive/github/<r-run-id>/aggregated-benchmark/raw_metrics.csv \
    --config configs/mediation_validation_v3.yaml --output results/generated/comparator-stage1 \
    --mintmed-raw results/generated/archive/github/36349731184/aggregated-benchmark/raw_metrics.csv \
                  results/generated/archive/github/<mintmed-run-id>/aggregated-benchmark/raw_metrics.csv
```

`load_mintmed_reference` refuses Mintmed rows whose seeds are not v3's. The results go into `comparator_results.md` (T17-S9) with per-cell tables for every metric and tool, the verdicts, the mixed-null comparison at N = 100 and N = 250, and runtime.
