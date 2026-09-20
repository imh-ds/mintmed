# Mintmed Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-beta Python package for observed-variable nonlinear mediation with declared Gaussian/Bernoulli node models, shared mediator simulation, model-standardized natural-effect contrasts, participant-bootstrap uncertainty, diagnostics, CLI output, and bounded validation evidence.

**Architecture:** A validated `ModelSpec` compiles into an immutable `AnalysisPlan`. Each mediator and the outcome is fit through one conditional-node interface; a single sequential g-formula engine then evaluates every regime, effect, moderator contrast, and bootstrap replicate. Reporting and validation consume structured result objects rather than recomputing statistics.

**Tech Stack:** Python 3.11, NumPy, SciPy, pandas, PyYAML, Patsy, Statsmodels, matplotlib, pytest; setuptools `src/` layout; GitHub Actions for sharded validation.

**Spec:** `outline/01_final_methodology_outline.md`; source roadmap: `outline/02_final_implementation_roadmap.md`; evidence audit: `outline/03_review_and_smoke_test_assessment.md`.

## Global Constraints

- Support Python `>=3.11,<3.12`; Python 3.14 may run the standalone feasibility artifact but is not a supported package runtime until the release matrix is repeated there.
- Support exactly one exposure contrast, one outcome, one to four observed mediators, independent participant rows, and Gaussian or Bernoulli endogenous nodes in the baseline.
- Compile templates and explicit specifications into the same immutable `ModelSpec`/`AnalysisPlan` representation.
- Permit only declared linear, quadratic, centered three-degree-of-freedom natural-spline terms, plus explicit pairwise interactions whose main effects are present.
- Fit OLS and logistic GLM with Statsmodels and design matrices with Patsy; do not implement custom IRLS or automatic smooth selection.
- Refit preprocessing, spline transforms, and node models inside every participant-bootstrap replicate while keeping category meaning and the selected integration-draw budget fixed.
- Define `TE`, `PNDE`, and `TNIE` using `mu(a,b)` and the convention `TE=mu(a1,a1)-mu(a0,a0)`, `PNDE=mu(a1,a0)-mu(a0,a0)`, `TNIE=mu(a1,a1)-mu(a1,a0)`.
- Report binary-outcome effects as probability differences and continuous-outcome effects in original outcome units.
- Use common numerical draws across regime contrasts and paired participant resamples for moderator contrasts.
- Never report default proportion mediated, clipped effects, significance labels, automatic term selection, information-theoretic causal effects, or silently reduced models.
- Treat optional information summaries, rho sensitivity, interventional mediator-specific decomposition, and automatic penalized smooths as post-baseline work.
- Preserve deterministic replicate identity across local, sharded, and combined validation runs; shard count and output path must not change scientific random streams.
- Keep the frozen inferential matrix within the 12 aggregate CPU-hour ceiling, including the one permitted targeted correction and rerun.
- Do not force-add the ignored `outline/` directory or modify `C:/Users/imhoh/GitHub/mintnet`.

## Review Focus

- A bootstrap resample loses one Bernoulli level: record a failed refit without changing coding, then apply the declared interval-withholding rule.
- Counterfactual exposure or moderator replacement participates in quadratic, spline, and interaction columns: rebuild through frozen Patsy `DesignInfo`, never by overwriting one matrix column.
- Tied continuous scale scores remain valid while nonfinite data and unsupported ordinal/count families fail with specific statuses.
- A declared exposure/moderator value lies outside observed support: return an unsupported-extrapolation status rather than a normal estimate.
- Parallel mediators enter a nonlinear-link or cross-mediator interaction outcome: retain the joint TNIE and mark individual contributions unavailable with a reason.

---

## Locked File Map

| File | Single responsibility |
|---|---|
| `src/mintmed/types.py` | Shared enums, statuses, warnings, hashes, effect/result dataclasses. |
| `src/mintmed/spec.py` | YAML-safe specification objects, parsing, validation, and template compilation. |
| `src/mintmed/design.py` | Patsy formula construction, fit-time `DesignInfo`, and frozen counterfactual transforms. |
| `src/mintmed/models.py` | Gaussian/Bernoulli fitted-node interface and Statsmodels implementations. |
| `src/mintmed/gformula.py` | Mediator-system fitting, common draws, sequential simulation, and `mu(a,b)`. |
| `src/mintmed/effects.py` | Named natural-effect contrasts, admissible parallel contributions, moderator contrasts. |
| `src/mintmed/uncertainty.py` | Full-refit participant bootstrap, deterministic seeds, failure accounting, intervals. |
| `src/mintmed/diagnostics.py` | Rank, event, support, residual, complexity, and failure summaries. |
| `src/mintmed/report.py` | JSON, CSV, Markdown, and curve exports from one result object. |
| `src/mintmed/api.py` | `estimate_plan` and `analyze_mediation` orchestration. |
| `src/mintmed/cli.py` | CSV/YAML command-line boundary only. |
| `src/mintmed/simulation/mediation.py` | Structural-equation fixtures and analytic truths. |
| `src/mintmed/experiments/mediation_validation.py` | Frozen matrix execution and shard contract. |
| `src/mintmed/experiments/mediation_validation_reporting.py` | Matrix summaries, gates, Monte Carlo uncertainty, evidence report. |
| `tests/mediation/` | Contract, oracle, failure, API, CLI, and reporting tests. |
| `tests/integration/` | End-to-end examples, comparator agreement, sharding, and determinism tests. |
| `examples/` | Three complete CSV/YAML analyses and commands. |
| `configs/` | Smoke and frozen validation configurations. |

