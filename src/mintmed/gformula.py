"""Shared deterministic g-formula fitting and regime standardization."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm, qmc

from .diagnostics import NodeFitError
from .models import FittedNode, fit_node
from .spec import AnalysisPlan, Family, TermKind
from .types import AnalysisStatus, Issue, RegimeMeans, _freeze_mapping


BLOCK_SIZE = 256
_BUDGETS = (256, 512, 1024, 2048, 4096)
_GAUSS_HERMITE_ORDER = 64


class GFormulaError(ValueError):
    """Typed failure raised by g-formula fitting or standardization."""

    def __init__(
        self,
        *,
        code: str,
        status: AnalysisStatus,
        message: str,
        node: str | None = None,
        regime: tuple[object, object] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = str(code)
        self.status = AnalysisStatus(status)
        self.message = str(message)
        self.node = node
        self.regime = regime
        self.details = _freeze_nested(details or {})
        super().__init__(self.message)


def _read_only_array(value: np.ndarray) -> np.ndarray:
    array = np.array(value, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def _freeze_nested(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping({key: _freeze_nested(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_nested(item) for item in value)
    if isinstance(value, np.ndarray):
        return _read_only_array(value)
    return value


@dataclass(frozen=True, slots=True)
class CommonDraws:
    """Common low-discrepancy mediator draws in participant-first form."""

    seed: int
    draw_count: int
    mediator_count: int
    uniforms: np.ndarray
    normals: np.ndarray
    epsilon: float = np.finfo(float).eps

    def __post_init__(self) -> None:
        if isinstance(self.draw_count, bool) or self.draw_count <= 0:
            raise ValueError("draw_count must be positive")
        if isinstance(self.mediator_count, bool) or self.mediator_count <= 0:
            raise ValueError("mediator_count must be positive")
        if not 0.0 < float(self.epsilon) < 0.5:
            raise ValueError("epsilon must lie strictly between 0 and 0.5")
        uniforms = _read_only_array(self.uniforms)
        normals = _read_only_array(self.normals)
        expected = (int(self.draw_count), int(self.mediator_count))
        if uniforms.shape != expected or normals.shape != expected:
            raise ValueError("draw arrays must have shape (draw_count, mediator_count)")
        if not np.isfinite(uniforms).all() or not np.isfinite(normals).all():
            raise ValueError("draw arrays must be finite")
        if np.any(uniforms < float(self.epsilon)) or np.any(uniforms > 1.0 - float(self.epsilon)):
            raise ValueError("uniform draws must respect epsilon clipping")
        object.__setattr__(self, "seed", int(self.seed))
        object.__setattr__(self, "draw_count", int(self.draw_count))
        object.__setattr__(self, "mediator_count", int(self.mediator_count))
        object.__setattr__(self, "epsilon", float(self.epsilon))
        object.__setattr__(self, "uniforms", uniforms)
        object.__setattr__(self, "normals", normals)

    @classmethod
    def from_seed(
        cls,
        *,
        seed: int,
        draw_count: int,
        mediator_count: int,
        epsilon: float = np.finfo(float).eps,
    ) -> "CommonDraws":
        if isinstance(draw_count, bool) or not isinstance(draw_count, (int, np.integer)):
            raise ValueError("draw_count must be a positive integer")
        if isinstance(mediator_count, bool) or not isinstance(mediator_count, (int, np.integer)):
            raise ValueError("mediator_count must be a positive integer")
        if draw_count <= 0 or mediator_count <= 0:
            raise ValueError("draw_count and mediator_count must be positive")
        if not 0.0 < float(epsilon) < 0.5:
            raise ValueError("epsilon must lie strictly between 0 and 0.5")
        sampler = qmc.Sobol(d=int(mediator_count), scramble=True, seed=int(seed))
        uniforms = sampler.random(n=int(draw_count))
        uniforms = np.clip(uniforms, float(epsilon), 1.0 - float(epsilon))
        normals = norm.ppf(uniforms)
        return cls(
            seed=int(seed),
            draw_count=int(draw_count),
            mediator_count=int(mediator_count),
            uniforms=uniforms,
            normals=normals,
            epsilon=float(epsilon),
        )

    def for_rows(self, row_count: int, mediator_index: int, family: Family) -> np.ndarray:
        if isinstance(row_count, bool) or not isinstance(row_count, (int, np.integer)) or row_count < 0:
            raise ValueError("row_count must be a nonnegative integer")
        if isinstance(mediator_index, bool) or not isinstance(mediator_index, (int, np.integer)):
            raise ValueError("mediator_index must be an integer")
        if not 0 <= mediator_index < self.mediator_count:
            raise ValueError("mediator_index is outside the draw dimensions")
        family = Family(family)
        source = self.uniforms[:, mediator_index] if family is Family.BERNOULLI else self.normals[:, mediator_index]
        return np.broadcast_to(source, (int(row_count), self.draw_count))


@dataclass(frozen=True, slots=True)
class FittedSystem:
    """Immutable fitted nodes and the integration choice for one analysis plan."""

    plan: AnalysisPlan
    nodes: tuple[FittedNode, ...]
    draws: CommonDraws | None
    draw_budget: int
    integration_method: str
    status: AnalysisStatus
    issues: tuple[Issue, ...] = ()
    mediator_residual_correlation: np.ndarray | None = None
    integration_diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allowed = {
            "sobol_blocked",
            "exact_binary_mediators",
            "gaussian_linear_exact",
            "gauss_hermite",
        }
        if self.integration_method not in allowed:
            raise ValueError(f"unsupported integration method {self.integration_method!r}")
        nodes = tuple(self.nodes)
        issues = tuple(self.issues)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "issues", issues)
        object.__setattr__(self, "status", AnalysisStatus(self.status))
        object.__setattr__(self, "draw_budget", int(self.draw_budget))
        object.__setattr__(self, "integration_diagnostics", _freeze_nested(self.integration_diagnostics))
        if self.mediator_residual_correlation is not None:
            correlation = _read_only_array(self.mediator_residual_correlation)
            mediator_count = len(_mediator_order(self.plan))
            if correlation.shape != (mediator_count, mediator_count):
                raise ValueError("mediator residual correlation has the wrong shape")
            object.__setattr__(self, "mediator_residual_correlation", correlation)

    @property
    def node_by_response(self) -> Mapping[str, FittedNode]:
        return _freeze_mapping({node.response: node for node in self.nodes})

    @property
    def mediator_nodes(self) -> tuple[FittedNode, ...]:
        index = self.node_by_response
        return tuple(index[name] for name in _mediator_order(self.plan))

    @property
    def outcome_node(self) -> FittedNode:
        return self.node_by_response[self.plan.nodes[-1].response]


def _error(
    code: str,
    status: AnalysisStatus,
    message: str,
    *,
    node: str | None = None,
    regime: tuple[object, object] | None = None,
    details: Mapping[str, Any] | None = None,
) -> GFormulaError:
    return GFormulaError(
        code=code,
        status=status,
        message=message,
        node=node,
        regime=regime,
        details=details,
    )


def _retained_frame(data: pd.DataFrame, plan: AnalysisPlan) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise _error("invalid_data", AnalysisStatus.FIT_FAILED, "data must be a pandas DataFrame")
    try:
        retained = data.loc[list(plan.retained_row_indices), list(plan.analysis_columns)].copy(deep=True)
    except (KeyError, IndexError) as exc:
        raise _error(
            "retained_rows_mismatch",
            AnalysisStatus.FIT_FAILED,
            "data does not contain the retained analysis rows and columns",
            details={"error": str(exc)},
        ) from exc
    if len(retained) != plan.retained_row_count or retained.index.tolist() != list(plan.retained_row_indices):
        raise _error(
            "retained_rows_mismatch",
            AnalysisStatus.FIT_FAILED,
            "retained row labels or count do not match AnalysisPlan",
        )
    return retained


def _expected_node_responses(plan: AnalysisPlan) -> tuple[str, ...]:
    return (*_mediator_order(plan), plan.nodes[-1].response)


def _mediator_order(plan: AnalysisPlan) -> tuple[str, ...]:
    """Return the scientific mediator order compiled into an AnalysisPlan."""

    declared = plan.diagnostics.get("factorization_order")
    if declared is not None:
        return tuple(str(name) for name in declared)
    return tuple(node.response for node in plan.nodes[:-1])


def _validate_node_order(plan: AnalysisPlan) -> None:
    observed = tuple(node.response for node in plan.nodes)
    expected = _expected_node_responses(plan)
    if observed != expected or len(set(observed)) != len(observed):
        raise _error(
            "node_order_mismatch",
            AnalysisStatus.FIT_FAILED,
            "fitted node order does not match AnalysisPlan",
            details={"expected": expected, "observed": observed},
        )


def _node_fit_error(exc: NodeFitError) -> GFormulaError:
    return _error(
        exc.code,
        AnalysisStatus.FIT_FAILED,
        str(exc),
        node=exc.response,
        details={"variable": exc.variable, "columns": exc.columns, **dict(exc.details)},
    )


def _parallel_groups(plan: AnalysisPlan) -> list[tuple[str, ...]]:
    mediator_names = set(_mediator_order(plan))
    eligible = [
        node.response
        for node in plan.nodes[:-1]
        if node.family is Family.GAUSSIAN
        and not mediator_names.intersection(node.scientific_parents)
        and not mediator_names.intersection(node.factorization_predictors)
    ]
    return [tuple(eligible)] if eligible else []


def _residual_correlation(retained: pd.DataFrame, plan: AnalysisPlan, nodes: Sequence[FittedNode]) -> np.ndarray:
    mediator_names = _mediator_order(plan)
    index = {node.response: node for node in nodes}
    correlation = np.eye(len(mediator_names), dtype=float)
    for group in _parallel_groups(plan):
        residuals = []
        for response in group:
            fitted = index[response]
            sigma = float(getattr(fitted, "sigma", np.nan))
            predicted = np.asarray(fitted.predict_mean(retained), dtype=float)
            observed = retained[response].to_numpy(dtype=float)
            residuals.append((observed - predicted) / sigma)
        matrix = np.column_stack(residuals)
        if matrix.shape[1] > 1:
            estimated = np.corrcoef(matrix, rowvar=False)
        else:
            estimated = np.ones((1, 1), dtype=float)
        estimated = np.asarray(estimated, dtype=float)
        np.fill_diagonal(estimated, 1.0)
        if not np.isfinite(estimated).all():
            raise _error(
                "residual_dependence_failed",
                AnalysisStatus.FIT_FAILED,
                "parallel residual correlation is not finite",
            )
        try:
            np.linalg.cholesky(estimated)
        except np.linalg.LinAlgError as exc:
            raise _error(
                "residual_dependence_failed",
                AnalysisStatus.FIT_FAILED,
                "parallel residual correlation is not positive definite",
            ) from exc
        positions = [mediator_names.index(response) for response in group]
        correlation[np.ix_(positions, positions)] = estimated
    return correlation


def _is_gaussian_linear(plan: AnalysisPlan) -> bool:
    if len(_mediator_order(plan)) != 1 or len(plan.nodes) != 2:
        return False
    mediator, outcome = plan.nodes
    if mediator.family is not Family.GAUSSIAN or outcome.family is not Family.GAUSSIAN:
        return False
    if mediator.interactions or outcome.interactions:
        return False
    if any(TermKind(term.kind) is not TermKind.LINEAR for node in plan.nodes for term in node.terms):
        return False
    mediator_name = _mediator_order(plan)[0]
    return mediator_name not in mediator.factorization_predictors


def _supports_gauss_hermite(plan: AnalysisPlan) -> bool:
    """Return whether one Gaussian mediator can be integrated deterministically."""

    mediator_nodes = tuple(plan.nodes[:-1])
    gaussian_nodes = [node for node in mediator_nodes if node.family is Family.GAUSSIAN]
    if len(gaussian_nodes) != 1:
        return False
    if any(node.interactions for node in plan.nodes):
        return False
    return all(node.family in {Family.GAUSSIAN, Family.BERNOULLI} for node in mediator_nodes)


def _gauss_hermite_diagnostics() -> Mapping[str, Any]:
    return {
        "quadrature_order": _GAUSS_HERMITE_ORDER,
        "accepted_draw_count": 0,
        "tolerance": None,
        "status": AnalysisStatus.OK.value,
    }


def _make_system(
    plan: AnalysisPlan,
    nodes: tuple[FittedNode, ...],
    *,
    draws: CommonDraws | None,
    draw_budget: int,
    method: str,
    status: AnalysisStatus = AnalysisStatus.OK,
    issues: tuple[Issue, ...] = (),
    correlation: np.ndarray | None,
    diagnostics: Mapping[str, Any] | None = None,
) -> FittedSystem:
    return FittedSystem(
        plan=plan,
        nodes=nodes,
        draws=draws,
        draw_budget=draw_budget,
        integration_method=method,
        status=status,
        issues=issues,
        mediator_residual_correlation=correlation,
        integration_diagnostics=diagnostics or {},
    )


def fit_system(data: pd.DataFrame, plan: AnalysisPlan) -> FittedSystem:
    """Fit all declared conditional nodes and select a deterministic integrator."""

    _validate_node_order(plan)
    retained = _retained_frame(data, plan)
    fitted: list[FittedNode] = []
    for node_plan in plan.nodes:
        try:
            fitted.append(fit_node(retained, node_plan))
        except NodeFitError as exc:
            raise _node_fit_error(exc) from exc
    nodes = tuple(fitted)
    correlation = _residual_correlation(retained, plan, nodes)
    mediator_count = len(_mediator_order(plan))
    if all(node.family is Family.BERNOULLI for node in nodes[:-1]) and mediator_count <= 4:
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="exact_binary_mediators",
            correlation=correlation,
        )
    if _is_gaussian_linear(plan):
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="gaussian_linear_exact",
            correlation=correlation,
        )
    if _supports_gauss_hermite(plan):
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="gauss_hermite",
            correlation=correlation,
            diagnostics=_gauss_hermite_diagnostics(),
        )
    return _select_integration(retained, plan, nodes, correlation)


def _draw_seed(base_seed: int, purpose: int, draw_count: int) -> int:
    sequence = np.random.SeedSequence([int(base_seed), int(purpose), int(draw_count)])
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def _effect_vector(means: RegimeMeans) -> np.ndarray:
    return np.array([means.total_effect, means.pure_natural_direct_effect, means.total_natural_indirect_effect])


def _sobol_system(
    plan: AnalysisPlan,
    nodes: tuple[FittedNode, ...],
    correlation: np.ndarray,
    draws: CommonDraws,
    diagnostics: Mapping[str, Any] | None = None,
) -> FittedSystem:
    return _make_system(
        plan,
        nodes,
        draws=draws,
        draw_budget=draws.draw_count,
        method="sobol_blocked",
        correlation=correlation,
        diagnostics=diagnostics,
    )


def _fit_system_with_fixed_budget(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    *,
    draw_seed: int,
    draw_budget: int,
) -> FittedSystem:
    """Fit a fresh system without adaptive integration selection.

    The point-analysis path intentionally retains :func:`fit_system`'s
    tolerance-driven budget selection.  Participant bootstrap replicates
    need a different contract: they must use the point budget exactly so
    replicate failures and estimates are attributable to the resampled data,
    not to a second integration-selection procedure.
    """

    if isinstance(draw_budget, bool) or not isinstance(draw_budget, (int, np.integer)):
        raise _error(
            "invalid_draw_budget",
            AnalysisStatus.INTEGRATION_FAILED,
            "draw_budget must be a positive integer",
        )
    if int(draw_budget) < 0:
        raise _error(
            "invalid_draw_budget",
            AnalysisStatus.INTEGRATION_FAILED,
            "draw_budget must be a nonnegative integer",
        )

    _validate_node_order(plan)
    retained = _retained_frame(data, plan)
    fitted: list[FittedNode] = []
    for node_plan in plan.nodes:
        try:
            fitted.append(fit_node(retained, node_plan))
        except NodeFitError as exc:
            raise _node_fit_error(exc) from exc
    nodes = tuple(fitted)
    correlation = _residual_correlation(retained, plan, nodes)
    mediator_count = len(_mediator_order(plan))
    if all(node.family is Family.BERNOULLI for node in nodes[:-1]) and mediator_count <= 4:
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="exact_binary_mediators",
            correlation=correlation,
        )
    if _is_gaussian_linear(plan):
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="gaussian_linear_exact",
            correlation=correlation,
        )
    if _supports_gauss_hermite(plan):
        return _make_system(
            plan,
            nodes,
            draws=None,
            draw_budget=0,
            method="gauss_hermite",
            correlation=correlation,
            diagnostics=_gauss_hermite_diagnostics(),
        )
    if int(draw_budget) == 0:
        raise _error(
            "invalid_draw_budget",
            AnalysisStatus.INTEGRATION_FAILED,
            "draw_budget must be positive for Sobol integration",
        )
    draws = CommonDraws.from_seed(
        seed=int(draw_seed),
        draw_count=int(draw_budget),
        mediator_count=mediator_count,
    )
    return _sobol_system(plan, nodes, correlation, draws)


def _primary_means(data: pd.DataFrame, system: FittedSystem, draws: CommonDraws) -> RegimeMeans:
    return _compute_means_with_system(data, system, draws)


def _select_integration(
    retained: pd.DataFrame,
    plan: AnalysisPlan,
    nodes: tuple[FittedNode, ...],
    correlation: np.ndarray,
) -> FittedSystem:
    start = plan.computation.integration_draws
    if start not in _BUDGETS:
        raise _error(
            "invalid_draw_budget",
            AnalysisStatus.INTEGRATION_FAILED,
            "integration_draws must be one of 256, 512, 1024, 2048, or 4096",
            details={"integration_draws": start},
        )
    tolerance = float(plan.computation.integration_tolerance)
    checks: list[Mapping[str, Any]] = []
    last_primary: CommonDraws | None = None
    for budget in _BUDGETS[_BUDGETS.index(start) :]:
        primary = CommonDraws.from_seed(
            seed=_draw_seed(plan.computation.seed, 8101, budget),
            draw_count=budget,
            mediator_count=len(_mediator_order(plan)),
        )
        independent = CommonDraws.from_seed(
            seed=_draw_seed(plan.computation.seed, 8102, budget),
            draw_count=budget,
            mediator_count=len(_mediator_order(plan)),
        )
        primary_system = _sobol_system(plan, nodes, correlation, primary)
        independent_system = _sobol_system(plan, nodes, correlation, independent)
        primary_means = _primary_means(retained, primary_system, primary)
        independent_means = _primary_means(retained, independent_system, independent)
        independent_delta = float(np.max(np.abs(_effect_vector(primary_means) - _effect_vector(independent_means))))
        doubling_delta: float | None = None
        doubled_means: RegimeMeans | None = None
        if budget < 4096:
            doubled = CommonDraws.from_seed(
                seed=_draw_seed(plan.computation.seed, 8101, budget * 2),
                draw_count=budget * 2,
                mediator_count=len(_mediator_order(plan)),
            )
            doubled_system = _sobol_system(plan, nodes, correlation, doubled)
            doubled_means = _primary_means(retained, doubled_system, doubled)
            doubling_delta = float(np.max(np.abs(_effect_vector(primary_means) - _effect_vector(doubled_means))))
        accepted = independent_delta <= tolerance and (doubling_delta is None or doubling_delta <= tolerance)
        checks.append({
            "draw_count": budget,
            "independent_scramble_max_delta": independent_delta,
            "doubling_max_delta": doubling_delta,
            "accepted": accepted,
        })
        last_primary = primary
        if accepted:
            accepted_draws = primary if budget == 4096 or doubled_means is None else doubled
            accepted_budget = accepted_draws.draw_count
            diagnostics = {
                "initial_draw_count": start,
                "accepted_draw_count": accepted_budget,
                "tolerance": tolerance,
                "candidate_checks": tuple(checks),
                "independent_scramble_max_delta": independent_delta,
                "doubling_max_delta": doubling_delta,
                "status": AnalysisStatus.OK.value,
            }
            return _sobol_system(plan, nodes, correlation, accepted_draws, diagnostics)
    assert last_primary is not None
    diagnostics = {
        "initial_draw_count": start,
        "accepted_draw_count": None,
        "tolerance": tolerance,
        "candidate_checks": tuple(checks),
        "independent_scramble_max_delta": checks[-1]["independent_scramble_max_delta"],
        "doubling_max_delta": checks[-1]["doubling_max_delta"],
        "status": AnalysisStatus.INTEGRATION_FAILED.value,
    }
    issue = Issue(
        code="integration_unresolved",
        message="Sobol integration did not satisfy the configured tolerance by 4096 draws",
        status=AnalysisStatus.INTEGRATION_FAILED,
    )
    return _make_system(
        plan=plan,
        nodes=nodes,
        draws=last_primary,
        draw_budget=last_primary.draw_count,
        method="sobol_blocked",
        status=AnalysisStatus.INTEGRATION_FAILED,
        issues=(issue,),
        correlation=correlation,
        diagnostics=diagnostics,
    )


def _expanded_frame(
    block: pd.DataFrame,
    draw_count: int,
    moderator_values: Mapping[str, object],
    simulated: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    row_positions = np.repeat(np.arange(len(block)), draw_count)
    expanded = block.iloc[row_positions].copy(deep=True)
    expanded.index = pd.RangeIndex(len(expanded))
    for name, value in moderator_values.items():
        expanded[name] = value
    for name, value in simulated.items():
        array = np.asarray(value, dtype=float)
        if array.shape != (len(block), draw_count):
            raise ValueError(f"simulated mediator {name!r} has the wrong shape")
        expanded[name] = array.reshape(-1)
    return expanded


def _prepare_expanded(
    block: pd.DataFrame,
    draw_count: int,
    exposure_name: str,
    exposure: object,
    moderator_values: Mapping[str, object],
    simulated: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    expanded = _expanded_frame(block, draw_count, moderator_values, simulated)
    expanded[exposure_name] = exposure
    return expanded


def _mediator_noise(
    fitted: FittedSystem,
    draws: CommonDraws,
    row_count: int,
) -> list[np.ndarray]:
    mediator_nodes = fitted.mediator_nodes
    mediator_count = len(mediator_nodes)
    base: list[np.ndarray] = []
    for index, node in enumerate(mediator_nodes):
        family = Family(node.family)
        values = np.array(draws.for_rows(row_count, index, family), dtype=float, copy=True)
        base.append(values)
    if fitted.mediator_residual_correlation is None:
        return base
    gaussian_positions = [index for index, node in enumerate(mediator_nodes) if Family(node.family) is Family.GAUSSIAN]
    if not gaussian_positions:
        return base
    cube = np.zeros((row_count, draws.draw_count, mediator_count), dtype=float)
    for index in gaussian_positions:
        cube[:, :, index] = base[index]
    cholesky = np.linalg.cholesky(np.asarray(fitted.mediator_residual_correlation, dtype=float))
    correlated = np.einsum("bdj,kj->bdk", cube, cholesky)
    for index in gaussian_positions:
        base[index] = correlated[:, :, index]
    return base


def _iter_standardized_blocks(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
    draws: CommonDraws,
    block_size: int = BLOCK_SIZE,
) -> Iterator[pd.DataFrame]:
    """Yield complete outcome predictor frames in participant-major order."""

    _validate_standardization_inputs(plan, fitted, moderator_values, draws)
    if isinstance(block_size, bool) or not isinstance(block_size, (int, np.integer)) or block_size <= 0:
        raise ValueError("block_size must be a positive integer")
    retained = _retained_frame(data, plan)
    exposure_name = _find_exposure_name(plan)
    for start in range(0, len(retained), int(block_size)):
        block = retained.iloc[start : start + int(block_size)].copy(deep=True)
        simulated: dict[str, np.ndarray] = {}
        noises = _mediator_noise(fitted, draws, len(block))
        for index, mediator_name in enumerate(_mediator_order(plan)):
            predictors = _prepare_expanded(
                block,
                draws.draw_count,
                exposure_name,
                mediator_exposure,
                moderator_values,
                simulated,
            )
            node = fitted.node_by_response[mediator_name]
            try:
                sampled = node.sample(predictors, noises[index].reshape(-1))
            except NodeFitError as exc:
                raise _error(
                    exc.code,
                    AnalysisStatus.FIT_FAILED,
                    str(exc),
                    node=mediator_name,
                    regime=(outcome_exposure, mediator_exposure),
                    details=dict(exc.details),
                ) from exc
            simulated[mediator_name] = np.asarray(sampled, dtype=float).reshape(
                len(block), draws.draw_count
            )
        yield _prepare_expanded(
            block,
            draws.draw_count,
            exposure_name,
            outcome_exposure,
            moderator_values,
            simulated,
        )


def _find_exposure_name(plan: AnalysisPlan) -> str:
    if not plan.analysis_columns:
        raise _error("missing_exposure", AnalysisStatus.FIT_FAILED, "could not identify the declared exposure")
    # estimate_plan preserves the validated variable registry order: exposure,
    # mediators, outcome, baseline, moderators, participant id.
    return plan.analysis_columns[0]


def _validate_standardization_inputs(
    plan: AnalysisPlan,
    fitted: FittedSystem,
    moderator_values: Mapping[str, object],
    draws: CommonDraws,
) -> None:
    if not isinstance(draws, CommonDraws):
        raise _error("invalid_draws", AnalysisStatus.FIT_FAILED, "draws must be a CommonDraws instance")
    mediator_count = len(_mediator_order(plan))
    if draws.mediator_count != mediator_count:
        raise _error("invalid_draws", AnalysisStatus.FIT_FAILED, "draw mediator count does not match the plan")
    if fitted.integration_method == "sobol_blocked" and draws.draw_count != fitted.draw_budget:
        raise _error("invalid_draws", AnalysisStatus.FIT_FAILED, "draw count does not match the accepted fitted budget")
    if not set(plan.contrast.moderator_values).issubset(moderator_values):
        missing = tuple(name for name in plan.contrast.moderator_values if name not in moderator_values)
        raise _error("missing_moderators", AnalysisStatus.FIT_FAILED, "moderator_values is missing declared fixed values", details={"missing": missing})
    if not np.isfinite(draws.uniforms).all() or not np.isfinite(draws.normals).all():
        raise _error("invalid_draws", AnalysisStatus.FIT_FAILED, "draw arrays must be finite")


def _standardize_regime_with_block(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
    draws: CommonDraws,
    block_size: int,
) -> float:
    total = 0.0
    count = 0
    for outcome_frame in _iter_standardized_blocks(
        data,
        plan,
        fitted,
        outcome_exposure=outcome_exposure,
        mediator_exposure=mediator_exposure,
        moderator_values=moderator_values,
        draws=draws,
        block_size=block_size,
    ):
        try:
            outcome_mean = fitted.outcome_node.predict_mean(outcome_frame)
        except NodeFitError as exc:
            raise _error(
                exc.code,
                AnalysisStatus.FIT_FAILED,
                str(exc),
                node=fitted.outcome_node.response,
                regime=(outcome_exposure, mediator_exposure),
                details=dict(exc.details),
            ) from exc
        if outcome_mean.size == 0:
            raise _error(
                "empty_standardization",
                AnalysisStatus.FIT_FAILED,
                "standardization produced no outcome cells",
                regime=(outcome_exposure, mediator_exposure),
            )
        total += float(np.asarray(outcome_mean, dtype=float).sum())
        count += int(outcome_mean.size)
    if count == 0:
        raise _error("empty_standardization", AnalysisStatus.FIT_FAILED, "standardization produced no outcome cells")
    return total / count


def standardize_regime(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
    draws: CommonDraws,
) -> float:
    """Evaluate E[Y(a, M(b))] on the fitted outcome response scale."""

    _validate_standardization_inputs(plan, fitted, moderator_values, draws)
    if fitted.status is AnalysisStatus.INTEGRATION_FAILED:
        raise _error(
            "integration_unresolved",
            AnalysisStatus.INTEGRATION_FAILED,
            "cannot compute regime means from an unresolved integration",
        )
    if fitted.integration_method == "exact_binary_mediators":
        return _enumerate_binary_regime(
            data,
            plan,
            fitted,
            outcome_exposure=outcome_exposure,
            mediator_exposure=mediator_exposure,
            moderator_values=moderator_values,
        )
    if fitted.integration_method == "gaussian_linear_exact":
        return _gaussian_linear_regime(
            data,
            plan,
            fitted,
            outcome_exposure=outcome_exposure,
            mediator_exposure=mediator_exposure,
            moderator_values=moderator_values,
        )
    if fitted.integration_method == "gauss_hermite":
        return _gauss_hermite_regime(
            data,
            plan,
            fitted,
            outcome_exposure=outcome_exposure,
            mediator_exposure=mediator_exposure,
            moderator_values=moderator_values,
        )
    return _standardize_regime_with_block(
        data,
        plan,
        fitted,
        outcome_exposure=outcome_exposure,
        mediator_exposure=mediator_exposure,
        moderator_values=moderator_values,
        draws=draws,
        block_size=BLOCK_SIZE,
    )


def _regime_frame(row: pd.DataFrame, plan: AnalysisPlan, exposure: object, moderators: Mapping[str, object]) -> pd.DataFrame:
    frame = row.copy(deep=True)
    frame[_find_exposure_name(plan)] = exposure
    for name, value in moderators.items():
        frame[name] = value
    return frame


def _enumerate_binary_regime(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
) -> float:
    retained = _retained_frame(data, plan)
    total = 0.0
    mediator_names = _mediator_order(plan)
    for _, observed in retained.iterrows():
        row = observed.to_frame().T
        row = _regime_frame(row, plan, mediator_exposure, moderator_values)
        row_total = 0.0
        for state in product((0.0, 1.0), repeat=len(mediator_names)):
            state_probability = 1.0
            current = row.copy(deep=True)
            for name, value in zip(mediator_names, state):
                current[name] = value
                try:
                    probability = float(fitted.node_by_response[name].predict_mean(current)[0])
                except NodeFitError as exc:
                    raise _error(
                        exc.code,
                        AnalysisStatus.FIT_FAILED,
                        str(exc),
                        node=name,
                        regime=(outcome_exposure, mediator_exposure),
                        details=dict(exc.details),
                    ) from exc
                state_probability *= probability if value == 1.0 else 1.0 - probability
            outcome_frame = _regime_frame(current, plan, outcome_exposure, moderator_values)
            try:
                outcome = float(fitted.outcome_node.predict_mean(outcome_frame)[0])
            except NodeFitError as exc:
                raise _error(
                    exc.code,
                    AnalysisStatus.FIT_FAILED,
                    str(exc),
                    node=fitted.outcome_node.response,
                    regime=(outcome_exposure, mediator_exposure),
                    details=dict(exc.details),
                ) from exc
            row_total += state_probability * outcome
        total += row_total
    if len(retained) == 0:
        raise _error("empty_standardization", AnalysisStatus.FIT_FAILED, "standardization produced no outcome cells")
    return total / len(retained)


def _repeat_frame(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    positions = np.repeat(np.arange(len(frame)), int(count))
    expanded = frame.iloc[positions].copy(deep=True)
    expanded.index = pd.RangeIndex(len(expanded))
    return expanded


def _gauss_hermite_regime(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
) -> float:
    """Integrate one-Gaussian-mediator systems by fixed Hermite quadrature."""

    retained = _retained_frame(data, plan)
    errors, weights = np.polynomial.hermite.hermgauss(_GAUSS_HERMITE_ORDER)
    errors = np.sqrt(2.0) * np.asarray(errors, dtype=float)
    weights = np.asarray(weights, dtype=float) / np.sqrt(np.pi)
    exposure_name = _find_exposure_name(plan)
    total = 0.0

    for _, observed in retained.iterrows():
        row = observed.to_frame().T
        row = _regime_frame(row, plan, mediator_exposure, moderator_values)
        branches: list[tuple[pd.DataFrame, np.ndarray]] = [(row, np.ones(1, dtype=float))]
        for mediator_name in _mediator_order(plan):
            node = fitted.node_by_response[mediator_name]
            next_branches: list[tuple[pd.DataFrame, np.ndarray]] = []
            if node.family is Family.BERNOULLI:
                for frame, branch_weights in branches:
                    try:
                        probability = np.asarray(node.predict_mean(frame), dtype=float).reshape(-1)
                    except NodeFitError as exc:
                        raise _error(
                            exc.code,
                            AnalysisStatus.FIT_FAILED,
                            str(exc),
                            node=mediator_name,
                            regime=(outcome_exposure, mediator_exposure),
                            details=dict(exc.details),
                        ) from exc
                    for value in (0.0, 1.0):
                        state = frame.copy(deep=True)
                        state[mediator_name] = value
                        state_weights = branch_weights * (probability if value == 1.0 else 1.0 - probability)
                        next_branches.append((state, state_weights))
            else:
                for frame, branch_weights in branches:
                    if len(frame) != 1:
                        raise _error(
                            "quadrature_structure_failed",
                            AnalysisStatus.FIT_FAILED,
                            "Gauss-Hermite integration received more than one Gaussian mediator",
                            node=mediator_name,
                            regime=(outcome_exposure, mediator_exposure),
                        )
                    expanded = _repeat_frame(frame, _GAUSS_HERMITE_ORDER)
                    try:
                        mean = np.asarray(node.predict_mean(expanded), dtype=float).reshape(-1)
                    except NodeFitError as exc:
                        raise _error(
                            exc.code,
                            AnalysisStatus.FIT_FAILED,
                            str(exc),
                            node=mediator_name,
                            regime=(outcome_exposure, mediator_exposure),
                            details=dict(exc.details),
                        ) from exc
                    expanded[mediator_name] = mean + float(node.sigma) * errors
                    next_branches.append((expanded, branch_weights * weights))
            branches = next_branches

        for frame, branch_weights in branches:
            outcome_frame = frame.copy(deep=True)
            outcome_frame[exposure_name] = outcome_exposure
            for name, value in moderator_values.items():
                outcome_frame[name] = value
            try:
                outcome = np.asarray(fitted.outcome_node.predict_mean(outcome_frame), dtype=float).reshape(-1)
            except NodeFitError as exc:
                raise _error(
                    exc.code,
                    AnalysisStatus.FIT_FAILED,
                    str(exc),
                    node=fitted.outcome_node.response,
                    regime=(outcome_exposure, mediator_exposure),
                    details=dict(exc.details),
                ) from exc
            if outcome.shape != branch_weights.shape:
                raise _error(
                    "quadrature_shape_failed",
                    AnalysisStatus.FIT_FAILED,
                    "quadrature outcome values and weights are not aligned",
                    node=fitted.outcome_node.response,
                    regime=(outcome_exposure, mediator_exposure),
                    details={"outcome_shape": outcome.shape, "weight_shape": branch_weights.shape},
                )
            total += float(np.dot(branch_weights, outcome))

    if len(retained) == 0:
        raise _error("empty_standardization", AnalysisStatus.FIT_FAILED, "standardization produced no outcome cells")
    return total / len(retained)


def _gaussian_linear_regime(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    *,
    outcome_exposure: object,
    mediator_exposure: object,
    moderator_values: Mapping[str, object],
) -> float:
    retained = _retained_frame(data, plan)
    mediator_name = _mediator_order(plan)[0]
    mediator_frame = _regime_frame(retained, plan, mediator_exposure, moderator_values)
    try:
        mediator_mean = fitted.node_by_response[mediator_name].predict_mean(mediator_frame)
    except NodeFitError as exc:
        raise _error(
            exc.code,
            AnalysisStatus.FIT_FAILED,
            str(exc),
            node=mediator_name,
            regime=(outcome_exposure, mediator_exposure),
            details=dict(exc.details),
        ) from exc
    outcome_frame = _regime_frame(retained, plan, outcome_exposure, moderator_values)
    outcome_frame[mediator_name] = mediator_mean
    try:
        outcome_mean = fitted.outcome_node.predict_mean(outcome_frame)
    except NodeFitError as exc:
        raise _error(
            exc.code,
            AnalysisStatus.FIT_FAILED,
            str(exc),
            node=fitted.outcome_node.response,
            regime=(outcome_exposure, mediator_exposure),
            details=dict(exc.details),
        ) from exc
    return float(np.asarray(outcome_mean, dtype=float).mean())


def _compute_means_with_system(data: pd.DataFrame, fitted: FittedSystem, draws: CommonDraws) -> RegimeMeans:
    plan = fitted.plan
    moderator_values = plan.contrast.moderator_values
    reference = plan.contrast.reference
    comparison = plan.contrast.comparison
    values = (
        standardize_regime(data, plan, fitted, outcome_exposure=reference, mediator_exposure=reference, moderator_values=moderator_values, draws=draws),
        standardize_regime(data, plan, fitted, outcome_exposure=comparison, mediator_exposure=reference, moderator_values=moderator_values, draws=draws),
        standardize_regime(data, plan, fitted, outcome_exposure=comparison, mediator_exposure=comparison, moderator_values=moderator_values, draws=draws),
    )
    return RegimeMeans(*values)


def compute_regime_means(data: pd.DataFrame, plan: AnalysisPlan, fitted: FittedSystem) -> RegimeMeans:
    """Compute the primary mu_00, mu_10, and mu_11 regimes."""

    if fitted.status is AnalysisStatus.INTEGRATION_FAILED:
        raise _error(
            "integration_unresolved",
            AnalysisStatus.INTEGRATION_FAILED,
            "cannot compute regime means from an unresolved integration",
        )
    if fitted.integration_method == "sobol_blocked":
        if fitted.draws is None or fitted.draws.draw_count != fitted.draw_budget:
            raise _error("invalid_draws", AnalysisStatus.FIT_FAILED, "fitted Sobol draws do not match the accepted budget")
        return _compute_means_with_system(data, fitted, fitted.draws)
    draws = CommonDraws.from_seed(
        seed=fitted.plan.computation.seed,
        draw_count=1,
        mediator_count=len(_mediator_order(fitted.plan)),
    )
    return _compute_means_with_system(data, fitted, draws)


__all__ = [
    "CommonDraws",
    "FittedSystem",
    "GFormulaError",
    "compute_regime_means",
    "fit_system",
    "standardize_regime",
]
