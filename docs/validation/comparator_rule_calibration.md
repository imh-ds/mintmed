# Task 17 Stage 1 comparison rules: feasibility calibration (T17-S5)

> **Pre-charter calibration on a separate seed. This is not evidence.** It
> uses master seed **20260929**, not the evaluation seed 20260927, and none of
> the evaluation datasets. Its only purpose is to let the Stage 1 charter
> (T17-S7) choose how each `stage1.comparison_rules` limit is judged before
> any evaluation data is seen. None of these numbers may be quoted as a
> comparison of Mintmed with R.

## Why

An earlier validation run failed because its gate could not be met even by a
correct method. The Stage 1 rules (owner confirmed 2026-09-28) are:

- primary: decision agreement ≥ 0.95; sign agreement when either method is
  significant ≥ 0.99;
- guardrails: bias excess ≤ 0.02 SD, coverage loss ≤ 2.5 pp, false-positive
  excess ≤ 2.0 pp (null cells), power loss ≤ 5 pp, width ratio ≤ 1.10;
- tolerable tier: decision agreement ≥ 0.90, coverage loss ≤ 5 pp, Mintmed
  coverage ≥ 0.90, false-positive excess ≤ 3 pp, power loss ≤ 10 pp, width
  ratio ≤ 1.25.

`comparator_benchmark_reporting.py` (T17-S3) judges agreement rates on the
Wilson lower bound and guardrail losses on the upper bound of a 2000-draw
paired percentile bootstrap. This calibration asks whether two methods that
genuinely agree pass those rules at n = 500, and whether a real difference
still fails.

## What was run

- `scripts/calibrate_comparator_rules.py --output <temp dir> --replicates 100 --workers 12`
  run locally on 2026-09-28. It writes a temporary copy of
  `configs/mediation_validation_v3.yaml` into the output directory:
  - master seed 20260929;
  - 100 replicates;
  - cells 01 (linear), 08 (quadratic) and 14 (mixed null, b path only);
  - stress disabled.

  The config hash is `70a51e3b5372af86…`. Nothing under `configs/` changed.
- Mintmed: `mediation_validation` with 399 percentile bootstrap refits.
- Comparators: `comparator_benchmark`, both modes, frozen settings. That
  means 399 bootstrap refits and 1000 quasi-Bayesian simulations for
  `mediate()`, and 399 refits for lavaan. lavaan does not support cell 08.
- Software: Windows 11, Python venv, R 4.6.0, mediation 4.5.1, lavaan 0.6-21.
- The paired comparisons use the T17-S3 code unchanged (`paired_comparison`,
  `classify_tier`). The script adds a bootstrap lower bound for the agreement
  rates, n = 500 extrapolations, discordance rates and analytic pass
  probabilities. It writes them to `calibration.json` in the output directory.
  Rerun the analysis with `--analyze-only`.

**Identical by construction.**
- In cells 01 and 14, lavaan and `mediate()` give the same point estimate as
  Mintmed (max |Δ| ≤ 4e-15). Only the bootstrap resamples differ.
- The same holds for `mediate()`'s PNDE in cell 08.

These 13 cell-effects, with 1300 dataset pairs, measure what **genuine
agreement** looks like.

**Not identical.** `mediate()`'s TNIE and TE in cell 08 carry Monte Carlo point error (up to 0.14 here).
That error also widens its intervals, so these two cell-effects show a real
difference.

## Results at n = 100, with n = 500 extrapolations

Column notes:
- **Wilson lower @500** keeps the observed rate and uses n = 500.
- **Boot lower @500** shrinks the n = 100 bootstrap half-width by √(100/500).
- **Paired-bootstrap lower bound of a rate** is degenerate (1.000) whenever
  agreement is perfect, so it gives no bound for sign agreement. It is
  omitted there.

