"""Structural-equation fixtures kept independent from fitted estimators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd
from scipy.special import expit

from mintmed.spec import (
    ComputationSpec,
    ContrastSpec,
    Family,
    InteractionSpec,
    ModelSpec,
    NodeSpec,
    Role,
    TemplateSpec,
    TermKind,
    TermSpec,
    VariableSpec,
    compile_template,
)


_FIXTURE_NAMES = (
    "linear",
    "quadratic_b",
    "cancellation",
    "interaction",
    "ushape_a",
    "serial_two",
    "serial_three",
    "parallel_correlated",
    "binary_two_mediators",
    "moderated_serial",
    "binary_mediator_gaussian_outcome",
    "mixed_binary_serial",
    "four_mediator_mixed",
    "sparse_events",
    "tied_score",
    "missingness",
    "opposing_paths",
)


class _FrozenDict(dict[str, Any]):
    """A dict-compatible mapping that rejects all mutation operations."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("mapping is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, np.ndarray):
        return tuple(_freeze_value(item) for item in value.tolist())
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return _FrozenDict({key: _freeze_value(item) for key, item in value.items()})


@dataclass(frozen=True, slots=True)
class SimulationFixture:
    """Generated observations, declared model, and population effect truth."""

    name: str
    data: pd.DataFrame
    spec: ModelSpec
    truth: tuple[float, float, float]
    truth_method: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if len(self.truth) != 3:
            raise ValueError("truth must contain TE, PNDE, and TNIE")
        object.__setattr__(self, "truth", tuple(float(value) for value in self.truth))
        object.__setattr__(self, "data", self.data.copy(deep=True))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


def _variable(
    name: str,
    role: Role,
    observed_type: str = "continuous",
    *,
    family: Family | None = None,
    levels: tuple[Any, ...] = (),
) -> VariableSpec:
    return VariableSpec(
        name=name,
        role=role,
        observed_type=observed_type,
        levels=levels,
        family=family,
    )


def _node(
    response: str,
    family: Family,
    terms: tuple[tuple[str, TermKind], ...],
    interactions: tuple[tuple[str, str], ...] = (),
) -> NodeSpec:
    return NodeSpec(
        response=response,
        family=family,
        intercept=True,
        terms=tuple(TermSpec(variable, kind) for variable, kind in terms),
        interactions=tuple(InteractionSpec(left, right) for left, right in interactions),
    )


def _linear_terms(*variables: str) -> tuple[tuple[str, TermKind], ...]:
    return tuple((variable, TermKind.LINEAR) for variable in variables)


def _fixture_template(
    *,
    exposure: VariableSpec,
    outcome: VariableSpec,
    mediators: tuple[VariableSpec, ...],
    nodes: tuple[NodeSpec, ...],
    edges: tuple[tuple[str, str], ...],
    mediator_order: tuple[str, ...],
    baseline: tuple[VariableSpec, ...] = (),
    moderators: tuple[VariableSpec, ...] = (),
    arrangement: str = "parallel",
    missing: str = "error",
    moderator_values: Mapping[str, Any] | None = None,
) -> ModelSpec:
    template = TemplateSpec(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        nodes=nodes,
        contrast=ContrastSpec(
            reference=0,
            comparison=1,
            moderator_values=moderator_values or {},
        ),
        computation=ComputationSpec(
            seed=20260919,
            bootstrap=0,
            integration_draws=256,
            integration_tolerance=1e-8,
        ),
        baseline=baseline,
        moderators=moderators,
        scientific_edges=edges,
        mediator_order=mediator_order,
        arrangement=arrangement,
        missing=missing,
    )
    return compile_template(template)


