"""Deterministic, resumable validation runner for the frozen mediation matrix.

The module deliberately keeps configuration and cell identity independent from
filesystem layout.  Later sections of the module add the fixed generators and
execution boundary; these first-level contracts are kept small so shard tools
can inspect a design without importing or fitting a model.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.special import expit

from ..simulation.mediation import SimulationFixture
from ..spec import (
    ComputationSpec,
    ContrastSpec,
    Family,
    InteractionSpec,
    NodeSpec,
    Role,
    TemplateSpec,
    TermKind,
    TermSpec,
    VariableSpec,
    compile_template,
)

COMBINATION_COLUMNS: tuple[str, str] = ("cell_id", "replicate")
RAW_COLUMNS: tuple[str, ...] = (
    "cell_id",
    "replicate",
    "data_seed",
    "analysis_seed",
    "config_hash",
    "truth_method",
    "outcome_kind",
    "estimand",
    "truth",
    "estimate",
    "bias",
    "lower",
    "upper",
    "coverage",
    "width",
    "zero_exclusion",
    "interval_available",
    "status",
    "failure_code",
    "failure_message",
    "runtime_seconds",
    "fit_count",
    "draw_budget",
    "metrics_json",
    "provenance_json",
)
EVIDENCE_ARTIFACTS: tuple[str, ...] = (
    "raw_metrics.csv",
    "cell_summary.csv",
    "summary.json",
    "report.md",
)

_CONFIG_KEYS = {
    "schema_version",
    "experiment",
    "master_seed",
    "replicates",
    "bootstrap_replicates",
    "bootstrap_mode",
    "integration_draws",
    "integration_tolerance",
    "max_seconds",
    "memory_budget_mb",
    "cell_ids",
    "stress",
    "gates",
}
_STRESS_KEYS = {"enabled", "replicates", "sample_size", "fixture_names"}
_GATE_KEYS = {
    "continuous_abs_bias_sd",
    "binary_abs_bias_probability",
    "coverage_wilson_lower",
    "null_false_zero_wilson_upper",
    "unavailable_or_fatal_max",
}
_DRAW_BUDGETS = {256, 512, 1024, 2048, 4096}
_BOOTSTRAP_MODES = {"standard", "quick_diagnostic"}
_STRESS_FIXTURES = {"tied_score", "sparse_events", "missingness", "opposing_paths"}


@dataclass(frozen=True, slots=True)
class ValidationCell:
    """Stable identity and scientific contract for one locked validation cell."""

    cell_id: str
    ordinal: int
    n: int
    generator_name: str = ""
    outcome_kind: str = "continuous"
    metric_names: tuple[str, ...] = ("TE", "PNDE", "TNIE")
    truth_method: str = "closed_form"
    population_outcome_sd: float | None = None


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Validated, output-independent design configuration."""

    schema_version: int
    experiment: str
    master_seed: int
    replicates: int
    bootstrap_replicates: int
    bootstrap_mode: str
    integration_draws: int
    integration_tolerance: float
    max_seconds: int
    memory_budget_mb: int
    cell_ids: tuple[str, ...]
    stress_enabled: bool
    stress_replicates: int
    stress_sample_size: int
    stress_fixture_names: tuple[str, ...]
    gates: tuple[tuple[str, float], ...]
    source_path: Path | None = None

    @property
    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment": self.experiment,
            "master_seed": self.master_seed,
            "replicates": self.replicates,
            "bootstrap_replicates": self.bootstrap_replicates,
            "bootstrap_mode": self.bootstrap_mode,
            "integration_draws": self.integration_draws,
            "integration_tolerance": self.integration_tolerance,
            "max_seconds": self.max_seconds,
            "memory_budget_mb": self.memory_budget_mb,
            "cell_ids": list(self.cell_ids),
            "stress": {
                "enabled": self.stress_enabled,
                "replicates": self.stress_replicates,
                "sample_size": self.stress_sample_size,
                "fixture_names": list(self.stress_fixture_names),
            },
            "gates": dict(self.gates),
        }

    @property
    def config_hash(self) -> str:
        encoded = json.dumps(
            self.canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")  # noqa: TRY004
    return value


def _required_int(raw: Mapping[str, Any], key: str, *, minimum: int) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}")
    return int(value)


def _required_float(raw: Mapping[str, Any], key: str, *, minimum: float) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a finite number >= {minimum}")  # noqa: TRY004
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{key} must be a finite number >= {minimum}")
    return result


