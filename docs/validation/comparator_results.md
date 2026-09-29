# Task 17 Stage 1 comparator results

This file permanently records the Task 17 Stage 1 comparison, fixed in advance by [`comparator_charter.md`](comparator_charter.md). The verdicts below are the charter's rules applied unchanged by `comparator_benchmark_reporting.py`; they are not re-graded here. Sections marked **descriptive** add interpretation and are not part of any verdict.

## Summary

**Question.** When Mintmed, R `mediation::mediate()` and lavaan all fit the **correctly specified** model to the same 500 datasets per design, does Mintmed's estimator (percentile participant bootstrap, 399 refits) behave as well as the standard tools?

**Answer: yes, with one documented difference.**
- Of 72 judged cell-effects, 68 are `negligible`, 2 are `tolerable` and 2 are `substantive`.
  - `mediation`: 36 negligible, 1 tolerable (cell 09 TNIE), 2 substantive (cell 08 TNIE, cell 11 TNIE), of 39.
  - `lavaan`: 32 negligible, 1 tolerable (cell 07 PNDE), of 33.
- No dataset anywhere had Mintmed and a comparator significant in opposite directions, and sign agreement was 1.00 in every cell-effect.
- Wherever the tools compute the same point estimate (every cell-effect except the TNIE and TE of cells 08, 09 and 11), Mintmed's estimates match `mediate()`'s and lavaan's (bias excess below 1e-15 SD), and coverage, width and power agree within the rules.

**The two `substantive` verdicts (and the `tolerable` cell 09) are the same finding.** They are the TNIE in the three cells where `mediate()`'s point estimate is computed by simulating the mediator once per observation (cells 08 quadratic outcome, 09 spline outcome, 11 binary mediator). There Mintmed and `mediate()` disagree on whether the interval excludes zero in 14–20% of datasets, against a `mediate()`-vs-`mediate()` floor of 6–9%. The direction is plain:
- Mintmed's intervals are 10–16% **narrower** and exclude zero **more often** (power 45% vs 26%, 67% vs 55%, 63% vs 48%). In 237 of the 247 disagreeing datasets, Mintmed excluded zero and `mediate()` did not.
- Mintmed's coverage is near nominal (94.6%, 94.8%, 94.0%); `mediate()` **over-covers** (97.6%, 98.2%, 97.2%).
- The charter counts both the excess disagreement and the coverage difference against Mintmed, so the verdict stands as `substantive`. It records a real difference in behaviour, not a Mintmed shortfall in coverage or power. A plausible explanation (descriptive, not tested directly) is `mediate()`'s own simulation noise, see [Cells 08, 09 and 11](#cells-08-09-and-11-tnie-descriptive).