## Core Interfaces

Implement these names and signatures exactly so tasks can be reviewed independently:

- `src/mintmed/spec.py`: `load_model_spec(path: Path) -> ModelSpec`, `compile_template(template: TemplateSpec) -> ModelSpec`, and `estimate_plan(data: pd.DataFrame, spec: ModelSpec) -> AnalysisPlan`.
- `src/mintmed/design.py`: `fit_design(data: pd.DataFrame, node: CompiledNodePlan) -> FrozenDesign` and `transform_design(design: FrozenDesign, data: pd.DataFrame) -> pd.DataFrame`.
- `src/mintmed/models.py`: `fit_node(data: pd.DataFrame, node: CompiledNodePlan) -> FittedNode`.
- `src/mintmed/gformula.py`: `fit_system(data: pd.DataFrame, plan: AnalysisPlan) -> FittedSystem`, `standardize_regime(data: pd.DataFrame, plan: AnalysisPlan, fitted: FittedSystem, *, outcome_exposure: object, mediator_exposure: object, moderator_values: Mapping[str, object], draws: CommonDraws) -> float`, and `compute_regime_means(data: pd.DataFrame, plan: AnalysisPlan, fitted: FittedSystem) -> RegimeMeans`.
- `src/mintmed/effects.py`: `natural_effects(means: RegimeMeans) -> tuple[EffectEstimate, EffectEstimate, EffectEstimate]` and `parallel_contributions(data: pd.DataFrame, plan: AnalysisPlan, fitted: FittedSystem, draws: CommonDraws, joint_tnie: float) -> ContributionResult`.
- `src/mintmed/uncertainty.py`: `bootstrap_analysis(data: pd.DataFrame, plan: AnalysisPlan, point: PointAnalysis) -> BootstrapResult`.
- `src/mintmed/api.py`: `analyze_mediation(data: pd.DataFrame, spec: ModelSpec) -> MediationResult`.

Do not change a signature without updating this section and every consuming task in the same commit.

### Task 1: Restore a supported Python 3.11 development environment

**Files:**
- Modify: `README.md`
- Verify: `pyproject.toml`

**Interfaces:**
- Consumes: existing package metadata and aggregation tests.
- Produces: a reproducible editable environment with all declared runtime/test dependencies.

- [ ] **Step 1: Confirm the interpreter contract**

Run:

```powershell
py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11); print(sys.executable)"
```

Expected: exit `0` and a Python 3.11 executable path. If the launcher cannot find 3.11, install or restore Python 3.11 before continuing; do not change `requires-python` to make another interpreter appear supported.

- [ ] **Step 2: Create and install the development environment**

Run:

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e ".[test]"
```

Expected: editable installation succeeds with Statsmodels and Patsy resolved.

- [ ] **Step 3: Run the inherited infrastructure tests**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest tests/integration/test_evidence_aggregation.py -q
```

Expected: `4 passed`.

- [ ] **Step 4: Document the exact bootstrap command**

Add this compact developer section to `README.md`:

````markdown
## Development

Mintmed currently supports Python 3.11.

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[test]"
./.venv/Scripts/python.exe -m pytest -q
```
````

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: record Python 3.11 development setup"
```

### Task 2: Define immutable shared types and result statuses

**Files:**
- Create: `src/mintmed/__init__.py`
- Create: `src/mintmed/types.py`
- Create: `tests/mediation/test_types.py`

**Interfaces:**
- Consumes: no earlier product interfaces.
- Produces: `AnalysisStatus`, `Issue`, `EffectEstimate`, `RegimeMeans`, `ContributionResult`, `PointAnalysis`, `BootstrapResult`, and `MediationResult`.

- [ ] **Step 1: Write failing construction and identity tests**

```python
from mintmed.types import AnalysisStatus, EffectEstimate, RegimeMeans


def test_regime_means_define_primary_identity() -> None:
    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)
    assert means.total_effect == 0.5
    assert means.pure_natural_direct_effect == 0.2
    assert means.total_natural_indirect_effect == 0.3


def test_effect_estimate_can_explicitly_withhold_interval() -> None:
    effect = EffectEstimate(
        name="TNIE",
        estimate=0.3,
        lower=None,
        upper=None,
        status=AnalysisStatus.INTERVAL_UNAVAILABLE,
        reason="2 of 400 bootstrap refits failed",
    )
    assert effect.interval_available is False
```

- [ ] **Step 2: Verify the tests fail because the module is absent**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_types.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'mintmed.types'`.

- [ ] **Step 3: Implement the shared values**

Use frozen dataclasses and this status vocabulary:

```python
class AnalysisStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"
    FIT_FAILED = "fit_failed"
    INTEGRATION_FAILED = "integration_failed"
    INTERVAL_UNAVAILABLE = "interval_unavailable"
    INCOMPLETE = "incomplete"