def load_config(path: Path) -> ValidationConfig:
    """Load and strictly validate one frozen validation design."""

    source = Path(path)
    try:
        raw_value = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"could not load validation configuration: {exc}") from exc
    raw = _require_mapping(raw_value, "configuration root")
    unknown = set(raw) - _CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown configuration key(s): {', '.join(sorted(unknown))}")

    schema_version = _required_int(raw, "schema_version", minimum=1)
    experiment = raw.get("experiment")
    if not isinstance(experiment, str) or not experiment.strip():
        raise ValueError("experiment must be a nonempty string")
    master_seed = _required_int(raw, "master_seed", minimum=0)
    replicates = _required_int(raw, "replicates", minimum=1)
    bootstrap_replicates = _required_int(raw, "bootstrap_replicates", minimum=0)
    bootstrap_mode = raw.get("bootstrap_mode")
    if bootstrap_mode not in _BOOTSTRAP_MODES:
        raise ValueError("bootstrap_mode must be standard or quick_diagnostic")
    integration_draws = _required_int(raw, "integration_draws", minimum=1)
    if integration_draws not in _DRAW_BUDGETS:
        raise ValueError(f"integration_draws must be one of {sorted(_DRAW_BUDGETS)}")
    integration_tolerance = _required_float(raw, "integration_tolerance", minimum=0.0)
    if integration_tolerance <= 0.0:
        raise ValueError("integration_tolerance must be positive")
    max_seconds = _required_int(raw, "max_seconds", minimum=1)
    memory_budget_mb = _required_int(raw, "memory_budget_mb", minimum=1)

    cell_values = raw.get("cell_ids")
    if not isinstance(cell_values, (list, tuple)) or not cell_values:
        raise ValueError("cell_ids must be a nonempty sequence")
    if any(not isinstance(value, str) for value in cell_values):
        raise ValueError("cell_ids must contain strings")
    cell_ids = tuple(cell_values)
    if len(set(cell_ids)) != len(cell_ids):
        raise ValueError("cell_ids contains duplicate cell IDs")
    unknown_cells = set(cell_ids) - set(_CELL_BY_ID)
    if unknown_cells:
        raise ValueError(f"unknown cell ID(s): {', '.join(sorted(unknown_cells))}")

    stress = _require_mapping(raw.get("stress"), "stress")
    stress_unknown = set(stress) - _STRESS_KEYS
    if stress_unknown:
        raise ValueError(f"unknown stress key(s): {', '.join(sorted(stress_unknown))}")
    stress_enabled = stress.get("enabled")
    if not isinstance(stress_enabled, bool):
        raise ValueError("stress.enabled must be boolean")  # noqa: TRY004
    stress_replicates = _required_int(stress, "replicates", minimum=0)
    stress_sample_size = _required_int(stress, "sample_size", minimum=2)
    fixture_values = stress.get("fixture_names")
    if not isinstance(fixture_values, (list, tuple)):
        raise ValueError("stress.fixture_names must be a sequence")  # noqa: TRY004
    stress_fixture_names = tuple(fixture_values)
    if any(not isinstance(value, str) for value in stress_fixture_names):
        raise ValueError("stress.fixture_names must contain strings")
    unknown_fixtures = set(stress_fixture_names) - _STRESS_FIXTURES
    if unknown_fixtures:
        raise ValueError(f"unknown stress fixture(s): {', '.join(sorted(unknown_fixtures))}")

    gates = _require_mapping(raw.get("gates"), "gates")
    gate_unknown = set(gates) - _GATE_KEYS
    if gate_unknown:
        raise ValueError(f"unknown gate key(s): {', '.join(sorted(gate_unknown))}")
    if set(gates) != _GATE_KEYS:
        raise ValueError("gates must declare every frozen gate")
    gate_values = tuple(
        (key, _required_float(gates, key, minimum=0.0))
        for key in sorted(_GATE_KEYS)
    )
    gate_map = dict(gate_values)
    for key in ("coverage_wilson_lower", "null_false_zero_wilson_upper", "unavailable_or_fatal_max"):
        if gate_map[key] > 1.0:
            raise ValueError(f"{key} must be between 0 and 1")
    return ValidationConfig(
        schema_version=schema_version,
        experiment=experiment,
        master_seed=master_seed,
        replicates=replicates,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_mode=str(bootstrap_mode),
        integration_draws=integration_draws,
        integration_tolerance=integration_tolerance,
        max_seconds=max_seconds,
        memory_budget_mb=memory_budget_mb,
        cell_ids=cell_ids,
        stress_enabled=stress_enabled,
        stress_replicates=stress_replicates,
        stress_sample_size=stress_sample_size,
        stress_fixture_names=stress_fixture_names,
        gates=gate_values,
        source_path=source.resolve(),
    )


def expected_combinations(config: ValidationConfig) -> set[tuple[str, int]]:
    """Return the complete two-key grid expected by shard aggregation."""

    return {
        (cell_id, replicate)
        for cell_id in config.cell_ids
        for replicate in range(config.replicates)
    }


def expected_row_count(config: ValidationConfig) -> int:
    return len(expected_combinations(config))


def seed_pair(master_seed: int, cell_ordinal: int, replicate: int) -> tuple[int, int]:
    """Return stable data and analysis seeds for one matrix combination."""

    if cell_ordinal < 1 or replicate < 0:
        raise ValueError("cell_ordinal must be positive and replicate nonnegative")
    data = np.random.SeedSequence(
        [int(master_seed), 1300, 1, int(cell_ordinal), int(replicate)]
    ).generate_state(1, dtype=np.uint64)[0]
    analysis = np.random.SeedSequence(
        [int(master_seed), 1300, 2, int(cell_ordinal), int(replicate)]
    ).generate_state(1, dtype=np.uint64)[0]
    return int(data), int(analysis)