**Mixed-null question.** The excess TNIE false-positive rate that failed Mintmed's run-2 null gate (cell 14, N = 100: 7.8%) **is shared by the standard tools' percentile bootstraps**: `mediate()` 8.2%, lavaan 7.2%, the `mediate()` rerun 7.0%. At N = 250 (cells 15 and 16) every tool is at 4.2–5.4%, so the excess does not persist at the larger sample size. See [Mixed-null comparison](#mixed-null-comparison).

**What this does and does not show.**
- Stage 1 covers **correctly specified models only**, on the 13 designs a comparator can estimate. Parity is the expected result for a correctly implemented estimator, and that is what was found.
- It says nothing about misspecification or about the information-guided direction of Task 18 ([`outline/06_resolution_information_guided_mediation.md`](../../outline/06_resolution_information_guided_mediation.md)). Stage 2 was merged into Task 18.
- It does not show that Mintmed is better than the other tools. "Not a tournament": no winner is declared.
- It does not change the run-2 verdict: run 2 stays failed on its null gate, and the mixed-null limitation in [`baseline_evidence.md`](baseline_evidence.md#known-limitations) stands. Stage 1 adds that the standard tools share it at N = 100.
- Cells 06 and 12 were estimable by Mintmed alone, and cell 07 by lavaan only.

## Run identity

| Item | Value |
|---|---|
| Charter | [`comparator_charter.md`](comparator_charter.md), frozen at commit `1c0d353` |
| Dispatched commit | `1c0d353a129c4df0283c1e0bb028b88c023b6555` (both runs; the charter commit). Nothing under `src/`, `scripts/`, `configs/`, `benchmarks/comparators/` or `.github/` changed between it and the reporting commit `5cdd3ba`. |
| R comparators and noise-floor rerun | GitHub run `36636602823`, `sharded_benchmark.yml`, 64 shards (16 cells × `0of4`–`3of4`), all `success`; 2026-09-29 21:57–23:45 UTC |
| Mintmed, cells 15 and 16 | GitHub run `36636611981`, 10 shards (2 cells × `0of5`–`4of5`), all `success`; 2026-09-29 21:57–23:22 UTC |
| Mintmed, cells 01–14 | Run 2, GitHub run `36349731184` (commit `9ff5de6`), reused unchanged |
| Configurations | `mediation_validation_v3.yaml`, hash `e6dc06ede1b1332056f41208654c55e2d217f021a82fbaa227e749ada5a4faf3`; `comparator_mintmed_cells15_16.yaml`, hash `a89c00731c7f8adf97e7ba6463d02ece5f47cd9911b13ff30ef75c55035fc3f3`; run 2: `mediation_validation_v2.yaml`, hash `0f2f738887b2a1669cf8c281e43fb9c258652291a4c50bbed9a009ffaafb953b`. One hash per file across all rows, as in the charter. |
| Raw inputs (SHA-256) | R comparators `results/generated/archive/github/36636602823/aggregated-benchmark/raw_metrics.csv`: `85936d76e4a78539a862fbfdd9ffd3fbf786097d156f293b72a972c6e75c078e` (112,108,701 bytes). Mintmed run 2: `b703847449c3c4c56b23ac0769685a3cb04d14bd63567ed2d84b949091247fbc` (12,106,089 bytes). Mintmed cells 15–16 (`…/36636611981/…`): `9cec95e9719923fbade19b6ecdc7438f25bf1371fe3a51cdf9d5906e2129b08c` (1,788,739 bytes). All three match `benchmarks/manifest.sha256`. |
| R environment | R 4.6.1, mediation 4.5.1, lavaan 0.7-2, jsonlite 2.0.0, `pins_match: true` on all 18,500 rows that ran R; OpenBLAS; one set of runner-script hashes across all rows |
| Paired comparison | The charter's [archiving command](comparator_charter.md#archiving), run locally into `results/generated/comparator-stage1/` (git-ignored): `paired_comparisons.csv` SHA-256 `a08d2807…`, `comparator_summary.csv` `9b9edbf0…`, `report.md` `944b782e…`, `summary.json` `a2970c76…`. A second run into a scratch folder reproduced all four files byte for byte (34 s). |
| Archived summaries | [`benchmarks/runs/36636602823/`](../../benchmarks/runs/36636602823/), [`benchmarks/runs/36636611981/`](../../benchmarks/runs/36636611981/); benchmark log rows 11 and 12 |

## Completeness and validity

The run is **valid** under [What counts as a failed run](comparator_charter.md#what-counts-as-a-failed-run):

- **Grid.** 24,000 of 24,000 comparator rows (3 tools × 16 cells × 500) and 1,000 of 1,000 Mintmed rows for cells 15–16; `complete_grid: true`, no duplicates or missing rows.
- **Statuses.** `mediation` and `mediation_reseed`: 6,500 `ok` and 1,500 `not_estimable` each (cells 06, 07, 12). `lavaan`: 5,487 `ok`, 13 `ok_warnings` and 2,500 `not_estimable` (cells 06, 08, 09, 11, 12). No `error`, `runner_failed` or `missing_output`. Every Mintmed row is `complete` (cells 15–16) or, for run 2, `complete` 5,500 / `complete_with_warnings` 1,500, with no missing interval apart from cell 10's point-only TNIE at W = 0 and W = 1.
- **The 13 lavaan warnings** (cells 01, 02, 05, 13, 15, 16) are all "1 bootstrap runs failed or did not converge": the interval used 398 of 399 refits. They count as successful rows, as the charter requires.
- **Settings.** Every row has 399 bootstrap refits, 1,000 quasi-Bayesian simulations and seed offsets 0 / 1000000007. No settings note was raised.
- **Failure rate.** 0 of 500 for every tool, mode and estimable cell-effect.
- **One-correction rule.** Not used. No harness error was found and nothing was rerun.

## Verdicts

Frozen rules: [Comparison rules](comparator_charter.md#comparison-rules). Each check is shown as the observed value with, in brackets or parentheses, the bound the rule uses. Positive coverage loss, false-positive excess and power loss mean Mintmed is lower (coverage, power) or higher (false positives) than the comparator; a width ratio below 1 means Mintmed's intervals are narrower. "Floor" is the `mediate()`-vs-rerun noise floor (`none` = zero floor, cell 07). Bias excess "≈0" means below 1e-15 SD: the tools compute identical point estimates there. Cell 10's `TNIE_W0` and `TNIE_W1` are point-only in Mintmed, so only the bias check applies. `Opp. sig.` = pairs significant in opposite directions; `Sign agr.` = sign agreement among the pairs where either interval excludes zero (count in parentheses).

**Non-negligible verdicts**

| Tool | Cell | Effect | Tier | Failed negligible checks | Failed tolerable checks |
|---|---|---|---|---|---|
| `mediation` | 08 quadratic, N = 100 | TNIE | **substantive** | decision excess (upper 17.2 > 5), coverage loss (point 3.0 > 2.5) | decision excess (upper 17.2 > 10) |
| `mediation` | 11 binary mediator, N = 150 | TNIE | **substantive** | decision excess (upper 11.0 > 5), coverage loss (point 3.2 > 2.5) | decision excess (upper 11.0 > 10) |
| `mediation` | 09 spline, N = 250 | TNIE | **tolerable** | decision excess (upper 8.6 > 5), coverage loss (point 3.4 > 2.5) | none (coverage upper 5.0 ≤ 5, Mintmed coverage 0.948 ≥ 0.90) |
| `lavaan` | 07 three serial mediators, N = 200 | PNDE | **tolerable** | decision excess (upper 7.0 > 5; zero floor) | none |

- The charter expected up to about 4 of the 68 cell-effects with a decision check to be labelled `tolerable` by chance alone. Two were `tolerable`; the lavaan cell 07 PNDE verdict is consistent with that: its 5.0 pp raw disagreement is in the range of the measured floors in other cells (0.8–8.6 pp), but cell 07 has no measured floor and is judged against zero.
- Under the original T17-S3 rules (absolute agreement, descriptive only), 56 of 72 cell-effects would have been `substantive`, including the linear cells where the tools compute identical estimates. This is the calibration's reason for the noise-floor rule.

**All cell-effects**

| Tool | Cell | Effect | Disagr. pp | Floor pp | Excess pp [95%] | Opp. sig. | Sign agr. (pairs) | Cov. loss pp (upper) | FP excess pp (upper) | Power loss pp (upper) | Width ratio (upper) | Bias excess SD (upper) | Tier | Failed checks |
|---|---|---|---:|---:|---|---:|---|---|---|---|---|---|---|---|
| lavaan | 01 | PNDE | 3.6 | 3.8 | -0.2 [-2.4, 2.0] | 0 | 1.00 (93) | 0.6 (2.0) | n/a | -1.2 (0.4) | 0.977 (0.983) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 01 | TE | 5.6 | 6.0 | -0.4 [-2.8, 2.0] | 0 | 1.00 (274) | 0.6 (2.0) | n/a | -2.4 (-0.4) | 0.979 (0.985) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 01 | TNIE | 5.2 | 5.0 | 0.2 [-2.2, 2.6] | 0 | 1.00 (353) | 0.8 (1.8) | n/a | -2.0 (0.0) | 0.977 (0.983) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 02 | PNDE | 5.8 | 5.4 | 0.4 [-2.0, 2.8] | 0 | 1.00 (186) | 0.4 (2.0) | n/a | -0.6 (1.6) | 0.979 (0.984) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 02 | TE | 2.8 | 1.6 | 1.2 [-0.2, 2.6] | 0 | 1.00 (461) | 0.2 (1.4) | n/a | -1.2 (0.4) | 0.978 (0.983) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 02 | TNIE | 1.4 | 1.4 | 0.0 [-1.0, 1.0] | 0 | 1.00 (490) | 0.4 (1.6) | n/a | 0.2 (1.2) | 0.976 (0.982) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 03 | PNDE | 3.0 | 4.8 | -1.8 [-3.6, 0.0] | 0 | 1.00 (96) | -0.2 (0.4) | n/a | -0.2 (1.4) | 0.982 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 03 | TE | 3.0 | 4.8 | -1.8 [-3.6, 0.0] | 0 | 1.00 (96) | -0.2 (0.4) | n/a | -0.2 (1.4) | 0.982 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 03 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| lavaan | 04 | PNDE | 4.0 | 3.6 | 0.4 [-1.8, 2.4] | 0 | 1.00 (89) | 0.8 (1.8) | n/a | 0.0 (1.8) | 0.981 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 04 | TE | 4.0 | 3.6 | 0.4 [-1.6, 2.6] | 0 | 1.00 (89) | 0.8 (1.8) | n/a | 0.0 (1.8) | 0.981 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 04 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| lavaan | 05 | PNDE | 3.0 | 3.0 | 0.0 [-1.8, 1.8] | 0 | 1.00 (91) | 0.8 (2.2) | n/a | -0.2 (1.2) | 0.980 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 05 | TE | 3.0 | 3.0 | 0.0 [-1.8, 1.8] | 0 | 1.00 (91) | 0.8 (2.0) | n/a | -0.2 (1.4) | 0.980 (0.986) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 05 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| lavaan | 07 | PNDE | 5.0 | none | 5.0 [3.2, 7.0] | 0 | 1.00 (159) | 0.6 (2.4) | n/a | -1.4 (0.6) | 0.980 (0.985) | ≈0 (< 1e-15) | **tolerable** | decision_excess |
| lavaan | 07 | TE | 3.2 | none | 3.2 [1.8, 4.8] | 0 | 1.00 (448) | 0.8 (2.0) | n/a | -1.6 (0.0) | 0.975 (0.981) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 07 | TNIE | 2.0 | none | 2.0 [1.0, 3.4] | 0 | 1.00 (469) | 0.4 (1.4) | n/a | -0.4 (0.8) | 0.981 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 10 | TNIE_W0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| lavaan | 10 | TNIE_W1 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| lavaan | 10 | TNIE_difference | 5.2 | 6.2 | -1.0 [-3.6, 1.4] | 0 | 1.00 (178) | 0.4 (1.6) | n/a | 0.4 (2.4) | 0.973 (0.979) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 13 | PNDE | 4.0 | 4.6 | -0.6 [-2.6, 1.4] | 0 | 1.00 (87) | 0.6 (1.8) | n/a | -0.8 (1.0) | 0.980 (0.986) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 13 | TE | 3.2 | 3.0 | 0.2 [-1.8, 2.0] | 0 | 1.00 (87) | 0.0 (1.2) | n/a | -0.8 (0.6) | 0.978 (0.984) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 13 | TNIE | 2.2 | 1.4 | 0.8 [-0.6, 2.2] | 0 | 1.00 (25) | 1.0 (2.4) | 1.0 (2.4) | n/a | 0.974 (0.982) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 14 | PNDE | 3.8 | 3.4 | 0.4 [-1.4, 2.2] | 0 | 1.00 (106) | 0.8 (1.8) | n/a | -1.4 (0.2) | 0.978 (0.984) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 14 | TE | 4.4 | 4.2 | 0.2 [-2.0, 2.4] | 0 | 1.00 (97) | 0.6 (1.6) | n/a | -2.8 (-1.0) | 0.980 (0.986) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 14 | TNIE | 1.8 | 2.4 | -0.6 [-2.0, 0.8] | 0 | 1.00 (42) | 0.6 (1.8) | 0.6 (1.8) | n/a | 0.974 (0.980) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 15 | PNDE | 5.0 | 6.0 | -1.0 [-3.0, 1.0] | 0 | 1.00 (160) | 1.0 (2.2) | n/a | -2.6 (-0.6) | 0.978 (0.984) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 15 | TE | 5.6 | 5.8 | -0.2 [-2.2, 1.8] | 0 | 1.00 (173) | 0.4 (1.8) | n/a | -1.6 (0.4) | 0.982 (0.987) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 15 | TNIE | 2.4 | 2.4 | 0.0 [-1.4, 1.4] | 0 | 1.00 (28) | 0.4 (1.8) | 0.4 (1.8) | n/a | 0.972 (0.979) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 16 | PNDE | 5.2 | 4.4 | 0.8 [-1.4, 3.0] | 0 | 1.00 (204) | 0.2 (1.2) | n/a | -2.8 (-0.8) | 0.983 (0.989) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 16 | TE | 5.4 | 5.6 | -0.2 [-2.6, 2.2] | 0 | 1.00 (165) | 1.0 (2.4) | n/a | -1.0 (1.0) | 0.979 (0.985) | ≈0 (< 1e-15) | negligible | – |
| lavaan | 16 | TNIE | 1.0 | 0.8 | 0.2 [-0.6, 1.2] | 0 | 1.00 (24) | 0.2 (1.0) | 0.2 (1.0) | n/a | 0.984 (0.990) | ≈0 (< 1e-15) | negligible | – |
| mediation | 01 | PNDE | 3.6 | 3.8 | -0.2 [-1.8, 1.4] | 0 | 1.00 (95) | 0.4 (1.6) | n/a | -0.4 (1.4) | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 01 | TE | 6.4 | 6.0 | 0.4 [-1.6, 2.4] | 0 | 1.00 (282) | 0.4 (1.8) | n/a | 0.0 (2.2) | 0.993 (0.999) | ≈0 (< 1e-15) | negligible | – |
| mediation | 01 | TNIE | 4.2 | 5.0 | -0.8 [-2.6, 1.0] | 0 | 1.00 (357) | 0.4 (1.2) | n/a | 0.6 (2.4) | 0.999 (1.006) | ≈0 (< 1e-15) | negligible | – |
| mediation | 02 | PNDE | 5.6 | 5.4 | 0.2 [-2.0, 2.2] | 0 | 1.00 (185) | 0.0 (1.4) | n/a | -0.8 (1.4) | 1.001 (1.007) | ≈0 (< 1e-15) | negligible | – |
| mediation | 02 | TE | 1.4 | 1.6 | -0.2 [-1.4, 1.0] | 0 | 1.00 (460) | -1.0 (0.0) | n/a | -0.2 (0.8) | 0.999 (1.005) | ≈0 (< 1e-15) | negligible | – |
| mediation | 02 | TNIE | 0.4 | 1.4 | -1.0 [-2.2, 0.0] | 0 | 1.00 (487) | 0.2 (1.4) | n/a | 0.0 (0.6) | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 03 | PNDE | 3.6 | 4.8 | -1.2 [-2.8, 0.4] | 0 | 1.00 (100) | -0.6 (0.4) | n/a | 0.8 (2.6) | 1.005 (1.010) | ≈0 (< 1e-15) | negligible | – |
| mediation | 03 | TE | 3.6 | 4.8 | -1.2 [-2.8, 0.4] | 0 | 1.00 (100) | -0.6 (0.4) | n/a | 0.8 (2.4) | 1.005 (1.011) | ≈0 (< 1e-15) | negligible | – |
| mediation | 03 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| mediation | 04 | PNDE | 3.8 | 3.6 | 0.2 [-1.4, 1.8] | 0 | 1.00 (91) | -0.2 (1.0) | n/a | 1.0 (2.8) | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 04 | TE | 3.8 | 3.6 | 0.2 [-1.4, 1.8] | 0 | 1.00 (91) | -0.2 (1.0) | n/a | 1.0 (2.8) | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 04 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| mediation | 05 | PNDE | 3.2 | 3.0 | 0.2 [-1.6, 2.0] | 0 | 1.00 (94) | 0.0 (1.2) | n/a | 0.8 (2.4) | 1.003 (1.010) | ≈0 (< 1e-15) | negligible | – |
| mediation | 05 | TE | 3.2 | 3.0 | 0.2 [-1.6, 2.0] | 0 | 1.00 (94) | 0.0 (1.2) | n/a | 0.8 (2.4) | 1.003 (1.010) | ≈0 (< 1e-15) | negligible | – |
| mediation | 05 | TNIE | 0.0 | 0.0 | 0.0 [0.0, 0.0] | 0 | n/a | 0.0 (0.0) | 0.0 (0.0) | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| mediation | 08 | PNDE | 4.2 | 4.2 | 0.0 [-2.0, 2.0] | 0 | 1.00 (109) | -0.8 (0.2) | n/a | -0.6 (1.2) | 1.001 (1.006) | ≈0 (< 1e-15) | negligible | – |
| mediation | 08 | TE | 6.6 | 4.4 | 2.2 [0.0, 4.4] | 0 | 1.00 (180) | 0.6 (1.8) | n/a | -1.4 (0.8) | 0.984 (0.989) | -0.0006 (0.0025) | negligible | – |
| mediation | 08 | TNIE | 19.8 | 6.4 | 13.4 [9.6, 17.2] | 0 | 1.00 (228) | 3.0 (4.6) | n/a | -18.6 (-15.2) | 0.840 (0.848) | 0.0006 (0.0025) | **substantive** | coverage_loss,decision_excess (tolerable: decision_excess) |
| mediation | 09 | PNDE | 6.4 | 6.2 | 0.2 [-1.8, 2.2] | 0 | 1.00 (195) | -0.4 (0.4) | n/a | -0.8 (1.4) | 1.000 (1.006) | ≈0 (< 1e-15) | negligible | – |
| mediation | 09 | TE | 4.8 | 5.4 | -0.6 [-2.8, 1.4] | 0 | 1.00 (335) | -0.2 (0.6) | n/a | -0.8 (1.2) | 0.981 (0.986) | -0.0010 (0.0014) | negligible | – |
| mediation | 09 | TNIE | 14.0 | 8.6 | 5.4 [2.2, 8.6] | 0 | 1.00 (339) | 3.4 (5.0) | n/a | -11.6 (-8.4) | 0.896 (0.903) | -0.0010 (0.0011) | **tolerable** | coverage_loss,decision_excess |
| mediation | 10 | TNIE_W0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| mediation | 10 | TNIE_W1 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | ≈0 (< 1e-15) | negligible | – |
| mediation | 10 | TNIE_difference | 5.8 | 6.2 | -0.4 [-2.6, 1.6] | 0 | 1.00 (182) | 0.0 (0.8) | n/a | 1.4 (3.6) | 0.997 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 11 | PNDE | 5.0 | 3.8 | 1.2 [-0.6, 3.0] | 0 | 1.00 (119) | -0.8 (0.4) | n/a | 0.2 (2.2) | 0.999 (1.005) | ≈0 (< 1e-15) | negligible | – |
| mediation | 11 | TE | 6.0 | 5.0 | 1.0 [-1.0, 3.0] | 0 | 1.00 (237) | 0.4 (1.8) | n/a | -2.4 (-0.4) | 0.979 (0.985) | -0.0010 (0.0021) | negligible | – |
| mediation | 11 | TNIE | 15.6 | 8.2 | 7.4 [4.0, 11.0] | 0 | 1.00 (318) | 3.2 (4.8) | n/a | -15.2 (-12.2) | 0.870 (0.876) | 0.0010 (0.0032) | **substantive** | coverage_loss,decision_excess (tolerable: decision_excess) |
| mediation | 13 | PNDE | 4.6 | 4.6 | 0.0 [-1.6, 1.8] | 0 | 1.00 (90) | 0.4 (1.4) | n/a | -0.2 (1.6) | 1.002 (1.008) | ≈0 (< 1e-15) | negligible | – |
| mediation | 13 | TE | 4.4 | 3.0 | 1.4 [-0.4, 3.2] | 0 | 1.00 (90) | 0.0 (1.0) | n/a | -0.8 (1.0) | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |
| mediation | 13 | TNIE | 1.2 | 1.4 | -0.2 [-1.2, 0.8] | 0 | 1.00 (24) | 0.4 (1.4) | 0.4 (1.4) | n/a | 1.002 (1.010) | ≈0 (< 1e-15) | negligible | – |
| mediation | 14 | PNDE | 3.2 | 3.4 | -0.2 [-1.8, 1.2] | 0 | 1.00 (110) | 1.2 (2.6) | n/a | 0.8 (2.4) | 1.001 (1.007) | ≈0 (< 1e-15) | negligible | – |
| mediation | 14 | TE | 4.6 | 4.2 | 0.4 [-1.2, 2.2] | 0 | 1.00 (105) | 0.2 (1.0) | n/a | 0.2 (2.2) | 1.003 (1.009) | ≈0 (< 1e-15) | negligible | – |
| mediation | 14 | TNIE | 1.6 | 2.4 | -0.8 [-2.2, 0.4] | 0 | 1.00 (44) | -0.4 (0.6) | -0.4 (0.6) | n/a | 0.998 (1.005) | ≈0 (< 1e-15) | negligible | – |
| mediation | 15 | PNDE | 4.2 | 6.0 | -1.8 [-3.8, 0.2] | 0 | 1.00 (166) | -0.6 (0.8) | n/a | 0.6 (2.4) | 1.000 (1.005) | ≈0 (< 1e-15) | negligible | – |
| mediation | 15 | TE | 5.0 | 5.8 | -0.8 [-3.0, 1.2] | 0 | 1.00 (177) | -0.4 (1.0) | n/a | 0.6 (2.6) | 1.000 (1.006) | ≈0 (< 1e-15) | negligible | – |
| mediation | 15 | TNIE | 1.2 | 2.4 | -1.2 [-2.6, 0.0] | 0 | 1.00 (28) | -0.8 (0.0) | -0.8 (0.2) | n/a | 0.996 (1.002) | ≈0 (< 1e-15) | negligible | – |
| mediation | 16 | PNDE | 5.0 | 4.4 | 0.6 [-1.6, 2.8] | 0 | 1.00 (210) | 0.0 (1.2) | n/a | -0.2 (2.0) | 1.000 (1.006) | ≈0 (< 1e-15) | negligible | – |
| mediation | 16 | TE | 5.8 | 5.6 | 0.2 [-1.8, 2.2] | 0 | 1.00 (169) | 0.0 (1.4) | n/a | 0.2 (2.4) | 0.996 (1.001) | ≈0 (< 1e-15) | negligible | – |
| mediation | 16 | TNIE | 1.2 | 0.8 | 0.4 [-0.4, 1.2] | 0 | 1.00 (25) | 0.0 (0.8) | 0.0 (1.0) | n/a | 0.998 (1.004) | ≈0 (< 1e-15) | negligible | – |

### Cells 08, 09 and 11 TNIE (descriptive)

This section explains the three non-negligible `mediation` verdicts. It does not change them.

| Cell | Coverage: Mintmed / `mediate()` / rerun | Mean width: Mintmed / `mediate()` | Zero exclusion: Mintmed / `mediate()` | Disagreeing datasets | Mintmed alone excludes 0 / `mediate()` alone | RMSE: Mintmed / `mediate()` |
|---|---|---|---|---:|---|---|
| 08 quadratic, N = 100 | 0.946 / 0.976 / 0.974 | 0.245 / 0.292 | 0.450 / 0.264 | 99 | 96 / 3 | 0.058 / 0.072 |
| 09 spline, N = 250 | 0.948 / 0.982 / 0.976 | 0.201 / 0.224 | 0.666 / 0.550 | 70 | 64 / 6 | 0.047 / 0.056 |
| 11 binary mediator, N = 150 | 0.940 / 0.972 / 0.974 | 0.240 / 0.276 | 0.634 / 0.482 | 78 | 77 / 1 | 0.065 / 0.076 |

- **What differs.** In these cells Mintmed integrates the mediator distribution exactly (Gauss–Hermite quadrature for 08 and 09, enumeration of the binary mediator for 11). `mediate()` computes its point estimate, and each bootstrap refit, from **one simulated mediator draw per observation** ([`comparator_support.md`](comparator_support.md#how-mediate-computes-its-point-estimate-with-boot--true)). That simulation error does not shrink with the number of bootstrap refits.
- **Its size here.** On the same datasets, `mediate()` and its reseeded rerun differ only in the R seed. The standard deviation of the difference between their TNIE point estimates is 0.061, 0.040 and 0.051 in cells 08, 09 and 11, i.e. about 0.043, 0.028 and 0.036 per run. That is roughly 55–75% of the sampling SD of Mintmed's estimate (0.058, 0.047, 0.065). In the linear cells the two runs' point estimates are identical.
- **A plausible explanation.** If every bootstrap refit carries its own simulation noise, the spread of the refits includes that noise on top of the sampling variation, so the percentile interval is wider than the sampling variation alone requires. That would give exactly what is observed: `mediate()` intervals about 11–19% wider than Mintmed's (width ratio 0.84–0.90), over-coverage (97–98%), and lower power. The rerun reproduces the same pattern (coverage 0.974 / 0.976 / 0.974), so it is systematic and not seed luck. This explanation was not tested directly (for example by averaging many mediator draws inside `mediate()`), so it is stated as likely, not established.
- **Consequence for the verdict.** Both failed checks are driven by `mediate()` behaving more conservatively, not by Mintmed losing coverage or power: Mintmed's coverage is within its Wilson interval of 0.95 in all three cells, and its power is higher (power loss upper bounds −15.2, −8.4, −12.2 pp). The charter's coverage rule counts any coverage difference in the comparator's favour against Mintmed, including over-coverage, and the decision rule is symmetric. The `substantive` label is therefore kept, as the one-correction rule requires, and is documented as a limitation in the sense of "Mintmed and `mediate()` reach materially different conclusions on the TNIE in these designs".
- **Floor.** The measured floor in these three cells (6.4, 8.6, 8.2 pp for TNIE) is higher than in the other cells (0.8–6.2 pp), as the charter anticipated: the rerun redraws the simulation error, so the floor contains it twice. That makes the decision check more lenient here, and the excess still exceeds the limits in cells 08 and 11.
- **Other effects in these cells are negligible.** PNDE is exact in `mediate()` (no A × M term), so its estimates equal Mintmed's. TE (`tau.coef`) inherits the TNIE simulation error, but its disagreement stays within the floor.
- Run 2 recorded that cell 08's TNIE misses are one-sided (truth above the interval 24 times, below 3). That is unchanged and is not what drives this verdict: Mintmed's coverage there is 0.946.

## Noise floor

The per-dataset floor is 1 when `mediation` and `mediation_reseed` (same datasets, different R seed) reach different decisions. It was computed on all 500 datasets of every `mediate()`-estimable cell (no missing intervals). The same floor is applied to lavaan. Cell 07 (lavaan only) has no measured floor and uses zero.

| Cell | TE (pp) | PNDE (pp) | TNIE (pp) |
|---|---:|---:|---:|
| 01 linear, N = 100 | 6.0 | 3.8 | 5.0 |
| 02 linear, N = 250 | 1.6 | 5.4 | 1.4 |
| 03 no A → M, N = 100 | 4.8 | 4.8 | 0.0 (structural zero) |
| 04 no M → Y, N = 100 | 3.6 | 3.6 | 0.0 (structural zero) |
| 05 no mediation, N = 100 | 3.0 | 3.0 | 0.0 (structural zero) |
| 07 three serial, N = 200 | none (0) | none (0) | none (0) |
| 08 quadratic, N = 100 | 4.4 | 4.2 | 6.4 |
| 09 spline, N = 250 | 5.4 | 6.2 | 8.6 |
| 10 moderated, N = 150 | — | — | 6.2 (`TNIE_difference`) |
| 11 binary mediator, N = 150 | 5.0 | 3.8 | 8.2 |
| 13 A-path only, N = 100 | 3.0 | 4.6 | 1.4 |
| 14 B-path only, N = 100 | 4.2 | 3.4 | 2.4 |
| 15 A-path only, N = 250 | 5.8 | 6.0 | 2.4 |
| 16 B-path only, N = 250 | 5.6 | 4.4 | 0.8 |

Across the 34 non-structural cell-effects the floor ranges from 0.8 to 8.6 pp (the calibration measured 67 of 1,300 pairs, 5.2%). Mintmed's own disagreement with `mediate()` stays within 2.2 pp of the floor in every cell-effect outside cells 08, 09 and 11 TNIE.

## Mixed-null comparison

Descriptive, as the charter requires. TNIE truth is 0 in cells 13–16; "excludes 0" counts intervals entirely above or below zero out of 500, with the 95% Wilson interval. Primary modes are the percentile bootstraps (399 refits); the last two columns are the package defaults (secondary modes).

| Cell | Mintmed | `mediation` | `lavaan` | `mediation_reseed` | `mediate()` quasi-Bayesian | lavaan delta method |
|---|---|---|---|---|---|---|
| 13 A-path only, N = 100 | 22 = 4.4% [2.9, 6.6] | 20 = 4.0% [2.6, 6.1] | 17 = 3.4% [2.1, 5.4] | 25 = 5.0% [3.4, 7.3] | 20 = 4.0% [2.6, 6.1] | 6 = 1.2% [0.6, 2.6] |
| 14 B-path only, N = 100 | 39 = 7.8% [5.8, 10.5] | 41 = 8.2% [6.1, 10.9] | 36 = 7.2% [5.2, 9.8] | 35 = 7.0% [5.1, 9.6] | 37 = 7.4% [5.4, 10.0] | 26 = 5.2% [3.6, 7.5] |
| 15 A-path only, N = 250 | 23 = 4.6% [3.1, 6.8] | 27 = 5.4% [3.7, 7.7] | 21 = 4.2% [2.8, 6.3] | 25 = 5.0% [3.4, 7.3] | 27 = 5.4% [3.7, 7.7] | 11 = 2.2% [1.2, 3.9] |
| 16 B-path only, N = 250 | 22 = 4.4% [2.9, 6.6] | 22 = 4.4% [2.9, 6.6] | 21 = 4.2% [2.8, 6.3] | 24 = 4.8% [3.3, 7.0] | 23 = 4.6% [3.1, 6.8] | 17 = 3.4% [2.1, 5.4] |

Paired false-positive excess (Mintmed − comparator, pp, upper bound in parentheses; judged at ≤ 2.0 pp observed, all `negligible`):

| Cell | vs `mediation` | vs `lavaan` |
|---|---|---|
| 13 | 0.4 (1.4) | 1.0 (2.4) |
| 14 | −0.4 (0.6) | 0.6 (1.8) |
| 15 | −0.8 (0.2) | 0.4 (1.8) |
| 16 | 0.0 (1.0) | 0.2 (1.0) |

- **N = 100.** In cell 14 all four percentile bootstraps exclude zero in 7.0–8.2% of datasets. Mintmed's 7.8% sits between `mediate()`'s two runs (8.2% and 7.0%), which differ only by bootstrap Monte Carlo error. This points to a property of percentile bootstrap intervals for a product of coefficients when A → M is zero and M → Y is strong, rather than to Mintmed's implementation. Mintmed's exclusions are two-sided (18 above zero, 21 below).
- **N = 250.** In cells 15 and 16 every bootstrap is at 4.2–5.4%, and every Wilson interval contains 5%. The run-2 excess does not persist at N = 250 in any tool.
- **Package defaults (descriptive).** lavaan's delta-method interval is conservative for a null indirect effect (1.2–5.2%), as expected for a normal-theory product interval. `mediate()`'s quasi-Bayesian default behaves like the bootstraps (7.4% in cell 14).
- Cell 13 (M → Y truly zero) is at or below 5% for every tool at both sample sizes.

## Per-cell operating characteristics (primary modes)

Every attempted dataset (500) is the denominator; no interval was missing. Mintmed's values for cells 01–14 are run 2's, computed from its raw rows, and agree with [`coverage_revalidation_results.md`](coverage_revalidation_results.md). `n/e` = not estimable by that tool ([support matrix](comparator_charter.md#support-matrix)). Cells 03–05's TNIE is a structural zero in every tool (estimate 0, width 0, always covered). `mediation_reseed` (`reseed`) is the noise-floor rerun and is never compared with Mintmed.

Cell key: 01 linear N = 100; 02 linear N = 250; 03 no A → M; 04 no M → Y; 05 no mediation; 06 parallel mediators with M1 × M2, N = 150; 07 three serial mediators, N = 200; 08 quadratic outcome, N = 100; 09 spline outcome, N = 250; 10 binary moderator, N = 150; 11 binary mediator, N = 150; 12 binary mediator and outcome, serial, N = 250; 13 A-path only, N = 100; 14 B-path only, N = 100; 15 A-path only, N = 250; 16 B-path only, N = 250.

**Coverage with 95% Wilson interval**

| Cell | Effect | Mintmed | `mediation` | `lavaan` | `mediation_reseed` |
|---|---|---|---|---|---|
| 01 | TE | 0.948 [0.925, 0.964] | 0.952 [0.930, 0.968] | 0.954 [0.932, 0.969] | 0.948 [0.925, 0.964] |
| 01 | PNDE | 0.950 [0.927, 0.966] | 0.954 [0.932, 0.969] | 0.956 [0.934, 0.971] | 0.950 [0.927, 0.966] |
| 01 | TNIE | 0.950 [0.927, 0.966] | 0.954 [0.932, 0.969] | 0.958 [0.937, 0.972] | 0.958 [0.937, 0.972] |
| 02 | TE | 0.960 [0.939, 0.974] | 0.950 [0.927, 0.966] | 0.962 [0.941, 0.976] | 0.950 [0.927, 0.966] |
| 02 | PNDE | 0.944 [0.920, 0.961] | 0.944 [0.920, 0.961] | 0.948 [0.925, 0.964] | 0.940 [0.916, 0.958] |
| 02 | TNIE | 0.928 [0.902, 0.948] | 0.930 [0.904, 0.949] | 0.932 [0.906, 0.951] | 0.920 [0.893, 0.941] |
| 03 | TE | 0.958 [0.937, 0.972] | 0.952 [0.930, 0.968] | 0.956 [0.934, 0.971] | 0.952 [0.930, 0.968] |
| 03 | PNDE | 0.958 [0.937, 0.972] | 0.952 [0.930, 0.968] | 0.956 [0.934, 0.971] | 0.952 [0.930, 0.968] |
| 03 | TNIE | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] |
| 04 | TE | 0.940 [0.916, 0.958] | 0.938 [0.913, 0.956] | 0.948 [0.925, 0.964] | 0.944 [0.920, 0.961] |
| 04 | PNDE | 0.940 [0.916, 0.958] | 0.938 [0.913, 0.956] | 0.948 [0.925, 0.964] | 0.944 [0.920, 0.961] |
| 04 | TNIE | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] |
| 05 | TE | 0.942 [0.918, 0.959] | 0.942 [0.918, 0.959] | 0.950 [0.927, 0.966] | 0.936 [0.911, 0.954] |
| 05 | PNDE | 0.942 [0.918, 0.959] | 0.942 [0.918, 0.959] | 0.950 [0.927, 0.966] | 0.936 [0.911, 0.954] |
| 05 | TNIE | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] | 1.000 [0.992, 1.000] |
| 06 | TNIE | 0.960 [0.939, 0.974] | n/e | n/e | n/e |
| 07 | TE | 0.938 [0.913, 0.956] | n/e | 0.946 [0.923, 0.963] | n/e |
| 07 | PNDE | 0.922 [0.895, 0.942] | n/e | 0.928 [0.902, 0.948] | n/e |
| 07 | TNIE | 0.946 [0.923, 0.963] | n/e | 0.950 [0.927, 0.966] | n/e |
| 08 | TE | 0.946 [0.923, 0.963] | 0.952 [0.930, 0.968] | n/e | 0.958 [0.937, 0.972] |
| 08 | PNDE | 0.940 [0.916, 0.958] | 0.932 [0.906, 0.951] | n/e | 0.932 [0.906, 0.951] |
| 08 | TNIE | 0.946 [0.923, 0.963] | 0.976 [0.959, 0.986] | n/e | 0.974 [0.956, 0.985] |
| 09 | TE | 0.958 [0.937, 0.972] | 0.956 [0.934, 0.971] | n/e | 0.950 [0.927, 0.966] |
| 09 | PNDE | 0.960 [0.939, 0.974] | 0.956 [0.934, 0.971] | n/e | 0.954 [0.932, 0.969] |
| 09 | TNIE | 0.948 [0.925, 0.964] | 0.982 [0.966, 0.991] | n/e | 0.976 [0.959, 0.986] |
| 10 | TNIE_W0 | point-only | 0.912 [0.884, 0.934] | 0.924 [0.897, 0.944] | 0.908 [0.879, 0.930] |
| 10 | TNIE_W1 | point-only | 0.938 [0.913, 0.956] | 0.950 [0.927, 0.966] | 0.944 [0.920, 0.961] |
| 10 | TNIE_difference | 0.936 [0.911, 0.954] | 0.936 [0.911, 0.954] | 0.940 [0.916, 0.958] | 0.938 [0.913, 0.956] |
| 11 | TE | 0.938 [0.913, 0.956] | 0.942 [0.918, 0.959] | n/e | 0.940 [0.916, 0.958] |
| 11 | PNDE | 0.956 [0.934, 0.971] | 0.948 [0.925, 0.964] | n/e | 0.956 [0.934, 0.971] |
| 11 | TNIE | 0.940 [0.916, 0.958] | 0.972 [0.954, 0.983] | n/e | 0.974 [0.956, 0.985] |
| 12 | TE | 0.944 [0.920, 0.961] | n/e | n/e | n/e |
| 12 | PNDE | 0.950 [0.927, 0.966] | n/e | n/e | n/e |
| 12 | TNIE | 0.956 [0.934, 0.971] | n/e | n/e | n/e |
| 13 | TE | 0.944 [0.920, 0.961] | 0.944 [0.920, 0.961] | 0.944 [0.920, 0.961] | 0.936 [0.911, 0.954] |
| 13 | PNDE | 0.938 [0.913, 0.956] | 0.942 [0.918, 0.959] | 0.944 [0.920, 0.961] | 0.938 [0.913, 0.956] |
| 13 | TNIE | 0.956 [0.934, 0.971] | 0.960 [0.939, 0.974] | 0.966 [0.946, 0.979] | 0.950 [0.927, 0.966] |
| 14 | TE | 0.934 [0.909, 0.953] | 0.936 [0.911, 0.954] | 0.940 [0.916, 0.958] | 0.932 [0.906, 0.951] |
| 14 | PNDE | 0.938 [0.913, 0.956] | 0.950 [0.927, 0.966] | 0.946 [0.923, 0.963] | 0.940 [0.916, 0.958] |
| 14 | TNIE | 0.922 [0.895, 0.942] | 0.918 [0.891, 0.939] | 0.928 [0.902, 0.948] | 0.930 [0.904, 0.949] |
| 15 | TE | 0.940 [0.916, 0.958] | 0.936 [0.911, 0.954] | 0.944 [0.920, 0.961] | 0.934 [0.909, 0.953] |
| 15 | PNDE | 0.936 [0.911, 0.954] | 0.930 [0.904, 0.949] | 0.946 [0.923, 0.963] | 0.942 [0.918, 0.959] |
| 15 | TNIE | 0.954 [0.932, 0.969] | 0.946 [0.923, 0.963] | 0.958 [0.937, 0.972] | 0.950 [0.927, 0.966] |
| 16 | TE | 0.954 [0.932, 0.969] | 0.954 [0.932, 0.969] | 0.964 [0.944, 0.977] | 0.946 [0.923, 0.963] |
| 16 | PNDE | 0.946 [0.923, 0.963] | 0.946 [0.923, 0.963] | 0.948 [0.925, 0.964] | 0.940 [0.916, 0.958] |
| 16 | TNIE | 0.956 [0.934, 0.971] | 0.956 [0.934, 0.971] | 0.958 [0.937, 0.972] | 0.952 [0.930, 0.968] |

**Mean interval width and zero exclusion (power for non-null effects, false positives for null TNIE)**

| Cell | Effect | Width: Mintmed | `mediation` | `lavaan` | `reseed` | Zero excl.: Mintmed | `mediation` | `lavaan` | `reseed` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 01 | TE | 0.865 | 0.871 | 0.884 | 0.869 | 0.532 | 0.532 | 0.508 | 0.524 |
| 01 | PNDE | 0.803 | 0.805 | 0.821 | 0.807 | 0.174 | 0.170 | 0.162 | 0.180 |
| 01 | TNIE | 0.454 | 0.454 | 0.465 | 0.454 | 0.690 | 0.696 | 0.670 | 0.682 |
| 02 | TE | 0.548 | 0.548 | 0.560 | 0.549 | 0.914 | 0.912 | 0.902 | 0.908 |
| 02 | PNDE | 0.507 | 0.507 | 0.518 | 0.508 | 0.346 | 0.338 | 0.340 | 0.352 |
| 02 | TNIE | 0.277 | 0.278 | 0.284 | 0.277 | 0.972 | 0.972 | 0.974 | 0.974 |
| 03 | TE | 0.780 | 0.777 | 0.795 | 0.775 | 0.178 | 0.186 | 0.176 | 0.178 |
| 03 | PNDE | 0.780 | 0.777 | 0.795 | 0.775 | 0.178 | 0.186 | 0.176 | 0.178 |
| 03 | TNIE | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 04 | TE | 0.775 | 0.776 | 0.790 | 0.774 | 0.158 | 0.168 | 0.158 | 0.164 |
| 04 | PNDE | 0.775 | 0.776 | 0.790 | 0.774 | 0.158 | 0.168 | 0.158 | 0.164 |
| 04 | TNIE | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 05 | TE | 0.778 | 0.775 | 0.794 | 0.777 | 0.168 | 0.176 | 0.166 | 0.178 |
| 05 | PNDE | 0.778 | 0.775 | 0.794 | 0.777 | 0.168 | 0.176 | 0.166 | 0.178 |
| 05 | TNIE | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 06 | TNIE | 0.521 | n/e | n/e | n/e | 0.920 | n/e | n/e | n/e |
| 07 | TE | 0.666 | n/e | 0.682 | n/e | 0.888 | n/e | 0.872 | n/e |
| 07 | PNDE | 0.578 | n/e | 0.590 | n/e | 0.300 | n/e | 0.286 | n/e |
| 07 | TNIE | 0.427 | n/e | 0.435 | n/e | 0.930 | n/e | 0.926 | n/e |
| 08 | TE | 0.819 | 0.832 | n/e | 0.832 | 0.334 | 0.320 | n/e | 0.332 |
| 08 | PNDE | 0.782 | 0.781 | n/e | 0.781 | 0.200 | 0.194 | n/e | 0.196 |
| 08 | TNIE | 0.245 | 0.292 | n/e | 0.293 | 0.450 | 0.264 | n/e | 0.260 |
| 09 | TE | 0.514 | 0.524 | n/e | 0.526 | 0.650 | 0.642 | n/e | 0.632 |
| 09 | PNDE | 0.509 | 0.509 | n/e | 0.512 | 0.362 | 0.354 | n/e | 0.360 |
| 09 | TNIE | 0.201 | 0.224 | n/e | 0.225 | 0.666 | 0.550 | n/e | 0.544 |
| 10 | TNIE_W0 | — | 0.342 | 0.351 | 0.342 | — | 0.184 | 0.154 | 0.172 |
| 10 | TNIE_W1 | — | 0.612 | 0.629 | 0.614 | — | 0.718 | 0.700 | 0.714 |
| 10 | TNIE_difference | 0.704 | 0.705 | 0.723 | 0.705 | 0.328 | 0.342 | 0.332 | 0.336 |
| 11 | TE | 0.656 | 0.670 | n/e | 0.670 | 0.456 | 0.432 | n/e | 0.442 |
| 11 | PNDE | 0.644 | 0.644 | n/e | 0.643 | 0.212 | 0.214 | n/e | 0.216 |
| 11 | TNIE | 0.240 | 0.276 | n/e | 0.275 | 0.634 | 0.482 | n/e | 0.468 |
| 12 | TE | 0.238 | n/e | n/e | n/e | 0.372 | n/e | n/e | n/e |
| 12 | PNDE | 0.241 | n/e | n/e | n/e | 0.124 | n/e | n/e | n/e |
| 12 | TNIE | 0.086 | n/e | n/e | n/e | 0.812 | n/e | n/e | n/e |
| 13 | TE | 0.774 | 0.775 | 0.791 | 0.775 | 0.162 | 0.154 | 0.154 | 0.156 |
| 13 | PNDE | 0.804 | 0.802 | 0.821 | 0.804 | 0.158 | 0.156 | 0.150 | 0.146 |
| 13 | TNIE | 0.239 | 0.239 | 0.245 | 0.239 | 0.044 | 0.040 | 0.034 | 0.050 |
| 14 | TE | 0.869 | 0.866 | 0.887 | 0.869 | 0.186 | 0.188 | 0.158 | 0.182 |
| 14 | PNDE | 0.781 | 0.781 | 0.799 | 0.784 | 0.200 | 0.208 | 0.186 | 0.198 |
| 14 | TNIE | 0.408 | 0.409 | 0.419 | 0.407 | 0.078 | 0.082 | 0.072 | 0.070 |
| 15 | TE | 0.490 | 0.490 | 0.499 | 0.488 | 0.326 | 0.332 | 0.310 | 0.310 |
| 15 | PNDE | 0.506 | 0.506 | 0.517 | 0.506 | 0.308 | 0.314 | 0.282 | 0.310 |
| 15 | TNIE | 0.135 | 0.135 | 0.139 | 0.135 | 0.046 | 0.054 | 0.042 | 0.050 |
| 16 | TE | 0.546 | 0.549 | 0.558 | 0.548 | 0.308 | 0.310 | 0.298 | 0.314 |
| 16 | PNDE | 0.491 | 0.491 | 0.499 | 0.492 | 0.396 | 0.394 | 0.368 | 0.378 |
| 16 | TNIE | 0.250 | 0.251 | 0.254 | 0.250 | 0.044 | 0.044 | 0.042 | 0.048 |

**Mean bias and RMSE**

| Cell | Effect | Bias: Mintmed | `mediation` | `lavaan` | `reseed` | RMSE: Mintmed | `mediation` | `lavaan` | `reseed` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 01 | TE | 0.0007 | 0.0007 | 0.0007 | 0.0007 | 0.2151 | 0.2151 | 0.2151 | 0.2151 |
| 01 | PNDE | -0.0006 | -0.0006 | -0.0006 | -0.0006 | 0.2012 | 0.2012 | 0.2012 | 0.2012 |
| 01 | TNIE | 0.0013 | 0.0013 | 0.0013 | 0.0013 | 0.1121 | 0.1121 | 0.1121 | 0.1121 |
| 02 | TE | 0.0031 | 0.0031 | 0.0031 | 0.0031 | 0.1314 | 0.1314 | 0.1314 | 0.1314 |
| 02 | PNDE | -0.0012 | -0.0012 | -0.0012 | -0.0012 | 0.1280 | 0.1280 | 0.1280 | 0.1280 |
| 02 | TNIE | 0.0043 | 0.0043 | 0.0043 | 0.0043 | 0.0766 | 0.0766 | 0.0766 | 0.0766 |
| 03 | TE | -0.0032 | -0.0032 | -0.0032 | -0.0032 | 0.1936 | 0.1936 | 0.1936 | 0.1936 |
| 03 | PNDE | -0.0032 | -0.0032 | -0.0032 | -0.0032 | 0.1936 | 0.1936 | 0.1936 | 0.1936 |
| 03 | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 04 | TE | -0.0078 | -0.0078 | -0.0078 | -0.0078 | 0.2029 | 0.2029 | 0.2029 | 0.2029 |
| 04 | PNDE | -0.0078 | -0.0078 | -0.0078 | -0.0078 | 0.2029 | 0.2029 | 0.2029 | 0.2029 |
| 04 | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 05 | TE | -0.0091 | -0.0091 | -0.0091 | -0.0091 | 0.2042 | 0.2042 | 0.2042 | 0.2042 |
| 05 | PNDE | -0.0091 | -0.0091 | -0.0091 | -0.0091 | 0.2042 | 0.2042 | 0.2042 | 0.2042 |
| 05 | TNIE | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 06 | TNIE | 0.0084 | n/e | n/e | n/e | 0.1225 | n/e | n/e | n/e |
| 07 | TE | -0.0028 | n/e | -0.0028 | n/e | 0.1751 | n/e | 0.1751 | n/e |
| 07 | PNDE | 0.0036 | n/e | 0.0036 | n/e | 0.1548 | n/e | 0.1548 | n/e |
| 07 | TNIE | -0.0064 | n/e | -0.0064 | n/e | 0.1094 | n/e | 0.1094 | n/e |
| 08 | TE | 0.0030 | 0.0038 | n/e | 0.0059 | 0.2172 | 0.2249 | n/e | 0.2202 |
| 08 | PNDE | 0.0056 | 0.0056 | n/e | 0.0056 | 0.2111 | 0.2111 | n/e | 0.2111 |
| 08 | TNIE | -0.0025 | -0.0017 | n/e | 0.0004 | 0.0578 | 0.0716 | n/e | 0.0731 |
| 09 | TE | 0.0072 | 0.0084 | n/e | 0.0067 | 0.1308 | 0.1339 | n/e | 0.1357 |
| 09 | PNDE | 0.0051 | 0.0051 | n/e | 0.0051 | 0.1264 | 0.1264 | n/e | 0.1264 |
| 09 | TNIE | 0.0021 | 0.0034 | n/e | 0.0016 | 0.0475 | 0.0556 | n/e | 0.0545 |
| 10 | TNIE_W0 | 0.0007 | 0.0007 | 0.0007 | 0.0007 | 0.0872 | 0.0872 | 0.0872 | 0.0872 |
| 10 | TNIE_W1 | -0.0047 | -0.0047 | -0.0047 | -0.0047 | 0.1636 | 0.1636 | 0.1636 | 0.1636 |
| 10 | TNIE_difference | -0.0054 | -0.0054 | -0.0054 | -0.0054 | 0.1878 | 0.1878 | 0.1878 | 0.1878 |
| 11 | TE | -0.0081 | -0.0092 | n/e | -0.0074 | 0.1764 | 0.1810 | n/e | 0.1782 |
| 11 | PNDE | -0.0120 | -0.0120 | n/e | -0.0120 | 0.1647 | 0.1647 | n/e | 0.1647 |
| 11 | TNIE | 0.0039 | 0.0029 | n/e | 0.0046 | 0.0649 | 0.0756 | n/e | 0.0740 |
| 12 | TE | 0.0019 | n/e | n/e | n/e | 0.0595 | n/e | n/e | n/e |
| 12 | PNDE | 0.0026 | n/e | n/e | n/e | 0.0594 | n/e | n/e | n/e |
| 12 | TNIE | -0.0007 | n/e | n/e | n/e | 0.0202 | n/e | n/e | n/e |
| 13 | TE | 0.0055 | 0.0055 | 0.0055 | 0.0055 | 0.1906 | 0.1906 | 0.1906 | 0.1906 |
| 13 | PNDE | 0.0079 | 0.0079 | 0.0079 | 0.0079 | 0.1986 | 0.1986 | 0.1986 | 0.1986 |
| 13 | TNIE | -0.0024 | -0.0024 | -0.0024 | -0.0024 | 0.0565 | 0.0565 | 0.0565 | 0.0565 |
| 14 | TE | 0.0127 | 0.0127 | 0.0127 | 0.0127 | 0.2336 | 0.2336 | 0.2336 | 0.2336 |
| 14 | PNDE | 0.0128 | 0.0128 | 0.0128 | 0.0128 | 0.2038 | 0.2038 | 0.2038 | 0.2038 |
| 14 | TNIE | -0.0001 | -0.0001 | -0.0001 | -0.0001 | 0.1034 | 0.1034 | 0.1034 | 0.1034 |
| 15 | TE | -0.0070 | -0.0070 | -0.0070 | -0.0070 | 0.1258 | 0.1258 | 0.1258 | 0.1258 |
| 15 | PNDE | -0.0074 | -0.0074 | -0.0074 | -0.0074 | 0.1316 | 0.1316 | 0.1316 | 0.1316 |
| 15 | TNIE | 0.0004 | 0.0004 | 0.0004 | 0.0004 | 0.0332 | 0.0332 | 0.0332 | 0.0332 |
| 16 | TE | 0.0027 | 0.0027 | 0.0027 | 0.0027 | 0.1395 | 0.1395 | 0.1395 | 0.1395 |
| 16 | PNDE | 0.0068 | 0.0068 | 0.0068 | 0.0068 | 0.1295 | 0.1295 | 0.1295 | 0.1295 |
| 16 | TNIE | -0.0041 | -0.0041 | -0.0041 | -0.0041 | 0.0619 | 0.0619 | 0.0619 | 0.0619 |

- **Point estimates.** Wherever the tools compute the same estimator (cells 01–05, 07, 10, 13–16, and PNDE in 08, 09, 11), bias and RMSE are identical to four decimals. The only differences are the TNIE and TE of cells 08, 09 and 11, where `mediate()`'s simulated point estimate adds RMSE (for TNIE 0.072 vs 0.058, 0.056 vs 0.047, 0.076 vs 0.065) without adding bias.
- **Coverage.** Mintmed's coverage ranges from 0.922 (cell 07 PNDE and cell 14 TNIE) to 0.960, `mediate()`'s from 0.912 (cell 10 `TNIE_W0`, which Mintmed reports point-only) to 0.982, and lavaan's from 0.924 to 0.966, excluding structural zeros.
- **Width.** lavaan's percentile intervals are consistently about 2% wider than Mintmed's and `mediate()`'s (width ratio 0.97–0.98 in every lavaan cell-effect), with correspondingly slightly lower power in some cells; this stays well inside the width and power rules.

## Package defaults (descriptive)

`mediation` secondary is the package default quasi-Bayesian interval (1,000 simulations); `lavaan` secondary is the default delta-method (normal-theory) interval. They are not compared with Mintmed and carry no verdict. Point estimates of the lavaan secondary mode equal its primary mode; the quasi-Bayesian point is a simulation average.

| Cell | Effect | QB coverage | QB width | QB zero excl. | QB bias | Delta coverage | Delta width | Delta zero excl. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 01 | TE | 0.956 | 0.884 | 0.510 | 0.0007 | 0.950 | 0.867 | 0.526 |
| 01 | PNDE | 0.958 | 0.810 | 0.158 | -0.0009 | 0.954 | 0.798 | 0.178 |
| 01 | TNIE | 0.958 | 0.457 | 0.690 | 0.0015 | 0.952 | 0.445 | 0.618 |
| 02 | TE | 0.966 | 0.556 | 0.912 | 0.0030 | 0.962 | 0.552 | 0.910 |
| 02 | PNDE | 0.944 | 0.512 | 0.346 | -0.0016 | 0.944 | 0.510 | 0.352 |
| 02 | TNIE | 0.938 | 0.281 | 0.974 | 0.0046 | 0.930 | 0.279 | 0.972 |
| 03 | TE | 0.958 | 0.786 | 0.180 | -0.0026 | 0.956 | 0.768 | 0.188 |
| 03 | PNDE | 0.958 | 0.786 | 0.180 | -0.0026 | 0.956 | 0.768 | 0.188 |
| 03 | TNIE | 1.000 | 0.000 | 0.000 | 0.0000 | 1.000 | 0.000 | 0.000 |
| 04 | TE | 0.942 | 0.781 | 0.162 | -0.0075 | 0.942 | 0.775 | 0.156 |
| 04 | PNDE | 0.942 | 0.781 | 0.162 | -0.0075 | 0.942 | 0.775 | 0.156 |
| 04 | TNIE | 1.000 | 0.000 | 0.000 | 0.0000 | 1.000 | 0.000 | 0.000 |
| 05 | TE | 0.946 | 0.786 | 0.166 | -0.0097 | 0.948 | 0.777 | 0.162 |
| 05 | PNDE | 0.946 | 0.786 | 0.166 | -0.0097 | 0.948 | 0.777 | 0.162 |
| 05 | TNIE | 1.000 | 0.000 | 0.000 | 0.0000 | 1.000 | 0.000 | 0.000 |
| 07 | TE | n/e | n/e | n/e | n/e | 0.948 | 0.672 | 0.892 |
| 07 | PNDE | n/e | n/e | n/e | n/e | 0.934 | 0.575 | 0.308 |
| 07 | TNIE | n/e | n/e | n/e | n/e | 0.954 | 0.422 | 0.916 |
| 08 | TE | 0.950 | 0.842 | 0.316 | 0.0026 | n/e | n/e | n/e |
| 08 | PNDE | 0.938 | 0.789 | 0.196 | 0.0053 | n/e | n/e | n/e |
| 08 | TNIE | 0.976 | 0.298 | 0.238 | -0.0027 | n/e | n/e | n/e |
| 09 | TE | 0.960 | 0.532 | 0.640 | 0.0072 | n/e | n/e | n/e |
| 09 | PNDE | 0.956 | 0.514 | 0.362 | 0.0052 | n/e | n/e | n/e |
| 09 | TNIE | 0.986 | 0.227 | 0.526 | 0.0021 | n/e | n/e | n/e |
| 10 | TNIE_W0 | 0.928 | 0.347 | 0.174 | 0.0005 | 0.894 | 0.301 | 0.146 |
| 10 | TNIE_W1 | 0.946 | 0.620 | 0.714 | -0.0051 | 0.944 | 0.633 | 0.590 |
| 10 | TNIE_difference | 0.944 | 0.717 | 0.344 | -0.0056 | 0.934 | 0.684 | 0.310 |
| 11 | TE | 0.944 | 0.679 | 0.414 | -0.0099 | n/e | n/e | n/e |
| 11 | PNDE | 0.964 | 0.651 | 0.210 | -0.0118 | n/e | n/e | n/e |
| 11 | TNIE | 0.976 | 0.273 | 0.454 | 0.0019 | n/e | n/e | n/e |
| 13 | TE | 0.948 | 0.792 | 0.150 | 0.0055 | 0.944 | 0.775 | 0.156 |
| 13 | PNDE | 0.950 | 0.815 | 0.152 | 0.0079 | 0.950 | 0.800 | 0.150 |
| 13 | TNIE | 0.960 | 0.241 | 0.040 | -0.0024 | 0.988 | 0.215 | 0.012 |
| 14 | TE | 0.938 | 0.887 | 0.160 | 0.0125 | 0.934 | 0.867 | 0.180 |
| 14 | PNDE | 0.954 | 0.791 | 0.194 | 0.0127 | 0.950 | 0.777 | 0.208 |
| 14 | TNIE | 0.926 | 0.413 | 0.074 | -0.0002 | 0.948 | 0.395 | 0.052 |
| 15 | TE | 0.938 | 0.494 | 0.330 | -0.0068 | 0.940 | 0.492 | 0.336 |
| 15 | PNDE | 0.940 | 0.508 | 0.314 | -0.0072 | 0.948 | 0.508 | 0.306 |
| 15 | TNIE | 0.946 | 0.137 | 0.054 | 0.0004 | 0.978 | 0.130 | 0.022 |
| 16 | TE | 0.954 | 0.555 | 0.300 | 0.0025 | 0.958 | 0.552 | 0.302 |
| 16 | PNDE | 0.950 | 0.495 | 0.384 | 0.0065 | 0.946 | 0.494 | 0.380 |
| 16 | TNIE | 0.954 | 0.253 | 0.046 | -0.0041 | 0.966 | 0.248 | 0.034 |

- The quasi-Bayesian interval behaves like `mediate()`'s bootstrap, including over-coverage of the TNIE in cells 08, 09 and 11 (0.976, 0.986, 0.976).
- The delta-method interval is conservative for the null TNIE of cells 13–16 (coverage 0.948–0.988) and under-covers cell 10's `TNIE_W0` (0.894).

## Runtime

Per-dataset medians in seconds, on GitHub Actions `ubuntu-latest`. Comparator times are the row runtime (model fits plus every mode the tool runs: `mediation` = bootstrap + quasi-Bayesian, `lavaan` = bootstrap + delta method). Mintmed's times for cells 01–14 are from run 2 (different runners on a different day) and are shown for scale only.

| Cell | `mediation` | `lavaan` | `mediation_reseed` | Mintmed |
|---|---:|---:|---:|---:|
| 01 | 3.55 | 6.94 | 1.90 | 6.34 |
| 02 | 4.52 | 8.04 | 2.27 | 6.53 |
| 03 | 2.98 | 5.72 | 1.59 | 6.61 |
| 04 | 3.58 | 5.79 | 1.88 | 5.25 |
| 05 | 3.54 | 6.19 | 1.77 | 6.45 |
| 06 | n/e | n/e | n/e | 27.52 |
| 07 | n/e | 8.92 | n/e | 12.48 |
| 08 | 5.60 | n/e | 2.33 | 15.82 |
| 09 | 10.21 | n/e | 3.75 | 22.38 |
| 10 | 10.06 | 10.27 | 5.02 | 80.36 |
| 11 | 4.32 | n/e | 2.35 | 9.49 |
| 12 | n/e | n/e | n/e | 13.24 |
| 13 | 3.39 | 6.44 | 1.79 | 7.24 |
| 14 | 4.07 | 7.66 | 2.15 | 6.54 |
| 15 | 4.43 | 8.23 | 2.28 | 7.61 |
| 16 | 4.39 | 8.12 | 2.17 | 5.18 |

| Item | Forecast (charter) | Measured |
|---|---:|---:|
| `mediation`, both modes | 10.41 CPU-h | 8.73 CPU-h |
| `lavaan`, both modes | 13.22 CPU-h | 11.10 CPU-h |
| `mediation_reseed` | 4.95 CPU-h | 4.15 CPU-h |
| Mintmed, cells 15–16 | 1.61 CPU-h | 1.81 CPU-h |
| Compute (sum of row runtimes; Mintmed as shard runtime) | 30.18 CPU-h | 25.79 CPU-h |
| Total job time, both runs (74 shard jobs plus 4 plan / aggregate jobs, i.e. including checkout, installs and R setup) | 34.28 CPU-h (with 5% allowance and 120 s per shard) | **27.31 CPU-h** of the 36 CPU-h budget |
| Slowest shard | 0.93 h (`cell10_moderated_n150`) | 1.30 h (`cell10_moderated_n150`, block `1of4`), within the 4 h limit |

- The comparators' shard runtime was 86,794 s (24.11 CPU-h, benchmark log row 11) and Mintmed's 6,507 s (1.81 CPU-h, row 12). Job times come from the GitHub Actions API (91,459 s and 6,842 s).
- The slowest shard exceeded its forecast because runner speed varied: the median `mediation` row time in cell 10 was 9.3, 16.5, 5.2 and 10.5 s in its four blocks. The forecast used conservative proxies for the other cells, so the total stayed below it.

## Limitations

- **No multiplicity adjustment.** Verdicts are per cell-effect. With 68 decision checks, a few `tolerable` verdicts are expected by chance; the lavaan cell 07 PNDE verdict is within that expectation.
- **Zero floor for cell 07.** `mediate()` cannot estimate cell 07, so its decision check uses a zero floor, which is stricter than the measured floors elsewhere (0.8–8.6 pp). Its `tolerable` PNDE verdict (5.0 pp raw disagreement) should be read with that in mind; no lavaan rerun was made to measure a floor there.
- **Double Monte Carlo error in the floor for cells 08, 09 and 11.** The rerun redraws `mediate()`'s simulated point estimate, so these floors contain that error twice, which makes the decision check more lenient there. The TNIE excess still exceeded the limits.
- **Substantive verdicts.** Cells 08 and 11 TNIE are `substantive` against `mediate()`: Mintmed and `mediate()` reach materially different significance decisions there, with Mintmed rejecting more often and `mediate()` over-covering (see above). The explanation offered is plausible but was not tested directly.
- **Coverage over-coverage counts against Mintmed.** As frozen, the coverage-loss check uses the signed difference (comparator − Mintmed), so a comparator that over-covers can fail Mintmed on coverage while Mintmed is at nominal. This is how cells 08, 09 and 11 failed their negligible coverage check. It is recorded here, not corrected.
- **Coverage of the comparison.** Cells 06 and 12 are not estimable by either comparator, and cell 07 only by lavaan; Mintmed's results in those cells have no external reference. Cells 08, 09 and 11 have `mediate()` only.
- **Correct specification only.** All tools fit the true model. Stage 1 says nothing about robustness to misspecification, which is Task 18's scope.
- **Single seed.** One master seed (the run-2 seed) and 500 datasets per cell. Mintmed's cells 01–14 are run 2's rows, not a fresh run.

## Reproduction

```bash
python -m mintmed.experiments.comparator_benchmark_reporting \
    --raw results/generated/archive/github/36636602823/aggregated-benchmark/raw_metrics.csv \
    --config configs/mediation_validation_v3.yaml --output results/generated/comparator-stage1 \
    --mintmed-raw results/generated/archive/github/36349731184/aggregated-benchmark/raw_metrics.csv \
                  results/generated/archive/github/36636611981/aggregated-benchmark/raw_metrics.csv
```

The inputs are fingerprinted in [`benchmarks/manifest.sha256`](../../benchmarks/manifest.sha256). The Mintmed per-cell values and the Mintmed runtimes above were computed directly from the Mintmed raw rows (`metrics_json`), and the runtime job times from the GitHub Actions API for runs `36636602823` and `36636611981`.