| Tool | Cell | Effect | Identical points | Decision agr. | Wilson lower | Boot lower | Wilson lower @500 | Boot lower @500 | Sig. pairs | Sign agr. | Wilson lower | Wilson lower @500 (pairs) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lavaan | 01 | PNDE | yes | 0.91 | 0.838 | 0.850 | 0.882 | 0.883 | 25 | 1.00 | 0.867 | 0.970 (125) |
| lavaan | 01 | TE | yes | 0.96 | 0.902 | 0.920 | 0.939 | 0.942 | 50 | 1.00 | 0.929 | 0.985 (250) |
| lavaan | 01 | TNIE | yes | 0.93 | 0.863 | 0.880 | 0.904 | 0.908 | 67 | 1.00 | 0.946 | 0.989 (335) |
| lavaan | 14 | PNDE | yes | 0.97 | 0.915 | 0.940 | 0.951 | 0.957 | 23 | 1.00 | 0.857 | 0.968 (115) |
| lavaan | 14 | TE | yes | 0.93 | 0.863 | 0.880 | 0.904 | 0.908 | 25 | 1.00 | 0.867 | 0.970 (125) |
| lavaan | 14 | TNIE (null) | yes | 0.96 | 0.902 | 0.920 | 0.939 | 0.942 | 8 | 1.00 | 0.676 | 0.912 (40) |
| mediation | 01 | PNDE | yes | 0.92 | 0.850 | 0.860 | 0.893 | 0.893 | 25 | 1.00 | 0.867 | 0.970 (125) |
| mediation | 01 | TE | yes | 0.94 | 0.875 | 0.890 | 0.916 | 0.918 | 53 | 1.00 | 0.932 | 0.986 (265) |
| mediation | 01 | TNIE | yes | 0.94 | 0.875 | 0.890 | 0.916 | 0.918 | 66 | 1.00 | 0.945 | 0.988 (330) |
| mediation | 08 | PNDE | yes | 0.98 | 0.930 | 0.950 | 0.964 | 0.967 | 14 | 1.00 | 0.785 | 0.948 (70) |
| mediation | 08 | TE | no (0.14) | 0.97 | 0.915 | 0.930 | 0.951 | 0.952 | 27 | 1.00 | 0.875 | 0.972 (135) |
| mediation | 08 | TNIE | no (0.14) | 0.84 | 0.756 | 0.760 | 0.805 | 0.804 | 46 | 1.00 | 0.923 | 0.984 (230) |
| mediation | 14 | PNDE | yes | 0.98 | 0.930 | 0.950 | 0.964 | 0.967 | 23 | 1.00 | 0.857 | 0.968 (115) |
| mediation | 14 | TE | yes | 0.95 | 0.888 | 0.910 | 0.927 | 0.932 | 25 | 1.00 | 0.867 | 0.970 (125) |
| mediation | 14 | TNIE (null) | yes | 0.96 | 0.902 | 0.920 | 0.939 | 0.942 | 9 | 1.00 | 0.701 | 0.921 (45) |

Each guardrail cell reads point / paired-bootstrap upper bound / upper bound
@500. The @500 value keeps the n = 100 point estimate and shrinks the
half-width by √(100/500). That is pessimistic, because the n = 100 point is
itself noisy: for example, a 6 pp power loss for identical point estimates.
The analytic section below gives the realistic n = 500 behaviour.

