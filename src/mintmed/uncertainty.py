"""Deterministic full-refit participant-bootstrap uncertainty."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
import time
from typing import Any

import numpy as np
import pandas as pd

from .diagnostics import NodeFitError
from .effects import moderator_contrasts, natural_effects, parallel_contributions
from .gformula import (
    CommonDraws,
    GFormulaError,
    _fit_system_with_fixed_budget,
    _mediator_order,
    standardize_regime,
)
from .spec import AnalysisPlan
from .types import (
    AnalysisStatus,
    BootstrapResult,
    EffectEstimate,
    PointAnalysis,
    RegimeMeans,
)


def _stream_seeds(base_seed: int, replicate: int) -> tuple[int, int]:
    """Return independent row and integration seeds for one replicate."""

    row_sequence = np.random.SeedSequence([int(base_seed), 4101, int(replicate)])
    integration_sequence = np.random.SeedSequence([int(base_seed), 4102, int(replicate)])
    row_seed = int(row_sequence.generate_state(1, dtype=np.uint64)[0])
    integration_seed = int(integration_sequence.generate_state(1, dtype=np.uint64)[0])
    return row_seed, integration_seed


def _resample_frame(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    row_positions: tuple[int, ...],
) -> tuple[pd.DataFrame, tuple[Any, ...]]:
    """Return a fresh local-index bootstrap frame and its source labels."""

    source = data.loc[list(plan.retained_row_indices), list(plan.analysis_columns)]
    row_indices = tuple(source.index[position] for position in row_positions)
    replicate_frame = source.iloc[list(row_positions)].copy(deep=True)
    replicate_frame.index = pd.RangeIndex(len(row_positions))
    return replicate_frame, row_indices


def _relabeled_plan(
    plan: AnalysisPlan,
    row_count: int,
    *,
    replicate: int,
    row_seed: int,
    integration_seed: int,
) -> AnalysisPlan:
    """Relabel a compiled plan for duplicated local bootstrap rows."""

    diagnostics = dict(plan.diagnostics)
    diagnostics.update(
        {
            "bootstrap_replicate": int(replicate),
            "bootstrap_row_seed": int(row_seed),
            "bootstrap_integration_seed": int(integration_seed),
        }
    )
    return replace(
        plan,
        retained_row_indices=tuple(range(row_count)),
        excluded_row_indices=(),
        original_row_count=row_count,
        retained_row_count=row_count,
        diagnostics=diagnostics,
    )


def _replicate_identity(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    replicate: int,
) -> tuple[dict[str, Any], pd.DataFrame, AnalysisPlan]:
    """Create reproducible participant rows and the private relabeled plan."""

    n_rows = len(plan.retained_row_indices)
    if n_rows == 0:
        raise GFormulaError(
            code="empty_analysis",
            status=AnalysisStatus.FIT_FAILED,
            message="cannot bootstrap an empty retained analysis population",
        )
    row_seed, integration_seed = _stream_seeds(plan.computation.seed, replicate)
    positions = np.random.default_rng(row_seed).integers(0, n_rows, size=n_rows)
    row_positions = tuple(int(position) for position in positions)
    replicate_frame, row_indices = _resample_frame(data, plan, row_positions)
    replicate_plan = _relabeled_plan(
        plan,
        n_rows,
        replicate=replicate,
        row_seed=row_seed,
        integration_seed=integration_seed,
    )
    identity = {
        "replicate": int(replicate),
        "row_seed": row_seed,
        "integration_seed": integration_seed,
        "row_positions": row_positions,
        "row_indices": row_indices,
    }
    return identity, replicate_frame, replicate_plan


def _base_record(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **identity,
        "status": None,
        "error_code": None,
        "error_message": None,
        "runtime_seconds": None,
        "accepted_draw_budget": None,
        "integration_draw_count": None,
        "TE": None,
        "PNDE": None,
        "TNIE": None,
        "contribution_available": None,
        "contribution_reason_code": None,
        "contribution_reason": None,
    }


def _record_failure(
    identity: Mapping[str, Any],
    *,
    status: AnalysisStatus | str,
    error_code: str,
    error_message: str,
    runtime_seconds: float,
) -> dict[str, Any]:
    record = _base_record(identity)
    record.update(
        {
            "status": AnalysisStatus(status).value,
            "error_code": str(error_code),
            "error_message": str(error_message),
            "runtime_seconds": float(runtime_seconds),
        }
    )
    return record


def _moderator_request(point: PointAnalysis) -> tuple[dict[str, tuple[object, ...]], dict[str, object]]:
    values: dict[str, list[object]] = {}
    baseline: dict[str, object] = {}
    for contrast in point.moderator_contrasts:
        if isinstance(contrast, Mapping):
            moderator = str(contrast["moderator"])
            value = contrast["value"]
            baseline_value = contrast["baseline_value"]
        else:
            moderator = str(getattr(contrast, "moderator"))
            value = getattr(contrast, "value")
            baseline_value = getattr(contrast, "baseline_value")
        values.setdefault(moderator, [])
        if value not in values[moderator]:
            values[moderator].append(value)
        baseline.setdefault(moderator, baseline_value)
    return {name: tuple(items) for name, items in values.items()}, baseline


def _canonical_value(value: object) -> str:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".15g")
    return str(value)


def _canonical_moderator_key(moderator: str, value: object, effect: str) -> str:
    return f"moderator_difference__{moderator}__{_canonical_value(value)}__{effect}"


def _replicate_means(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: Any,
    draws: CommonDraws,
) -> RegimeMeans:
    reference = plan.contrast.reference
    comparison = plan.contrast.comparison
    moderators = plan.contrast.moderator_values
    return RegimeMeans(
        mu_00=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=reference,
            mediator_exposure=reference,
            moderator_values=moderators,
            draws=draws,
        ),
        mu_10=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=comparison,
            mediator_exposure=reference,
            moderator_values=moderators,
            draws=draws,
        ),
        mu_11=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=comparison,
            mediator_exposure=comparison,
            moderator_values=moderators,
            draws=draws,
        ),
    )


def _run_replicate(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    point: PointAnalysis,
    replicate: int,
) -> dict[str, Any]:
    """Fit and evaluate one bootstrap replicate from scratch."""

    identity, replicate_frame, replicate_plan = _replicate_identity(data, plan, replicate)
    started = time.perf_counter()
    fitted = _fit_system_with_fixed_budget(
        replicate_frame,
        replicate_plan,
        draw_seed=identity["integration_seed"],
        draw_budget=point.draw_budget,
    )
    if fitted.integration_method == "sobol_blocked":
        if point.draw_budget <= 0 or fitted.draw_budget != point.draw_budget or fitted.draws is None:
            raise GFormulaError(
                code="bootstrap_draw_budget_mismatch",
                status=AnalysisStatus.INTEGRATION_FAILED,
                message="bootstrap refit did not retain the accepted point draw budget",
            )
        draws = fitted.draws
    else:
        draws = CommonDraws.from_seed(
            seed=identity["integration_seed"],
            draw_count=1,
            mediator_count=len(_mediator_order(replicate_plan)),
        )
    means = _replicate_means(replicate_frame, replicate_plan, fitted, draws)
    units = point.effects[0].units if point.effects else "outcome_units"
    effects = natural_effects(
        means,
        exposure_reference=replicate_plan.contrast.reference,
        exposure_comparison=replicate_plan.contrast.comparison,
        units=units,
        interpretation=replicate_plan.contrast.interpretation,
        numerical_tolerance=replicate_plan.computation.integration_tolerance,
    )
    if any(effect.status is not AnalysisStatus.OK for effect in effects):
        reason = next((effect.reason for effect in effects if effect.reason), "effect_evaluation_failed")
        raise GFormulaError(
            code=str(reason),
            status=AnalysisStatus.INTEGRATION_FAILED,
            message="bootstrap natural-effect decomposition failed",
        )

    record = _base_record(identity)
    record.update(
        {
            "status": AnalysisStatus.OK.value,
            "runtime_seconds": float(time.perf_counter() - started),
            "accepted_draw_budget": int(fitted.draw_budget),
            "integration_draw_count": int(draws.draw_count),
        }
    )
    record.update({effect.name: float(effect.estimate) for effect in effects})

    if point.contributions is not None:
        contribution = parallel_contributions(
            replicate_frame,
            replicate_plan,
            fitted,
            draws,
            means.total_natural_indirect_effect,
            numerical_tolerance=replicate_plan.computation.integration_tolerance,
        )
        record["contribution_available"] = bool(contribution.available)
        record["contribution_reason_code"] = contribution.reason_code
        record["contribution_reason"] = contribution.reason
        if contribution.available:
            record.update(
                {
                    name: float(effect.estimate)
                    for name, effect in contribution.contributions.items()
                }
            )

    moderator_values, baseline_values = _moderator_request(point)
    if moderator_values:
        contrasts = moderator_contrasts(
            replicate_frame,
            replicate_plan,
            fitted,
            draws,
            moderator_values=moderator_values,
            baseline_values=baseline_values,
            units=units,
            numerical_tolerance=replicate_plan.computation.integration_tolerance,
        )
        for contrast in contrasts:
            for difference in contrast.differences:
                key = _canonical_moderator_key(contrast.moderator, contrast.value, difference.name)
                record[key] = float(difference.estimate)
    return record


def _interval_eligibility(requested: int, successful: int, failed: int) -> bool:
    """Return whether a completed ordinary run meets the interval rule."""

    if requested >= 400:
        return successful >= 390 and failed / requested <= 0.01
    return successful == requested and failed == 0


def _point_candidates(point: PointAnalysis) -> dict[str, EffectEstimate]:
    candidates = {effect.name: effect for effect in point.effects}
    if point.contributions is not None and point.contributions.available:
        candidates.update(point.contributions.contributions)
    for contrast in point.moderator_contrasts:
        if isinstance(contrast, Mapping):
            moderator = str(contrast["moderator"])
            value = contrast["value"]
            differences = contrast["differences"]
        else:
            moderator = str(getattr(contrast, "moderator"))
            value = getattr(contrast, "value")
            differences = getattr(contrast, "differences")
        for difference in differences:
            key = _canonical_moderator_key(moderator, value, difference.name)
            candidates[key] = difference
    return candidates


def _intervals_from_records(
    records: tuple[Mapping[str, Any], ...],
    requested: int,
    point: PointAnalysis,
    *,
    complete: bool,
    quick_diagnostic: bool,
) -> tuple[tuple[EffectEstimate, ...], AnalysisStatus, dict[str, Any]]:
    successful = sum(record.get("status") == AnalysisStatus.OK.value for record in records)
    failed = sum(
        record.get("status") not in {AnalysisStatus.OK.value, AnalysisStatus.INCOMPLETE.value}
        for record in records
    )
    candidates = _point_candidates(point)
    if requested == 0:
        eligible = False
        provisional = False
        overall_reason = "bootstrap_not_requested"
    elif not complete:
        eligible = False
        provisional = False
        overall_reason = "bootstrap_incomplete"
    else:
        ordinary = _interval_eligibility(requested, successful, failed)
        provisional = bool(quick_diagnostic and not ordinary and successful >= 2)
        eligible = ordinary or provisional
        if eligible:
            overall_reason = "quick_diagnostic_provisional" if provisional else None
        elif successful < 2:
            overall_reason = "fewer_than_two_successful_replicates"
        else:
            overall_reason = "bootstrap_failure_threshold"

    intervals: list[EffectEstimate] = []
    missing_optional = False
    for key, point_effect in candidates.items():
        values = [
            float(record[key])
            for record in records
            if record.get("status") == AnalysisStatus.OK.value
            and key in record
            and record[key] is not None
            and np.isfinite(float(record[key]))
        ]
        metadata = dict(point_effect.metadata)
        metadata.update(
            {
                "interval_key": key,
                "bootstrap_requested": requested,
                "bootstrap_successful": successful,
                "bootstrap_failed": failed,
                "bootstrap_provisional": provisional,
            }
        )
        reason = overall_reason
        status = AnalysisStatus.INTERVAL_UNAVAILABLE
        lower: float | None = None
        upper: float | None = None
        if eligible and len(values) >= 2:
            lower, upper = (float(bound) for bound in np.percentile(values, [2.5, 97.5], method="linear"))
            status = AnalysisStatus.WARNING if provisional else AnalysisStatus.OK
            reason = "quick_diagnostic_provisional" if provisional else None
        elif eligible and len(values) < 2:
            reason = "fewer_than_two_successful_replicates"
        if key not in {effect.name for effect in point.effects} and len(values) < successful:
            missing_optional = True
        intervals.append(
            EffectEstimate(
                name=key,
                estimate=float(point_effect.estimate),
                lower=lower,
                upper=upper,
                status=status,
                reason=reason,
                units=point_effect.units,
                metadata=metadata,
            )
        )

    primary_keys = {effect.name for effect in point.effects}
    primary_available = bool(primary_keys) and all(
        interval.interval_available for interval in intervals if interval.name in primary_keys
    )
    if not complete:
        status = AnalysisStatus.INCOMPLETE
    elif requested == 0 or not eligible or not primary_available:
        status = AnalysisStatus.INTERVAL_UNAVAILABLE
    elif provisional or missing_optional:
        status = AnalysisStatus.WARNING
    else:
        status = AnalysisStatus.OK
    metadata = {
        "interval_policy": "percentile_2.5_97.5_successful_finite_values",
        "requested": requested,
        "successful": successful,
        "failed": failed,
        "eligible": bool(eligible and primary_available),
        "provisional": provisional,
        "reason": overall_reason,
    }
    return tuple(intervals), status, metadata


def bootstrap_analysis(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    point: PointAnalysis,
) -> BootstrapResult:
    """Run the deterministic participant bootstrap for one point analysis."""

    requested = int(plan.computation.bootstrap)
    if requested < 0:
        raise ValueError("plan.computation.bootstrap must be nonnegative")
    records: list[Mapping[str, Any]] = []
    interrupted = False
    stopped_before_replicate: int | None = None
    started = time.perf_counter()
    max_seconds = plan.computation.max_seconds
    for replicate in range(requested):
        if max_seconds is not None and time.perf_counter() - started >= max_seconds:
            interrupted = True
            stopped_before_replicate = replicate
            break
        attempt_started = time.perf_counter()
        try:
            records.append(_run_replicate(data, plan, point, replicate))
        except (TimeoutError, KeyboardInterrupt) as exc:
            identity, _frame, _replicate_plan = _replicate_identity(data, plan, replicate)
            records.append(
                _record_failure(
                    identity,
                    status=AnalysisStatus.INCOMPLETE,
                    error_code="bootstrap_interrupted",
                    error_message=str(exc) or type(exc).__name__,
                    runtime_seconds=time.perf_counter() - attempt_started,
                )
            )
            interrupted = True
            break
        except GFormulaError as exc:
            identity, _frame, _replicate_plan = _replicate_identity(data, plan, replicate)
            records.append(
                _record_failure(
                    identity,
                    status=exc.status,
                    error_code=exc.code,
                    error_message=exc.message,
                    runtime_seconds=time.perf_counter() - attempt_started,
                )
            )
        except NodeFitError as exc:
            identity, _frame, _replicate_plan = _replicate_identity(data, plan, replicate)
            records.append(
                _record_failure(
                    identity,
                    status=AnalysisStatus.FIT_FAILED,
                    error_code=exc.code,
                    error_message=str(exc),
                    runtime_seconds=time.perf_counter() - attempt_started,
                )
            )
    record_tuple = tuple(records)
    successful = sum(record.get("status") == AnalysisStatus.OK.value for record in record_tuple)
    failed = sum(
        record.get("status") not in {AnalysisStatus.OK.value, AnalysisStatus.INCOMPLETE.value}
        for record in record_tuple
    )
    intervals, status, interval_metadata = _intervals_from_records(
        record_tuple,
        requested,
        point,
        complete=not interrupted and len(record_tuple) == requested,
        quick_diagnostic=point.metadata.get("bootstrap_mode") == "quick_diagnostic",
    )
    failure_counts = Counter(
        str(record["error_code"])
        for record in record_tuple
        if record.get("error_code") is not None
    )
    metadata = {
        **interval_metadata,
        "attempted": len(record_tuple),
        "runtime_seconds": float(time.perf_counter() - started),
        "complete": not interrupted and len(record_tuple) == requested,
        "stopped_before_replicate": stopped_before_replicate,
        "quick_diagnostic": point.metadata.get("bootstrap_mode") == "quick_diagnostic",
    }
    return BootstrapResult(
        requested=requested,
        attempted=len(record_tuple),
        successful=successful,
        failed=failed,
        replicates=record_tuple,
        intervals=intervals,
        status=status,
        failure_counts=dict(failure_counts),
        metadata=metadata,
    )


__all__ = ["bootstrap_analysis"]
