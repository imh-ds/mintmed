"""Evidence summaries and release gates for validation raw rows.

This companion never refits a model.  It consumes the runner's public raw-row
contract, expands the canonical metric JSON, and computes descriptive and gate
statistics with explicit denominators.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binom

from .mediation_validation import (
    COMBINATION_COLUMNS,
    NULL_TNIE_CELL_IDS,
    RAW_COLUMNS,
    ValidationConfig,
    cell_definition,
    coverage_rule,
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
        try:
            provenance = json.loads(str(source["provenance_json"]))
        except (TypeError, json.JSONDecodeError):
            provenance = {}
        bootstrap_failed = provenance.get("bootstrap_failed") if isinstance(provenance, Mapping) else None
        for metric in definition.metric_names:
            record = metrics[metric]
            if not isinstance(record, Mapping):
                raise ValueError(f"metric {metric} in {cell_id} is not a mapping")  # noqa: TRY004
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
                    "bootstrap_failed": bootstrap_failed,
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
        f"{prefix}_mc_se": None if trials == 0 else float(math.sqrt((successes / trials) * (1.0 - successes / trials) / trials)),
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
        available_successes = int(group.loc[available, "coverage"].astype(bool).sum())
        available_trials = int(available.sum())
        available_lower, available_upper = wilson(available_successes, available_trials)
        draw_values = pd.to_numeric(group["draw_budget"], errors="coerce").dropna()
        zero_successes = int(group["zero_exclusion"].astype(bool).sum())
        # Under the <400-replicate rule a single failed refit withholds every
        # interval; count datasets lost to only one or two failures.
        few_failures = pd.to_numeric(group.get("bootstrap_failed"), errors="coerce").isin([1, 2])
        few_failure_withheld = int((unavailable & few_failures).sum())
        zero_lower, zero_upper = wilson(zero_successes, attempted)
        finite_biases = biases.dropna()
        mean_bias = None if finite_biases.empty else float(finite_biases.mean())
        truths = pd.to_numeric(group["truth"], errors="coerce")
        lowers = pd.to_numeric(group["lower"], errors="coerce")
        uppers = pd.to_numeric(group["upper"], errors="coerce")
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
                "mean_bias": mean_bias,
                # Simulation-study bias is |mean(estimate - truth)|; the mean
                # absolute error is descriptive and also carries sampling spread.
                "absolute_bias": None if mean_bias is None else abs(mean_bias),
                "bias_mc_se": (
                    None
                    if len(finite_biases) < 2
                    else float(finite_biases.std(ddof=1) / math.sqrt(len(finite_biases)))
                ),
                "mean_absolute_error": None if finite_biases.empty else float(finite_biases.abs().mean()),
                "rmse": None if biases.dropna().empty else float(np.sqrt(np.mean(np.square(biases.dropna())))),
                "mean_width": _mean_or_none(group.loc[available, "width"]),
                "few_failure_withheld_rows": few_failure_withheld,
                "few_failure_withheld_rate": float(few_failure_withheld / attempted) if attempted else None,
                "zero_exclusions": zero_successes,
                "zero_exclusion_rate": float(zero_successes / attempted) if attempted else None,
                "zero_exclusion_mc_se": None if attempted == 0 else float(math.sqrt((zero_successes / attempted) * (1.0 - zero_successes / attempted) / attempted)),
                "runtime_mean_seconds": _mean_or_none(group["runtime_seconds"]),
                "fit_count_mean": _mean_or_none(group["fit_count"]),
                "draw_budget_min": None if draw_values.empty else float(draw_values.min()),
                "draw_budget_max": None if draw_values.empty else float(draw_values.max()),
                "population_outcome_sd": definition.population_outcome_sd,
                **_wilson_fields(coverage_successes, attempted, "coverage"),
                # Descriptive: on which side available intervals missed the truth.
                "truth_above_interval_rows": int((available & (truths > uppers)).sum()),
                "truth_below_interval_rows": int((available & (truths < lowers)).sum()),
                "available_only_coverage": None if available_trials == 0 else float(available_successes / available_trials),
                "available_only_coverage_wilson_lower": available_lower,
                "available_only_coverage_wilson_upper": available_upper,
                "available_only_coverage_mc_se": None if available_trials == 0 else float(math.sqrt((available_successes / available_trials) * (1.0 - available_successes / available_trials) / available_trials)),
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


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def _scaled_mc_se(value: Any, scale: float) -> float | None:
    return float(value) / scale if _present(value) else None


def _bias_gate(values: list[tuple[float, float | None]], threshold: float) -> dict[str, Any]:
    """Gate the worst |mean bias| and report its Monte Carlo SE descriptively."""

    if not values:
        return {
            "threshold": threshold,
            "observed": None,
            "observed_mc_se": None,
            "threshold_within_mc_band": None,
            "passed": False,
        }
    observed, mc_se = max(values, key=lambda item: item[0])
    return {
        "threshold": threshold,
        "observed": observed,
        "observed_mc_se": mc_se,
        # Descriptive only: whether the threshold lies within 1.96 MC SEs of the
        # worst observed bias, i.e. the verdict is not Monte Carlo decisive.
        "threshold_within_mc_band": (
            None if mc_se is None else bool(abs(observed - threshold) <= 1.96 * mc_se)
        ),
        "passed": observed <= threshold,
    }


def coverage_critical_count(trials: int, gated_effects: int, nominal: float, family_alpha: float) -> int:
    """Return the largest covered count that fails the exact binomial rule.

    An effect fails when ``BinomialCDF(covered; trials, nominal) <=
    family_alpha / gated_effects``. Returns -1 when no count can fail.
    """

    if trials < 1 or gated_effects < 1:
        raise ValueError("trials and gated_effects must be positive")
    per_effect_alpha = family_alpha / gated_effects
    counts = np.arange(trials + 1)
    failing = counts[binom.cdf(counts, trials, nominal) <= per_effect_alpha]
    return int(failing.max()) if failing.size else -1


def _exact_binomial_coverage_gate(eligible: pd.DataFrame, gates: Mapping[str, float]) -> dict[str, Any]:
    """Bonferroni-adjusted one-sided exact binomial test of each effect's coverage."""

    nominal = float(gates["coverage_nominal"])
    family_alpha = float(gates["coverage_family_alpha"])
    rows = eligible.loc[pd.to_numeric(eligible["coverage_trials"], errors="coerce") > 0]
    gated_effects = len(rows)
    per_effect_alpha = family_alpha / gated_effects if gated_effects else None
    effects = []
    for row in rows.itertuples():
        covered, trials = int(row.coverage_successes), int(row.coverage_trials)
        p_value = float(binom.cdf(covered, trials, nominal))
        effects.append(
            {
                "cell_id": row.cell_id,
                "metric": row.metric,
                "covered": covered,
                "trials": trials,
                "p_value": p_value,
                "critical_count": coverage_critical_count(trials, gated_effects, nominal, family_alpha),
                "truth_above_interval_rows": int(row.truth_above_interval_rows),
                "truth_below_interval_rows": int(row.truth_below_interval_rows),
                "passed": p_value > per_effect_alpha,
            }
        )
    return {
        "rule": "exact_binomial_bonferroni",
        "threshold": per_effect_alpha,
        "observed": min((effect["p_value"] for effect in effects), default=None),
        "nominal": nominal,
        "family_alpha": family_alpha,
        "gated_effects": gated_effects,
        "failing_effects": [f"{effect['cell_id']}:{effect['metric']}" for effect in effects if not effect["passed"]],
        "effects": effects,
        "passed": bool(effects) and all(effect["passed"] for effect in effects),
    }


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
    continuous_bias = [
        (
            float(row.absolute_bias) / float(row.population_outcome_sd),
            _scaled_mc_se(row.bias_mc_se, float(row.population_outcome_sd)),
        )
        for row in continuous.itertuples()
        if _present(row.absolute_bias) and row.population_outcome_sd not in (None, 0)
    ]
    binary_bias = [
        (float(row.absolute_bias), _scaled_mc_se(row.bias_mc_se, 1.0))
        for row in binary.itertuples()
        if _present(row.absolute_bias)
    ]
    if coverage_rule(gates) == "wilson_lower":
        coverage_values = [
            float(value) for value in eligible["coverage_wilson_lower"].dropna().tolist()
        ]
        coverage_gate = (
            "coverage_wilson_lower",
            {
                "threshold": gates["coverage_wilson_lower"],
                "observed": min(coverage_values, default=None),
                "passed": bool(coverage_values) and min(coverage_values) >= gates["coverage_wilson_lower"],
            },
        )
    else:
        coverage_gate = ("coverage_exact_binomial_bonferroni", _exact_binomial_coverage_gate(eligible, gates))
    null_rows = eligible.loc[eligible["metric"].isin({"TNIE"}) & (eligible["outcome_kind"] == "continuous")]
    null_rows = null_rows.loc[null_rows["cell_id"].isin(set(NULL_TNIE_CELL_IDS))]
    null_upper = [float(value) for value in null_rows["zero_exclusion_wilson_upper"].dropna().tolist()]
    unavailable_rates = [float(value) for value in eligible["unavailable_or_fatal_rate"].dropna().tolist()]

    results = {
        "continuous_abs_bias_sd": _bias_gate(continuous_bias, gates["continuous_abs_bias_sd"]),
        "binary_abs_bias_probability": _bias_gate(binary_bias, gates["binary_abs_bias_probability"]),
        coverage_gate[0]: coverage_gate[1],
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
        "Bias gates compare the absolute mean bias |mean(estimate - truth)| with the threshold; the mean absolute error is reported descriptively in the summaries. The MC SE column is the Monte Carlo standard error of the worst mean bias.",
        "",
        "| Gate | Observed | MC SE | Threshold | Passed |",
        "|---|---:|---:|---:|:---:|",
    ]
    for name, result in gate_result["gates"].items():
        mc_se = result.get("observed_mc_se")
        lines.append(
            f"| {name} | {result['observed']} | {'' if mc_se is None else mc_se} | {result['threshold']} | {result['passed']} |"
        )
    exact = gate_result["gates"].get("coverage_exact_binomial_bonferroni")
    if exact is not None:
        lines.extend(
            [
                "",
                "### Coverage: exact binomial with Bonferroni adjustment",
                "",
                f"Each of the {exact['gated_effects']} gated effects fails when the one-sided exact binomial p-value against "
                f"{exact['nominal']} coverage is at most {exact['family_alpha']} / {exact['gated_effects']}. "
                "Missing intervals count as misses. Miss sides are descriptive.",
                "",
                "| Cell | Metric | Covered | Trials | Critical count | p-value | Truth above / below | Passed |",
                "|---|---|---:|---:|---:|---:|---|:---:|",
            ]
        )
        for effect in exact["effects"]:
            lines.append(
                f"| {effect['cell_id']} | {effect['metric']} | {effect['covered']} | {effect['trials']} | "
                f"{effect['critical_count']} | {effect['p_value']:.4g} | "
                f"{effect['truth_above_interval_rows']} / {effect['truth_below_interval_rows']} | {effect['passed']} |"
            )
    lines.extend(
        [
            "",
            "## Failures and unavailable intervals",
            "",
            "Unavailable intervals count as noncoverage; failed rows remain in attempted and fatal denominators.",
            "",
            _interval_rule_sentence(config),
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


def _require_single_configuration(raw: pd.DataFrame, config: ValidationConfig) -> None:
    """Refuse rows produced under a configuration other than ``config``."""

    if raw.empty:
        return
    hashes = set(raw["config_hash"].astype(str))
    if hashes != {config.config_hash}:
        foreign = sorted(hashes - {config.config_hash})
        raise ValueError(
            f"raw rows carry config_hash values {foreign} other than the config's {config.config_hash}"
        )
    expected = {
        "config_hash": config.config_hash,
        "bootstrap_requested": config.bootstrap_replicates,
        "bootstrap_mode": config.bootstrap_mode,
    }
    for index, text in raw["provenance_json"].items():
        try:
            provenance = json.loads(str(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid provenance_json in raw row {index}") from exc
        if not isinstance(provenance, Mapping):
            raise ValueError(f"invalid provenance_json in raw row {index}")
        for key, value in expected.items():
            if key in provenance and provenance[key] != value:
                raise ValueError(
                    f"raw row {index} provenance {key}={provenance[key]!r} contradicts the config ({value!r})"
                )


def _interval_rule(config: ValidationConfig) -> str:
    """Name the bootstrap interval rule the configured replicate count implies."""

    if config.bootstrap_mode == "quick_diagnostic":
        return "quick_diagnostic_provisional"
    if config.bootstrap_replicates >= 400:
        return "ge_390_successes_and_le_1pct_failures"
    return f"all_{config.bootstrap_replicates}_refits_must_succeed"


def _interval_rule_sentence(config: ValidationConfig) -> str:
    rule = _interval_rule(config)
    if rule.startswith("all_"):
        return (
            f"Interval rule: zero-failure. With {config.bootstrap_replicates} standard replicates (< 400), a single "
            "failed refit withholds every interval for that dataset; `few_failure_withheld_rows` counts the datasets "
            "whose intervals were withheld because only one or two refits failed."
        )
    if rule == "quick_diagnostic_provisional":
        return "Interval rule: quick-diagnostic; every interval is provisional and is not release evidence."
    return "Interval rule: at least 390 successful refits and at most 1% failures."


def write_report(raw: pd.DataFrame, config: ValidationConfig, output_dir: Path) -> None:
    """Write the complete evidence artifact set from raw rows only."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw metrics columns do not match the frozen contract")
    raw = raw.loc[:, list(RAW_COLUMNS)].copy()
    _require_single_configuration(raw, config)
    _atomic_text(output / "raw_metrics.csv", raw.to_csv(index=False, lineterminator="\n"))
    long = expand_metrics(raw, config)
    summary = summarize_metrics(long, raw, config)
    gate_result = evaluate_gates(summary, raw, config)
    _atomic_text(output / "cell_summary.csv", summary.to_csv(index=False, lineterminator="\n"))
    stress_separate = (output / "stress_metrics.csv").is_file()
    summary_payload = {
        "schema_version": 1,
        "config_hash": config.config_hash,
        "expected_rows": len(expected_combinations(config)),
        "observed_rows": len(raw),
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
            "interval_rule": _interval_rule(config),
        },
    }
    _atomic_text(output / "summary.json", json.dumps(summary_payload, indent=2, sort_keys=True) + "\n")
    _atomic_text(
        output / "report.md",
        _report_markdown(raw, summary, gate_result, config, stress_separate=stress_separate),
    )


__all__ = [
    "WILSON_Z",
    "coverage_critical_count",
    "evaluate_gates",
    "expand_metrics",
    "summarize_metrics",
    "wilson",
    "write_report",
]