| Tool | Cell | Effect | Bias excess (SD) | Coverage loss (pp) | Power loss (pp) | FP excess (pp) | Width ratio | Coverage (Mintmed / comparator) |
|---|---|---|---|---|---|---|---|---|
| lavaan | 01 | PNDE | 0 / 0 / 0 | 1.0 / 5.0 / 2.8 | -1.0 / 5.0 / 1.7 | n/a | 0.988 / 1.002 / 0.994 | 0.93 / 0.94 |
| lavaan | 01 | TE | 0 / 0 / 0 | 1.0 / 3.0 / 1.9 | 2.0 / 6.0 / 3.8 | n/a | 0.982 / 0.996 / 0.989 | 0.96 / 0.97 |
| lavaan | 01 | TNIE | 0 / 0 / 0 | -1.0 / 3.0 / 0.8 | 1.0 / 6.0 / 3.2 | n/a | 0.980 / 0.995 / 0.987 | 0.94 / 0.93 |
| lavaan | 14 | PNDE | 0 / 0 / 0 | 0.0 / 3.0 / 1.3 | 1.0 / 4.0 / 2.3 | n/a | 0.993 / 1.007 / 0.999 | 0.91 / 0.91 |
| lavaan | 14 | TE | 0 / 0 / 0 | 1.0 / 5.0 / 2.8 | -1.0 / 4.0 / 1.2 | n/a | 0.985 / 0.998 / 0.990 | 0.91 / 0.92 |
| lavaan | 14 | TNIE (null) | 0 / 0 / 0 | 2.0 / 6.0 / 3.8 | n/a | 2.0 / 6.0 / 3.8 | 0.973 / 0.985 / 0.978 | 0.93 / 0.95 |
| mediation | 01 | PNDE | 0 / 0 / 0 | 0.0 / 3.0 / 1.3 | 0.0 / 5.0 / 2.2 | n/a | 1.011 / 1.025 / 1.017 | 0.93 / 0.93 |
| mediation | 01 | TE | 0 / 0 / 0 | 1.0 / 3.0 / 1.9 | 6.0 / 11.0 / 8.2 | n/a | 1.009 / 1.023 / 1.015 | 0.96 / 0.97 |
| mediation | 01 | TNIE | 0 / 0 / 0 | -1.0 / 3.0 / 0.8 | 0.0 / 5.0 / 2.2 | n/a | 1.003 / 1.018 / 1.010 | 0.94 / 0.93 |
| mediation | 08 | PNDE | 0 / 0 / 0 | 1.0 / 3.0 / 1.9 | 2.0 / 5.0 / 3.3 | n/a | 0.988 / 1.001 / 0.994 | 0.94 / 0.95 |
| mediation | 08 | TE | 0.0029 / 0.0092 / 0.0057 | 3.0 / 7.0 / 4.8 | -3.0 / 0.0 / -1.7 | n/a | 0.976 / 0.988 / 0.981 | 0.94 / 0.97 |
| mediation | 08 | TNIE | -0.0029 / 0.0036 / 0 | 6.0 / 11.0 / 8.2 | -16.0 / -9.0 / -12.9 | n/a | 0.833 / 0.853 / 0.842 | 0.87 / 0.93 |
| mediation | 14 | PNDE | 0 / 0 / 0 | 4.0 / 8.0 / 5.8 | 2.0 / 5.0 / 3.3 | n/a | 1.008 / 1.022 / 1.014 | 0.91 / 0.95 |
| mediation | 14 | TE | 0 / 0 / 0 | 3.0 / 7.0 / 4.8 | 1.0 / 5.0 / 2.8 | n/a | 1.006 / 1.018 / 1.011 | 0.91 / 0.94 |
| mediation | 14 | TNIE (null) | 0 / 0 / 0 | 0.0 / 4.0 / 1.8 | n/a | 0.0 / 4.0 / 1.8 | 0.995 / 1.009 / 1.001 | 0.93 / 0.93 |

With the T17-S3 judging, **every** cell-effect is `substantive`, including
the 13 that are identical by construction. With agreement judged on the
observed rate (`tier_primary_on_point`), 7 of those 13 are `tolerable` and 6
are `substantive`.

## The noise floor of genuine agreement

These rates are pooled over the 13 identical-point cell-effects (1300 pairs):

| Quantity | Value |
|---|---:|
| Decision disagreement rate: one method excludes zero, the other does not | 0.0515 (67 / 1300) |
| Implied decision-agreement floor | **0.948** (Wilson 95% CI 0.935–0.959) |
| Observed range across the 13 cell-effects at n = 100 | 0.91–0.98 (consistent with one common rate: counts 2–9 of 100) |
| Pairs significant in opposite directions | **0 / 1300** |
| Sign disagreements among pairs where either method is significant | 0 / 413 |
| Coverage discordance rate (one interval covers, the other does not) | 0.031 |
| Zero-exclusion discordance rate: all effects / null TNIE only | 0.052 / 0.040 |

