"""Reporting companion of :mod:`mintmed.experiments.information_diagnostic`.

``write_report(raw, config, output_dir)`` is the ``_reporting`` half of the
``scripts/aggregate_shards.py`` contract. It checks that every
``(mechanism, n, replicate, node)`` of the configuration appears exactly once
(the complete-grid check) and writes:

* ``cell_summary.csv``: one line per ``(mechanism, n, node)`` with dataset and
  unavailable counts, rejection counts at the *nominal* p <= 0.05 for every arm
  and sensitivity, and runtime summaries;
* ``runtime_summary.csv``: runtime per check by ``(n, node)``;
* ``summary.json`` and ``report.md``.

Warning rule used everywhere in Task 18: an arm warns on a dataset when its
status is ``ok`` and its p-value (the information permutation p-value, or the
battery's minimum Holm-adjusted p-value) is ``<= threshold``. An unavailable
check never warns and stays in the denominator. The nominal 0.05 rates here are
descriptive; warning thresholds are matched on the calibration seed by
``scripts/calibrate_diagnostic_thresholds.py``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .information_diagnostic import (
    COMBINATION_COLUMNS,
    RAW_COLUMNS,
    DiagnosticConfig,
    _atomic_text,
    expected_keys,
    expected_row_count,
)

__all__ = ["ARMS", "NOMINAL", "arm_warnings", "check_complete_grid", "summarize_cells", "wilson", "write_report"]

NOMINAL = 0.05
WILSON_Z = 1.959963984540054
# arm id -> (p-value column, status column); sensitivities are outcome-node only.
ARMS: dict[str, tuple[str, str]] = {
    "information": ("info_p_value", "info_status"),
    "conventional": ("lof_min_adjusted_p", "lof_status"),
    "information_insample": ("info_insample_p_value", "info_insample_status"),
    "information_k20": ("info_k20_p_value", "info_k20_status"),
}
RUNTIME_COLUMNS: dict[str, str] = {
    "information": "info_runtime_seconds",
    "information_insample": "info_insample_runtime_seconds",
    "information_k20": "info_k20_runtime_seconds",
    "conventional": "lof_runtime_seconds",
    "node_total": "dataset_runtime_seconds",
}


def wilson(successes: int, trials: int, z: float = WILSON_Z) -> tuple[float | None, float | None]:
    """Two-sided Wilson score interval."""

    if trials == 0:
        return None, None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * trials)) / trials) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def arm_warnings(frame: pd.DataFrame, arm: str, threshold: float) -> np.ndarray:
    """Boolean warning per row: status ``ok`` and p-value ``<= threshold``."""

    p_column, status_column = ARMS[arm]
    p = pd.to_numeric(frame[p_column], errors="coerce").to_numpy(dtype=float)
    ok = frame[status_column].astype(str).to_numpy() == "ok"
    with np.errstate(invalid="ignore"):
        return ok & (p <= threshold)


def arm_available(frame: pd.DataFrame, arm: str) -> np.ndarray:
    return frame[ARMS[arm][1]].astype(str).to_numpy() == "ok"


def check_complete_grid(raw: pd.DataFrame, config: DiagnosticConfig) -> dict[str, Any]:
    keys = list(
        zip(
            raw["mechanism"].astype(str),
            raw["n"].astype(int),
            raw["replicate"].astype(int),
            raw["node"].astype(str),
            strict=True,
        )
    )
    observed = set(keys)
    expected = expected_keys(config)
    missing = expected - observed
    extra = observed - expected
    duplicates = len(keys) - len(observed)
    return {
        "complete": not missing and not extra and duplicates == 0 and len(raw) == expected_row_count(config),
        "expected_rows": expected_row_count(config),
        "observed_rows": int(len(raw)),
        "missing": len(missing),
        "unexpected": len(extra),
        "duplicates": int(duplicates),
        "missing_examples": sorted(missing)[:5],
    }


def summarize_cells(raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (mechanism, n, node), group in raw.groupby(list(COMBINATION_COLUMNS), sort=False):
        record: dict[str, Any] = {
            "mechanism": mechanism,
            "category": str(group["category"].iloc[0]),
            "n": int(n),
            "node": node,
            "datasets": int(len(group)),
        }
        for arm in ARMS:
            available = arm_available(group, arm)
            if arm.startswith("information_") and not available.any() and node != "outcome":
                continue
            warns = arm_warnings(group, arm, NOMINAL)
            low, high = wilson(int(warns.sum()), len(group))
            record[f"{arm}_unavailable"] = int((~available).sum())
            record[f"{arm}_reject_nominal"] = int(warns.sum())
            record[f"{arm}_rate_nominal"] = float(warns.mean())
            record[f"{arm}_wilson_low"] = low
            record[f"{arm}_wilson_high"] = high
        for name, column in RUNTIME_COLUMNS.items():
            values = pd.to_numeric(group[column], errors="coerce").dropna()
            if values.empty:
                continue
            record[f"runtime_{name}_mean"] = float(values.mean())
            record[f"runtime_{name}_max"] = float(values.max())
        records.append(record)
    frame = pd.DataFrame.from_records(records)
    return frame.sort_values(["node", "mechanism", "n"], kind="stable").reset_index(drop=True)


def summarize_runtime(raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (n, node), group in raw.groupby(["n", "node"]):
        for name, column in RUNTIME_COLUMNS.items():
            values = pd.to_numeric(group[column], errors="coerce").dropna()
            if values.empty:
                continue
            records.append(
                {
                    "n": int(n),
                    "node": node,
                    "check": name,
                    "count": int(values.size),
                    "mean_seconds": float(values.mean()),
                    "median_seconds": float(values.median()),
                    "p95_seconds": float(values.quantile(0.95)),
                    "max_seconds": float(values.max()),
                }
            )
    return pd.DataFrame.from_records(records)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _report(summary: dict[str, Any], cells: pd.DataFrame, runtime: pd.DataFrame) -> str:
    grid = summary["grid"]
    lines = [
        f"# Information diagnostic run: {summary['experiment']}",
        "",
        f"- Config hash: `{summary['config_hash']}`; master seed {summary['master_seed']}.",
        f"- Rows: {grid['observed_rows']} of {grid['expected_rows']}; complete grid: **{grid['complete']}**.",
        "- Rates below use the *nominal* rule p <= 0.05 and are descriptive only. Calibrated thresholds come from "
        "`scripts/calibrate_diagnostic_thresholds.py` on the calibration seed.",
        "",
        "## Rejections at nominal 0.05 (count / datasets)",
        "",
    ]
    for node in ("outcome", "mediator"):
        subset = cells.loc[cells["node"] == node]
        if subset.empty:
            continue
        arms = [arm for arm in ARMS if f"{arm}_reject_nominal" in subset.columns and subset[f"{arm}_reject_nominal"].notna().any()]
        if node == "mediator":
            arms = [arm for arm in arms if not arm.startswith("information_")]
        lines += [f"### {node} node", "", "| Mechanism | N | " + " | ".join(arms) + " | info unavailable |",
                  "|---|---:|" + "---:|" * (len(arms) + 1)]
        for _, row in subset.iterrows():
            cells_text = [f"{int(row[f'{arm}_reject_nominal'])}/{int(row['datasets'])}" for arm in arms]
            lines.append(f"| {row['mechanism']} | {int(row['n'])} | " + " | ".join(cells_text)
                         + f" | {int(row['information_unavailable'])} |")
        lines.append("")
    lines += ["## Runtime per dataset (seconds)", "", "| N | Node | Check | Mean | Median | p95 | Max |",
              "|---:|---|---|---:|---:|---:|---:|"]
    for _, row in runtime.iterrows():
        lines.append(
            f"| {int(row['n'])} | {row['node']} | {row['check']} | {_fmt(row['mean_seconds'])} | "
            f"{_fmt(row['median_seconds'])} | {_fmt(row['p95_seconds'])} | {_fmt(row['max_seconds'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(
    raw: pd.DataFrame,
    config: DiagnosticConfig,
    output_dir: str | Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Validate the grid and write the summaries; raise on an incomplete grid unless told otherwise."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    raw = raw.loc[:, list(RAW_COLUMNS)].copy()
    hashes = set(raw["config_hash"].astype(str))
    if raw.empty or hashes != {config.config_hash}:
        raise ValueError(f"rows carry config_hash values {sorted(hashes)}, expected {config.config_hash}")
    grid = check_complete_grid(raw, config)
    if require_complete and not grid["complete"]:
        raise ValueError(f"incomplete information-diagnostic grid: {grid}")
    cells = summarize_cells(raw)
    runtime = summarize_runtime(raw)
    _atomic_text(output / "cell_summary.csv", cells.to_csv(index=False, lineterminator="\n"))
    _atomic_text(output / "runtime_summary.csv", runtime.to_csv(index=False, lineterminator="\n"))
    summary = {
        "schema_version": 1,
        "experiment": config.experiment,
        "config_hash": config.config_hash,
        "master_seed": config.master_seed,
        "grid": {key: (value if key != "missing_examples" else [list(v) for v in value]) for key, value in grid.items()},
        "nominal_threshold": NOMINAL,
        "warning_rule": "status ok and p <= threshold; unavailable counts in the denominator as no warning",
        "info_status_counts": {str(k): int(v) for k, v in raw["info_status"].value_counts().items()},
        "lof_status_counts": {str(k): int(v) for k, v in raw["lof_status"].value_counts().items()},
        "cells": json.loads(cells.to_json(orient="records")),
        "runtime": json.loads(runtime.to_json(orient="records")),
    }
    _atomic_text(output / "summary.json", json.dumps(summary, indent=2) + "\n")
    _atomic_text(output / "report.md", _report(summary, cells, runtime))
    return summary
