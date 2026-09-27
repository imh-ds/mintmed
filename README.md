# mintmed
Mediation with Information-aware Nonlinear Terms

Mintmed estimates natural direct and indirect effects (TE, PNDE, TNIE) for **observed-variable** mediation models. You declare every node model, and Mintmed evaluates the effects with a model-standardized g-formula, using participant-bootstrap intervals.

## Status: research beta

Mintmed was checked on 12 fixed simulation designs ([evidence report](docs/validation/baseline_evidence.md)):
- **Point estimates:** essentially unbiased in all 12 designs.
- **Intervals:** the pre-registered coverage check **failed**.
  - Average coverage was 94.8%.
  - Indirect-effect intervals under-covered with a quadratic outcome (91.5%) and a binary mediator (89.5%).
  - Treat TNIE intervals in similar designs as somewhat too narrow.
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
| [`baseline_release_charter.md`](docs/validation/baseline_release_charter.md) | The validation design and gates, frozen before the run |
| [`baseline_run1_results.md`](docs/validation/baseline_run1_results.md) | The permanent record of the run (coverage gate failed) |
| [`interval_correction_check.md`](docs/validation/interval_correction_check.md) | The BC/BCa check, and why it was not adopted |
| [`baseline_evidence.md`](docs/validation/baseline_evidence.md) | The evidence summary and supported designs |