**Why the floor is so low.** Two independent 399-refit percentile bootstraps
of the same estimator disagree on whether an interval excludes zero whenever the
endpoint lies within their Monte Carlo jitter of zero. About 5% of datasets
fall there. That comes from the bootstrap Monte Carlo error of the 2.5% and
97.5% quantiles, not from any difference between the methods.

**The consequence.** The owner's negligible limit for decision agreement
(0.95) sits on top of the noise floor. The tolerable limit (0.90) is only
about 5 pp below it.

## Analytic feasibility at n = 500

Wilson intervals use z = 1.96, as in the reporting code.

**Minimum observed agreement for the Wilson lower bound to clear a limit at n = 500:**

| Limit | Successes needed | Observed rate needed |
|---:|---:|---:|
| 0.95 | 485 / 500 | 0.970 |
| 0.90 | 464 / 500 | 0.928 |
| 0.85 | 441 / 500 | 0.882 |
| 0.99 | 500 / 500 | 1.000 (not reachable with even one disagreement) |

**Significant pairs needed for the sign-agreement Wilson lower bound to clear
a limit:**

| Limit | With perfect agreement | With 1 disagreement | With 2 disagreements |
|---:|---:|---:|---:|
| 0.99 | 381 | 563 | 726 |
| 0.95 | 73 | 110 | 142 |
| 0.90 | 35 | n/c | n/c |

`n/c`: not computed.

**How many significant pairs a cell will have at n = 500.** Five times the n = 100 counts gives:

- 40–45 in the null TNIE;
- 115–135 for PNDE and TE;
- about 330 for the linear TNIE.

**So a 0.99 Wilson lower bound is unreachable in every calibrated cell.** It
fails even with perfect sign agreement. A 0.95 Wilson lower bound is reachable
only with at least 73 significant pairs.

**Decision agreement: pass probability at n = 500** (exact binomial):

| Judged as | True agreement 0.948 (floor) | 0.936 | 0.93 | 0.92 | 0.90 | 0.88 | 0.85 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Wilson lower ≥ 0.95 (T17-S3) | 0.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Observed ≥ 0.95 | 0.47 | 0.12 | 0.04 | 0.01 | 0.00 | 0.00 | 0.00 |
| Wilson lower ≥ 0.90 | 0.98 | 0.80 | 0.61 | 0.29 | 0.02 | 0.00 | 0.00 |
| Observed ≥ 0.90 | 1.00 | 1.00 | 0.99 | 0.96 | 0.54 | 0.09 | 0.00 |
| Wilson lower ≥ 0.85 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 0.48 | 0.02 |
| Observed ≥ 0.85 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | 0.53 |

**Guardrails: pass probability at n = 500 for a single cell-effect.**

- **Model.** A paired difference of two binary indicators with discordance
  rate d has SE ≈ √(d / 500). The bootstrap upper bound is ≈ point + 1.96 SE.
  Probabilities use a normal approximation.
- **Inputs.**
  - Coverage: d = 0.031, so SE = 0.78 pp.
  - Power: d = 0.052, so SE = 1.02 pp.
  - False positives: d = 0.040 (null TNIE only, 200 pairs, so imprecise),
    so SE = 0.89 pp.