def _single_gaussian_spec(
    *,
    mediator_terms: tuple[tuple[str, TermKind], ...] | None = None,
    outcome_terms: tuple[tuple[str, TermKind], ...] | None = None,
    outcome_interactions: tuple[tuple[str, str], ...] = (),
    missing: str = "error",
) -> ModelSpec:
    exposure = _variable("A", Role.EXPOSURE)
    mediator = _variable("M", Role.MEDIATOR, family=Family.GAUSSIAN)
    outcome = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    return _fixture_template(
        exposure=exposure,
        outcome=outcome,
        mediators=(mediator,),
        nodes=(
            _node("M", Family.GAUSSIAN, mediator_terms or _linear_terms("A")),
            _node(
                "Y",
                Family.GAUSSIAN,
                outcome_terms or _linear_terms("A", "M"),
                outcome_interactions,
            ),
        ),
        edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        mediator_order=("M",),
        arrangement="parallel",
        missing=missing,
    )


def _continuous_exposure(rng: np.random.Generator, n: int) -> np.ndarray:
    values = rng.standard_normal(n)
    values[0], values[1] = 0.0, 1.0
    return values


def _binary_exposure(rng: np.random.Generator, n: int) -> np.ndarray:
    values = rng.integers(0, 2, size=n).astype(float)
    values[0], values[1] = 0.0, 1.0
    return values


def _binary_draw(rng: np.random.Generator, probability: np.ndarray) -> np.ndarray:
    return (rng.random(len(probability)) < probability).astype(float)


def _three_means(mu: Callable[[float, float], float]) -> tuple[float, float, float]:
    mu00 = mu(0.0, 0.0)
    mu10 = mu(1.0, 0.0)
    mu11 = mu(1.0, 1.0)
    return (mu11 - mu00, mu10 - mu00, mu11 - mu10)


def _linear_data(rng: np.random.Generator, n: int) -> pd.DataFrame:
    exposure = _continuous_exposure(rng, n)
    mediator = 0.7 * exposure + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.6 * mediator + rng.standard_normal(n)
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome})


def _linear_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    return _linear_data(rng, n), _single_gaussian_spec(), {}


def _quadratic_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    mediator = 0.7 * exposure + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.5 * mediator**2 + rng.standard_normal(n)
    spec = _single_gaussian_spec(
        outcome_terms=(
            ("A", TermKind.LINEAR),
            ("M", TermKind.QUADRATIC),
        )
    )
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), spec, {}


def _cancellation_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    mediator = exposure + rng.standard_normal(n)
    outcome = mediator - exposure + rng.standard_normal(n)
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), _single_gaussian_spec(), {}


def _interaction_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    mediator = 0.7 * exposure + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.6 * mediator + 0.4 * exposure * mediator + rng.standard_normal(n)
    spec = _single_gaussian_spec(outcome_interactions=(("A", "M"),))
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), spec, {}


def _ushape_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    k = 0.8 / np.sqrt(2.0)
    mediator = k * (exposure**2 - 1.0) + 0.6 * rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.6 * mediator + rng.standard_normal(n)
    spec = _single_gaussian_spec(mediator_terms=(("A", TermKind.QUADRATIC),))
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), spec, {}


def _serial_spec(
    mediator_variables: tuple[VariableSpec, ...],
    nodes: tuple[NodeSpec, ...],
    edges: tuple[tuple[str, str], ...],
    outcome: VariableSpec,
) -> ModelSpec:
    return _fixture_template(
        exposure=_variable("A", Role.EXPOSURE),
        outcome=outcome,
        mediators=mediator_variables,
        nodes=nodes,
        edges=edges,
        mediator_order=tuple(variable.name for variable in mediator_variables),
        arrangement="sequential",
    )


def _serial_two_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    m1 = 0.6 * exposure + rng.standard_normal(n)
    m2 = 0.4 * exposure + 0.5 * m1 + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.3 * m1 + 0.7 * m2 + rng.standard_normal(n)
    mediators = (
        _variable("M1", Role.MEDIATOR, family=Family.GAUSSIAN),
        _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
    )
    outcome_spec = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    nodes = (
        _node("M1", Family.GAUSSIAN, _linear_terms("A")),
        _node("M2", Family.GAUSSIAN, _linear_terms("A", "M1")),
        _node("Y", Family.GAUSSIAN, _linear_terms("A", "M1", "M2")),
    )
    edges = (("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"))
    spec = _serial_spec(mediators, nodes, edges, outcome_spec)
    data = pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "Y": outcome})
    return data, spec, {}


