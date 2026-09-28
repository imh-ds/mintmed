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
