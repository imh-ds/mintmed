# Interval correction check: BC and BCa (not adopted)

After run 1 failed its coverage gate ([`baseline_run1_results.md`](baseline_run1_results.md)), the charter allowed one targeted correction. The candidate correction was to replace the percentile bootstrap interval with a bias-corrected (BC) or bias-corrected and accelerated (BCa) interval, which target the skewed indirect effects in cells 08 and 11.

This file records the check done before deciding. **Neither interval was adopted, and the one correction was not used.** Mintmed keeps the percentile interval.

## What was run

- **Cells:** the two under-covering cells, `cell11_binary_mediator_n150` and `cell08_quadratic_n100`, plus `cell01_linear_n100` as a well-behaved control.
- **Datasets:** all 200 datasets per cell from run 1, with the same data and analysis seeds and the frozen configuration. The percentile intervals reproduce run 1 exactly.
- **Intervals:** from the same 399 bootstrap replicates per dataset:
  - **Percentile:** the 2.5% and 97.5% quantiles (the current method).
  - **BC:** `z0 = Φ⁻¹(share of replicates below the estimate, ties counted half)`. Each endpoint's probability is `Φ(2·z0 + z_α)`.
  - **BCa:** as BC, with the acceleration `a` from a leave-one-out jackknife (one extra point fit per participant). Each endpoint's probability is `Φ(z0 + (z0 + z_α) / (1 − a(z0 + z_α)))`.
- **Where:** locally (Windows, Python 3.11.9, 16 worker processes), with `scripts/compare_bootstrap_intervals.py`. The row-level output is kept in git-ignored `results/generated/bc-bca-experiment/`.

Every dataset finished `complete` with 399 successful replicates.

## Results

Intervals containing the truth, out of 200 datasets. The coverage gate required at least 189.

| Cell | Effect | Percentile | BC | BCa | Truth above / below interval (percentile → BCa) | Mean width vs percentile (BC / BCa) |
|---|---|---:|---:|---:|---|---|
| `cell01_linear_n100` | TE | 191 | 190 | 190 | 7/2 → 8/2 | 1.00 / 1.00 |
| `cell01_linear_n100` | PNDE | 187 | 187 | 187 | 7/6 → 7/6 | 1.00 / 1.00 |
| `cell01_linear_n100` | TNIE | 186 | 186 | 186 | 8/6 → 7/7 | 1.02 / 1.01 |
| `cell08_quadratic_n100` | TE | 191 | 191 | 190 | 4/5 → 5/5 | 1.00 / 1.00 |
| `cell08_quadratic_n100` | PNDE | 190 | 188 | 187 | 2/8 → 4/9 | 1.00 / 1.00 |
| `cell08_quadratic_n100` | TNIE | 183 | 187 | 186 | 12/5 → 6/8 | 1.06 / 1.07 |
| `cell11_binary_mediator_n150` | TE | 189 | 189 | 189 | 8/3 → 8/3 | 1.00 / 1.00 |
| `cell11_binary_mediator_n150` | PNDE | 188 | 188 | 188 | 9/3 → 9/3 | 1.00 / 1.00 |
| `cell11_binary_mediator_n150` | TNIE | 179 | 182 | 184 | 15/6 → 9/7 | 1.03 / 1.02 |

**Runtime.** BC reuses the bootstrap replicates, so it costs nothing extra. BCa needs a jackknife: one extra point fit per participant, so 100–150 extra fits per dataset here. Locally, the median time per dataset including the jackknife was 14 s (cell 01), 30 s (cell 08) and 89 s (cell 11). Run 1's mean on GitHub Actions was 5.3 s, 14.7 s and 9.8 s. The machines differ, so these are only indicative.

## Findings

1. **The gains are small.** BC and BCa add 3–5 covered datasets on the two under-covering indirect effects. That is about the size of the Monte Carlo error of a count out of 200 (about ±3). Neither method reaches 189 on either effect.
2. **The misses become balanced, not fewer.** BCa turns cell 11's lopsided misses (truth above the interval 15 times, below 6) into balanced ones (9 and 7). That is the expected effect of a skewness correction, but total coverage barely moves.
3. **Small losses elsewhere.** Cell 08 PNDE drops from 190 to 188 (BC) or 187 (BCa).
4. **The control cell is unchanged, and it is below the gate too.** Cell 01 is a correctly specified linear model. It covers 186–191 of 200 under every method. So most of run 1's failure comes from the gate being unattainable at 200 datasets, not from the interval method.
5. **BCa is expensive.** In cell 11 it made each dataset several times slower.

## Decision

Neither BC nor BCa removes the root cause, so neither is adopted as the charter's one correction:
- Run 1 stands as the Task 15 result: **coverage gate failed**.
- The modest undercoverage of indirect-effect intervals when that effect's sampling distribution is skewed (cells 08 and 11) is documented as a known limitation in [`baseline_evidence.md`](baseline_evidence.md).
- A feasible, pre-set coverage rule is recorded for the **next** validation plan. It is not applied to run 1.

The decision and its rationale are recorded in the implementation decision log (entry "Task 15 — interval correction not adopted").
