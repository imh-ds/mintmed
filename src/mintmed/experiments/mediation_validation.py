"""Deterministic, resumable validation runner for the frozen mediation matrix.

The module deliberately keeps configuration and cell identity independent from
filesystem layout.  Later sections of the module add the fixed generators and
execution boundary; these first-level contracts are kept small so shard tools
can inspect a design without importing or fitting a model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.special import expit
import yaml

from mintmed.simulation.mediation import SimulationFixture
from mintmed.spec import (
    ComputationSpec,
    ContrastSpec,
    Family,
    InteractionSpec,
    NodeSpec,
    Role,
    TermKind,
    TermSpec,
    TemplateSpec,
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
        raise ValueError(f"{label} must be a mapping")
    return value


def _required_int(raw: Mapping[str, Any], key: str, *, minimum: int) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}")
    return int(value)


def _required_float(raw: Mapping[str, Any], key: str, *, minimum: float) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a finite number >= {minimum}")
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
        raise ValueError("stress.enabled must be boolean")
    stress_replicates = _required_int(stress, "replicates", minimum=0)
    stress_sample_size = _required_int(stress, "sample_size", minimum=2)
    fixture_values = stress.get("fixture_names")
    if not isinstance(fixture_values, (list, tuple)):
        raise ValueError("stress.fixture_names must be a sequence")
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
            _node("Y", outcome_kind, outcome_names, kind=outcome_term_kind),
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
    kind = TermKind.NATURAL_SPLINE if cell.generator_name == "spline" else TermKind.LINEAR
    spec = _single_spec(
        outcome_kind=Family.GAUSSIAN,
        outcome_term_kind=kind if cell.generator_name == "spline" else (
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


def run(*_args: Any, **_kwargs: Any) -> Any:
    """Execution boundary placeholder completed by the runner implementation."""

    raise NotImplementedError("validation execution is not implemented yet")


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
    "generate_cell",
    "load_config",
    "metric_record",
    "run",
    "seed_pair",
]
