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
from typing import Any

import numpy as np
import yaml


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
    """Stable registry identity; scientific fields are added by the cell layer."""

    cell_id: str
    ordinal: int
    n: int


_CELL_REGISTRY: tuple[ValidationCell, ...] = (
    ValidationCell("cell01_linear_n100", 1, 100),
    ValidationCell("cell02_linear_n250", 2, 250),
    ValidationCell("cell03_no_a_to_m_n100", 3, 100),
    ValidationCell("cell04_no_m_to_y_n100", 4, 100),
    ValidationCell("cell05_no_mediation_n100", 5, 100),
    ValidationCell("cell06_parallel_interaction_n150", 6, 150),
    ValidationCell("cell07_serial_three_n200", 7, 200),
    ValidationCell("cell08_quadratic_n100", 8, 100),
    ValidationCell("cell09_spline_n250", 9, 250),
    ValidationCell("cell10_moderated_n150", 10, 150),
    ValidationCell("cell11_binary_mediator_n150", 11, 150),
    ValidationCell("cell12_mixed_binary_serial_n250", 12, 250),
)
_CELL_BY_ID = {cell.cell_id: cell for cell in _CELL_REGISTRY}
if len(_CELL_BY_ID) != len(_CELL_REGISTRY) or {
    cell.ordinal for cell in _CELL_REGISTRY
} != set(range(1, len(_CELL_REGISTRY) + 1)):
    raise RuntimeError("validation cell registry IDs and ordinals must be unique")


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


def run(*_args: Any, **_kwargs: Any) -> Any:
    """Execution boundary placeholder completed by the runner implementation."""

    raise NotImplementedError("validation execution is not implemented yet")


__all__ = [
    "COMBINATION_COLUMNS",
    "EVIDENCE_ARTIFACTS",
    "RAW_COLUMNS",
    "ValidationCell",
    "ValidationConfig",
    "expected_combinations",
    "expected_row_count",
    "load_config",
    "metric_record",
    "run",
    "seed_pair",
]
