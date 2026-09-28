# Null-gate fix check: candidate intervals for the mixed-null TNIE (not adopted)

Run 2 failed its null false zero-exclusion gate ([`coverage_revalidation_results.md`](coverage_revalidation_results.md)). In cell 14, where the A → M path is truly zero but estimated and M → Y is 0.5, the percentile interval for the TNIE excluded zero in 39 of 500 datasets (7.8%). The charter allows one targeted correction ([`coverage_revalidation_charter.md`](coverage_revalidation_charter.md#one-correction-rule)).

This file records the check done before deciding. **No candidate was adopted, the one correction was not used, and there is no rerun.** Mintmed keeps the percentile interval.

## What was run

- **Cells:**
  - `cell14_b_path_only_n100`, the failing cell;
  - `cell13_a_path_only_n100`, the other mixed-null cell;
  - `cell01_linear_n100`, a well-behaved control, to measure the cost in power;
  - `cell08_quadratic_n100` (fresh seed only), a non-null cell with a skewed TNIE and modest power.
- **Datasets:** 500 per cell, with the frozen v2 configuration (`configs/mediation_validation_v2.yaml`), for two master seeds:
  - **Run-2 seed `20260927`** (cells 01, 13, 14): the same datasets as run 2. The percentile intervals and estimates reproduce run 2 to within 3 × 10⁻¹⁵.
  - **Fresh seed `20260928`** (cells 01, 08, 13, 14): new datasets, to check how much of the cell-14 result is chance.
- **Intervals:** from the same 399 bootstrap replicates per dataset, where N is the sample size (100 here):
  - **Percentile** (`pct`): the 2.5% and 97.5% quantiles (the current method).
  - **Expanded percentile** (`exp`, Hesterberg 2015): percentile quantiles at tail probability `Φ(−√(N / (N − 1)) · t_{0.975, N−1})` instead of 0.025.
  - **t × bootstrap SD** (`tse`): `estimate ± t_{0.975, N−1} × SD(replicates)`.
  - **BC** (`bc`): the bias-corrected percentile interval, as in [`interval_correction_check.md`](interval_correction_check.md).
- **Where:** locally (Windows), with `scripts/compare_interval_fixes.py`, a diagnostic outside the package and gates. The row-level output is kept in git-ignored `results/generated/interval-fix-experiment/` (`run2_seed.csv`, `fresh_seed.csv`).

Every dataset had 399 successful replicates.

## Results

### False positives for the null TNIE

Intervals excluding zero, out of 500 datasets. The truth is 0. The run-2 gate requires the 95% Wilson upper bound of this rate to be at most 0.10, which with 500 datasets means at most 36 exclusions.

| Cell | Seed | Percentile | Expanded percentile | t × SD | BC |
|---|---|---:|---:|---:|---:|
| `cell14_b_path_only_n100` | run 2 (20260927) | 39 | 37 | 20 | 44 |
| `cell14_b_path_only_n100` | fresh (20260928) | 32 | 31 | 16 | 41 |
| `cell14_b_path_only_n100` | pooled, of 1,000 | 71 (7.1%) | 68 (6.8%) | 36 (3.6%) | 85 (8.5%) |
| `cell13_a_path_only_n100` | run 2 (20260927) | 22 | 20 | 4 | 40 |
| `cell13_a_path_only_n100` | fresh (20260928) | 21 | 20 | 4 | 40 |

- Pooled 95% Wilson intervals for cell 14: percentile 5.7–8.9%; expanded percentile 5.4–8.5%; t × SD 2.6–4.9%; BC 6.9–10.4%.
- Per seed, the Wilson upper bounds for cell 14's percentile interval are 0.105 (run-2 seed, fails the gate) and 0.089 (fresh seed, would pass). The expanded percentile interval's 37 on the run-2 seed would still fail (upper bound 0.1003).

### Coverage

Intervals containing the truth, out of 500. The run-2 coverage gate fails an effect at 458 or fewer.

| Cell | Seed | Effect | Percentile | Expanded percentile | t × SD | BC |
|---|---|---|---:|---:|---:|---:|
| `cell01_linear_n100` | run 2 | TE | 474 | 477 | 479 | 474 |
| `cell01_linear_n100` | run 2 | PNDE | 475 | 480 | 480 | 474 |
| `cell01_linear_n100` | run 2 | TNIE | 475 | 476 | 479 | 475 |
| `cell01_linear_n100` | fresh | TE | 469 | 471 | 472 | 465 |
| `cell01_linear_n100` | fresh | PNDE | 466 | 469 | 467 | 466 |
| `cell01_linear_n100` | fresh | TNIE | 462 | 466 | 461 | 467 |
| `cell08_quadratic_n100` | fresh | TE | 472 | 475 | 476 | 472 |
| `cell08_quadratic_n100` | fresh | PNDE | 472 | 474 | 474 | 470 |
| `cell08_quadratic_n100` | fresh | TNIE | 480 | 481 | 478 | 484 |
| `cell13_a_path_only_n100` | run 2 | TE | 472 | 475 | 474 | 474 |
| `cell13_a_path_only_n100` | run 2 | PNDE | 469 | 472 | 476 | 471 |
| `cell13_a_path_only_n100` | run 2 | TNIE | 478 | 480 | 496 | 460 |
| `cell13_a_path_only_n100` | fresh | TE | 476 | 479 | 477 | 475 |
| `cell13_a_path_only_n100` | fresh | PNDE | 466 | 467 | 475 | 468 |
| `cell13_a_path_only_n100` | fresh | TNIE | 479 | 480 | 496 | 460 |
| `cell14_b_path_only_n100` | run 2 | TE | 467 | 468 | 469 | 468 |
| `cell14_b_path_only_n100` | run 2 | PNDE | 469 | 470 | 476 | 470 |
| `cell14_b_path_only_n100` | run 2 | TNIE | 461 | 463 | 480 | **456** |
| `cell14_b_path_only_n100` | fresh | TE | 472 | 473 | 473 | 468 |
| `cell14_b_path_only_n100` | fresh | PNDE | 473 | 474 | 477 | 471 |
| `cell14_b_path_only_n100` | fresh | TNIE | 468 | 469 | 484 | 459 |

In cell 08 (fresh seed), the TNIE misses with truth above / below the interval were 17 / 3 (percentile), 17 / 2 (expanded percentile), 22 / 0 (t × SD) and 11 / 5 (BC).

### Power for non-null TNIEs

Intervals excluding zero, out of 500, where the true TNIE is not zero (0.25 in cell 01, 0.10 in cell 08).

| Cell | Seed | Percentile | Expanded percentile | t × SD | BC |
|---|---|---:|---:|---:|---:|
| `cell01_linear_n100` | run 2 | 345 (69.0%) | 341 (68.2%) | 285 (57.0%) | 371 (74.2%) |
| `cell01_linear_n100` | fresh | 341 (68.2%) | 338 (67.6%) | 280 (56.0%) | 362 (72.4%) |
| `cell08_quadratic_n100` | fresh | 227 (45.4%) | 222 (44.4%) | 88 (17.6%) | 305 (61.0%) |

### Widths

Mean interval width relative to the percentile interval, over every cell, seed and effect checked:
- **Expanded percentile:** 1.016–1.022, so about 2% wider throughout.
- **t × SD:** 0.997–1.028.
- **BC:** 0.999–1.059; the widest is cell 08's TNIE.

## Findings

1. **Part of the failure is chance, but not all of it.** The percentile interval gave 39 false positives with the run-2 seed and 32 with a fresh seed. The fresh seed alone would have passed the gate (Wilson upper 0.089). Pooled over 1,000 datasets, the rate is 7.1% (5.7–8.9%): above the nominal 5%, and probably below the gate's 10%.
2. **The expanded percentile interval changes almost nothing.** It is about 2% wider and removes 1–2 false positives per 500 datasets.
3. **t × bootstrap SD halves the false positives, but at a large cost in power.** In cell 14 it gave 20 and 16, and in cell 13 only 4 per seed (it over-covers there, 496 of 500). But TNIE power fell from 68–69% to 56–57% in cell 01, and from 227 to 88 of 500 in cell 08. In cell 08 all 22 of its TNIE misses were on one side.
4. **BC makes the null problem worse.** It raised false positives to 44 and 41 in cell 14 and to 40 per seed in cell 13. With the run-2 seed, cell 14 TNIE covered only 456 of 500, which would **fail** the coverage gate.
5. **No candidate is a targeted fix.** Each either leaves the false-positive rate about where it is, or trades it for a large loss of power in ordinary designs, or makes it worse.

## Decision

The owner chose **option 2** on 2026-09-27: no candidate is adopted as the charter's one correction.
- The one correction is not used, and there is no rerun.
- Run 2 stands as the Task 16 result: **FAILED** on the null false zero-exclusion gate.
- The limitation is documented in [`baseline_evidence.md`](baseline_evidence.md#known-limitations): in mixed-null designs where the A → M path is truly zero and M → Y is strong, at N = 100, the TNIE false-positive rate is about 6–8% rather than 5%.
- Possible later work, outside Task 16: check the rate at larger N, and research intervals designed for products of coefficients. Either would be a new feature with its own pre-registered validation.

The decision and its rationale are recorded in the implementation decision log (entry "Task 16 — outcome: null-gate limitation documented (option 2)").

## Note on the "no estimator tournament" rule

The charter's one-correction rule forbids an estimator tournament. Comparing four intervals offline sits uneasily with that rule. The comparison was used only to judge whether a targeted correction existed and what it would cost. Because none was adopted and nothing was rerun, the run-2 verdict was not chosen by that comparison and still stands as failed.