```

`RegimeMeans` exposes the three arithmetic properties tested above. `EffectEstimate.interval_available` returns `lower is not None and upper is not None`. `Issue` contains `code`, `message`, `status`, and optional `node`. `PointAnalysis` contains fitted system metadata, regime means, effects, contributions, moderator contrasts, and the accepted draw budget. `MediationResult` contains specification/analysis hashes, effects, contributions, diagnostics, bootstrap summary, provenance, and overall status; fields use tuples/mappings rather than mutable default lists.

- [ ] **Step 4: Export only the stable API marker**

Set `src/mintmed/__init__.py` to:

```python
"""Model-based nonlinear mediation for observed variables."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Run the tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_types.py -q
git add src/mintmed tests/mediation/test_types.py
git commit -m "feat: add mediation result types"
```

Expected: tests pass before the commit.

### Task 3: Parse and validate explicit specifications

**Files:**
- Create: `src/mintmed/spec.py`
- Create: `tests/mediation/test_spec.py`

**Interfaces:**
- Consumes: `Issue` and `AnalysisStatus` from Task 2.
- Produces: `VariableSpec`, `TermSpec`, `InteractionSpec`, `ScientificModel`, `NodeSpec`, `ContrastSpec`, `ComputationSpec`, `ModelSpec`, `load_model_spec(Path)`.

- [ ] **Step 1: Write failing YAML parsing tests**

Create tests using `tmp_path` that establish all of these literal outcomes:

```python
spec = load_model_spec(path)
assert spec.exposure.name == "condition"
assert spec.scientific.mediator_order == ("coping", "efficacy")
assert spec.contrast.reference == 0
assert spec.contrast.comparison == 1
assert spec.nodes[-1].family == Family.GAUSSIAN
```

Add separate tests that unknown keys, duplicate variable roles, nonexistent predictors, missing intercept declarations, cycles, a natural spline with `df != 3`, an interaction without both main effects, and an ordinal endogenous variable each raise `SpecValidationError` with a stable error code.

- [ ] **Step 2: Verify the parser tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_spec.py -q`

Expected: import failure for `mintmed.spec`.

- [ ] **Step 3: Implement strict dataclasses and enums**

Define enums with these serialized values:

```python
class Role(str, Enum):
    EXPOSURE = "exposure"
    MEDIATOR = "mediator"
    OUTCOME = "outcome"
    COVARIATE = "covariate"
    MODERATOR = "moderator"
    PARTICIPANT_ID = "participant_id"


class Family(str, Enum):
    GAUSSIAN = "gaussian"
    BERNOULLI = "bernoulli"


class TermKind(str, Enum):
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    NATURAL_SPLINE = "natural_spline"
    CATEGORICAL = "categorical"
```

Reject extra YAML keys by comparing each mapping key set with the dataclass field set before construction. Parse terms as objects, never as executable formula text.

- [ ] **Step 4: Implement graph and term validation**

Use Kahn's algorithm over declared scientific edges. Validate exactly one exposure/outcome, one to four mediators, mediator order equality with the mediator set, pre-exposure covariate/moderator declarations, valid variable references, family compatibility, `df=3`, explicit main effects, and a node for every mediator/outcome.

- [ ] **Step 5: Run focused and full tests, then commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_spec.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/spec.py tests/mediation/test_spec.py
git commit -m "feat: validate explicit mediation specifications"
```

### Task 4: Compile templates and perform data preflight

**Files:**
- Modify: `src/mintmed/spec.py`
- Create: `src/mintmed/diagnostics.py`
- Create: `tests/mediation/test_plan.py`

**Interfaces:**
- Consumes: Task 3 specification objects and a pandas `DataFrame`.
- Produces: `TemplateSpec`, `CompiledNodePlan`, `AnalysisPlan`, `compile_template`, `estimate_plan`.

- [ ] **Step 1: Write failing compiler tests**

Test one single, one correlated-parallel, and one moderated-serial template. Assert the parallel compiler includes earlier mediators as `factorization_predictors` but not `scientific_parents`. Assert explicit specifications are not silently augmented.

Add preflight tests for missing columns, nonfinite values, nonbinary Bernoulli values, tied continuous values, complete-case counts, exposure contrasts outside support, sparse binary events, and repeated participant IDs.

- [ ] **Step 2: Verify the compiler tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_plan.py -q`

Expected: imports for `TemplateSpec` or `estimate_plan` fail.

- [ ] **Step 3: Implement the compiled plan**

`CompiledNodePlan` contains `response`, `family`, `terms`, `interactions`, `scientific_parents`, `factorization_predictors`, and frozen category levels. `AnalysisPlan` contains the cleaned analysis row indices, compiled nodes in mediator-then-outcome order, contrast, computation, warnings, `specification_hash`, and `analysis_hash`.

Compute hashes with canonical sorted JSON. The analysis hash includes a SHA-256 digest of column names, dtypes, row indices, and `pandas.util.hash_pandas_object(data, index=True)` bytes; it excludes paths and runtime limits.

- [ ] **Step 4: Implement explicit preflight outcomes**

Missingness policy `error` raises `DataValidationError(code="missing_values")`. Policy `complete_case` drops rows once before fitting and records original/retained counts. Out-of-range exposure or fixed moderator values raise `UnsupportedAnalysisError(code="unsupported_extrapolation")`. Ties are accepted. Participant IDs with duplicates raise `UnsupportedAnalysisError(code="repeated_rows")`.

- [ ] **Step 5: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_plan.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/spec.py src/mintmed/diagnostics.py tests/mediation/test_plan.py
git commit -m "feat: compile mediation analysis plans"
```

### Task 5: Build and freeze declared design matrices

**Files:**
- Create: `src/mintmed/design.py`
- Create: `tests/mediation/test_design.py`

**Interfaces:**
- Consumes: `CompiledNodePlan`.
- Produces: `FrozenDesign(formula, design_info, columns, rank)` plus `fit_design` and `transform_design`.

- [ ] **Step 1: Write failing transform tests**

Test that a fitted three-df centered natural spline has the same columns during counterfactual prediction; changing exposure updates exposure-by-mediator interactions; changing a moderator updates moderator interactions; categorical reference levels remain frozen; and rank-deficient declared designs raise `NodeFitError(code="rank_deficient")`.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_design.py -q`

Expected: import failure for `mintmed.design`.

- [ ] **Step 3: Implement safe formula construction**

Map structured terms internally:

```python
LINEAR: Q("name")
QUADRATIC: I(Q("name") ** 2)
NATURAL_SPLINE: cr(Q("name"), df=3, constraints="center")
CATEGORICAL: C(Q("name"), levels=list(node.category_levels["name"]))
```

Quote names from validated identifiers only. Build an intercept once. Build interactions as `(<left>):(<right>)`; include main terms independently. Fit with `patsy.dmatrix(formula, data, return_type="dataframe")`; predict with `patsy.build_design_matrices([design_info], frame, return_type="dataframe")[0]`.

- [ ] **Step 4: Enforce the rank contract**

Compute `np.linalg.matrix_rank(matrix.to_numpy())`; require equality with the number of columns. Report the response and column names in the error. Do not drop a column or reduce spline degrees of freedom.

- [ ] **Step 5: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_design.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/design.py tests/mediation/test_design.py
git commit -m "feat: freeze declared node designs"
```

### Task 6: Fit Gaussian and Bernoulli conditional nodes

**Files:**
- Create: `src/mintmed/models.py`
- Create: `tests/mediation/test_nodes.py`

**Interfaces:**
- Consumes: `FrozenDesign`, `CompiledNodePlan`.
- Produces: `FittedNode` protocol, `GaussianNode`, `BernoulliNode`, `fit_node`.

- [ ] **Step 1: Write failing node tests**

Use seeded literal fixtures to assert Gaussian coefficients/predictions against `statsmodels.OLS(y, design_matrix)`, Bernoulli probabilities against `statsmodels.GLM(y, design_matrix, family=statsmodels.api.families.Binomial())`, Gaussian residual SD uses `sqrt(ssr/df_resid)`, and seeded sampling is deterministic. Test separation and nonconvergence return `NodeFitError` rather than a regularized fallback.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_nodes.py -q`

Expected: import failure for `mintmed.models`.

- [ ] **Step 3: Implement one node protocol**

```python
class FittedNode(Protocol):
    response: str
    family: Family
    design: FrozenDesign

    def predict_mean(self, frame: pd.DataFrame) -> np.ndarray:
        pass

    def sample(self, frame: pd.DataFrame, latent: np.ndarray) -> np.ndarray:
        pass

    def log_density(self, frame: pd.DataFrame, observed: np.ndarray) -> np.ndarray:
        pass
```

Gaussian sampling is `mean + sigma * latent_normal`; Bernoulli sampling is `(latent_uniform < probability).astype(float)`. Clip Bernoulli probabilities only for log-density evaluation at `np.finfo(float).eps`, not for reported means.

- [ ] **Step 4: Convert fit problems into typed failures**

Capture Statsmodels convergence metadata and separation warnings. Raise codes `separation`, `nonconvergence`, `rank_deficient`, or `invalid_residual_variance`. Record parameter counts and event counts for diagnostics.

- [ ] **Step 5: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_nodes.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/models.py tests/mediation/test_nodes.py
git commit -m "feat: fit Gaussian and Bernoulli nodes"
```

### Task 7: Add structural-equation fixtures and analytic truths

**Files:**
- Create: `src/mintmed/simulation/__init__.py`
- Create: `src/mintmed/simulation/mediation.py`
- Create: `tests/mediation/test_simulation.py`

**Interfaces:**
- Consumes: NumPy RNG only.
- Produces: `SimulationFixture`, `sample_fixture(name, n, rng)`, `analytic_effects(name)`.

- [ ] **Step 1: Write failing truth tests**

Pin the five feasibility truths for contrast `0 -> 1`:

```python
assert analytic_effects("linear") == pytest.approx((0.62, 0.20, 0.42))
assert analytic_effects("quadratic_b") == pytest.approx((0.445, 0.20, 0.245))
assert analytic_effects("cancellation") == pytest.approx((0.0, -1.0, 1.0))
assert analytic_effects("interaction") == pytest.approx((0.90, 0.20, 0.70))
assert analytic_effects("ushape_a") == pytest.approx((0.2 + 0.6 * 0.8 / np.sqrt(2), 0.2, 0.6 * 0.8 / np.sqrt(2)))
```

Also test deterministic serial, correlated-parallel, small binary, moderator, sparse-event, and four-mediator fixtures return named DataFrame columns and a complete `ModelSpec` builder.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_simulation.py -q`

- [ ] **Step 3: Port the five equations, not the smoke estimator**

Copy only the data-generating equations and analytic truths from `outline/feasibility_smoke_2026-09-19.py`. Do not copy its `Node`, LOO selection, redundant spline design, or `g_computation` implementation.

- [ ] **Step 4: Add baseline architecture fixtures**

Implement serial Gaussian, correlated parallel Gaussian, exact two-Bernoulli-mediator, baseline-moderated serial, and four-mediator mixed fixtures with explicit truth metadata. For correlated parallel mediators, generate correlated residual normals before applying node equations; do not encode a false scientific arrow.

- [ ] **Step 5: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_simulation.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/simulation tests/mediation/test_simulation.py
git commit -m "feat: add mediation oracle fixtures"
```

### Task 8: Implement the shared g-formula engine

**Files:**
- Create: `src/mintmed/gformula.py`
- Create: `tests/mediation/test_gformula.py`

**Interfaces:**
- Consumes: `AnalysisPlan`, fitted nodes, simulation fixtures.
- Produces: `CommonDraws`, `FittedSystem`, `fit_system`, `standardize_regime`, `compute_regime_means`.

- [ ] **Step 1: Write failing regime tests**

Test exact linear single-mediator, exact small-binary enumeration, serial two-mediator truth, correlated-parallel dependence preservation, four mediators, and binary-outcome probability differences. Assert `mu_00`, `mu_10`, and `mu_11` are deterministic for the same seeds and unchanged by dictionary ordering.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_gformula.py -q`

- [ ] **Step 3: Generate common low-discrepancy draws**

Use `scipy.stats.qmc.Sobol(d=number_of_mediators, scramble=True, seed=seed)` to generate uniforms. Clip only to `(eps, 1-eps)` before `scipy.stats.norm.ppf`. Store both uniforms and normals in `CommonDraws`; every regime uses the same arrays.

- [ ] **Step 4: Implement sequential mediator simulation**

For mediator `j`, copy the standardized baseline frame, replace exposure by `mediator_exposure`, replace fixed moderators, insert already simulated mediators `0..j-1`, and sample node `j`. For the outcome, replace exposure by `outcome_exposure`, insert the complete simulated mediator vector, predict the conditional mean, and average across draws then participants.

Process draws in fixed-size blocks and accumulate sums/counts so memory is proportional to `participants * block_size * variables`, never `bootstrap_replicates * participants * draws`. For a small fully binary mediator vector, exact enumeration may bypass simulation only after matching the reference engine in tests.

- [ ] **Step 5: Implement numerical accuracy selection**

At the point fit, compare two independent scrambles at 256 draws and compare 256 versus 512. Double through 4096 until every primary effect changes by at most `integration_tolerance`. Freeze the accepted draw count for all bootstrap replicates. Return `INTEGRATION_FAILED` if 4096 misses tolerance.

- [ ] **Step 6: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_gformula.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/gformula.py tests/mediation/test_gformula.py
git commit -m "feat: add shared mediation standardization engine"
```

### Task 9: Compute effects, valid contributions, and moderator contrasts

**Files:**
- Create: `src/mintmed/effects.py`
- Create: `tests/mediation/test_effects.py`

**Interfaces:**
- Consumes: `RegimeMeans`, fitted outcome design, optional moderator regimes.
- Produces: `natural_effects`, `parallel_contributions`, `ModeratorContrast`.

- [ ] **Step 1: Write failing effect tests**

Test exact TE/PNDE/TNIE values, cancellation with `TE=0`, identity within floating tolerance, risk-difference labeling, additive parallel contributions summing to TNIE, and contribution refusal for a logit outcome, serial structure, or a term containing two mediators.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_effects.py -q`

- [ ] **Step 3: Implement named effects**

Return three `EffectEstimate` objects in order `TE`, `PNDE`, `TNIE`. Check `abs(TE - PNDE - TNIE) <= 1e-10`; otherwise return an `INTEGRATION_FAILED` issue rather than altering components.

- [ ] **Step 4: Implement the attribution gate**

Permit individual contributions only for an identity-linked Gaussian outcome whose mediator-containing terms each reference exactly one mediator and whose scientific arrangement is parallel. Compute each contribution by evaluating that mediator's outcome-term block under its `a1` versus `a0` marginal draws while holding outcome exposure at `a1`. Return `available=False` and a stable reason code for all other models.

- [ ] **Step 5: Implement moderator contrasts**

Evaluate each prespecified moderator value over the same baseline rows and remaining-covariate distribution. Store effect differences in declared order; do not subset rows by observed moderator value.

- [ ] **Step 6: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_effects.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/effects.py tests/mediation/test_effects.py
git commit -m "feat: compute mediation effects and contrasts"
```

### Task 10: Add full-refit participant-bootstrap uncertainty

**Files:**
- Create: `src/mintmed/uncertainty.py`
- Create: `tests/mediation/test_uncertainty.py`

**Interfaces:**
- Consumes: `AnalysisPlan`, point draw budget, point effects.
- Produces: `bootstrap_analysis` and percentile intervals attached by effect name.

- [ ] **Step 1: Write failing bootstrap tests**

Test deterministic row indices, different integration streams from row streams, full transform refitting, fixed category schema, paired moderator differences, missing-category failure, separation failure, time-limited incomplete status, and interval withholding when failures exceed 1% or successes are below 390 for a 400-replicate test request.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_uncertainty.py -q`

- [ ] **Step 3: Implement deterministic stream separation**

Derive row and integration seeds using:

```python
row_sequence = np.random.SeedSequence([plan.computation.seed, 4101, replicate])
integration_sequence = np.random.SeedSequence([plan.computation.seed, 4102, replicate])
```

Bootstrap exactly `n` participant rows with replacement. Re-run `estimate_plan`, fit every node, and compute every requested effect on that resample.

- [ ] **Step 4: Implement failure accounting and intervals**

Store one record per attempted replicate with `replicate`, `row_seed`, `integration_seed`, `status`, `error_code`, and effect columns. Never retry until a success quota is reached. Use 2.5th/97.5th percentiles of successful values only when failures are at most 1% and at least 390 successes exist for a request of 400 or more; otherwise withhold all intervals and retain point estimates.

For the default 999-replicate analysis, a runtime cutoff produces `INCOMPLETE` and no interval. Only an explicitly requested `quick_diagnostic` mode may return a provisional interval, and its status/label must appear in every export.

- [ ] **Step 5: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_uncertainty.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed/uncertainty.py tests/mediation/test_uncertainty.py
git commit -m "feat: add full-refit bootstrap uncertainty"
```

### Task 11: Assemble diagnostics and the public analysis API

**Files:**
- Modify: `src/mintmed/diagnostics.py`
- Create: `src/mintmed/api.py`
- Modify: `src/mintmed/__init__.py`
- Create: `tests/mediation/test_analysis.py`

**Interfaces:**
- Consumes: every baseline computational component.
- Produces: `analyze_mediation(data, spec) -> MediationResult`.

- [ ] **Step 1: Write failing end-to-end API tests**

Run tiny deterministic analyses for single, correlated-parallel, moderated-serial, binary, and four-mediator fixtures. Assert units, statuses, parameter counts, binary event counts, warnings for `N<100`, support summaries, interval failure counts, and provenance versions.

- [ ] **Step 2: Verify the tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_analysis.py -q`

- [ ] **Step 3: Implement orchestration in one direction**

`analyze_mediation` performs: `estimate_plan` → point `fit_system` → draw-budget selection → `compute_regime_means` → effects/contributions/moderation → bootstrap → diagnostics → immutable `MediationResult`. Catch only typed domain exceptions at the API boundary and translate them into result statuses; unexpected programmer exceptions must propagate during development.

- [ ] **Step 4: Implement diagnostic contents**

Include rows original/used, parameters per node, design ranks, Bernoulli event/non-event counts, observed exposure/moderator ranges, integration comparisons, node convergence, bootstrap requested/attempted/successful/failed counts, failure codes, and explicit assumption/exclusion strings.

- [ ] **Step 5: Export public entry points**

Export `analyze_mediation`, `compile_template`, `estimate_plan`, `load_model_spec`, `MediationResult`, and `__version__` from `mintmed.__init__`.

- [ ] **Step 6: Run tests and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_analysis.py -q
./.venv/Scripts/python.exe -m pytest -q
git add src/mintmed tests/mediation/test_analysis.py
git commit -m "feat: expose the mediation analysis API"
```

### Task 12: Export reports, CLI results, and three runnable examples

**Files:**
- Create: `src/mintmed/report.py`
- Create: `src/mintmed/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/mediation/test_report.py`
- Create: `tests/integration/test_cli.py`
- Create: `examples/single/analysis.yaml`
- Create: `examples/single/data.csv`
- Create: `examples/parallel/analysis.yaml`
- Create: `examples/parallel/data.csv`
- Create: `examples/serial_moderated/analysis.yaml`
- Create: `examples/serial_moderated/data.csv`

**Interfaces:**
- Consumes: `MediationResult`, CSV data, strict YAML spec.
- Produces: `analysis.json`, `effects.csv`, `bootstrap.csv`, `report.md`, optional fitted-curve CSV/PNG files.

- [ ] **Step 1: Write failing serialization tests**

Assert JSON has specification/analysis hashes, effects, diagnostics, provenance, and statuses; CSV retains negative effects and missing intervals as empty values; Markdown begins with contrast/answer, then uncertainty, model, assumptions, diagnostics, and limitations.

- [ ] **Step 2: Write a failing CLI integration test**

Invoke:

```powershell
./.venv/Scripts/python.exe -m mintmed.cli --data examples/single/data.csv --spec examples/single/analysis.yaml --output <temporary-directory>
```

Assert exit `0` and all four required artifacts exist. Add a malformed-spec case that exits `2` and prints the typed validation code without a traceback.

- [ ] **Step 3: Verify tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/mediation/test_report.py tests/integration/test_cli.py -q`

- [ ] **Step 4: Implement report writers and CLI**

Use `dataclasses.asdict` plus explicit Enum conversion for JSON. Use one effect row per estimand/moderator condition. Never infer a significance label. Add to `pyproject.toml`:

```toml
[project.scripts]
mintmed = "mintmed.cli:main"
```

- [ ] **Step 5: Create the examples from seeded fixtures**

Generate fixed small CSVs once from Task 7 functions and commit their values. Each YAML declares every variable, term, interaction, contrast, seed, bootstrap count, and missingness policy. Use a small bootstrap count labeled `quick_diagnostic` in examples so documentation runs finish promptly.

- [ ] **Step 6: Run tests and all examples, then commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/mediation/test_report.py tests/integration/test_cli.py -q
./.venv/Scripts/mintmed.exe --data examples/single/data.csv --spec examples/single/analysis.yaml --output results/generated/example-single
./.venv/Scripts/python.exe -m pytest -q
git add pyproject.toml src/mintmed examples tests
git commit -m "feat: add mediation CLI reports and examples"
```

### Task 13: Implement the frozen validation runner and reporting contract

**Files:**
- Create: `src/mintmed/experiments/__init__.py`
- Create: `src/mintmed/experiments/mediation_validation.py`
- Create: `src/mintmed/experiments/mediation_validation_reporting.py`
- Create: `configs/mediation_validation_smoke.yaml`
- Create: `configs/mediation_validation.yaml`
- Create: `tests/integration/test_mediation_validation.py`
- Verify: `scripts/aggregate_shards.py`
- Verify: `.github/workflows/sharded_benchmark.yml`

**Interfaces:**
- Consumes: `analyze_mediation`, simulation fixtures, generic shard aggregation.
- Produces: `load_config`, `expected_combinations`, `expected_row_count`, `COMBINATION_COLUMNS`, per-replicate raw metrics, provenance, and release summaries.

- [ ] **Step 1: Write failing runner contract tests**

Assert smoke configuration combinations are unique; a sharded run equals an unsharded run after sorting; completed replicates are flushed immediately; rerunning skips only rows whose full key/hash matches; and aggregation rejects a missing/duplicate combination.

- [ ] **Step 2: Verify tests fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/integration/test_mediation_validation.py -q`

- [ ] **Step 3: Implement the locked combination key**

Use:

```python
COMBINATION_COLUMNS = ("cell_id", "replicate")
```

Each row contains cell/replicate, data seed, analysis seed, estimand, truth, estimate, bias, interval bounds, coverage, width, zero exclusion, interval availability, status, failure code, runtime, fit count, and draw budget. Write one row atomically after each completed replicate.

- [ ] **Step 4: Encode the 12 baseline cells exactly**

Use independent standard-normal disturbances unless a cell states otherwise, balanced binary exposure, continuous mediator/outcome residual SD `1`, and baseline `C ~ N(0,1)` with coefficient `0.3` wherever shown:

1. `N=100`: `M=.5A+.3C+eM`; `Y=.2A+.5M+.3C+eY`.
2. `N=250`: the same generator as cell 1.
3. `N=100`: cell 1 with the `A -> M` coefficient set to zero.
4. `N=100`: cell 1 with the `M -> Y` coefficient set to zero.
5. `N=100`: cell 1 with both `A -> M` and `M -> Y` coefficients set to zero.
6. `N=150`: parallel mediators with exposure coefficients `.5/.4`, residual correlation `.4`, and `Y=.2A+.4M1+.4M2+.2M1*M2+.3C+eY`; report joint effect only.
7. `N=200`: `M1=.5A+.3C+e1`; `M2=.2A+.5M1+.3C+e2`; `M3=.2A+.5M2+.3C+e3`; `Y=.2A+.2M1+.2M2+.4M3+.3C+eY`.
8. `N=100`: cell 1 mediator with `Y=.2A+.4M^2+.3C+eY`, fitted with the declared quadratic term.
9. `N=250`: the cell 8 generator fitted with the prespecified three-df natural spline.
10. `N=150`: binary baseline `W` independent of `C`; `M=(.3+.3W)A+.2W+.3C+eM`; `Y=.2A+(.3+.3W)M+.2W+.3C+eY`; estimate TNIE at `W=0`, TNIE at `W=1`, and their difference.
11. `N=150`: `logit P(M=1)=-.4+.8A+.3C`; `Y=.2A+.6M+.3C+eY`.
12. `N=250`: binary `M1` as cell 11; `M2=.3A+.5M1+.3C+e2`; `logit P(Y=1)=-.5+.2A+.4M1+.4M2+.3C`.

Run 200 independent datasets per cell and 399 bootstrap replicates per dataset: 2,400 datasets and 957,600 bootstrap pipeline refits plus point fits. Add a separate noninferential `N=50` diagnostic set for tied scores, sparse events, missingness, and stronger opposing paths; do not multiply it into the inferential matrix. Keep the deterministic four-mediator oracle and runtime probe outside the 12-cell inferential claim.

- [ ] **Step 5: Implement summaries and gates**

Report bias, RMSE, coverage, interval width, zero-exclusion frequency, unavailable-interval rate, runtime, and binomial Monte Carlo standard errors. Gate continuous absolute bias at `<=0.05` population outcome SD and binary absolute bias at `<=0.02` probability units; require the 95% Wilson lower coverage bound to be `>=0.90`; require the 95% Wilson upper false-zero-exclusion bound in null cells to be `<=0.10`; and require unavailable intervals/fatal fits in ordinary-use cells to be `<=1%`. A missing interval counts as noncoverage in the primary denominator. Analytic identities, independent comparison, numerical precision, reproducibility, and runtime requirements must also pass; power is reported but is not a gate.

- [ ] **Step 6: Run local smoke and commit**

```powershell
./.venv/Scripts/python.exe -m pytest tests/integration/test_mediation_validation.py tests/integration/test_evidence_aggregation.py -q
./.venv/Scripts/python.exe -m mintmed.experiments.mediation_validation --config configs/mediation_validation_smoke.yaml --output results/generated/validation-smoke
./.venv/Scripts/python.exe scripts/aggregate_shards.py --module mintmed.experiments.mediation_validation --config configs/mediation_validation_smoke.yaml --shards-dir results/generated/test-shards --output results/generated/test-aggregate
git add src/mintmed/experiments configs tests/integration
git commit -m "feat: add bounded mediation validation runner"
```

### Task 14: Complete analytic, independent-package, and runtime acceptance

**Files:**
- Create: `tests/integration/test_reference_agreement.py`
- Create: `scripts/run_runtime_pilot.py`
- Create: `docs/validation/runtime_pilot.md`
- Create: `docs/validation/reference_agreement.md`

**Interfaces:**
- Consumes: completed baseline API and examples.
- Produces: independent numerical agreement and measured cost forecast before the frozen matrix is dispatched.

- [ ] **Step 1: Add exact/analytic acceptance tests**

Run every Task 7 truth through population/oracle computation and finite-sample implementation checks. Require exact linear fast/reference calculations to agree with general simulation within the selected integration tolerance; do not require noisy estimates to equal population truths.

- [ ] **Step 2: Add independent Statsmodels Mediation agreement**

For one continuous single-mediator linear case with identical rows/covariates and no interaction, compare Mintmed point TE/PNDE/TNIE with `statsmodels.stats.mediation.Mediation`. Record Statsmodels/Patsy versions, estimand convention, covariates, exposure values, and Monte Carlo settings. Set the agreement tolerance before viewing the result.

- [ ] **Step 3: Measure five complete runtime cases**

Run `N in {100,250}`, one to three mediators, Gaussian and Bernoulli nodes, and a spline case with the complete bootstrap/integration check. Record wall time, CPU time, peak memory, fit count, draw budget, and failures. The script writes JSON first and renders Markdown from that JSON.

- [ ] **Step 4: Forecast before dispatch**

Multiply measured per-replicate cost by every frozen matrix cell/replicate count. If the aggregate forecast exceeds 12 CPU-hours, optimize batching/exact expectations/shared arrays once, rerun the pilot, and document the new forecast. If still above budget, stop and request a narrower declared envelope before any matrix dispatch.

- [ ] **Step 5: Verify and commit acceptance artifacts**

```powershell
./.venv/Scripts/python.exe -m pytest tests/integration/test_reference_agreement.py -q
./.venv/Scripts/python.exe scripts/run_runtime_pilot.py --output results/generated/runtime-pilot.json
./.venv/Scripts/python.exe -m pytest -q
git add tests/integration/test_reference_agreement.py scripts/run_runtime_pilot.py docs/validation
git commit -m "test: establish mediation reference and runtime acceptance"
```

### Task 15: Run the frozen matrix and publish the research-beta boundary

**Files:**
- Create: `docs/validation/baseline_release_charter.md`
- Create: `docs/validation/baseline_evidence.md`
- Create: `docs/user-guide.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: frozen configuration, runtime forecast, sharded workflow.
- Produces: one immutable release charter, raw evidence artifacts, concise evidence report, and user-facing scope/limitations.

- [ ] **Step 1: Freeze the charter before execution**

Record configuration SHA-256, git commit, cell definitions, truths, estimands, seeds, replicate counts, bootstrap count, draw rule, gates, failure denominator, CPU ceiling, and the single-correction rule. Commit the charter and configuration before dispatching.

- [ ] **Step 2: Dispatch and aggregate the matrix**

Use `.github/workflows/sharded_benchmark.yml` with runner `mintmed.experiments.mediation_validation`, the frozen config, and explicit cell/batch shard dimensions. Download artifacts, aggregate with `scripts/aggregate_shards.py`, and verify exact expected combinations with no duplicates.

- [ ] **Step 3: Apply the stopping rule**

If a gate fails, identify one root cause and permit one targeted correction plus affected-cell rerun within the 12-hour total. A persistent failure narrows the documented supported envelope or postpones that feature; it does not expand the grid or introduce a new estimator.

- [ ] **Step 4: Write evidence and user documentation**

Lead with supported and unsupported cells, then bias/coverage/width/failure/runtime tables with Monte Carlo uncertainty. The user guide states assumptions, original outcome units, binary risk differences, natural-effect convention, no required significant total effect, no default mediated proportion, unsupported repeated/multilevel rows, unsupported latent measurement, and complete-case population implications.

- [ ] **Step 5: Perform clean-install release verification**

```powershell
py -3.11 -m venv .release-venv
./.release-venv/Scripts/python.exe -m pip install .
./.release-venv/Scripts/mintmed.exe --data examples/single/data.csv --spec examples/single/analysis.yaml --output results/generated/release-check
./.release-venv/Scripts/python.exe -m pytest -q
```

Expected: installation, example, and full tests succeed with no undeclared dependency.

- [ ] **Step 6: Commit the release boundary**

```powershell
git add README.md docs configs/mediation_validation.yaml
git commit -m "docs: publish mintmed research-beta evidence"
```

## Post-Baseline Extensions

Do not start these during Tasks 1–15. Each requires a separate approved plan and its promotion checks from Section 14 of the source roadmap:

1. Automatic penalized smooths with full-bootstrap selection validation.
2. Restricted single-Gaussian-mediator rho sensitivity with analytic and `medsens` agreement.
3. Ordered interventional mediator-specific decomposition with the independent-interaction counterexample.
4. Predictive log-score gain or regime Jensen–Shannon summaries, labeled as descriptive information rather than causal indirect effects.
5. Ordinal, missing-data, clustered, longitudinal, location-scale, latent-variable, or R-wrapper extensions.

## Final Verification Checklist

- [ ] `./.venv/Scripts/python.exe -m pytest -q` reports zero failures.
- [ ] `./.venv/Scripts/python.exe -m pip check` reports no broken requirements.
- [ ] All three example commands produce JSON, effects CSV, bootstrap CSV, and Markdown.
- [ ] Scientific and analysis hashes are stable across output directories and shard layouts.
- [ ] Same seed/config/data produce identical point and bootstrap results.
- [ ] Missing-category, separation, rank, support, integration, timeout, and incomplete-run cases produce explicit statuses.
- [ ] TE equals PNDE plus TNIE within the recorded numerical tolerance in every successful analysis.
- [ ] Binary results are probability differences; continuous results remain in original outcome units.
- [ ] Individual parallel contributions appear only under the admissibility gate.
- [ ] Frozen validation artifacts cover every expected combination exactly once.
- [ ] Claims in README/user guide do not exceed the cell-specific evidence report.
