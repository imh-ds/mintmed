"""Shardable runner for the Task 18 Phase 1 diagnostic calibration (T18-S4).

For every dataset of the nine diagnostic mechanisms
(:mod:`mintmed.experiments.diagnostic_mechanisms`) the runner applies both
status-only (C2) diagnostics to the analyst's fixed base model:

* the information arm, :func:`information_check.information_check`
  (residual CMIknn with the joint local permutation null), and
* the conventional arm, :func:`lack_of_fit.lack_of_fit_battery`
  (partial-F candidate terms plus Breusch-Pagan, Holm combined),

at the outcome node ``Y | A, M, C`` (primary, tested parent ``M``) and at the
mediator node ``M | A, C`` (secondary, tested parent ``A``). At the outcome
node it also runs two information sensitivities: in-sample residuals, and
``k_cmi_fraction = 0.2``.

The runner records p-values only. Warning thresholds are *not* part of the
configuration: they are matched afterwards on the calibration seed by
``scripts/calibrate_diagnostic_thresholds.py`` and frozen before evaluation.

It implements the aggregation contract of ``scripts/aggregate_shards.py`` so
that ``.github/workflows/sharded_benchmark.yml`` can run it::

    python -m mintmed.experiments.information_diagnostic \\
        --config configs/information_diagnostic_calibration.yaml \\
        --output OUT --mechanism N1_linear --replicate-block 0of4 [--n 100]

Row contract: one row per ``(mechanism, n, replicate, node)``;
``COMBINATION_COLUMNS`` is ``(mechanism, n, node)`` and the aggregator adds
``replicate`` to its duplicate key. ``write_report`` refuses an incomplete grid.

Seeds
-----
* Data: ``diagnostic_mechanisms.dataset_seed(master_seed, mechanism, n, r)``.
* Analysis (folds and permutations of the information arm):
  ``SeedSequence([master_seed, 1801, code, n, r, node_code])`` reduced to one
  32-bit integer (:func:`analysis_seed`). Domain tag 1801 keeps it apart from
  the data stream (tag 1800). The two outcome-node sensitivities reuse the
  primary analysis seed, so they share its folds (k = 0.2) and permutation
  stream, which makes the comparison with the primary check paired.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from . import diagnostic_mechanisms as dm
from .information_check import InformationCheckResult, information_check
from .lack_of_fit import LackOfFitResult, lack_of_fit_battery
from .mediation_validation import replicate_block_range

__all__ = [
    "ANALYSIS_SEED_DOMAIN",
    "COMBINATION_COLUMNS",
    "DiagnosticConfig",
    "LOF_COMPONENTS",
    "NODES",
    "RAW_COLUMNS",
    "analysis_seed",
    "analyse_dataset",
    "expected_combinations",
    "expected_keys",
    "expected_row_count",
    "load_config",
    "read_raw",
    "run",
]

ANALYSIS_SEED_DOMAIN = 1801
NODES: tuple[str, ...] = ("outcome", "mediator")
_NODE_CODES = {"outcome": 1, "mediator": 2}
COMBINATION_COLUMNS: tuple[str, ...] = ("mechanism", "n", "node")
LOF_COMPONENTS: tuple[str, ...] = (
    "mean_curvature_M",
    "mean_interaction_AM",
    "mean_curvature_C",
    "mean_interaction_AC",
    "variance_BP",
)

_INFO_FIELDS = (
    "statistic",
    "p_value",
    "status",
    "reason",
    "runtime_seconds",
)
RAW_COLUMNS: tuple[str, ...] = (
    "config_hash",
    "experiment",
    "master_seed",
    "mechanism",
    "category",
    "n",
    "replicate",
    "node",
    "formula",
    "tested_parent",
    "analysis_seed",
    "n_used",
    # information arm, primary settings
    "info_statistic",
    "info_p_value",
    "info_status",
    "info_reason",
    "info_runtime_seconds",
    "info_stratum_n0",
    "info_stratum_n1",
    "info_estimate_0",
    "info_estimate_1",
    "info_k_cmi_0",
    "info_k_cmi_1",
    "info_zero_radius_points",
    "info_residual_tied_rows",
    "info_parent_tied_rows",
    # information sensitivities (outcome node only; empty at the mediator node)
    "info_insample_statistic",
    "info_insample_p_value",
    "info_insample_status",
    "info_insample_reason",
    "info_insample_runtime_seconds",
    "info_k20_statistic",
    "info_k20_p_value",
    "info_k20_status",
    "info_k20_reason",
    "info_k20_runtime_seconds",
    # conventional battery
    "lof_min_adjusted_p",
    "lof_warning_nominal",
    "lof_status",
    "lof_reason",
    "lof_runtime_seconds",
    *(f"lof_{name}_{kind}" for name in LOF_COMPONENTS for kind in ("p", "adj_p", "status")),
    "dataset_runtime_seconds",
)


@dataclass(frozen=True)
class DiagnosticConfig:
    """One frozen design of the information-diagnostic study."""

    schema_version: int
    experiment: str
    master_seed: int
    replicates: int
    sample_sizes: tuple[int, ...]
    mechanisms: tuple[str, ...]
    permutations: int
    k_cmi_fraction: float
    k_perm: int
    folds: int
    sensitivity_k_cmi_fraction: float
    sensitivities: bool
    lof_alpha: float
    spline_df: int
    purpose: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment": self.experiment,
            "purpose": self.purpose,
            "master_seed": self.master_seed,
            "replicates": self.replicates,
            "sample_sizes": list(self.sample_sizes),
            "mechanisms": list(self.mechanisms),
            "information": {
                "permutations": self.permutations,
                "k_cmi_fraction": self.k_cmi_fraction,
                "k_perm": self.k_perm,
                "folds": self.folds,
                "residuals": "cross_fitted",
                "sensitivities": self.sensitivities,
                "sensitivity_k_cmi_fraction": self.sensitivity_k_cmi_fraction,
            },
            "conventional": {"alpha": self.lof_alpha, "spline_df": self.spline_df},
        }

    @property
    def config_hash(self) -> str:
        encoded = json.dumps(self.canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


_TOP_KEYS = {
    "schema_version",
    "experiment",
    "purpose",
    "master_seed",
    "replicates",
    "sample_sizes",
    "mechanisms",
    "information",
    "conventional",
}
_INFO_KEYS = {
    "permutations",
    "k_cmi_fraction",
    "k_perm",
    "folds",
    "residuals",
    "sensitivities",
    "sensitivity_k_cmi_fraction",
}
_LOF_KEYS = {"alpha", "spline_df"}


def _int(raw: Mapping[str, Any], key: str, minimum: int) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}")
    return int(value)


def _fraction(raw: Mapping[str, Any], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) < 1:
        raise ValueError(f"{key} must be a number in (0, 1)")
    return float(value)


def load_config(path: str | Path) -> DiagnosticConfig:
    """Load and strictly validate an information-diagnostic configuration."""

    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"could not load configuration: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("configuration root must be a mapping")
    unknown = set(raw) - _TOP_KEYS
    if unknown:
        raise ValueError(f"unknown configuration key(s): {', '.join(sorted(unknown))}")
    info = raw.get("information") or {}
    lof = raw.get("conventional") or {}
    if not isinstance(info, Mapping) or not isinstance(lof, Mapping):
        raise ValueError("information and conventional must be mappings")
    if set(info) - _INFO_KEYS or set(lof) - _LOF_KEYS:
        raise ValueError("unknown key(s) under information or conventional")
    if info.get("residuals", "cross_fitted") != "cross_fitted":
        raise ValueError("the primary information residuals must be cross_fitted")
    experiment = raw.get("experiment")
    if not isinstance(experiment, str) or not experiment.strip():
        raise ValueError("experiment must be a nonempty string")
    sizes = raw.get("sample_sizes")
    if not isinstance(sizes, list) or not sizes or any(isinstance(v, bool) or not isinstance(v, int) or v < 2 for v in sizes):
        raise ValueError("sample_sizes must be a nonempty list of integers")
    if len(set(sizes)) != len(sizes):
        raise ValueError("sample_sizes must be distinct")
    mechanisms = raw.get("mechanisms")
    if not isinstance(mechanisms, list) or not mechanisms or len(set(mechanisms)) != len(mechanisms):
        raise ValueError("mechanisms must be a nonempty list of distinct ids")
    for mid in mechanisms:
        dm.mechanism(mid)
    sensitivities = info.get("sensitivities", True)
    if not isinstance(sensitivities, bool):
        raise ValueError("information.sensitivities must be true or false")
    purpose = raw.get("purpose", "")
    return DiagnosticConfig(
        schema_version=_int(raw, "schema_version", 1),
        experiment=experiment.strip(),
        master_seed=_int(raw, "master_seed", 0),
        replicates=_int(raw, "replicates", 1),
        sample_sizes=tuple(int(v) for v in sizes),
        mechanisms=tuple(str(v) for v in mechanisms),
        permutations=_int(info, "permutations", 1),
        k_cmi_fraction=_fraction(info, "k_cmi_fraction"),
        k_perm=_int(info, "k_perm", 1),
        folds=_int(info, "folds", 2),
        sensitivity_k_cmi_fraction=_fraction(info, "sensitivity_k_cmi_fraction"),
        sensitivities=sensitivities,
        lof_alpha=_fraction(lof, "alpha"),
        spline_df=_int(lof, "spline_df", 1),
        purpose=str(purpose).strip() if purpose else "",
    )


# ---------------------------------------------------------------------------
# Contract helpers


def expected_combinations(config: DiagnosticConfig) -> set[tuple[str, int, str]]:
    return {(mid, int(n), node) for mid in config.mechanisms for n in config.sample_sizes for node in NODES}


def expected_keys(config: DiagnosticConfig) -> set[tuple[str, int, int, str]]:
    return {
        (mid, int(n), rep, node)
        for mid, n, node in expected_combinations(config)
        for rep in range(config.replicates)
    }


def expected_row_count(config: DiagnosticConfig) -> int:
    return len(config.mechanisms) * len(config.sample_sizes) * config.replicates * len(NODES)


def analysis_seed(master: int, mechanism_id: str, n: int, replicate: int, node: str) -> int:
    """Deterministic 32-bit analysis seed, separate from the data stream."""

    code = dm.mechanism(mechanism_id).code
    sequence = np.random.SeedSequence(
        [int(master), ANALYSIS_SEED_DOMAIN, code, int(n), int(replicate), _NODE_CODES[node]]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


# ---------------------------------------------------------------------------
# Per-dataset analysis


def _info_fields(prefix: str, result: InformationCheckResult | None) -> dict[str, Any]:
    if result is None:
        return {f"{prefix}_{name}": None for name in _INFO_FIELDS}
    return {
        f"{prefix}_statistic": result.statistic,
        f"{prefix}_p_value": result.p_value,
        f"{prefix}_status": result.status,
        f"{prefix}_reason": result.reason or "",
        f"{prefix}_runtime_seconds": result.runtime_seconds,
    }


def _stratum_fields(node: str, result: InformationCheckResult) -> dict[str, Any]:
    """Sizes, estimates and k per stratum (A = 0/1 at the outcome node).

    At the mediator node there is no stratification; the sizes are the
    tested-parent (A) level sizes and the single estimate is stored as
    ``info_estimate_0`` with ``info_k_cmi_0``.
    """

    out: dict[str, Any] = {
        "info_stratum_n0": None,
        "info_stratum_n1": None,
        "info_estimate_0": None,
        "info_estimate_1": None,
        "info_k_cmi_0": None,
        "info_k_cmi_1": None,
        "info_zero_radius_points": None,
        "info_residual_tied_rows": None,
        "info_parent_tied_rows": None,
    }
    if node == "outcome":
        sizes = dict(result.stratum_sizes)
        out["info_stratum_n0"] = sizes.get("0")
        out["info_stratum_n1"] = sizes.get("1")
        out["info_estimate_0"] = result.stratum_estimates.get("0")
        out["info_estimate_1"] = result.stratum_estimates.get("1")
        out["info_k_cmi_0"] = result.k_cmi.get("0")
        out["info_k_cmi_1"] = result.k_cmi.get("1")
    else:
        levels = dict(result.settings.get("tested_parent_level_sizes", {}) or {})
        out["info_stratum_n0"] = levels.get("0")
        out["info_stratum_n1"] = levels.get("1")
        out["info_estimate_0"] = result.stratum_estimates.get("all")
        out["info_k_cmi_0"] = result.k_cmi.get("all")
    if result.ties:
        out["info_zero_radius_points"] = sum(int(v["zero_radius_points"]) for v in result.ties.values())
        out["info_residual_tied_rows"] = sum(int(v["residual_tied_rows"]) for v in result.ties.values())
        out["info_parent_tied_rows"] = sum(int(v["parent_tied_rows"]) for v in result.ties.values())
    return out


def _lof_fields(result: LackOfFitResult) -> dict[str, Any]:
    out: dict[str, Any] = {
        "lof_min_adjusted_p": result.min_adjusted_p,
        "lof_warning_nominal": bool(result.warning),
        "lof_status": result.status,
        "lof_reason": result.reason or "",
        "lof_runtime_seconds": result.runtime_seconds,
    }
    for name in LOF_COMPONENTS:
        out[f"lof_{name}_p"] = None
        out[f"lof_{name}_adj_p"] = None
        out[f"lof_{name}_status"] = None
    for component in result.components:
        out[f"lof_{component.name}_p"] = component.p_value
        out[f"lof_{component.name}_adj_p"] = component.adjusted_p_value
        out[f"lof_{component.name}_status"] = component.status
    return out


def analyse_dataset(config: DiagnosticConfig, mechanism_id: str, n: int, replicate: int) -> list[dict[str, Any]]:
    """Generate one dataset and return its two node rows."""

    started = time.perf_counter()
    mech = dm.mechanism(mechanism_id)
    data = dm.generate(mechanism_id, n, dm.dataset_seed(config.master_seed, mechanism_id, n, replicate))
    generated = time.perf_counter()
    common = {
        "config_hash": config.config_hash,
        "experiment": config.experiment,
        "master_seed": config.master_seed,
        "mechanism": mechanism_id,
        "category": mech.category,
        "n": int(n),
        "replicate": int(replicate),
    }
    info_kwargs = {
        "permutations": config.permutations,
        "k_perm": config.k_perm,
        "folds": config.folds,
    }
    rows: list[dict[str, Any]] = []
    for node in NODES:
        node_started = time.perf_counter()
        seed = analysis_seed(config.master_seed, mechanism_id, n, replicate, node)
        if node == "outcome":
            formula, parent, stratify = mech.outcome_formula, mech.outcome_tested_parent, "A"
        else:
            formula, parent, stratify = mech.mediator_formula, mech.mediator_tested_parent, None
        primary = information_check(
            data, formula, parent, stratify_by=stratify, seed=seed,
            k_cmi_fraction=config.k_cmi_fraction, residuals="cross_fitted", **info_kwargs,
        )
        insample = k20 = None
        if node == "outcome" and config.sensitivities:
            insample = information_check(
                data, formula, parent, stratify_by=stratify, seed=seed,
                k_cmi_fraction=config.k_cmi_fraction, residuals="in_sample", **info_kwargs,
            )
            k20 = information_check(
                data, formula, parent, stratify_by=stratify, seed=seed,
                k_cmi_fraction=config.sensitivity_k_cmi_fraction, residuals="cross_fitted", **info_kwargs,
            )
        battery = lack_of_fit_battery(data, formula, parent, alpha=config.lof_alpha, spline_df=config.spline_df)
        row = {
            **common,
            "node": node,
            "formula": formula,
            "tested_parent": parent,
            "analysis_seed": seed,
            "n_used": primary.n,
            **_info_fields("info", primary),
            **_stratum_fields(node, primary),
            **_info_fields("info_insample", insample),
            **_info_fields("info_k20", k20),
            **_lof_fields(battery),
            "dataset_runtime_seconds": time.perf_counter() - node_started,
        }
        rows.append(row)
    # dataset_runtime_seconds is per node row (all checks at that node); the
    # data-generation time is added to the outcome row.
    rows[0]["dataset_runtime_seconds"] += generated - started
    return rows


# ---------------------------------------------------------------------------
# I/O


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    new_file = not path.is_file() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS, extrasaction="raise", lineterminator="\n")
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in RAW_COLUMNS})
        handle.flush()
        os.fsync(handle.fileno())


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, float):
        return repr(value)
    return value


def read_raw(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        dtype={"config_hash": str, "mechanism": str, "node": str, "category": str, "formula": str},
        keep_default_na=True,
    )


def _existing_rows(path: Path, config: DiagnosticConfig) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        return pd.DataFrame(columns=RAW_COLUMNS)
    raw = read_raw(path)
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw_metrics.csv columns do not match the information-diagnostic row contract")
    if raw.empty:
        return raw
    if set(raw["config_hash"].astype(str)) != {config.config_hash}:
        raise ValueError("raw_metrics.csv holds rows from another configuration; use a fresh --output")
    if raw.duplicated(subset=["mechanism", "n", "replicate", "node"]).any():
        raise ValueError("raw_metrics.csv contains duplicate (mechanism, n, replicate, node) keys")
    return raw


def run(
    config: DiagnosticConfig,
    output_dir: str | Path,
    *,
    mechanisms: Sequence[str] | None = None,
    sample_sizes: Sequence[int] | None = None,
    replicate_start: int = 0,
    replicate_stop: int | None = None,
    no_report: bool = False,
) -> pd.DataFrame:
    """Analyse the selected datasets and append two rows per dataset."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_text(output / "resolved_config.yaml", yaml.safe_dump(config.canonical_dict, sort_keys=False))
    selected_mechanisms = tuple(mechanisms) if mechanisms else config.mechanisms
    unknown = set(selected_mechanisms) - set(config.mechanisms)
    if unknown:
        raise ValueError(f"mechanism(s) not in the configuration: {sorted(unknown)}")
    selected_sizes = tuple(int(v) for v in sample_sizes) if sample_sizes else config.sample_sizes
    if set(selected_sizes) - set(config.sample_sizes):
        raise ValueError("--n must be one of the configuration's sample_sizes")
    stop = config.replicates if replicate_stop is None else int(replicate_stop)
    if not 0 <= replicate_start <= stop <= config.replicates:
        raise ValueError("replicate bounds must satisfy 0 <= start <= stop <= replicates")

    raw_path = output / "raw_metrics.csv"
    existing = _existing_rows(raw_path, config)
    done = set(
        zip(existing["mechanism"].astype(str), existing["n"].astype(int), existing["replicate"].astype(int), strict=True)
    ) if not existing.empty else set()
    started = time.perf_counter()
    written = 0
    for mid in selected_mechanisms:
        for n in selected_sizes:
            for rep in range(replicate_start, stop):
                if (mid, int(n), rep) in done:
                    continue
                rows = analyse_dataset(config, mid, int(n), rep)
                _append_rows(raw_path, rows)
                written += len(rows)

    final = _existing_rows(raw_path, config)
    metadata = {
        "schema_version": 1,
        "experiment": config.experiment,
        "runner": "mintmed.experiments.information_diagnostic",
        "config_hash": config.config_hash,
        "combination_columns": list(COMBINATION_COLUMNS),
        "expected_rows": expected_row_count(config),
        "observed_rows": int(len(final)),
        "rows_written_this_run": int(written),
        "selection": {
            "mechanisms": list(selected_mechanisms),
            "sample_sizes": list(selected_sizes),
            "replicate_start": int(replicate_start),
            "replicate_stop": int(stop),
        },
        "runtime_seconds": float(time.perf_counter() - started),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "git_commit": os.environ.get("GITHUB_SHA"),
        "charter_sha256": None,
    }
    _atomic_text(output / "metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    if not no_report:
        from .information_diagnostic_reporting import write_report

        write_report(final, config, output, require_complete=False)
    return final


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mechanism", action="append", dest="mechanisms", help="mechanism id (repeatable)")
    parser.add_argument("--n", action="append", type=int, dest="sample_sizes", help="sample size (repeatable)")
    parser.add_argument("--replicate-start", type=int, default=0)
    parser.add_argument("--replicate-stop", type=int)
    parser.add_argument("--replicate-block", help="shard block INDEX:COUNT (or INDEXofCOUNT) of the replicates")
    parser.add_argument("--no-report", action="store_true")
    try:
        arguments = parser.parse_args(argv)
        config = load_config(arguments.config)
        start, stop = arguments.replicate_start, arguments.replicate_stop
        if arguments.replicate_block is not None:
            if start != 0 or stop is not None:
                raise ValueError("--replicate-block cannot be combined with explicit replicate bounds")
            start, stop = replicate_block_range(config.replicates, arguments.replicate_block)
        run(
            config,
            arguments.output,
            mechanisms=arguments.mechanisms,
            sample_sizes=arguments.sample_sizes,
            replicate_start=start,
            replicate_stop=stop,
            no_report=arguments.no_report,
        )
    except (OSError, ValueError) as exc:
        parser.print_usage()
        print(f"error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
