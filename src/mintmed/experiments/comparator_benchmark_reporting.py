"""Summaries and paired Mintmed comparisons for the Task 17 comparator raw rows.

``write_report(raw, config, output_dir)`` is the reporting companion used by
``scripts/aggregate_shards.py``. It never refits anything. It expands the
``records_json`` of every ``(tool, cell_id, replicate)`` row and writes, per
tool, mode, cell and effect: bias, bias Monte Carlo SE, RMSE, coverage with a
Wilson interval, mean width, zero exclusion (power, or false positives in the
null-TNIE cells), failure rate and runtime.

When Mintmed's raw rows are supplied (``mintmed_raw_paths``, or the
``MINTMED_REFERENCE_RAW`` environment variable holding paths separated by
``os.pathsep``), it also applies the plan's ``stage1.comparison_rules`` to the
primary mode of each comparator, paired by dataset. The gate and tier logic
(``paired_comparison``, ``judge``, ``classify_tier``) is pure Python.

Interpretation choices (to be frozen in the Stage 1 charter, T17-S7):

* Primary agreement metrics are judged on the lower Wilson bound of the
  agreement rate (``tier``); ``tier_primary_on_point`` judges them on the
  observed rate instead, because a Wilson lower bound of 0.99 needs about 380
  significant pairs even with perfect agreement. Every guardrail loss is judged on the upper bound of a paired
  percentile bootstrap interval (datasets resampled jointly, 2000 draws, seed
  derived from the tool, cell and effect).
* A dataset whose interval is missing for either method counts as a decision
  disagreement (conservative) and, as in Mintmed's gates, as noncoverage.
* Sign agreement is evaluated on the datasets where at least one method's
  interval excludes zero: the two point estimates must have the same sign.
* Tolerable-tier limits the plan does not list (sign agreement, bias excess)
  keep their negligible-tier values. ``coverage_abs_min`` applies to Mintmed's
  coverage point estimate.
* A check that cannot be computed (for example decision agreement for cell 10's
  point-only ``TNIE_W0``/``TNIE_W1`` in Mintmed, or the width ratio of a
  structural zero) is reported as not applicable and does not affect the tier.
"""

from __future__ import annotations

import json
import math
import os
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .comparator_benchmark import (
    COMBINATION_COLUMNS,
    ESTIMATED_STATUSES,
    FAILED_STATUSES,
    MODES,
    RAW_COLUMNS,
    TOOLS,
    expected_combinations,
)
from .mediation_validation import NULL_TNIE_CELL_IDS, ValidationConfig, cell_definition, seed_pair
from .mediation_validation_reporting import wilson

REFERENCE_ENV = "MINTMED_REFERENCE_RAW"
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260928