def _serial_three_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    m1 = 0.5 * exposure + rng.standard_normal(n)
    m2 = 0.3 * exposure + 0.4 * m1 + rng.standard_normal(n)
    m3 = 0.2 * exposure + 0.3 * m1 + 0.5 * m2 + rng.standard_normal(n)
    outcome = 0.1 * exposure + 0.2 * m1 + 0.3 * m2 + 0.4 * m3 + rng.standard_normal(n)
    mediators = tuple(_variable(name, Role.MEDIATOR, family=Family.GAUSSIAN) for name in ("M1", "M2", "M3"))
    outcome_spec = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    nodes = (
        _node("M1", Family.GAUSSIAN, _linear_terms("A")),
        _node("M2", Family.GAUSSIAN, _linear_terms("A", "M1")),
        _node("M3", Family.GAUSSIAN, _linear_terms("A", "M1", "M2")),
        _node("Y", Family.GAUSSIAN, _linear_terms("A", "M1", "M2", "M3")),
    )
    edges = (
        ("A", "M1"), ("A", "M2"), ("M1", "M2"),
        ("A", "M3"), ("M1", "M3"), ("M2", "M3"),
        ("A", "Y"), ("M1", "Y"), ("M2", "Y"), ("M3", "Y"),
    )
    spec = _serial_spec(mediators, nodes, edges, outcome_spec)
    data = pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "M3": m3, "Y": outcome})
    return data, spec, {}


def _parallel_correlated_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    errors = rng.multivariate_normal(np.zeros(2), np.array([[1.0, 0.65], [0.65, 1.0]]), size=n)
    m1 = 0.5 * exposure + errors[:, 0]
    m2 = -0.3 * exposure + errors[:, 1]
    outcome = 0.15 * exposure + 0.4 * m1 + 0.6 * m2 + 0.2 * m1 * m2 + rng.standard_normal(n)
    mediators = (
        _variable("M1", Role.MEDIATOR, family=Family.GAUSSIAN),
        _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
    )
    outcome_spec = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    nodes = (
        _node("M1", Family.GAUSSIAN, _linear_terms("A")),
        _node("M2", Family.GAUSSIAN, _linear_terms("A")),
        _node(
            "Y",
            Family.GAUSSIAN,
            _linear_terms("A", "M1", "M2"),
            (("M1", "M2"),),
        ),
    )
    edges = (("A", "M1"), ("A", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"))
    spec = _fixture_template(
        exposure=_variable("A", Role.EXPOSURE),
        outcome=outcome_spec,
        mediators=mediators,
        nodes=nodes,
        edges=edges,
        mediator_order=("M1", "M2"),
        arrangement="parallel",
    )
    data = pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "Y": outcome})
    metadata = {"rho": 0.65, "covariance": ((1.0, 0.65), (0.65, 1.0))}
    return data, spec, metadata


def _binary_two_spec() -> ModelSpec:
    exposure = _variable("A", Role.EXPOSURE, "binary", levels=(0, 1))
    mediators = (
        _variable("M1", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),
        _variable("M2", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),
    )
    outcome = _variable("Y", Role.OUTCOME, "binary", family=Family.BERNOULLI, levels=(0, 1))
    nodes = (
        _node("M1", Family.BERNOULLI, _linear_terms("A")),
        _node("M2", Family.BERNOULLI, _linear_terms("A", "M1")),
        _node("Y", Family.BERNOULLI, _linear_terms("A", "M1", "M2")),
    )
    edges = (("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"))
    return _fixture_template(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        nodes=nodes,
        edges=edges,
        mediator_order=("M1", "M2"),
        arrangement="sequential",
    )


