"""Evidence summaries and release gates for validation raw rows.

This companion never refits a model.  It consumes the runner's public raw-row
contract, expands the canonical metric JSON, and computes descriptive and gate
statistics with explicit denominators.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .mediation_validation import (
    COMBINATION_COLUMNS,
    EVIDENCE_ARTIFACTS,
    RAW_COLUMNS,
    ValidationConfig,
    cell_definition,
    expected_combinations,
)


WILSON_Z = 1.959963984540054
_DIRECT_MODERATOR_METRICS = {"TNIE_W0", "TNIE_W1"}
_FATAL_STATUSES = {
    "fit_failed",
    "invalid_specification",
    "invalid_data",
    "unsupported_analysis",
    "integration_unresolved",
    "incomplete",
}


def wilson(
    successes: int,
    trials: int,
    z: float = WILSON_Z,
) -> tuple[float | None, float | None]:
    """Return a two-sided Wilson interval, including zero/one boundaries."""

    if trials == 0:
        return None, None
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("Wilson successes/trials must satisfy 0 <= successes <= trials")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * trials)) / trials) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def expand_metrics(raw: pd.DataFrame, config: ValidationConfig) -> pd.DataFrame:
    """Expand one canonical metrics JSON object per raw combination."""

    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw metrics columns do not match the frozen contract")
    rows: list[dict[str, Any]] = []
    for _, source in raw.iterrows():
        cell_id = str(source["cell_id"])
        definition = cell_definition(cell_id)
        try:
            metrics = json.loads(str(source["metrics_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid metrics_json for {cell_id}") from exc
        if not isinstance(metrics, Mapping) or set(metrics) != set(definition.metric_names):
            raise ValueError(f"metrics_json for {cell_id} does not match its fixed metric names")
        for metric in definition.metric_names:
            record = metrics[metric]
            if not isinstance(record, Mapping):
                raise ValueError(f"metric {metric} in {cell_id} is not a mapping")
            rows.append(
                {
                    "cell_id": cell_id,
                    "replicate": int(source["replicate"]),
                    "metric": metric,
                    "outcome_kind": definition.outcome_kind,
                    "truth": record.get("truth"),
                    "estimate": record.get("estimate"),
                    "bias": record.get("bias"),
                    "lower": record.get("lower"),
                    "upper": record.get("upper"),
                    "coverage": _as_bool(record.get("coverage")),
                    "width": record.get("width"),
                    "zero_exclusion": _as_bool(record.get("zero_exclusion")),
                    "interval_available": _as_bool(record.get("interval_available")),
                    "status": str(record.get("status") or source["status"]),
                    "reason": record.get("reason"),
                    "runtime_seconds": float(source["runtime_seconds"]),
                    "fit_count": source["fit_count"],
                    "draw_budget": source["draw_budget"],
                    "population_outcome_sd": definition.population_outcome_sd,
                }
            )
    return pd.DataFrame(rows)


def _mean_or_none(values: pd.Series) -> float | None:
    finite = pd.to_numeric(values, errors="coerce").dropna()
    return None if finite.empty else float(finite.mean())


def _wilson_fields(successes: int, trials: int, prefix: str) -> dict[str, Any]:
    lower, upper = wilson(successes, trials)
    return {
        f"{prefix}_successes": int(successes),
        f"{prefix}_trials": int(trials),
        prefix: None if trials == 0 else float(successes / trials),
        f"{prefix}_wilson_lower": lower,
        f"{prefix}_wilson_upper": upper,
    }


def summarize_metrics(
    long: pd.DataFrame,
    raw: pd.DataFrame,
    config: ValidationConfig,
) -> pd.DataFrame:
    """Compute per-cell/per-metric summaries with explicit denominators."""

    records: list[dict[str, Any]] = []
    for (cell_id, metric), group in long.groupby(["cell_id", "metric"], sort=True):
        definition = cell_definition(str(cell_id))
        attempted = len(group)
        estimates = pd.to_numeric(group["estimate"], errors="coerce")
        biases = pd.to_numeric(group["bias"], errors="coerce")
        finite = estimates.notna()
        available = group["interval_available"].astype(bool)
        fatal = group["status"].isin(_FATAL_STATUSES) | ~finite
        unavailable = ~available
        coverage_successes = int(group["coverage"].astype(bool).sum())
        coverage_lower, coverage_upper = wilson(coverage_successes, attempted)
        available_successes = int(group.loc[available, "coverage"].astype(bool).sum())
        available_trials = int(available.sum())
        available_lower, available_upper = wilson(available_successes, available_trials)
        zero_successes = int(group["zero_exclusion"].astype(bool).sum())
        zero_lower, zero_upper = wilson(zero_successes, attempted)
        abs_bias = biases.abs().dropna()
        records.append(
            {
                "cell_id": str(cell_id),
                "metric": str(metric),
                "outcome_kind": definition.outcome_kind,
                "attempted_rows": attempted,
                "finite_estimates": int(finite.sum()),
                "fatal_rows": int(fatal.sum()),
                "interval_available_rows": available_trials,
                "unavailable_interval_rows": int(unavailable.sum()),
                "unavailable_or_fatal_rows": int((unavailable | fatal).sum()),
                "mean_bias": _mean_or_none(biases),
                "absolute_bias": None if abs_bias.empty else float(abs_bias.mean()),
                "rmse": None if biases.dropna().empty else float(np.sqrt(np.mean(np.square(biases.dropna())))),
                "mean_width": _mean_or_none(group.loc[available, "width"]),
                "zero_exclusions": zero_successes,
                "zero_exclusion_rate": float(zero_successes / attempted) if attempted else None,
                "runtime_mean_seconds": _mean_or_none(group["runtime_seconds"]),
                "fit_count_mean": _mean_or_none(group["fit_count"]),
                "draw_budget_min": _mean_or_none(group["draw_budget"]),
                "draw_budget_max": None if group["draw_budget"].dropna().empty else float(pd.to_numeric(group["draw_budget"], errors="coerce").max()),
                "population_outcome_sd": definition.population_outcome_sd,
                **_wilson_fields(coverage_successes, attempted, "coverage"),
                "available_only_coverage": None if available_trials == 0 else float(available_successes / available_trials),
                "available_only_coverage_wilson_lower": available_lower,
                "available_only_coverage_wilson_upper": available_upper,
                "zero_exclusion_wilson_lower": zero_lower,
                "zero_exclusion_wilson_upper": zero_upper,
                "unavailable_interval_rate": float(unavailable.sum() / attempted) if attempted else None,
                "unavailable_or_fatal_rate": float((unavailable | fatal).sum() / attempted) if attempted else None,
            }
        )
    return pd.DataFrame(records)


def _eligible(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    return summary.loc[
        ~((summary["cell_id"] == "cell10_moderated_n150") & summary["metric"].isin(_DIRECT_MODERATOR_METRICS))
    ]


def evaluate_gates(
    summary: pd.DataFrame,
    raw: pd.DataFrame,
    config: ValidationConfig,
) -> dict[str, Any]:
    """Evaluate the locked gates without allowing power to affect release."""

    expected = expected_combinations(config)
    observed = set(raw[list(COMBINATION_COLUMNS)].itertuples(index=False, name=None))
    complete_grid = observed == expected and not raw.duplicated(subset=list(COMBINATION_COLUMNS)).any()
    gates = dict(config.gates)
    eligible = _eligible(summary)

    continuous = eligible.loc[eligible["outcome_kind"] == "continuous"]
    binary = eligible.loc[eligible["outcome_kind"] == "binary"]
    continuous_values = [
        float(row.absolute_bias) / float(row.population_outcome_sd)
        for row in continuous.itertuples()
        if row.absolute_bias is not None and row.population_outcome_sd not in (None, 0)
    ]
    binary_values = [float(row.absolute_bias) for row in binary.itertuples() if row.absolute_bias is not None]
    coverage_values = [
        float(value) for value in eligible["coverage_wilson_lower"].dropna().tolist()
    ]
    null_rows = eligible.loc[eligible["metric"].isin({"TNIE"}) & (eligible["outcome_kind"] == "continuous")]
    null_rows = null_rows.loc[null_rows["cell_id"].isin({"cell03_no_a_to_m_n100", "cell04_no_m_to_y_n100", "cell05_no_mediation_n100"})]
    null_upper = [float(value) for value in null_rows["zero_exclusion_wilson_upper"].dropna().tolist()]
    unavailable_rates = [float(value) for value in eligible["unavailable_or_fatal_rate"].dropna().tolist()]

    results = {
        "continuous_abs_bias_sd": {
            "threshold": gates["continuous_abs_bias_sd"],
            "observed": max(continuous_values, default=None),
            "passed": bool(continuous_values) and max(continuous_values) <= gates["continuous_abs_bias_sd"],
        },
        "binary_abs_bias_probability": {
            "threshold": gates["binary_abs_bias_probability"],
            "observed": max(binary_values, default=None),
            "passed": bool(binary_values) and max(binary_values) <= gates["binary_abs_bias_probability"],
        },
        "coverage_wilson_lower": {
            "threshold": gates["coverage_wilson_lower"],
            "observed": min(coverage_values, default=None),
            "passed": bool(coverage_values) and min(coverage_values) >= gates["coverage_wilson_lower"],
        },
        "null_false_zero_wilson_upper": {
            "threshold": gates["null_false_zero_wilson_upper"],
            "observed": max(null_upper, default=None),
            "passed": not null_upper or max(null_upper) <= gates["null_false_zero_wilson_upper"],
        },
        "unavailable_or_fatal_max": {
            "threshold": gates["unavailable_or_fatal_max"],
            "observed": max(unavailable_rates, default=None),
            "passed": bool(unavailable_rates) and max(unavailable_rates) <= gates["unavailable_or_fatal_max"],
        },
    }
    for value in results.values():
        value["passed"] = bool(value["passed"] and complete_grid)
    return {
        "complete_grid": complete_grid,
        "gates": results,
        "overall_pass": complete_grid and all(value["passed"] for value in results.values()),
        "power_is_descriptive": True,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _report_markdown(
    raw: pd.DataFrame,
    summary: pd.DataFrame,
    gate_result: Mapping[str, Any],
    config: ValidationConfig,
    *,
    stress_separate: bool,
) -> str:
    lines = [
        "# Mintmed validation evidence",
        "",
        "## Scope and frozen design",
        "",
        f"The report covers the declared `{config.experiment}` design with {len(raw)} observed inferential rows and {len(config.cell_ids)} selected cells. The locked matrix is not changed by reporting.",
        "",
        "## Reproducibility and shard contract",
        "",
        f"Configuration hash: `{config.config_hash}`. Stable combination key: `{COMBINATION_COLUMNS}`. Scientific rows are comparable after sorting by cell ID and replicate; runtime is descriptive.",
        "",
        "## Cell and metric summaries",
        "",
        summary.to_string(index=False) if not summary.empty else "No inferential metric rows were observed.",
        "",
        "## Gate results",
        "",
        f"Overall gate result: **{'PASS' if gate_result['overall_pass'] else 'FAIL'}**. Power is descriptive only and is not a release gate.",
        "",
        "| Gate | Observed | Threshold | Passed |",
        "|---|---:|---:|:---:|",
    ]
    for name, result in gate_result["gates"].items():
        lines.append(f"| {name} | {result['observed']} | {result['threshold']} | {result['passed']} |")
    lines.extend(
        [
            "",
            "## Failures and unavailable intervals",
            "",
            "Unavailable intervals count as noncoverage; failed rows remain in attempted and fatal denominators.",
            "",
            "## Stress diagnostics",
            "",
            f"Stress diagnostics are separate from inferential denominators: **{stress_separate}**.",
            "",
            "## Limitations and stopping rule",
            "",
            "This evidence package is valid only for the frozen cells, seeds, bootstrap settings, and declared gates. Power does not change the stopping decision.",
            "",
            "## Provenance",
            "",
            f"Schema version: `{config.schema_version}`; Python/runtime details are recorded in metadata.json without output paths.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(raw: pd.DataFrame, config: ValidationConfig, output_dir: Path) -> None:
    """Write the complete evidence artifact set from raw rows only."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw metrics columns do not match the frozen contract")
    raw = raw.loc[:, list(RAW_COLUMNS)].copy()
    _atomic_text(output / "raw_metrics.csv", raw.to_csv(index=False, lineterminator="\n"))
    long = expand_metrics(raw, config)
    summary = summarize_metrics(long, raw, config)
    gate_result = evaluate_gates(summary, raw, config)
    _atomic_text(output / "cell_summary.csv", summary.to_csv(index=False, lineterminator="\n"))
    stress_separate = (output / "stress_metrics.csv").is_file()
    summary_payload = {
        "schema_version": 1,
        "config_hash": config.config_hash,
        "expected_rows": int(len(expected_combinations(config))),
        "observed_rows": int(len(raw)),
        "complete_grid": bool(gate_result["complete_grid"]),
        "combination_columns": list(COMBINATION_COLUMNS),
        "cell_summaries": _json_safe(summary.to_dict(orient="records")),
        "gates": _json_safe(gate_result),
        "stress": {
            "separate": stress_separate,
            "excluded_from_inferential_denominators": True,
        },
        "provenance": {
            "experiment": config.experiment,
            "bootstrap_replicates": config.bootstrap_replicates,
            "bootstrap_mode": config.bootstrap_mode,
            "integration_draws": config.integration_draws,
        },
    }
    _atomic_text(output / "summary.json", json.dumps(summary_payload, indent=2, sort_keys=True) + "\n")
    _atomic_text(
        output / "report.md",
        _report_markdown(raw, summary, gate_result, config, stress_separate=stress_separate),
    )


__all__ = [
    "WILSON_Z",
    "evaluate_gates",
    "expand_metrics",
    "summarize_metrics",
    "wilson",
    "write_report",
]