# Plan stage1.comparison_rules (owner confirmed 2026-09-28).
COMPARISON_RULES: dict[str, Any] = {
    "primary": {
        "decision_agreement_min": 0.95,
        "sign_agreement_when_either_significant_min": 0.99,
    },
    "guardrails": {
        "bias_excess_sd_max": 0.02,
        "coverage_loss_pp_max": 2.5,
        "false_positive_excess_pp_max": 2.0,
        "power_loss_pp_max": 5.0,
        "width_ratio_max": 1.10,
    },
    "tolerable": {
        "decision_agreement_min": 0.90,
        "coverage_loss_pp_max": 5.0,
        "coverage_abs_min": 0.90,
        "false_positive_excess_pp_max": 3.0,
        "power_loss_pp_max": 10.0,
        "width_ratio_max": 1.25,
    },
}
# check name -> (limit key, direction, judged bound)
_CHECKS: dict[str, tuple[str, str, str]] = {
    "decision_agreement": ("decision_agreement_min", "min", "lower"),
    "sign_agreement": ("sign_agreement_when_either_significant_min", "min", "lower"),
    "bias_excess_sd": ("bias_excess_sd_max", "max", "upper"),
    "coverage_loss_pp": ("coverage_loss_pp_max", "max", "upper"),
    "false_positive_excess_pp": ("false_positive_excess_pp_max", "max", "upper"),
    "power_loss_pp": ("power_loss_pp_max", "max", "upper"),
    "width_ratio": ("width_ratio_max", "max", "upper"),
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return bool(value)


def _float_or_nan(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def expand_records(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per tool x mode x cell x replicate x effect."""

    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("comparator raw columns do not match the frozen contract")
    rows: list[dict[str, Any]] = []
    for source in raw.itertuples(index=False):
        cell_id = str(source.cell_id)
        definition = cell_definition(cell_id)
        records = json.loads(str(source.records_json))
        if set(records) != set(MODES):
            raise ValueError(f"{source.tool}/{cell_id}/{source.replicate}: records_json modes {sorted(records)}")
        for mode, effects in records.items():
            if set(effects) != set(definition.metric_names):
                raise ValueError(f"{source.tool}/{cell_id}: records_json effects do not match the cell")
            for effect, record in effects.items():
                rows.append(
                    {
                        "tool": str(source.tool),
                        "mode": mode,
                        "cell_id": cell_id,
                        "replicate": int(source.replicate),
                        "effect": effect,
                        "truth": _float_or_nan(record.get("truth")),
                        "estimate": _float_or_nan(record.get("estimate")),
                        "bias": _float_or_nan(record.get("bias")),
                        "lower": _float_or_nan(record.get("lower")),
                        "upper": _float_or_nan(record.get("upper")),
                        "coverage": _as_bool(record.get("coverage")),
                        "width": _float_or_nan(record.get("width")),
                        "zero_exclusion": _as_bool(record.get("zero_exclusion")),
                        "interval_available": _as_bool(record.get("interval_available")),
                        "status": str(record.get("status")),
                        "reason": record.get("reason"),
                        "runtime_seconds": _float_or_nan(record.get("runtime_seconds")),
                        "sims_requested": _float_or_nan(record.get("sims_requested")),
                        "sims_successful": _float_or_nan(record.get("sims_successful")),
                        "population_outcome_sd": definition.population_outcome_sd,
                        "outcome_kind": definition.outcome_kind,
                    }
                )
    return pd.DataFrame(rows)


def _rate_fields(successes: int, trials: int, prefix: str) -> dict[str, Any]:
    lower, upper = wilson(successes, trials)
    return {
        f"{prefix}_successes": int(successes),
        f"{prefix}_trials": int(trials),
        prefix: None if trials == 0 else successes / trials,
        f"{prefix}_wilson_lower": lower,
        f"{prefix}_wilson_upper": upper,
    }


def is_null_effect(cell_id: str, effect: str) -> bool:
    return effect == "TNIE" and cell_id in NULL_TNIE_CELL_IDS


def summarize(long: pd.DataFrame) -> pd.DataFrame:
    """Per tool/mode/cell/effect operating characteristics with explicit denominators."""

    records: list[dict[str, Any]] = []
    if long.empty:
        return pd.DataFrame(records)
    for (tool, mode, cell_id, effect), group in long.groupby(["tool", "mode", "cell_id", "effect"], sort=True):
        attempted = len(group)
        not_estimable = int((group["status"] == "not_estimable").sum())
        base = {"tool": tool, "mode": mode, "cell_id": cell_id, "effect": effect, "attempted": attempted,
                "null_effect": is_null_effect(str(cell_id), str(effect))}
        if not_estimable == attempted:
            records.append({**base, "estimable": False, "not_estimable_reason": group["reason"].iloc[0]})
            continue
        finite = group["estimate"].notna() & group["status"].isin(ESTIMATED_STATUSES)
        failed = ~finite
        biases = group.loc[finite, "bias"]
        sd = group["population_outcome_sd"].iloc[0]
        mean_bias = float(biases.mean()) if len(biases) else None
        runtime = group["runtime_seconds"].dropna()
        available = group["interval_available"]
        records.append(
            {
                **base,
                "estimable": True,
                "not_estimable_rows": not_estimable,
                "finite_estimates": int(finite.sum()),
                "failed_rows": int(failed.sum()),
                "failure_rate": float(failed.sum() / attempted),
                "warning_rows": int((group["status"] == "ok_warnings").sum()),
                "mean_bias": mean_bias,
                "abs_bias_sd": None if mean_bias is None or not sd else abs(mean_bias) / sd,
                "bias_mc_se": float(biases.std(ddof=1) / math.sqrt(len(biases))) if len(biases) > 1 else None,
                "rmse": float(np.sqrt(np.mean(np.square(biases)))) if len(biases) else None,
                "interval_available_rows": int(available.sum()),
                "mean_width": float(group.loc[available, "width"].mean()) if available.any() else None,
                # Missing intervals count as noncoverage, as in Mintmed's gates.
                **_rate_fields(int(group["coverage"].sum()), attempted, "coverage"),
                **_rate_fields(int(group["zero_exclusion"].sum()), attempted, "zero_exclusion"),
                "runtime_mean_seconds": float(runtime.mean()) if len(runtime) else None,
                "runtime_median_seconds": float(runtime.median()) if len(runtime) else None,
                "runtime_total_seconds": float(runtime.sum()) if len(runtime) else None,
                "sims_successful_min": float(group["sims_successful"].min()) if group["sims_successful"].notna().any() else None,
            }
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Mintmed reference and paired comparisons


def load_mintmed_reference(paths: Sequence[Path | str]) -> pd.DataFrame:
    """Load Mintmed validation raw rows into one row per cell x replicate x effect.

    Seeds are read as text and checked against ``seed_pair`` so a reference
    produced from other datasets is refused.
    """

    frames = []
    for path in paths:
        raw = pd.read_csv(path, dtype={"data_seed": str, "analysis_seed": str, "config_hash": str, "cell_id": str})
        required = {"cell_id", "replicate", "data_seed", "analysis_seed", "metrics_json"}
        if not required <= set(raw.columns):
            raise ValueError(f"{path}: not a Mintmed validation raw_metrics.csv")
        frames.append(raw)
    if not frames:
        return pd.DataFrame()
    raw = pd.concat(frames, ignore_index=True)
    raw["replicate"] = raw["replicate"].astype(int)
    if raw.duplicated(subset=["cell_id", "replicate"]).any():
        raise ValueError("Mintmed reference rows repeat a (cell_id, replicate)")
    rows = []
    for source in raw.itertuples(index=False):
        metrics = json.loads(str(source.metrics_json))
        rows.extend(
            {
                "cell_id": str(source.cell_id),
                "replicate": int(source.replicate),
                "data_seed": str(source.data_seed),
                "analysis_seed": str(source.analysis_seed),
                "effect": effect,
                "truth": _float_or_nan(record.get("truth")),
                "estimate": _float_or_nan(record.get("estimate")),
                "bias": _float_or_nan(record.get("bias")),
                "lower": _float_or_nan(record.get("lower")),
                "upper": _float_or_nan(record.get("upper")),
                "coverage": _as_bool(record.get("coverage")),
                "width": _float_or_nan(record.get("width")),
                "zero_exclusion": _as_bool(record.get("zero_exclusion")),
                "interval_available": _as_bool(record.get("interval_available")),
            }
            for effect, record in metrics.items()
        )
    return pd.DataFrame(rows)


def check_reference_seeds(reference: pd.DataFrame, master_seed: int) -> None:
    """Refuse Mintmed rows whose seeds are not the config's seeds for that dataset."""

    pairs = reference.drop_duplicates(subset=["cell_id", "replicate"])
    for row in pairs.itertuples(index=False):
        data_seed, analysis_seed = seed_pair(master_seed, cell_definition(row.cell_id).ordinal, int(row.replicate))
        if row.data_seed != str(data_seed) or row.analysis_seed != str(analysis_seed):
            raise ValueError(f"Mintmed reference {row.cell_id}/{row.replicate} was produced from other seeds")


def decisions(lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """+1 / -1 when the interval excludes zero above / below, 0 when it includes zero, NaN if missing."""

    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    out = np.where(lower > 0.0, 1.0, np.where(upper < 0.0, -1.0, 0.0))
    return np.where(np.isfinite(lower) & np.isfinite(upper), out, np.nan)


def _bootstrap_seed(key: str) -> np.random.SeedSequence:
    return np.random.SeedSequence([BOOTSTRAP_SEED, zlib.crc32(key.encode("utf-8"))])


def _percentile_interval(draws: np.ndarray) -> tuple[float | None, float | None]:
    finite = draws[np.isfinite(draws)]
    if finite.size == 0:
        return None, None
    return float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))


def _paired_bootstrap(
    statistic: Any, columns: Sequence[np.ndarray], key: str, draws: int = BOOTSTRAP_DRAWS
) -> tuple[float | None, float | None, float | None]:
    """Point value and percentile interval of ``statistic`` over jointly resampled datasets."""

    n = len(columns[0])
    if n == 0:
        return None, None, None
    point = statistic(*columns)
    if point is None or not math.isfinite(point):
        return None, None, None
    rng = np.random.default_rng(_bootstrap_seed(key))
    indices = rng.integers(0, n, size=(draws, n))
    values = np.array([_finite_or_nan(statistic(*(column[index] for column in columns))) for index in indices])
    lower, upper = _percentile_interval(values)
    return float(point), lower, upper


def _finite_or_nan(value: Any) -> float:
    return float(value) if value is not None and math.isfinite(value) else math.nan


def _abs_bias_excess(scale: float):
    def statistic(bias_m: np.ndarray, bias_c: np.ndarray) -> float:
        return (abs(float(np.mean(bias_m))) - abs(float(np.mean(bias_c)))) / scale

    return statistic


def _mean_difference_pp(left: np.ndarray, right: np.ndarray) -> float:
    return 100.0 * (float(np.mean(left)) - float(np.mean(right)))


def _width_ratio(width_m: np.ndarray, width_c: np.ndarray) -> float | None:
    denominator = float(np.mean(width_c))
    if denominator <= 0.0:
        return None
    return float(np.mean(width_m)) / denominator


def paired_comparison(
    mintmed: pd.DataFrame,
    comparator: pd.DataFrame,
    *,
    tool: str,
    cell_id: str,
    effect: str,
    population_sd: float | None,
    null_effect: bool,
) -> dict[str, Any]:
    """Compute the plan's primary metrics and guardrail losses for one cell-effect.

    ``mintmed`` and ``comparator`` hold one row per replicate with columns
    ``estimate, bias, lower, upper, coverage, width, zero_exclusion,
    interval_available``; they are paired by ``replicate``.
    """

    key = f"{tool}|{cell_id}|{effect}"
    merged = mintmed.merge(comparator, on="replicate", suffixes=("_m", "_c"), how="inner")
    n = len(merged)
    result: dict[str, Any] = {"tool": tool, "cell_id": cell_id, "effect": effect, "pairs": n,
                              "null_effect": bool(null_effect)}
    mintmed_intervals = bool(merged["interval_available_m"].any()) if n else False
    comparator_intervals = bool(merged["interval_available_c"].any()) if n else False
    result["mintmed_point_only"] = not mintmed_intervals

    # Primary: decision and sign agreement (Wilson intervals on the rates).
    if n and mintmed_intervals and comparator_intervals:
        decision_m = decisions(merged["lower_m"], merged["upper_m"])
        decision_c = decisions(merged["lower_c"], merged["upper_c"])
        agree = np.isfinite(decision_m) & np.isfinite(decision_c) & (decision_m == decision_c)
        result.update(_check_fields("decision_agreement", int(agree.sum()), n))
        either = (np.abs(np.nan_to_num(decision_m)) == 1.0) | (np.abs(np.nan_to_num(decision_c)) == 1.0)
        signs_equal = np.sign(merged["estimate_m"].to_numpy(float)) == np.sign(merged["estimate_c"].to_numpy(float))
        result.update(_check_fields("sign_agreement", int((either & signs_equal).sum()), int(either.sum())))
        result["significant_pairs"] = int(either.sum())
        result["opposite_significant_pairs"] = int((np.nan_to_num(decision_m) * np.nan_to_num(decision_c) == -1.0).sum())
    else:
        result.update(_not_applicable("decision_agreement"))
        result.update(_not_applicable("sign_agreement"))

    # Guardrails: paired bootstrap over datasets.
    finite = merged["bias_m"].notna() & merged["bias_c"].notna() if n else pd.Series(dtype=bool)
    result["bias_pairs"] = int(finite.sum()) if n else 0
    if n and finite.any() and population_sd:
        result.update(
            _interval_fields(
                "bias_excess_sd",
                _paired_bootstrap(
                    _abs_bias_excess(float(population_sd)),
                    [merged.loc[finite, "bias_m"].to_numpy(float), merged.loc[finite, "bias_c"].to_numpy(float)],
                    key + "|bias",
                ),
            )
        )
    else:
        result.update(_not_applicable("bias_excess_sd"))
    if n and mintmed_intervals and comparator_intervals:
        coverage_m = merged["coverage_m"].to_numpy(float)
        coverage_c = merged["coverage_c"].to_numpy(float)
        result["mintmed_coverage"] = float(coverage_m.mean())
        result["comparator_coverage"] = float(coverage_c.mean())
        result.update(
            _interval_fields(
                "coverage_loss_pp",
                _paired_bootstrap(lambda m, c: _mean_difference_pp(c, m), [coverage_m, coverage_c], key + "|coverage"),
            )
        )
        exclusion_m = merged["zero_exclusion_m"].to_numpy(float)
        exclusion_c = merged["zero_exclusion_c"].to_numpy(float)
        result["mintmed_zero_exclusion"] = float(exclusion_m.mean())
        result["comparator_zero_exclusion"] = float(exclusion_c.mean())
        if null_effect:
            result.update(
                _interval_fields(
                    "false_positive_excess_pp",
                    _paired_bootstrap(lambda m, c: _mean_difference_pp(m, c), [exclusion_m, exclusion_c], key + "|fp"),
                )
            )
            result.update(_not_applicable("power_loss_pp"))
        else:
            result.update(
                _interval_fields(
                    "power_loss_pp",
                    _paired_bootstrap(lambda m, c: _mean_difference_pp(c, m), [exclusion_m, exclusion_c], key + "|power"),
                )
            )
            result.update(_not_applicable("false_positive_excess_pp"))
        both = (merged["interval_available_m"] & merged["interval_available_c"]).to_numpy(bool)
        if both.any() and float(merged.loc[both, "width_c"].mean()) > 0.0:
            result.update(
                _interval_fields(
                    "width_ratio",
                    _paired_bootstrap(
                        _width_ratio,
                        [merged.loc[both, "width_m"].to_numpy(float), merged.loc[both, "width_c"].to_numpy(float)],
                        key + "|width",
                    ),
                )
            )
        else:
            result.update(_not_applicable("width_ratio"))
    else:
        for name in ("coverage_loss_pp", "false_positive_excess_pp", "power_loss_pp", "width_ratio"):
            result.update(_not_applicable(name))
        result["mintmed_coverage"] = None
    return result


def _check_fields(name: str, successes: int, trials: int) -> dict[str, Any]:
    lower, upper = wilson(successes, trials)
    return {
        name: None if trials == 0 else successes / trials,
        f"{name}_lower": lower,
        f"{name}_upper": upper,
        f"{name}_trials": trials,
    }


def _interval_fields(name: str, values: tuple[float | None, float | None, float | None]) -> dict[str, Any]:
    point, lower, upper = values
    return {name: point, f"{name}_lower": lower, f"{name}_upper": upper}


def _not_applicable(name: str) -> dict[str, Any]:
    return {name: None, f"{name}_lower": None, f"{name}_upper": None}


PRIMARY_CHECKS = ("decision_agreement", "sign_agreement")


def judge(
    comparison: Mapping[str, Any],
    limits: Mapping[str, float],
    *,
    primary_basis: str = "bound",
) -> dict[str, bool | None]:
    """Pass/fail of every applicable check against ``limits`` (None = not applicable).

    Guardrails are always judged on their interval bound. ``primary_basis``
    ``"bound"`` judges the agreement rates on their lower Wilson bound;
    ``"point"`` on the observed rate.
    """

    if primary_basis not in {"bound", "point"}:
        raise ValueError("primary_basis must be 'bound' or 'point'")
    verdicts: dict[str, bool | None] = {}
    for check, (limit_key, direction, bound) in _CHECKS.items():
        use_point = primary_basis == "point" and check in PRIMARY_CHECKS
        value = comparison.get(check if use_point else f"{check}_{bound}")
        if limit_key not in limits or value is None or (isinstance(value, float) and math.isnan(value)):
            verdicts[check] = None
            continue
        limit = float(limits[limit_key])
        verdicts[check] = bool(value >= limit) if direction == "min" else bool(value <= limit)
    return verdicts


def _negligible_limits(rules: Mapping[str, Any]) -> dict[str, float]:
    return {**rules["primary"], **rules["guardrails"]}


def _tolerable_limits(rules: Mapping[str, Any]) -> dict[str, float]:
    # Limits the tolerable tier does not relax keep their negligible values.
    return {**_negligible_limits(rules), **rules["tolerable"]}


def classify_tier(
    comparison: Mapping[str, Any],
    rules: Mapping[str, Any] = COMPARISON_RULES,
    *,
    primary_basis: str = "bound",
) -> dict[str, Any]:
    """Return ``negligible``, ``tolerable`` or ``substantive`` with the per-check verdicts."""

    negligible = judge(comparison, _negligible_limits(rules), primary_basis=primary_basis)
    tolerable_limits = _tolerable_limits(rules)
    tolerable = judge(comparison, tolerable_limits, primary_basis=primary_basis)
    coverage = comparison.get("mintmed_coverage")
    coverage_ok = None if coverage is None else bool(coverage >= float(tolerable_limits["coverage_abs_min"]))
    if all(value is not False for value in negligible.values()):
        tier = "negligible"
    elif all(value is not False for value in tolerable.values()) and coverage_ok is not False:
        tier = "tolerable"
    else:
        tier = "substantive"
    return {
        "tier": tier,
        "negligible_checks": negligible,
        "tolerable_checks": {**tolerable, "coverage_abs_min": coverage_ok},
        "applicable_checks": sorted(name for name, value in negligible.items() if value is not None),
    }


def compare_with_mintmed(long: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Paired comparisons of every comparator's primary mode with Mintmed."""

    rows = []
    primary = long.loc[long["mode"] == "primary"]
    for (tool, cell_id, effect), group in primary.groupby(["tool", "cell_id", "effect"], sort=True):
        if (group["status"] == "not_estimable").all():
            continue
        mine = reference.loc[(reference["cell_id"] == cell_id) & (reference["effect"] == effect)]
        if mine.empty:
            continue
        definition = cell_definition(str(cell_id))
        comparison = paired_comparison(
            mine, group, tool=str(tool), cell_id=str(cell_id), effect=str(effect),
            population_sd=definition.population_outcome_sd, null_effect=is_null_effect(str(cell_id), str(effect)),
        )
        tier = classify_tier(comparison)
        comparison["tier"] = tier["tier"]
        # Descriptive alternative for the charter decision: agreement rates on
        # their observed value (a Wilson lower bound >= 0.99 needs roughly 380
        # significant pairs even with perfect sign agreement).
        comparison["tier_primary_on_point"] = classify_tier(comparison, primary_basis="point")["tier"]
        comparison["checks_json"] = json.dumps(
            {"negligible": tier["negligible_checks"], "tolerable": tier["tolerable_checks"]}, sort_keys=True
        )
        rows.append(comparison)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Artifacts


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
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


def _reference_paths(explicit: Sequence[Path | str] | None) -> list[Path]:
    if explicit is not None:
        return [Path(path) for path in explicit]
    value = os.environ.get(REFERENCE_ENV, "")
    return [Path(item) for item in value.split(os.pathsep) if item]


def _format(value: Any, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def _markdown(summary: pd.DataFrame, comparisons: pd.DataFrame, raw: pd.DataFrame, config: ValidationConfig,
              complete_grid: bool, settings_notes: list[str]) -> str:
    lines = [
        "# Mintmed comparator benchmark (Task 17)",
        "",
        f"Configuration `{config.experiment}` (hash `{config.config_hash}`), {len(raw)} raw rows keyed by "
        f"`{COMBINATION_COLUMNS}`; complete grid: **{complete_grid}**.",
        "",
    ]
    if settings_notes:
        lines += ["**Settings differ from the frozen design:** " + "; ".join(settings_notes), ""]
    lines += [
        "## Operating characteristics",
        "",
        "Coverage and zero exclusion use every attempted dataset as the denominator (a missing interval is a miss). "
        "Bias is |mean(estimate - truth)|, scaled by the population outcome SD in `abs_bias_sd`.",
        "",
        "| Tool | Mode | Cell | Effect | Failures | Bias | MC SE | RMSE | Coverage [Wilson] | Width | Zero excl. | Runtime (s) |",
        "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in summary.to_dict(orient="records"):
        if not row.get("estimable"):
            lines.append(f"| {row['tool']} | {row['mode']} | {row['cell_id']} | {row['effect']} | not estimable: "
                         f"{row.get('not_estimable_reason')} | | | | | | | |")
            continue
        lines.append(
            f"| {row['tool']} | {row['mode']} | {row['cell_id']} | {row['effect']} | {int(row['failed_rows'])}/{int(row['attempted'])} | "
            f"{_format(row['mean_bias'])} | {_format(row['bias_mc_se'])} | {_format(row['rmse'])} | "
            f"{_format(row['coverage'])} [{_format(row['coverage_wilson_lower'])}, {_format(row['coverage_wilson_upper'])}] | "
            f"{_format(row['mean_width'])} | {_format(row['zero_exclusion'])} | {_format(row['runtime_mean_seconds'])} |"
        )
    lines += ["", "## Paired comparison with Mintmed (primary modes)", ""]
    if comparisons.empty:
        lines += ["No Mintmed reference rows were supplied, so no paired comparison was made.", ""]
    else:
        lines += [
            "Primary metrics are judged on the lower Wilson bound; guardrail losses on the upper bound of a paired "
            "percentile bootstrap interval. `n/a` marks a check that does not apply.",
            "",
            "| Tool | Cell | Effect | Pairs | Decision agr. (lower) | Sign agr. (lower) | Bias excess SD (upper) | "
            "Coverage loss pp (upper) | FP excess pp (upper) | Power loss pp (upper) | Width ratio (upper) | Tier | "
            "Tier (agreement on point) |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
        for row in comparisons.to_dict(orient="records"):
            lines.append(
                f"| {row['tool']} | {row['cell_id']} | {row['effect']} | {row['pairs']} | "
                f"{_format(row['decision_agreement'])} ({_format(row['decision_agreement_lower'])}) | "
                f"{_format(row['sign_agreement'])} ({_format(row['sign_agreement_lower'])}) | "
                f"{_format(row['bias_excess_sd'])} ({_format(row['bias_excess_sd_upper'])}) | "
                f"{_format(row['coverage_loss_pp'])} ({_format(row['coverage_loss_pp_upper'])}) | "
                f"{_format(row['false_positive_excess_pp'])} ({_format(row['false_positive_excess_pp_upper'])}) | "
                f"{_format(row['power_loss_pp'])} ({_format(row['power_loss_pp_upper'])}) | "
                f"{_format(row['width_ratio'])} ({_format(row['width_ratio_upper'])}) | {row['tier']} | "
                f"{row['tier_primary_on_point']} |"
            )
        lines.append("")
    return "\n".join(lines)


def _settings_notes(raw: pd.DataFrame, config: ValidationConfig) -> list[str]:
    notes = set()
    for text in raw["provenance_json"]:
        try:
            settings = json.loads(str(text)).get("settings", {})
        except (json.JSONDecodeError, AttributeError):
            continue
        if settings.get("boot_sims") not in (None, config.bootstrap_replicates):
            notes.add(f"bootstrap refits {settings.get('boot_sims')} (config: {config.bootstrap_replicates})")
        if settings.get("qb_sims") not in (None, 1000):
            notes.add(f"quasi-Bayesian sims {settings.get('qb_sims')} (frozen: 1000)")
    return sorted(notes)


def write_report(
    raw: pd.DataFrame,
    config: ValidationConfig,
    output_dir: Path,
    *,
    mintmed_raw_paths: Sequence[Path | str] | None = None,
) -> dict[str, Any]:
    """Write raw rows, per-effect summaries and (with a Mintmed reference) paired comparisons."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    raw = raw.loc[:, list(RAW_COLUMNS)].copy()
    raw["replicate"] = raw["replicate"].astype(int)
    hashes = set(raw["config_hash"].astype(str))
    if raw.empty or hashes != {config.config_hash}:
        raise ValueError(f"comparator rows carry config_hash values {sorted(hashes)}, expected {config.config_hash}")
    observed = set(raw[list(COMBINATION_COLUMNS)].itertuples(index=False, name=None))
    complete_grid = observed == expected_combinations(config) and not raw.duplicated(subset=list(COMBINATION_COLUMNS)).any()
    _atomic_text(output / "raw_metrics.csv", raw.to_csv(index=False, lineterminator="\n"))
    long = expand_records(raw)
    summary = summarize(long)
    _atomic_text(output / "comparator_summary.csv", summary.to_csv(index=False, lineterminator="\n"))

    reference_paths = _reference_paths(mintmed_raw_paths)
    comparisons = pd.DataFrame()
    if reference_paths:
        reference = load_mintmed_reference(reference_paths)
        check_reference_seeds(reference, config.master_seed)
        comparisons = compare_with_mintmed(long, reference)
        _atomic_text(output / "paired_comparisons.csv", comparisons.to_csv(index=False, lineterminator="\n"))
    notes = _settings_notes(raw, config)
    payload = {
        "schema_version": 1,
        "config_hash": config.config_hash,
        "combination_columns": list(COMBINATION_COLUMNS),
        "expected_rows": len(expected_combinations(config)),
        "observed_rows": len(raw),
        "complete_grid": bool(complete_grid),
        "tools": list(TOOLS),
        "row_status_counts": {f"{tool}:{status}": int(count) for (tool, status), count in raw.groupby(["tool", "status"]).size().items()},
        "settings_notes": notes,
        "comparison_rules": COMPARISON_RULES,
        "reference_paths": [path.name for path in reference_paths],
        "summaries": _json_safe(summary.to_dict(orient="records")),
        "paired_comparisons": _json_safe(comparisons.to_dict(orient="records")),
        "failed_statuses": sorted(FAILED_STATUSES),
    }
    _atomic_text(output / "summary.json", json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n")
    _atomic_text(output / "report.md", _markdown(summary, comparisons, raw, config, complete_grid, notes))
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    from .comparator_benchmark import load_config, read_raw

    parser = argparse.ArgumentParser(description="Report comparator raw rows, optionally paired with Mintmed.")
    parser.add_argument("--raw", required=True, type=Path, help="comparator raw_metrics.csv")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mintmed-raw", nargs="*", type=Path, default=None, help="Mintmed raw_metrics.csv file(s)")
    arguments = parser.parse_args(argv)
    write_report(read_raw(arguments.raw), load_config(arguments.config), arguments.output,
                 mintmed_raw_paths=arguments.mintmed_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPARISON_RULES",
    "classify_tier",
    "compare_with_mintmed",
    "decisions",
    "expand_records",
    "judge",
    "load_mintmed_reference",
    "paired_comparison",
    "summarize",
    "write_report",
]