def _binary_two_mediators_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    p1 = expit(-0.4 + 0.8 * exposure)
    m1 = _binary_draw(rng, p1)
    p2 = expit(-0.2 + 0.5 * exposure + 0.7 * m1)
    m2 = _binary_draw(rng, p2)
    p_y = expit(-0.5 + 0.2 * exposure + 0.4 * m1 + 0.6 * m2)
    outcome = _binary_draw(rng, p_y)
    data = pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "Y": outcome})
    return data, _binary_two_spec(), {}


def _binary_two_mu(a: float, b: float) -> float:
    p1 = expit(-0.4 + 0.8 * b)
    total = 0.0
    for m1 in (0.0, 1.0):
        p_m1 = p1 if m1 else 1.0 - p1
        p2 = expit(-0.2 + 0.5 * b + 0.7 * m1)
        for m2 in (0.0, 1.0):
            p_m2 = p2 if m2 else 1.0 - p2
            total += p_m1 * p_m2 * expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.6 * m2)
    return float(total)


def _binary_mediator_gaussian_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    mediator = _binary_draw(rng, expit(-0.4 + 0.8 * exposure))
    outcome = 0.2 * exposure + 0.6 * mediator + rng.standard_normal(n)
    spec = _fixture_template(
        exposure=_variable("A", Role.EXPOSURE, "binary", levels=(0, 1)),
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=(_variable("M", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),),
        nodes=(
            _node("M", Family.BERNOULLI, _linear_terms("A")),
            _node("Y", Family.GAUSSIAN, _linear_terms("A", "M")),
        ),
        edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        mediator_order=("M",),
    )
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), spec, {}


def _moderated_spec() -> ModelSpec:
    exposure = _variable("A", Role.EXPOSURE, "binary", levels=(0, 1))
    baseline = (_variable("C", Role.COVARIATE),)
    moderators = (_variable("W", Role.MODERATOR, "binary", levels=(0, 1)),)
    mediators = (
        _variable("M1", Role.MEDIATOR, family=Family.GAUSSIAN),
        _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
    )
    outcome = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    nodes = (
        _node(
            "M1",
            Family.GAUSSIAN,
            _linear_terms("A", "W", "C"),
            (("W", "A"),),
        ),
        _node("M2", Family.GAUSSIAN, _linear_terms("A", "M1", "C")),
        _node(
            "Y",
            Family.GAUSSIAN,
            _linear_terms("A", "W", "C", "M1", "M2"),
            (("W", "M1"), ("W", "M2")),
        ),
    )
    edges = (("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"))
    return _fixture_template(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        nodes=nodes,
        edges=edges,
        mediator_order=("M1", "M2"),
        baseline=baseline,
        moderators=moderators,
        arrangement="sequential",
        moderator_values={"W": 0.0},
    )


def _moderated_serial_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    moderator = _binary_exposure(rng, n)
    baseline = rng.standard_normal(n)
    m1 = (0.3 + 0.3 * moderator) * exposure + 0.2 * moderator + 0.3 * baseline + rng.standard_normal(n)
    m2 = 0.2 * exposure + 0.4 * m1 + 0.3 * baseline + rng.standard_normal(n)
    outcome = (
        0.2 * exposure
        + (0.3 + 0.3 * moderator) * m1
        + (0.2 + 0.2 * moderator) * m2
        + 0.2 * moderator
        + 0.3 * baseline
        + rng.standard_normal(n)
    )
    data = pd.DataFrame({"A": exposure, "W": moderator, "C": baseline, "M1": m1, "M2": m2, "Y": outcome})
    metadata = {
        "truth_by_moderator": ((0.0, _moderated_truth(0.0)), (1.0, _moderated_truth(1.0))),
    }
    return data, _moderated_spec(), metadata


def _moderated_mu(a: float, b: float, w: float) -> float:
    m1 = (0.3 + 0.3 * w) * b + 0.2 * w
    m2 = 0.2 * b + 0.4 * m1
    return 0.2 * a + (0.3 + 0.3 * w) * m1 + (0.2 + 0.2 * w) * m2 + 0.2 * w


