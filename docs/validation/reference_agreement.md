# Task 14 reference agreement

## Scope

This document records the narrow independent-package compatibility anchor for
Task 14. It is intentionally limited to one continuous, single-mediator,
no-interaction linear model. It is not evidence that all Statsmodels,
PROCESS-style, moderated, nonlinear, binary-outcome, or multiple-mediator
analyses are interchangeable with mintmed.

## Model and estimand

The same generated rows were supplied to both implementations:

```text
M = 0.5 A + 0.3 C + eM
Y = 0.2 A + 0.5 M + 0.3 C + eY
```

- Fixture: `cell01_linear_n100`
- Rows: 100
- Exposure: `A=0` reference, `A=1` comparison
- Covariate: `C`
- Mintmed outcome specification: `Y ~ A + M + C`
- Mintmed mediator specification: `M ~ A + C`
- Statsmodels formulas: `Y ~ A + M + C` and `M ~ A + C`
- Statsmodels method: `Mediation.fit(method="parametric", n_rep=2048)`
- Mintmed bootstrap: disabled for the point comparison
- Mintmed integration draw budget: exact Gaussian-linear path (`draw_budget=0`)
- Mintmed data seed: `20260924`
- Mintmed analysis/Statsmodels RNG seed: `20260925`
- Absolute comparison tolerance: `0.08`
- Mintmed identity tolerance: `1e-10`

The mapping is:

| Mintmed effect | Statsmodels value | Rationale |
|---|---|---|
| `TE` | `MediationResults.total_effect.mean()` | total exposure contrast |
| `PNDE` | `MediationResults.ADE_avg.mean()` | average direct effect under the declared no-interaction convention |
| `TNIE` | `MediationResults.ACME_avg.mean()` | average causal mediated effect |

## Environment and provenance

The initial diagnostic run used Python `3.12.14`; the package-supported
Python 3.11 interpreter was unavailable at that time because the repository
`.venv` launcher pointed to a missing base executable. That original result is
retained below as a diagnostic compatibility record. The supported-runtime
rerun is recorded in the next section.

| Component | Version/value |
|---|---|
| Python | `3.12.14` (diagnostic only) |
| mintmed | `0.1.0` |
| Statsmodels | `0.14.6` |
| NumPy | `2.5.1` |
| SciPy | `1.18.0` |
| pandas | `3.0.3` |
| Patsy | `1.0.3` |
| source Git commit | `134fbc295661bd9ec836353a56d123c4aa231c97` |
| frozen validation config hash | `2a86c29394f869921f17f6cafa1a89cfd1bf70b3a141f6129d8ecf45d5a4ea22` |
| Mintmed specification hash | `a2f642fb7b82b866c744cc3e4da7dd615043fc91644407e835b430b46f318a5b` |
| Mintmed analysis hash | `8cbfcf798585a5daf81222141b055881f3c0ad8912b8ff24705ffbee59e6b978` |

The Statsmodels call uses a saved/restored NumPy global RNG state and the
declared analysis seed. The comparison test is reproducible without changing
the package’s caller RNG state.

## Observed comparison

| Effect | Mintmed | Statsmodels | Difference |
|---|---:|---:|---:|
| `TE` | 0.6183397722 | 0.6291617146 | 0.0108219413 |
| `PNDE` | 0.2805976418 | 0.2879900885 | 0.0073924468 |
| `TNIE` | 0.3377421305 | 0.3411716260 | 0.0034294956 |

All three absolute differences are below the predeclared `0.08` anchor
tolerance. Mintmed also satisfies `TE = PNDE + TNIE` within `1e-10` without
using the independent package to define that identity.

## Reproduction

```powershell
$env:PYTHONPATH = 'src'
& 'C:\tmp\scova-v4-test\Scripts\python.exe' -m pytest tests/integration/test_reference_agreement.py::test_statsmodels_anchor_matches_mintmed_for_one_linear_model -q
```

The command above reproduces the historical diagnostic result in the Python
3.12 environment. The supported-runtime command is:

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/integration/test_reference_agreement.py::test_statsmodels_anchor_matches_mintmed_for_one_linear_model -q
```

The supported command and the full repository suite passed on 2026-09-25;
the original 3.12 provenance and observed values remain unchanged.

## Supported-runtime verification

On 2026-09-25, the focused reference/runtime acceptance suite passed under the
repository `.venv` with Python `3.11.9` (`43 passed`). The complete repository
suite also passed (`322 passed`). The supported environment reported:

| Component | Version/value |
|---|---|
| Python | `3.11.9` |
| mintmed | `0.1.0` |
| Statsmodels | `0.14.6` |
| NumPy | `2.4.6` |
| SciPy | `1.17.1` |
| pandas | `3.0.6` |
| Patsy | `1.0.3` |
| verification Git commit | `4155db619f43b5b7c186b290d6b772c4379e6a57` |

This clears the Python interpreter-availability blocker. It does not resolve
the two separate Task 14 runtime-pilot integration cases documented in
`docs/validation/runtime_pilot.md`.
