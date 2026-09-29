# mintmed
Mediation with Information-aware Nonlinear Terms

Mintmed estimates natural direct and indirect effects (TE, PNDE, TNIE) for **observed-variable** mediation models. You declare every node model, and Mintmed evaluates the effects with a model-standardized g-formula, using participant-bootstrap intervals.

## Status: research beta

Mintmed was checked in two pre-registered simulation runs on 14 fixed designs ([evidence report](docs/validation/baseline_evidence.md)). **Neither run fully passed.**
- **Point estimates:** essentially unbiased in all 14 designs, in both runs.
- **Run 1** (12 designs, 200 datasets each): the coverage check **failed**. Average coverage was 94.8%, but the check as written was nearly impossible to pass at 200 datasets.
- **Run 2** (14 designs, 500 datasets each):
  - the coverage check **passed**: no effect under-covered, and average coverage was 94.9%;
  - the check for false indirect effects **failed**. When the exposure → mediator path is truly zero but included in the model, and the mediator → outcome path is strong, the indirect-effect interval excluded zero in 7.8% of datasets at N = 100 (about 6–8% across repeats) instead of 5%.
  - Run 1's apparent undercoverage of indirect effects with a quadratic outcome or a binary mediator did not replicate.
- **What the failed check means in practice:** it is a real but mild caveat, not a reason to avoid Mintmed.
  - It adds about 2 extra false positives per 100 analyses, and only in that one kind of design.
  - Estimates and interval coverage were unaffected.
  - Treat a borderline indirect effect with extra caution when the exposure → mediator path is itself weak. See [Known limitations](docs/validation/baseline_evidence.md#known-limitations).
- **Comparison with standard tools** (Task 17 Stage 1, [results](docs/validation/comparator_results.md)): on the same datasets and correctly specified models, the difference between Mintmed and R `mediation::mediate()` or lavaan was negligible in 68 of 72 pre-registered comparisons, tolerable in 2 and substantive in 2.
  - Both substantive differences and one tolerable one are in designs where `mediate()` simulates the mediator (a quadratic or spline outcome, a binary mediator). There Mintmed's indirect-effect intervals were narrower and near 95% coverage, while `mediate()`'s over-covered, so the two often reach different significance decisions.
  - The false-indirect-effect excess above also appears in `mediate()` and lavaan at N = 100, and in no tool at N = 250.
  - This is a parity check, not evidence that Mintmed is better, and it says nothing about misspecified models.
- **Other designs:** untested and not validated. This includes four mediators, continuous exposures or moderators, samples below 100, and any misspecified model.

Mintmed does not test causal identification assumptions. By default its effects are model-standardized contrasts, not causal effects.

## Quick start

Mintmed requires Python 3.11.

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install .
./.venv/Scripts/mintmed.exe --data examples/single/data.csv --spec examples/single/analysis.yaml --output results/single
```

See the [user guide](docs/user-guide.md) for specifications, reading the results, uncertainty, warnings and limitations.

## Development

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[test]"
./.venv/Scripts/python.exe -m pytest -q
```

## Validation documents

| Document | Contents |
|---|---|
| [`baseline_release_charter.md`](docs/validation/baseline_release_charter.md) | The run-1 validation design and gates, frozen before the run |
| [`baseline_run1_results.md`](docs/validation/baseline_run1_results.md) | The permanent record of run 1 (coverage gate failed) |
| [`interval_correction_check.md`](docs/validation/interval_correction_check.md) | The BC/BCa check after run 1, and why it was not adopted |
| [`coverage_revalidation_charter.md`](docs/validation/coverage_revalidation_charter.md) | The run-2 validation design and gates, frozen before the run |
| [`coverage_revalidation_results.md`](docs/validation/coverage_revalidation_results.md) | The permanent record of run 2 (null false-positive gate failed) |
| [`null_gate_fix_check.md`](docs/validation/null_gate_fix_check.md) | The candidate fixes after run 2, and why none was adopted |
| [`baseline_evidence.md`](docs/validation/baseline_evidence.md) | The evidence summary across both runs, supported designs and known limitations |
| [`comparator_charter.md`](docs/validation/comparator_charter.md) | The Task 17 Stage 1 comparison design and rules, frozen before the run |
| [`comparator_results.md`](docs/validation/comparator_results.md) | The permanent record of Task 17 Stage 1: Mintmed against `mediate()` and lavaan |
| [`benchmarks/benchmark_log.md`](benchmarks/benchmark_log.md) | The running log of every benchmark run, with archived summaries and artifact fingerprints |