def _mixed_binary_serial_spec() -> ModelSpec:
    exposure = _variable("A", Role.EXPOSURE, "binary", levels=(0, 1))
    mediators = (
        _variable("M1", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),
        _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
    )
    outcome = _variable("Y", Role.OUTCOME, "binary", family=Family.BERNOULLI, levels=(0, 1))
    nodes = (
        _node("M1", Family.BERNOULLI, _linear_terms("A")),
        _node("M2", Family.GAUSSIAN, _linear_terms("A", "M1")),
        _node("Y", Family.BERNOULLI, _linear_terms("A", "M1", "M2")),
    )
    edges = (("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"))
    return _fixture_template(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        nodes=nodes,
        edges=edges,
        mediator_order=("M1", "M2"),
        arrangement="sequential",
    )


def _mixed_binary_serial_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    m1 = _binary_draw(rng, expit(-0.4 + 0.8 * exposure))
    m2 = 0.3 * exposure + 0.5 * m1 + rng.standard_normal(n)
    outcome = _binary_draw(rng, expit(-0.5 + 0.2 * exposure + 0.4 * m1 + 0.4 * m2))
    return (
        pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "Y": outcome}),
        _mixed_binary_serial_spec(),
        {"quadrature_order": 64},
    )


def _mixed_binary_mu(a: float, b: float) -> float:
    nodes, weights = np.polynomial.hermite.hermgauss(64)
    p1 = expit(-0.4 + 0.8 * b)
    total = 0.0
    for m1 in (0.0, 1.0):
        p_m1 = p1 if m1 else 1.0 - p1
        m2 = 0.3 * b + 0.5 * m1 + np.sqrt(2.0) * nodes
        probabilities = expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.4 * m2)
        total += p_m1 * float(np.dot(weights, probabilities) / np.sqrt(np.pi))
    return float(total)


def _four_mediator_spec() -> ModelSpec:
    exposure = _variable("A", Role.EXPOSURE, "binary", levels=(0, 1))
    mediators = (
        _variable("M1", Role.MEDIATOR, family=Family.GAUSSIAN),
        _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
        _variable("M3", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),
        _variable("M4", Role.MEDIATOR, family=Family.GAUSSIAN),
    )
    outcome = _variable("Y", Role.OUTCOME, family=Family.GAUSSIAN)
    nodes = (
        _node("M1", Family.GAUSSIAN, _linear_terms("A")),
        _node("M2", Family.GAUSSIAN, _linear_terms("A", "M1")),
        _node("M3", Family.BERNOULLI, _linear_terms("A")),
        _node("M4", Family.GAUSSIAN, _linear_terms("A", "M1", "M2", "M3")),
        _node("Y", Family.GAUSSIAN, _linear_terms("A", "M1", "M2", "M3", "M4")),
    )
    edges = (
        ("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "M3"),
        ("A", "M4"), ("M1", "M4"), ("M2", "M4"), ("M3", "M4"),
        ("A", "Y"), ("M1", "Y"), ("M2", "Y"), ("M3", "Y"), ("M4", "Y"),
    )
    return _fixture_template(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        nodes=nodes,
        edges=edges,
        mediator_order=("M1", "M2", "M3", "M4"),
        arrangement="sequential",
    )


def _four_mediator_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    m1 = 0.4 * exposure + rng.standard_normal(n)
    m2 = 0.2 * exposure + 0.3 * m1 + rng.standard_normal(n)
    m3 = _binary_draw(rng, expit(-0.3 + 0.6 * exposure))
    m4 = 0.1 * exposure + 0.2 * m1 + 0.3 * m2 + 0.4 * m3 + rng.standard_normal(n)
    outcome = 0.1 * exposure + 0.2 * m1 + 0.3 * m2 + 0.4 * m3 + 0.5 * m4 + rng.standard_normal(n)
    metadata = {"mediator_count": 4, "mixed_families": True}
    data = pd.DataFrame({"A": exposure, "M1": m1, "M2": m2, "M3": m3, "M4": m4, "Y": outcome})
    return data, _four_mediator_spec(), metadata


def _binary_mediator_gaussian_truth(a: float, b: float) -> float:
    return float(0.2 * a + 0.6 * expit(-0.4 + 0.8 * b))


def _moderated_truth(w: float) -> tuple[float, float, float]:
    return _three_means(lambda a, b: _moderated_mu(a, b, w))


def _four_mediator_truth(a: float, b: float) -> float:
    m1 = 0.4 * b
    m2 = 0.2 * b + 0.3 * m1
    m3 = expit(-0.3 + 0.6 * b)
    m4 = 0.1 * b + 0.2 * m1 + 0.3 * m2 + 0.4 * m3
    return float(0.1 * a + 0.2 * m1 + 0.3 * m2 + 0.4 * m3 + 0.5 * m4)


def _sparse_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _binary_exposure(rng, n)
    probabilities = expit(-4.0 + 0.5 * exposure)
    mediator = _binary_draw(rng, probabilities)
    outcome = 0.2 * exposure + 0.6 * mediator + rng.standard_normal(n)
    spec = _fixture_template(
        exposure=_variable("A", Role.EXPOSURE, "binary", levels=(0, 1)),
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=(_variable("M", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),),
        nodes=(_node("M", Family.BERNOULLI, _linear_terms("A")), _node("Y", Family.GAUSSIAN, _linear_terms("A", "M"))),
        edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        mediator_order=("M",),
    )
    metadata = {"event_probability": (float(expit(-4.0)), float(expit(-3.5)))}
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), spec, metadata