def metric_record(
    truth: float,
    estimate: float | None,
    lower: float | None,
    upper: float | None,
    *,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build one canonical metric record without fabricating unavailable values."""

    finite = estimate is not None and math.isfinite(float(estimate))
    available = lower is not None and upper is not None
    return {
        "truth": float(truth),
        "estimate": None if estimate is None else float(estimate),
        "bias": float(estimate - truth) if finite else None,
        "lower": None if lower is None else float(lower),
        "upper": None if upper is None else float(upper),
        "coverage": bool(available and lower <= truth <= upper),
        "width": float(upper - lower) if available else None,
        "zero_exclusion": bool(available and (upper < 0.0 or lower > 0.0)),
        "interval_available": bool(available),
        "status": str(status),
        "reason": reason,
    }


def _three_means(mu: Callable[[float, float], float]) -> tuple[float, float, float]:
    """Return TE, PNDE, TNIE for the locked 0-to-1 contrast."""

    baseline = float(mu(0.0, 0.0))
    natural_direct = float(mu(1.0, 0.0))
    total = float(mu(1.0, 1.0))
    return total - baseline, natural_direct - baseline, total - natural_direct


def _hermite64() -> tuple[np.ndarray, np.ndarray]:
    nodes, weights = np.polynomial.hermite.hermgauss(64)
    return np.sqrt(2.0) * nodes, weights / np.sqrt(np.pi)


def _cell11_mu(a: float, b: float) -> float:
    c_values, c_weights = _hermite64()
    probabilities = expit(-0.4 + 0.8 * b + 0.3 * c_values)
    return float(0.2 * a + 0.6 * np.dot(c_weights, probabilities))


def _cell12_mu(a: float, b: float) -> float:
    c_values, c_weights = _hermite64()
    e_values, e_weights = _hermite64()
    total = 0.0
    for c_value, c_weight in zip(c_values, c_weights):
        p_m1 = float(expit(-0.4 + 0.8 * b + 0.3 * c_value))
        m2_errors = e_values
        for m1, p_branch in ((0.0, 1.0 - p_m1), (1.0, p_m1)):
            m2 = 0.3 * b + 0.5 * m1 + 0.3 * c_value + m2_errors
            p_y = expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.4 * m2 + 0.3 * c_value)
            total += float(c_weight * p_branch * np.dot(e_weights, p_y))
    return total


_FIXED_TRUTHS: dict[str, tuple[float, float, float]] = {
    "cell01_linear_n100": (0.45, 0.20, 0.25),
    "cell02_linear_n250": (0.45, 0.20, 0.25),
    "cell03_no_a_to_m_n100": (0.20, 0.20, 0.00),
    "cell04_no_m_to_y_n100": (0.20, 0.20, 0.00),
    "cell05_no_mediation_n100": (0.20, 0.20, 0.00),
    "cell06_parallel_interaction_n150": (0.60, 0.20, 0.40),
    "cell07_serial_three_n200": (0.56, 0.20, 0.36),
    "cell08_quadratic_n100": (0.30, 0.20, 0.10),
    "cell09_spline_n250": (0.30, 0.20, 0.10),
    "cell10_moderated_n150": (0.29, 0.20, 0.09),
}


def cell_truth(cell_id: str) -> tuple[float, float, float]:
    """Return an independent population truth, never a generated-sample value."""

    if cell_id in _FIXED_TRUTHS:
        return _FIXED_TRUTHS[cell_id]
    if cell_id == "cell11_binary_mediator_n150":
        return _three_means(_cell11_mu)
    if cell_id == "cell12_mixed_binary_serial_n250":
        return _three_means(_cell12_mu)
    raise ValueError(f"unknown validation cell ID {cell_id!r}")


_CELL_REGISTRY = (
    ValidationCell("cell01_linear_n100", 1, 100, "linear", "continuous", population_outcome_sd=math.sqrt(1.503125)),
    ValidationCell("cell02_linear_n250", 2, 250, "linear", "continuous", population_outcome_sd=math.sqrt(1.503125)),
    ValidationCell("cell03_no_a_to_m_n100", 3, 100, "no_a_to_m", "continuous", population_outcome_sd=math.sqrt(1.35)),
    ValidationCell("cell04_no_m_to_y_n100", 4, 100, "no_m_to_y", "continuous", population_outcome_sd=math.sqrt(1.1)),
    ValidationCell("cell05_no_mediation_n100", 5, 100, "no_mediation", "continuous", population_outcome_sd=math.sqrt(1.1)),
    ValidationCell("cell06_parallel_interaction_n150", 6, 150, "parallel_interaction", "continuous", ("TNIE",), population_outcome_sd=1.5),
    ValidationCell("cell07_serial_three_n200", 7, 200, "serial_three", "continuous", population_outcome_sd=math.sqrt(1.0 + 0.56**2 * 0.25 + 0.57**2 + 0.4**2 * 3)),
    ValidationCell("cell08_quadratic_n100", 8, 100, "quadratic", "continuous", population_outcome_sd=1.35),
    ValidationCell("cell09_spline_n250", 9, 250, "spline", "continuous", population_outcome_sd=1.35),
    ValidationCell("cell10_moderated_n150", 10, 150, "moderated", "continuous", ("TNIE_W0", "TNIE_W1", "TNIE_difference"), population_outcome_sd=1.5),
    ValidationCell("cell11_binary_mediator_n150", 11, 150, "binary_mediator", "binary", truth_method="gauss_hermite_64"),
    ValidationCell("cell12_mixed_binary_serial_n250", 12, 250, "mixed_binary_serial", "binary", truth_method="gauss_hermite_64"),
)
_CELL_BY_ID = {cell.cell_id: cell for cell in _CELL_REGISTRY}
if len(_CELL_BY_ID) != len(_CELL_REGISTRY) or {
    cell.ordinal for cell in _CELL_REGISTRY
} != set(range(1, len(_CELL_REGISTRY) + 1)):
    raise RuntimeError("validation cell registry IDs and ordinals must be unique")


def cell_definition(cell_id: str) -> ValidationCell:
    try:
        return _CELL_BY_ID[cell_id]
    except KeyError as exc:
        raise ValueError(f"unknown validation cell ID {cell_id!r}") from exc


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
        family=family,
        levels=levels,
    )


def _terms(names: Sequence[str], kind: TermKind = TermKind.LINEAR) -> tuple[TermSpec, ...]:
    return tuple(
        TermSpec(name, kind, df=3 if kind is TermKind.NATURAL_SPLINE else None)
        for name in names
    )


def _node(
    response: str,
    family: Family,
    names: Sequence[str],
    *,
    kind: TermKind = TermKind.LINEAR,
    interactions: Sequence[tuple[str, str]] = (),
) -> NodeSpec:
    return NodeSpec(
        response=response,
        family=family,
        intercept=True,
        terms=_terms(names, kind),
        interactions=tuple(InteractionSpec(left, right) for left, right in interactions),
    )


def _compile_spec(
    *,
    outcome: VariableSpec,
    mediators: Sequence[VariableSpec],
    nodes: Sequence[NodeSpec],
    baseline: Sequence[VariableSpec] = (),
    moderators: Sequence[VariableSpec] = (),
    edges: Sequence[tuple[str, str]],
    order: Sequence[str],
    arrangement: str = "parallel",
    moderator_values: Mapping[str, Any] | None = None,
) -> Any:
    exposure = _variable("A", Role.EXPOSURE, "binary", levels=(0, 1))
    return compile_template(
        TemplateSpec(
            exposure=exposure,
            outcome=outcome,
            mediators=tuple(mediators),
            baseline=tuple(baseline),
            moderators=tuple(moderators),
            nodes=tuple(nodes),
            contrast=ContrastSpec(
                reference=0,
                comparison=1,
                moderator_values=dict(moderator_values or {}),
            ),
            computation=ComputationSpec(
                seed=0,
                bootstrap=0,
                integration_draws=256,
                integration_tolerance=1e-8,
                max_seconds=600,
                memory_budget_mb=1024,
            ),
            scientific_edges=tuple(edges),
            mediator_order=tuple(order),
            arrangement=arrangement,
            missing="error",
        )
    )


def _binary_exposure(rng: np.random.Generator, n: int) -> np.ndarray:
    values = np.resize(np.array([0.0, 1.0]), n).astype(float)
    if n > 2:
        tail = values[2:].copy()
        rng.shuffle(tail)
        values[2:] = tail
    return values


def _single_spec(*, outcome_kind: Family, outcome_type: str = "continuous", outcome_term_kind: TermKind = TermKind.LINEAR, a_to_m: bool = True, m_to_y: bool = True) -> Any:
    baseline = (_variable("C", Role.COVARIATE),)
    mediator = _variable("M", Role.MEDIATOR, family=Family.GAUSSIAN)
    outcome = _variable("Y", Role.OUTCOME, outcome_type, family=outcome_kind, levels=(0, 1) if outcome_kind is Family.BERNOULLI else ())
    mediator_names = ("A", "C") if a_to_m else ("C",)
    outcome_names = ["A", "C"]
    if m_to_y:
        outcome_names.append("M")
    outcome_terms = _terms(outcome_names)
    if outcome_term_kind is not TermKind.LINEAR:
        outcome_terms = _terms(outcome_names[:-1]) + _terms(("M",), outcome_term_kind)
    edges = [("A", "Y")]
    if a_to_m:
        edges.insert(0, ("A", "M"))
    if m_to_y:
        edges.append(("M", "Y"))
    return _compile_spec(
        outcome=outcome,
        mediators=(mediator,),
        baseline=baseline,
        nodes=(
            _node("M", Family.GAUSSIAN, mediator_names),
            NodeSpec(
                response="Y",
                family=outcome_kind,
                intercept=True,
                terms=outcome_terms,
            ),
        ),
        edges=edges,
        order=("M",),
    )


def _fixture(
    cell: ValidationCell,
    data: pd.DataFrame,
    spec: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> SimulationFixture:
    return SimulationFixture(
        name=cell.cell_id,
        data=data,
        spec=spec,
        truth=cell_truth(cell.cell_id),
        truth_method=cell.truth_method,
        metadata={
            "cell_id": cell.cell_id,
            "cell_ordinal": cell.ordinal,
            "population_outcome_sd": cell.population_outcome_sd,
            **dict(metadata or {}),
        },
    )


def _generate_single(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    n = cell.n
    a = _binary_exposure(rng, n)
    c = rng.standard_normal(n)
    e_m = rng.standard_normal(n)
    if cell.generator_name == "no_a_to_m":
        m = 0.3 * c + e_m
    else:
        m = 0.5 * a + 0.3 * c + e_m
    e_y = rng.standard_normal(n)
    if cell.generator_name in {"no_m_to_y", "no_mediation"}:
        y = 0.2 * a + 0.3 * c + e_y
    elif cell.generator_name == "quadratic" or cell.generator_name == "spline":
        y = 0.2 * a + 0.4 * m**2 + 0.3 * c + e_y
    else:
        y = 0.2 * a + 0.5 * m + 0.3 * c + e_y
    if cell.generator_name == "no_mediation":
        m = 0.3 * c + e_m
    spec = _single_spec(
        outcome_kind=Family.GAUSSIAN,
        outcome_term_kind=TermKind.NATURAL_SPLINE if cell.generator_name == "spline" else (
            TermKind.QUADRATIC if cell.generator_name == "quadratic" else TermKind.LINEAR
        ),
        a_to_m=cell.generator_name != "no_a_to_m",
        m_to_y=cell.generator_name not in {"no_m_to_y", "no_mediation"},
    )
    return _fixture(cell, pd.DataFrame({"A": a, "C": c, "M": m, "Y": y}), spec)


def _generate_parallel_interaction(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    a = _binary_exposure(rng, cell.n)
    c = rng.standard_normal(cell.n)
    errors = rng.multivariate_normal(
        np.zeros(2), np.array([[1.0, 0.4], [0.4, 1.0]]), size=cell.n
    )
    m1 = 0.5 * a + errors[:, 0]
    m2 = 0.4 * a + errors[:, 1]
    y = 0.2 * a + 0.4 * m1 + 0.4 * m2 + 0.2 * m1 * m2 + 0.3 * c + rng.standard_normal(cell.n)
    spec = _compile_spec(
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=(
            _variable("M1", Role.MEDIATOR, family=Family.GAUSSIAN),
            _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
        ),
        baseline=(_variable("C", Role.COVARIATE),),
        nodes=(
            _node("M1", Family.GAUSSIAN, ("A",)),
            _node("M2", Family.GAUSSIAN, ("A",)),
            _node("Y", Family.GAUSSIAN, ("A", "C", "M1", "M2"), interactions=(("M1", "M2"),)),
        ),
        edges=(("A", "M1"), ("A", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y")),
        order=("M1", "M2"),
    )
    return _fixture(
        cell,
        pd.DataFrame({"A": a, "C": c, "M1": m1, "M2": m2, "Y": y}),
        spec,
        metadata={"covariance": ((1.0, 0.4), (0.4, 1.0)), "joint_metric": "TNIE"},
    )


def _generate_serial_three(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    a = _binary_exposure(rng, cell.n)
    c = rng.standard_normal(cell.n)
    m1 = 0.5 * a + 0.3 * c + rng.standard_normal(cell.n)
    m2 = 0.2 * a + 0.5 * m1 + 0.3 * c + rng.standard_normal(cell.n)
    m3 = 0.2 * a + 0.5 * m2 + 0.3 * c + rng.standard_normal(cell.n)
    y = 0.2 * a + 0.2 * m1 + 0.2 * m2 + 0.4 * m3 + 0.3 * c + rng.standard_normal(cell.n)
    mediators = tuple(_variable(name, Role.MEDIATOR, family=Family.GAUSSIAN) for name in ("M1", "M2", "M3"))
    spec = _compile_spec(
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=mediators,
        baseline=(_variable("C", Role.COVARIATE),),
        nodes=(
            _node("M1", Family.GAUSSIAN, ("A", "C")),
            _node("M2", Family.GAUSSIAN, ("A", "M1", "C")),
            _node("M3", Family.GAUSSIAN, ("A", "M2", "C")),
            _node("Y", Family.GAUSSIAN, ("A", "M1", "M2", "M3", "C")),
        ),
        edges=(("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "M3"), ("M2", "M3"), ("A", "Y"), ("M1", "Y"), ("M2", "Y"), ("M3", "Y")),
        order=("M1", "M2", "M3"),
        arrangement="sequential",
    )
    return _fixture(cell, pd.DataFrame({"A": a, "C": c, "M1": m1, "M2": m2, "M3": m3, "Y": y}), spec)


def _generate_moderated(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    a = _binary_exposure(rng, cell.n)
    w = _binary_exposure(rng, cell.n)
    c = rng.standard_normal(cell.n)
    m = (0.3 + 0.3 * w) * a + 0.2 * w + 0.3 * c + rng.standard_normal(cell.n)
    y = 0.2 * a + (0.3 + 0.3 * w) * m + 0.2 * w + 0.3 * c + rng.standard_normal(cell.n)
    spec = _compile_spec(
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=(_variable("M", Role.MEDIATOR, family=Family.GAUSSIAN),),
        baseline=(_variable("C", Role.COVARIATE),),
        nodes=(
            _node("M", Family.GAUSSIAN, ("A", "W", "C"), interactions=(("W", "A"),)),
            _node("Y", Family.GAUSSIAN, ("A", "W", "C", "M"), interactions=(("W", "M"),)),
        ),
        edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        order=("M",),
        moderators=(_variable("W", Role.MODERATOR, "binary", levels=(0, 1)),),
        moderator_values={"W": 0.0},
    )
    return _fixture(
        cell,
        pd.DataFrame({"A": a, "W": w, "C": c, "M": m, "Y": y}),
        spec,
        metadata={
            "truth_by_moderator": {
                "W=0": (0.29, 0.20, 0.09),
                "W=1": (0.56, 0.20, 0.36),
                "difference_W1_minus_W0_TNIE": 0.27,
            }
        },
    )


def _generate_binary_mediator(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    a = _binary_exposure(rng, cell.n)
    c = rng.standard_normal(cell.n)
    m = rng.binomial(1, expit(-0.4 + 0.8 * a + 0.3 * c)).astype(float)
    y = 0.2 * a + 0.6 * m + 0.3 * c + rng.standard_normal(cell.n)
    spec = _compile_spec(
        outcome=_variable("Y", Role.OUTCOME, family=Family.GAUSSIAN),
        mediators=(_variable("M", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),),
        baseline=(_variable("C", Role.COVARIATE),),
        nodes=(_node("M", Family.BERNOULLI, ("A", "C")), _node("Y", Family.GAUSSIAN, ("A", "M", "C"))),
        edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        order=("M",),
    )
    return _fixture(cell, pd.DataFrame({"A": a, "C": c, "M": m, "Y": y}), spec, metadata={"quadrature_order": 64})


def _generate_mixed_binary_serial(rng: np.random.Generator, cell: ValidationCell) -> SimulationFixture:
    a = _binary_exposure(rng, cell.n)
    c = rng.standard_normal(cell.n)
    m1 = rng.binomial(1, expit(-0.4 + 0.8 * a + 0.3 * c)).astype(float)
    m2 = 0.3 * a + 0.5 * m1 + 0.3 * c + rng.standard_normal(cell.n)
    y = rng.binomial(1, expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.4 * m2 + 0.3 * c)).astype(float)
    spec = _compile_spec(
        outcome=_variable("Y", Role.OUTCOME, "binary", family=Family.BERNOULLI, levels=(0, 1)),
        mediators=(
            _variable("M1", Role.MEDIATOR, "binary", family=Family.BERNOULLI, levels=(0, 1)),
            _variable("M2", Role.MEDIATOR, family=Family.GAUSSIAN),
        ),
        baseline=(_variable("C", Role.COVARIATE),),
        nodes=(
            _node("M1", Family.BERNOULLI, ("A", "C")),
            _node("M2", Family.GAUSSIAN, ("A", "M1", "C")),
            _node("Y", Family.BERNOULLI, ("A", "M1", "M2", "C")),
        ),
        edges=(("A", "M1"), ("A", "M2"), ("M1", "M2"), ("A", "Y"), ("M1", "Y"), ("M2", "Y")),
        order=("M1", "M2"),
        arrangement="sequential",
    )
    return _fixture(
        cell,
        pd.DataFrame({"A": a, "C": c, "M1": m1, "M2": m2, "Y": y}),
        spec,
        metadata={"quadrature_order": 64},
    )


_GENERATORS: Mapping[str, Callable[[np.random.Generator, ValidationCell], SimulationFixture]] = {
    "linear": _generate_single,
    "no_a_to_m": _generate_single,
    "no_m_to_y": _generate_single,
    "no_mediation": _generate_single,
    "quadratic": _generate_single,
    "spline": _generate_single,
    "parallel_interaction": _generate_parallel_interaction,
    "serial_three": _generate_serial_three,
    "moderated": _generate_moderated,
    "binary_mediator": _generate_binary_mediator,
    "mixed_binary_serial": _generate_mixed_binary_serial,
}


def generate_cell(cell_id: str, data_seed: int) -> SimulationFixture:
    """Generate one locked validation dataset using only its data seed."""

    cell = cell_definition(cell_id)
    rng = np.random.default_rng(int(data_seed))
    return _GENERATORS[cell.generator_name](rng, cell)


def _effect_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(effect.get("name")): effect
        for effect in payload.get("effects", ())
        if isinstance(effect, Mapping) and effect.get("name") is not None
    }


def _interval_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    bootstrap = payload.get("bootstrap")
    if not isinstance(bootstrap, Mapping):
        return {}
    return {
        str(effect.get("name")): effect
        for effect in bootstrap.get("intervals", ())
        if isinstance(effect, Mapping) and effect.get("name") is not None
    }


def _metric_from_effect(
    truth: float,
    point: Mapping[str, Any] | None,
    interval: Mapping[str, Any] | None,
    *,
    status: str,
    reason: str | None,
) -> dict[str, Any]:
    point = point or {}
    interval = interval or {}
    estimate = point.get("estimate")
    lower = interval.get("lower", point.get("lower"))
    upper = interval.get("upper", point.get("upper"))
    point_reason = point.get("reason")
    return metric_record(
        truth,
        None if estimate is None else float(estimate),
        None if lower is None else float(lower),
        None if upper is None else float(upper),
        status=str(point.get("status", status)),
        reason=reason or interval.get("reason") or point_reason,
    )


def extract_metrics(payload: Mapping[str, Any], cell_id: str) -> dict[str, dict[str, Any]]:
    """Extract the fixed metrics from one public ``result_to_dict`` payload."""

    definition = cell_definition(cell_id)
    overall_status = str(payload.get("overall_status") or "unknown")
    error = payload.get("diagnostics", {}).get("error") if isinstance(payload.get("diagnostics"), Mapping) else None
    failure_reason = str(error.get("code")) if isinstance(error, Mapping) and error.get("code") else None
    effects = _effect_index(payload)
    intervals = _interval_index(payload)

    if cell_id != "cell10_moderated_n150":
        truth = dict(zip(("TE", "PNDE", "TNIE"), cell_truth(cell_id)))
        return {
            name: _metric_from_effect(
                truth[name],
                effects.get(name),
                intervals.get(name),
                status=overall_status,
                reason=failure_reason,
            )
            for name in definition.metric_names
        }

    truth = {"TNIE_W0": 0.09, "TNIE_W1": 0.36, "TNIE_difference": 0.27}
    moderation = payload.get("diagnostics", {}).get("moderation", {})
    contrasts = moderation.get("contrasts", ()) if isinstance(moderation, Mapping) else ()
    direct: dict[int, Mapping[str, Any]] = {}
    difference_point: Mapping[str, Any] | None = None
    for contrast in contrasts:
        if not isinstance(contrast, Mapping):
            continue
        try:
            value = int(float(contrast.get("value")))
        except (TypeError, ValueError):
            continue
        contrast_effects = contrast.get("effects", ())
        for effect in contrast_effects:
            if isinstance(effect, Mapping) and effect.get("name") == "TNIE":
                direct[value] = effect
        for effect in contrast.get("differences", ()):
            if isinstance(effect, Mapping) and effect.get("name") == "TNIE":
                difference_point = effect
    if difference_point is None and 0 in direct and 1 in direct:
        left = direct[0].get("estimate")
        right = direct[1].get("estimate")
        if left is not None and right is not None:
            difference_point = {"estimate": float(right) - float(left), "status": overall_status}
    direct_points = {
        value: {key: item for key, item in effect.items() if key not in {"lower", "upper"}}
        for value, effect in direct.items()
    }
    return {
        "TNIE_W0": _metric_from_effect(
            truth["TNIE_W0"], direct_points.get(0), None, status=overall_status,
            reason=(direct_points.get(0) or {}).get("reason") if direct_points.get(0) else failure_reason,
        ),
        "TNIE_W1": _metric_from_effect(
            truth["TNIE_W1"], direct_points.get(1), None, status=overall_status,
            reason=(direct_points.get(1) or {}).get("reason") if direct_points.get(1) else failure_reason,
        ),
        "TNIE_difference": _metric_from_effect(
            truth["TNIE_difference"],
            difference_point,
            intervals.get("moderator_difference__W__1__TNIE"),
            status=overall_status,
            reason=failure_reason,
        ),
    }


def _prepare_spec(fixture: SimulationFixture, config: ValidationConfig, analysis_seed: int) -> Any:
    computation = replace(
        fixture.spec.computation,
        seed=int(analysis_seed),
        bootstrap=int(config.bootstrap_replicates),
        bootstrap_mode=config.bootstrap_mode,
        integration_draws=int(config.integration_draws),
        integration_tolerance=float(config.integration_tolerance),
        max_seconds=int(config.max_seconds),
        memory_budget_mb=int(config.memory_budget_mb),
    )
    return replace(fixture.spec, computation=computation)


def row_from_payload(
    payload: Mapping[str, Any],
    *,
    config: ValidationConfig,
    cell: ValidationCell,
    replicate: int,
    data_seed: int,
    analysis_seed: int,
    runtime_seconds: float,
) -> dict[str, Any]:
    metrics = extract_metrics(payload, cell.cell_id)
    first = metrics[cell.metric_names[0]]
    diagnostics = payload.get("diagnostics", {})
    error = diagnostics.get("error") if isinstance(diagnostics, Mapping) else None
    provenance = payload.get("provenance", {})
    node_payload = diagnostics.get("nodes", ()) if isinstance(diagnostics, Mapping) else ()
    fit_count = len(node_payload) if isinstance(node_payload, (Mapping, Sequence)) and not isinstance(node_payload, str) else 0
    draw_budget = provenance.get("accepted_draw_budget") if isinstance(provenance, Mapping) else None
    if draw_budget is None and isinstance(diagnostics, Mapping):
        integration = diagnostics.get("integration", {})
        if isinstance(integration, Mapping):
            draw_budget = integration.get("accepted_draw_budget")
    safe_provenance = {
        "cell_id": cell.cell_id,
        "cell_ordinal": cell.ordinal,
        "n": cell.n,
        "data_seed": int(data_seed),
        "analysis_seed": int(analysis_seed),
        "config_hash": config.config_hash,
        "truth_method": cell.truth_method,
        "specification_hash": payload.get("specification_hash"),
        "analysis_hash": payload.get("analysis_hash"),
        "bootstrap_requested": config.bootstrap_replicates,
        "bootstrap_mode": config.bootstrap_mode,
        "integration_method": provenance.get("integration_method") if isinstance(provenance, Mapping) else None,
        "accepted_draw_budget": draw_budget,
    }
    return {
        "replicate": int(replicate),
        "data_seed": int(data_seed),
        "analysis_seed": int(analysis_seed),
        "config_hash": config.config_hash,
        "truth_method": cell.truth_method,
        "outcome_kind": cell.outcome_kind,
        "estimand": cell.metric_names[0],
        "truth": first["truth"],
        "estimate": first["estimate"],
        "bias": first["bias"],
        "lower": first["lower"],
        "upper": first["upper"],
        "coverage": first["coverage"],
        "width": first["width"],
        "zero_exclusion": first["zero_exclusion"],
        "interval_available": first["interval_available"],
        "status": str(payload.get("overall_status") or first["status"]),
        "failure_code": error.get("code") if isinstance(error, Mapping) else None,
        "failure_message": error.get("message") if isinstance(error, Mapping) else None,
        "runtime_seconds": float(runtime_seconds),
        "fit_count": int(fit_count),
        "draw_budget": draw_budget,
        "metrics_json": json.dumps(metrics, sort_keys=True, separators=(",", ":")),
        "provenance_json": json.dumps(safe_provenance, sort_keys=True, separators=(",", ":")),
    }


def selected_combinations(
    config: ValidationConfig,
    *,
    cell_ids: Sequence[str] | None = None,
    replicate: int | None = None,
    replicate_start: int = 0,
    replicate_stop: int | None = None,
) -> tuple[tuple[str, int], ...]:
    """Validate CLI filters and return registry-ordered matrix combinations."""

    if replicate is not None and (replicate_start != 0 or replicate_stop is not None):
        raise ValueError("--replicate cannot be combined with replicate range filters")
    requested_cells = tuple(cell_ids) if cell_ids is not None else config.cell_ids
    if not requested_cells:
        raise ValueError("at least one cell ID must be selected")
    if len(set(requested_cells)) != len(requested_cells):
        raise ValueError("cell selection contains duplicate IDs")
    unknown = set(requested_cells) - set(config.cell_ids)
    if unknown:
        raise ValueError(f"selected cell(s) are not in the loaded configuration: {sorted(unknown)}")
    if replicate is not None:
        if replicate < 0 or replicate >= config.replicates:
            raise ValueError("replicate is outside the configured range")
        replicates = (int(replicate),)
    else:
        stop = config.replicates if replicate_stop is None else int(replicate_stop)
        if replicate_start < 0 or stop > config.replicates or replicate_start >= stop:
            raise ValueError("replicate range must be nonempty and within the configured range")
        replicates = tuple(range(int(replicate_start), stop))
    ordered_cells = sorted(requested_cells, key=lambda value: cell_definition(value).ordinal)
    return tuple((cell_id, rep) for cell_id in ordered_cells for rep in replicates)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_resume_rows(path: Path, config: ValidationConfig) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=RAW_COLUMNS)
    raw = pd.read_csv(path, dtype={"cell_id": str, "config_hash": str})
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw_metrics.csv columns do not match the frozen raw-row contract")
    if raw.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    raw["replicate"] = raw["replicate"].astype(int)
    if raw.duplicated(subset=list(COMBINATION_COLUMNS)).any():
        raise ValueError("raw_metrics.csv contains duplicate combination keys")
    allowed = expected_combinations(config)
    current = raw.loc[raw["config_hash"].astype(str) == config.config_hash]
    observed = set(current[list(COMBINATION_COLUMNS)].itertuples(index=False, name=None))
    unexpected = observed - allowed
    if unexpected:
        raise ValueError(f"raw_metrics.csv contains combinations outside the loaded design: {sorted(unexpected)}")
    retained = raw.loc[raw["config_hash"].astype(str) == config.config_hash, list(RAW_COLUMNS)].copy()
    if len(retained) != len(raw):
        _atomic_text(path, retained.to_csv(index=False, lineterminator="\n"))
    return retained


def _append_row(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.is_file() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS, extrasaction="raise", lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerow({column: row.get(column) for column in RAW_COLUMNS})
        handle.flush()
        os.fsync(handle.fileno())


def _write_metadata(
    output_dir: Path,
    config: ValidationConfig,
    *,
    runtime_seconds: float,
    observed_rows: int,
    stress_written: bool,
) -> None:
    metadata = {
        "schema_version": 1,
        "experiment": config.experiment,
        "config_hash": config.config_hash,
        "combination_columns": list(COMBINATION_COLUMNS),
        "expected_rows": expected_row_count(config),
        "observed_rows": int(observed_rows),
        "runtime_seconds": float(runtime_seconds),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "stress_separate": bool(stress_written),
        "git_commit": None,
        "charter_sha256": None,
    }
    _atomic_text(output_dir / "metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def _write_stress(
    config: ValidationConfig,
    output_dir: Path,
) -> None:
    from mintmed.api import analyze_mediation
    from mintmed.report import result_to_dict
    from mintmed.simulation import sample_fixture

    rows: list[dict[str, Any]] = []
    for fixture_index, name in enumerate(config.stress_fixture_names):
        for replicate in range(config.stress_replicates):
            seed = int(
                np.random.SeedSequence(
                    [config.master_seed, 1300, 90, fixture_index, replicate]
                ).generate_state(1, dtype=np.uint64)[0]
            )
            fixture = sample_fixture(name, config.stress_sample_size, np.random.default_rng(seed))
            started = time.perf_counter()
            result = analyze_mediation(fixture.data, fixture.spec)
            payload = result_to_dict(result)
            diagnostics = payload.get("diagnostics", {})
            error = diagnostics.get("error") if isinstance(diagnostics, Mapping) else None
            rows.append(
                {
                    "fixture_name": name,
                    "replicate": replicate,
                    "seed": seed,
                    "sample_size": config.stress_sample_size,
                    "truth_method": fixture.truth_method,
                    "status": payload.get("overall_status"),
                    "failure_code": error.get("code") if isinstance(error, Mapping) else None,
                    "failure_message": error.get("message") if isinstance(error, Mapping) else None,
                    "runtime_seconds": time.perf_counter() - started,
                }
            )
    frame = pd.DataFrame(rows)
    _atomic_text(output_dir / "stress_metrics.csv", frame.to_csv(index=False, lineterminator="\n"))


def _analyze_combination(
    config: ValidationConfig,
    cell_id: str,
    replicate: int,
) -> dict[str, Any]:
    from mintmed.api import analyze_mediation
    from mintmed.report import result_to_dict

    cell = cell_definition(cell_id)
    data_seed, analysis_seed = seed_pair(config.master_seed, cell.ordinal, replicate)
    fixture = generate_cell(cell_id, data_seed)
    spec = _prepare_spec(fixture, config, analysis_seed)
    started = time.perf_counter()
    result = analyze_mediation(fixture.data, spec)
    payload = result_to_dict(result)
    return row_from_payload(
        payload,
        config=config,
        cell=cell,
        replicate=replicate,
        data_seed=data_seed,
        analysis_seed=analysis_seed,
        runtime_seconds=time.perf_counter() - started,
    )


def run(
    config: ValidationConfig,
    output_dir: Path,
    *,
    cell_ids: Sequence[str] | None = None,
    replicate: int | None = None,
    replicate_start: int = 0,
    replicate_stop: int | None = None,
    include_stress: bool = False,
    stress_only: bool = False,
    no_report: bool = False,
) -> pd.DataFrame:
    """Execute selected combinations with durable, resumable raw rows."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_text(output / "resolved_config.yaml", yaml.safe_dump(config.canonical_dict, sort_keys=False))
    started = time.perf_counter()
    selected = () if stress_only else selected_combinations(
        config,
        cell_ids=cell_ids,
        replicate=replicate,
        replicate_start=replicate_start,
        replicate_stop=replicate_stop,
    )
    raw_path = output / "raw_metrics.csv"
    existing = _read_resume_rows(raw_path, config) if not stress_only else pd.DataFrame(columns=RAW_COLUMNS)
    existing_keys = set(existing[list(COMBINATION_COLUMNS)].itertuples(index=False, name=None))
    for cell_id, replicate_id in selected:
        if (cell_id, replicate_id) in existing_keys:
            continue
        row = _analyze_combination(config, cell_id, replicate_id)
        _append_row(raw_path, row)
        existing = pd.concat([existing, pd.DataFrame([row], columns=RAW_COLUMNS)], ignore_index=True)
        existing_keys.add((cell_id, replicate_id))

    stress_written = bool(include_stress or stress_only)
    if include_stress or stress_only:
        if not config.stress_enabled:
            raise ValueError("stress execution requested but stress.enabled is false")
        _write_stress(config, output)
    _write_metadata(
        output,
        config,
        runtime_seconds=time.perf_counter() - started,
        observed_rows=len(existing),
        stress_written=stress_written,
    )
    if not no_report and not stress_only:
        from .mediation_validation_reporting import write_report

        write_report(existing, config, output)
    return existing


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell-id", action="append", dest="cell_ids")
    parser.add_argument("--cell-ids", nargs="+", dest="cell_ids_many")
    parser.add_argument("--replicate", type=int)
    parser.add_argument("--replicate-start", type=int, default=0)
    parser.add_argument("--replicate-stop", type=int)
    parser.add_argument("--include-stress", action="store_true")
    parser.add_argument("--stress-only", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    try:
        arguments = parser.parse_args(argv)
        if arguments.cell_ids and arguments.cell_ids_many:
            raise ValueError("--cell-id and --cell-ids cannot be combined")
        selected_cells = arguments.cell_ids or arguments.cell_ids_many
        config = load_config(arguments.config)
        run(
            config,
            arguments.output,
            cell_ids=selected_cells,
            replicate=arguments.replicate,
            replicate_start=arguments.replicate_start,
            replicate_stop=arguments.replicate_stop,
            include_stress=arguments.include_stress,
            stress_only=arguments.stress_only,
            no_report=arguments.no_report,
        )
    except (OSError, ValueError) as exc:
        parser.print_usage()
        print(f"error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMBINATION_COLUMNS",
    "EVIDENCE_ARTIFACTS",
    "RAW_COLUMNS",
    "ValidationCell",
    "ValidationConfig",
    "cell_definition",
    "cell_truth",
    "expected_combinations",
    "expected_row_count",
    "extract_metrics",
    "generate_cell",
    "load_config",
    "metric_record",
    "row_from_payload",
    "run",
    "seed_pair",
    "selected_combinations",
]