| Guardrail (limit) | Judged on | Pass if true loss = 0 | Pass if true loss = limit | Pass if true loss = tolerable limit |
|---|---|---:|---:|---:|
| Coverage loss (2.5 pp) | upper bound (T17-S3) | 0.89 | 0.03 | 0.00 (5 pp) |
| Coverage loss (2.5 pp) | point | 1.00 | 0.50 | 0.00 (5 pp) |
| FP excess (2.0 pp) | upper bound (T17-S3) | **0.61** | 0.03 | 0.00 (3 pp) |
| FP excess (2.0 pp) | point | 0.99 | 0.50 | 0.13 (3 pp) |
| FP excess, tolerable (3.0 pp) | upper bound | 0.92 | — | 0.03 |
| Power loss (5 pp) | upper bound (T17-S3) | 1.00 | 0.03 | 0.00 (10 pp) |
| Width ratio (1.10) | upper bound (T17-S3) | ≈ 1: genuine ratios 0.97–1.01, upper − point ≈ 0.006 at n = 500 | | |
| Bias excess (0.02 SD) | upper bound (T17-S3) | ≈ 1: exactly 0 for identical points; ≤ 0.009 at n = 100 even with `mediate()`'s cell-08 Monte Carlo noise | | |

**Multiplicity.** The applicable checks are summed over about 40 cell-effects
per comparator. A per-check false-fail rate of 11% (coverage) or 39% (false
positives) therefore guarantees spurious non-negligible tiers.

## Recommendation for the Stage 1 charter (T17-S7)

These numbers apply only if the owner re-decides the limits. Changing any
limit, or what a limit is judged on, is an owner decision for the charter.

1. **Replace "decision agreement ≥ 0.95" as a pass/fail rule.** It is at the
   noise floor of two identical methods (0.948). It fails a genuinely
   agreeing pair with probability 0.99 on the Wilson lower bound and 0.53 on
   the observed rate. Recommended, in order of preference:
   - **(a) Measure the floor and judge the excess.**
     - Run `mediate()`'s primary mode a second time on the same datasets
       with a fixed seed offset. That is about 6 CPU-hours (the T17-S4 forecast for the primary mode) for 500 datasets
       × 13 cells. The two runs' disagreement is the per-cell bootstrap
       noise floor, which also applies to lavaan in the linear cells.
     - Judge the *excess* disagreement, disagreement(Mintmed, comparator) −
       disagreement(comparator, comparator rerun), on the upper bound of its
       paired bootstrap interval: ≤ 5 pp for negligible (the owner's 0.95
       read as "5 pp beyond noise") and ≤ 10 pp for tolerable.
     - A normal approximation gives SE ≲ 1.4 pp. A genuinely agreeing pair
       should then pass about 94% of the time, and a real 5 pp excess should
       fail about 97.5% of the time.
     - Caveat: this rule was not run in this calibration. The rerun should
       be validated in the GitHub pilot first.
   - **(b) If no rerun is wanted, use an absolute limit set below the floor.**
     - Judge on the observed rate: ≥ 0.90 for negligible and ≥ 0.85 for
       tolerable. A genuinely agreeing pair passes with probability ≥ 0.99,
       even if its cell's floor is as low as 0.93.
     - A true agreement of 0.88 fails 91% of the time; 0.85 fails always.
     - A true agreement of exactly 0.90 passes about half the time. That is
       unavoidable at n = 500 when the limit lies within about 3 pp of the
       floor.
     - Judging on the Wilson lower bound ≥ 0.90 instead is proper
       non-inferiority. But it fails a genuine pair 20–40% of the time if the
       cell's floor is 0.93–0.936.
   - In either case, **add "no pair significant in opposite directions"**
     (observed count ≤ 1% of pairs) as the directional primary check. This is
     what the plan says decision agreement is for, and it was 0 of 1300 here.
     One-sided disagreements that are asymmetric are already caught by the
     power-loss and false-positive guardrails.
2. **Sign agreement ≥ 0.99: judge on the observed rate, not the Wilson lower bound.**
   - The Wilson lower bound needs at least 381 significant pairs with zero
     disagreements. No calibrated cell reaches that at n = 500. The null TNIE
     has about 40 significant pairs and PNDE/TE about 125.
   - The paired-bootstrap lower bound is degenerate (1.0) at perfect
     agreement.
   - On the observed rate, a genuinely agreeing pair passes (0 of 413 sign
     disagreements here).
   - Report the number of significant pairs next to the rate. Below about 100
     pairs, one disagreement already moves the rate by more than 1 pp, so the
     count ("at most one opposite-sign point among significant pairs") is
     easier to read.