def _tied_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = rng.integers(0, 3, size=n).astype(float)
    exposure[0], exposure[1] = 0.0, 1.0
    mediator = 0.7 * exposure + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.6 * mediator + rng.standard_normal(n)
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), _single_gaussian_spec(), {"tie_values": (0.0, 1.0, 2.0)}


def _missing_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    data = _linear_data(rng, n)
    m_rows = tuple(range(0, n, 7))
    y_rows = tuple(range(0, n, 11))
    data.loc[list(m_rows), "M"] = np.nan
    data.loc[list(y_rows), "Y"] = np.nan
    spec = _single_gaussian_spec(missing="complete_case")
    metadata = {"missing_columns": ("M", "Y"), "missing_rows": {"M": m_rows, "Y": y_rows}}
    return data, spec, metadata


def _opposing_fixture(rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]:
    exposure = _continuous_exposure(rng, n)
    mediator = 1.4 * exposure + rng.standard_normal(n)
    outcome = -1.5 * exposure + (1.5 / 1.4) * mediator + rng.standard_normal(n)
    return pd.DataFrame({"A": exposure, "M": mediator, "Y": outcome}), _single_gaussian_spec(), {}


_GENERATORS: Mapping[str, Callable[[np.random.Generator, int], tuple[pd.DataFrame, ModelSpec, Mapping[str, Any]]]] = {
    "linear": _linear_fixture,
    "quadratic_b": _quadratic_fixture,
    "cancellation": _cancellation_fixture,
    "interaction": _interaction_fixture,
    "ushape_a": _ushape_fixture,
    "serial_two": _serial_two_fixture,
    "serial_three": _serial_three_fixture,
    "parallel_correlated": _parallel_correlated_fixture,
    "binary_two_mediators": _binary_two_mediators_fixture,
    "moderated_serial": _moderated_serial_fixture,
    "binary_mediator_gaussian_outcome": _binary_mediator_gaussian_fixture,
    "mixed_binary_serial": _mixed_binary_serial_fixture,
    "four_mediator_mixed": _four_mediator_fixture,
    "sparse_events": _sparse_fixture,
    "tied_score": _tied_fixture,
    "missingness": _missing_fixture,
    "opposing_paths": _opposing_fixture,
}


def _truth_linear() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.2 * a + 0.42 * b)


def _truth_quadratic() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.2 * a + 0.5 * (0.49 * b**2 + 1.0))


def _truth_cancellation() -> tuple[float, float, float]:
    return _three_means(lambda a, b: b - a)


def _truth_interaction() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.2 * a + 0.7 * b * (0.6 + 0.4 * a))


def _truth_ushape() -> tuple[float, float, float]:
    k = 0.8 / np.sqrt(2.0)
    return _three_means(lambda a, b: 0.2 * a + 0.6 * k * (b**2 - 1.0))


def _truth_serial_two() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.2 * a + 0.67 * b)


def _truth_serial_three() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.1 * a + 0.49 * b)


def _truth_parallel_correlated() -> tuple[float, float, float]:
    return _three_means(
        lambda a, b: 0.15 * a + 0.4 * (0.5 * b) + 0.6 * (-0.3 * b) + 0.2 * (-0.15 * b**2 + 0.65)
    )


def _truth_binary_two() -> tuple[float, float, float]:
    return _three_means(_binary_two_mu)


def _truth_moderated() -> tuple[float, float, float]:
    return _moderated_truth(0.0)


def _truth_binary_mediator_gaussian() -> tuple[float, float, float]:
    return _three_means(_binary_mediator_gaussian_truth)


def _truth_mixed_binary() -> tuple[float, float, float]:
    return _three_means(_mixed_binary_mu)


def _truth_four_mediator() -> tuple[float, float, float]:
    return _three_means(_four_mediator_truth)


def _truth_sparse() -> tuple[float, float, float]:
    return _three_means(lambda a, b: 0.2 * a + 0.6 * expit(-4.0 + 0.5 * b))


def _truth_opposing() -> tuple[float, float, float]:
    return _three_means(lambda a, b: -1.5 * a + (1.5 / 1.4) * (1.4 * b))


_TRUTHS: Mapping[str, Callable[[], tuple[float, float, float]]] = {
    "linear": _truth_linear,
    "quadratic_b": _truth_quadratic,
    "cancellation": _truth_cancellation,
    "interaction": _truth_interaction,
    "ushape_a": _truth_ushape,
    "serial_two": _truth_serial_two,
    "serial_three": _truth_serial_three,
    "parallel_correlated": _truth_parallel_correlated,
    "binary_two_mediators": _truth_binary_two,
    "moderated_serial": _truth_moderated,
    "binary_mediator_gaussian_outcome": _truth_binary_mediator_gaussian,
    "mixed_binary_serial": _truth_mixed_binary,
    "four_mediator_mixed": _truth_four_mediator,
    "sparse_events": _truth_sparse,
    "tied_score": _truth_linear,
    "missingness": _truth_linear,
    "opposing_paths": _truth_opposing,
}


_TRUTH_METHODS = {
    "binary_two_mediators": "exact_enumeration",
    "mixed_binary_serial": "gauss_hermite_64",
}


def _validate_name(name: str) -> None:
    if name not in _FIXTURE_NAMES:
        raise ValueError(f"unknown simulation fixture {name!r}")


def _validate_size(n: int) -> None:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n <= 1:
        raise ValueError("n must be an integer greater than one")


def sample_fixture(name: str, n: int, rng: np.random.Generator) -> SimulationFixture:
    """Generate one named fixture using only the supplied NumPy generator."""

    _validate_name(name)
    _validate_size(n)
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    data, spec, metadata = _GENERATORS[name](rng, int(n))
    return SimulationFixture(
        name=name,
        data=data,
        spec=spec,
        truth=_TRUTHS[name](),
        truth_method=_TRUTH_METHODS.get(name, "closed_form"),
        metadata=metadata,
    )


def analytic_effects(name: str) -> tuple[float, float, float]:
    """Return the audited population effects for the ``0 -> 1`` contrast."""

    _validate_name(name)
    return tuple(float(value) for value in _TRUTHS[name]())


__all__ = ["SimulationFixture", "analytic_effects", "sample_fixture"]