3. **Coverage loss (2.5 / 5 pp):**
   - For negligible, judge the point on ≤ 2.5 pp and the upper bound on ≤ 5 pp.
     - A genuinely agreeing pair passes with probability 0.999.
     - A true 5 pp loss fails with probability 0.999.
   - The T17-S3 upper-bound-only rule fails an agreeing pair 11% of the time
     per cell-effect.
   - For tolerable, keep the upper bound on ≤ 5 pp and Mintmed's coverage
     ≥ 0.90.
4. **False-positive excess (2.0 / 3.0 pp, null cells):** judge on the point
   and report the upper bound.
   - n = 500 cannot resolve 2 pp: SE ≈ 0.9 pp, and 2 pp is 2.2 SE.
   - The upper-bound rule fails a genuinely agreeing pair 39% of the time.
   - Point ≤ 2.0 pp passes an agreeing pair with probability 0.99. It fails a
     true 3 pp excess with probability 0.87, and a true 4 pp excess with
     probability 0.99.
   - The mixed-null question (cells 13–16) should also be answered
     descriptively. Compare each method's false-positive rate with its Wilson
     interval, not only the paired excess.
5. **Power loss (5 pp), width ratio (1.10) and bias excess (0.02 SD): keep the upper-bound judgment.**
   - They are feasible: a genuinely agreeing pair passes with probability
     ≥ 0.998.
   - A loss at the limit fails with probability 0.975.
6. **Example of a real difference.** `mediate()` in cell 08 (TNIE):
   - Its Monte Carlo point noise widens its intervals (width ratio 0.83).
     It covers 0.93 against Mintmed's 0.87 over these 100 datasets.
   - Decision agreement is 0.84.
   - Under recommendation 1(b) and 3, it would be flagged
     (0.84 < 0.85; coverage loss point 6 pp > 5 pp).
   - This is 100 datasets on a calibration seed. Whether Mintmed undercovers
     in cell 08 is a question for the evaluation data, not this document.

## Timing per dataset

**Uncontended** (serial, one process at a time, `OMP_NUM_THREADS=2`, 5
calibration datasets per cell). These are the numbers to use:

| Cell | Mintmed (399 refits) | mediate primary (399) | mediate QB (1000) | lavaan primary (399) | lavaan delta |
|---|---:|---:|---:|---:|---:|
| 01 linear N=100 | 5.2 | 1.5–2.0 | 1.3–1.6 | 6.7–6.9 | 0.03–0.05 |
| 08 quadratic N=100 | 11.5–11.9 | 1.7–2.0 | 2.3–2.6 | n/e | n/e |
| 14 mixed null N=100 | 5.3–5.4 | 1.6–2.0 | 1.3–1.6 | 7.0–7.2 | 0.03–0.05 |

Seconds per dataset, per mode. Mintmed's time is the whole analysis.

**Contended** (the 100-dataset calibration run itself). It ran 12 jobs at once on 20 logical cores, and the
harness tests ran alongside it for the first ~20 minutes. Median seconds per
dataset:

| Cell | Mintmed | mediate primary | mediate QB | lavaan primary | lavaan delta |
|---|---:|---:|---:|---:|---:|
| 01 | 43.9 | 12.7 | 12.5 | 62.1 | 0.32 |
| 08 | 21.9 | 13.5 | 20.8 | n/e | n/e |
| 14 | 9.7 | 3.2 | 2.9 | 13.6 | 0.07 |

**Reading the contended timings.** They are 2–9 times the uncontended ones and
are not a forecast. They show that shards sharing a runner inflate
wall-clock time heavily. The charter's forecast should come from a GitHub
pilot (T17-S7).
