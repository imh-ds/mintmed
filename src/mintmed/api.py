"""Public orchestration for one complete Mintmed mediation analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import platform
from typing import Any

import numpy as np
import pandas as pd
import patsy
import scipy
import statsmodels

from .diagnostics import (
    DataValidationError,
    NodeFitError,
    PlanValidationError,
    UnsupportedAnalysisError,
    assemble_diagnostics,
)
from .effects import ModeratorContrast, moderator_contrasts, natural_effects, parallel_contributions
from .gformula import CommonDraws, FittedSystem, GFormulaError, compute_regime_means, fit_system, _mediator_order
from .spec import AnalysisPlan, ModelSpec, SpecValidationError, estimate_plan
from .types import (
    AnalysisStatus,
    BootstrapResult,
    ContributionResult,
    EffectEstimate,
    Issue,
    MediationResult,
    PointAnalysis,
)


def _json_safe(value: Any) -> Any:
    """Normalize public diagnostic values to JSON-compatible values."""

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (AnalysisStatus,)):
        return value.value
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _specification_hash(spec: ModelSpec) -> str:
    """Hash a canonical specification when no data-dependent plan exists."""

    try:
        canonical = spec.canonical_json()
    except (TypeError, ValueError, OverflowError):
        return ""
    return sha256(canonical.encode("utf-8")).hexdigest()


def _issue_for_exception(exc: Exception) -> Issue:
    """Convert one expected exception to the shared issue vocabulary."""

    if isinstance(exc, SpecValidationError):
        return Issue(
            code=exc.code,
            message=str(exc),
            status=AnalysisStatus.UNSUPPORTED,
            path=exc.path,
        )
    if isinstance(exc, NodeFitError):
        return exc.to_issue()
    if isinstance(exc, PlanValidationError):
        return exc.to_issue()
    if isinstance(exc, GFormulaError):
        path = f"nodes.{exc.node}" if exc.node is not None else "integration"
        return Issue(
            code=exc.code,
            message=exc.message,
            status=exc.status,
            node=exc.node,
            path=path,
        )
    raise TypeError(f"unsupported exception type: {type(exc).__name__}")


def _failure_state(exc: Exception, stage: str) -> str:
    """Map an expected failure to the serialized overall state."""

    if isinstance(exc, SpecValidationError):
        return "invalid_specification"
    if isinstance(exc, DataValidationError):
        return "invalid_data"
    if isinstance(exc, UnsupportedAnalysisError):
        return "unsupported_analysis"
    if isinstance(exc, PlanValidationError):
        return "invalid_specification"
    if isinstance(exc, GFormulaError):
        if exc.status is AnalysisStatus.INTEGRATION_FAILED:
            return "integration_unresolved"
        if exc.status is AnalysisStatus.UNSUPPORTED:
            return "unsupported_analysis"
        return "fit_failed"
    if isinstance(exc, NodeFitError):
        return "fit_failed"
    raise TypeError(f"unsupported exception type: {type(exc).__name__} at {stage}")


def _analysis_status(state: str) -> AnalysisStatus:
    """Map the public serialized state to the existing result status enum."""

    return {
        "complete": AnalysisStatus.OK,
        "complete_with_warnings": AnalysisStatus.WARNING,
        "point_only": AnalysisStatus.WARNING,
        "incomplete": AnalysisStatus.INCOMPLETE,
        "invalid_specification": AnalysisStatus.UNSUPPORTED,
        "invalid_data": AnalysisStatus.UNSUPPORTED,
        "unsupported_analysis": AnalysisStatus.UNSUPPORTED,
        "fit_failed": AnalysisStatus.FIT_FAILED,
        "integration_unresolved": AnalysisStatus.INTEGRATION_FAILED,
    }[state]


def _point_draws(plan: AnalysisPlan, fitted: FittedSystem) -> CommonDraws:
    """Return the exact common draw object used by point-effect components."""

    if fitted.draws is not None:
        return fitted.draws
    return CommonDraws.from_seed(
        seed=plan.computation.seed,
        draw_count=1,
        mediator_count=len(_mediator_order(plan)),
    )


def _declared_moderator_requests(
    spec: ModelSpec,
    plan: AnalysisPlan,
) -> Mapping[str, Sequence[object]]:
    """Return only explicitly declared moderator levels."""

    requests: dict[str, tuple[object, ...]] = {}
    for moderator in spec.moderators:
        if moderator.levels:
            requests[moderator.name] = tuple(moderator.levels)
    return requests


def _effect_record(effect: EffectEstimate) -> dict[str, Any]:
    """Serialize one effect without losing its reason or metadata."""

    return {
        "name": effect.name,
        "estimate": _json_safe(effect.estimate),
        "lower": _json_safe(effect.lower),
        "upper": _json_safe(effect.upper),
        "status": effect.status.value,
        "reason": effect.reason,
        "units": effect.units,
        "interval_available": effect.interval_available,
        "metadata": _json_safe(effect.metadata),
    }


def _moderator_record(contrast: ModeratorContrast) -> dict[str, Any]:
    """Serialize a standardized moderator contrast for diagnostics."""

    return {
        "moderator": contrast.moderator,
        "value": _json_safe(contrast.value),
        "baseline_value": _json_safe(contrast.baseline_value),
        "status": contrast.status.value,
        "reason": contrast.reason,
        "effects": [_effect_record(effect) for effect in contrast.effects],
        "differences": [_effect_record(effect) for effect in contrast.differences],
        "metadata": _json_safe(contrast.metadata),
    }


def _moderation_payload(
    requested: Mapping[str, Sequence[object]],
    baseline: Mapping[str, object],
    contrasts: Sequence[ModeratorContrast],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build the JSON-compatible moderation diagnostic section."""

    status = "unsupported" if reason is not None else (
        "ok" if all(contrast.status is AnalysisStatus.OK for contrast in contrasts)
        else "warning"
    )
    return {
        "requested": bool(requested),
        "status": status if requested else "not_requested",
        "baseline_values": _json_safe(baseline),
        "requested_values": _json_safe(requested),
        "contrasts": [_moderator_record(contrast) for contrast in contrasts],
        "reason": reason,
    }


def _build_provenance(
    spec: ModelSpec,
    plan: AnalysisPlan | None,
    fitted: FittedSystem | None,
    bootstrap: BootstrapResult | None,
) -> Mapping[str, object]:
    """Build stable, output-independent computation provenance."""

    specification_hash = plan.specification_hash if plan is not None else _specification_hash(spec)
    analysis_hash = plan.analysis_hash if plan is not None else ""
    return {
        "mintmed_version": _package_version(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "statsmodels_version": statsmodels.__version__,
        "patsy_version": patsy.__version__,
        "seed": int(spec.computation.seed),
        "bootstrap_requested": int(spec.computation.bootstrap),
        "bootstrap_mode": spec.computation.bootstrap_mode,
        "integration_initial_draws": int(spec.computation.integration_draws),
        "integration_tolerance": float(spec.computation.integration_tolerance),
        "integration_method": fitted.integration_method if fitted is not None else None,
        "accepted_draw_budget": fitted.draw_budget if fitted is not None else None,
        "specification_hash": specification_hash,
        "analysis_hash": analysis_hash,
        "bootstrap_status": bootstrap.status.value if bootstrap is not None else "not_requested",
    }


def _package_version() -> str:
    """Read the package version without importing the package namespace."""

    from . import __version__

    return __version__


def _result_for_failure(
    *,
    state: str,
    issue: Issue,
    spec: ModelSpec,
    plan: AnalysisPlan | None,
    fitted: FittedSystem | None,
    stage: str,
) -> MediationResult:
    """Return a structured result for an expected typed failure."""

    diagnostics = assemble_diagnostics(
        plan,
        fitted,
        overall_status=state,
        error=issue,
        stage=stage,
    )
    return MediationResult(
        specification_hash=plan.specification_hash if plan is not None else _specification_hash(spec),
        analysis_hash=plan.analysis_hash if plan is not None else "",
        effects=(),
        contributions=None,
        diagnostics=diagnostics,
        bootstrap=None,
        provenance=_build_provenance(spec, plan, fitted, None),
        status=_analysis_status(state),
    )


def _overall_state(
    plan: AnalysisPlan,
    bootstrap: BootstrapResult | None,
    *,
    optional_warnings: Sequence[Issue],
    moderation: Mapping[str, Any],
    contributions: ContributionResult | None,
) -> str:
    """Resolve overall state with fatal and uncertainty precedence."""

    if bootstrap is None:
        if optional_warnings or plan.warnings:
            return "complete_with_warnings"
        if moderation.get("status") not in {None, "ok", "not_requested"}:
            return "complete_with_warnings"
        if contributions is not None and not contributions.available:
            return "complete_with_warnings"
        return "point_only"
    if bootstrap.status is AnalysisStatus.INCOMPLETE:
        return "incomplete"
    if bootstrap.status is AnalysisStatus.INTERVAL_UNAVAILABLE:
        return "point_only"
    if bootstrap.status is AnalysisStatus.WARNING:
        return "complete_with_warnings"
    if optional_warnings or plan.warnings:
        return "complete_with_warnings"
    if moderation.get("status") not in {None, "ok", "not_requested"}:
        return "complete_with_warnings"
    if contributions is not None and not contributions.available:
        return "complete_with_warnings"
    return "complete"


def _bootstrap_failure(
    plan: AnalysisPlan,
    issue: Issue,
) -> BootstrapResult:
    """Represent a typed bootstrap-stage failure without discarding point effects."""

    return BootstrapResult(
        requested=int(plan.computation.bootstrap),
        attempted=0,
        successful=0,
        failed=0,
        status=AnalysisStatus.INCOMPLETE,
        failure_counts={issue.code: 1},
        metadata={"error": issue.message, "stage": "bootstrap"},
    )


def analyze_mediation(data: pd.DataFrame, spec: ModelSpec) -> MediationResult:
    """Run one supported mediation analysis and return an immutable result."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if not isinstance(spec, ModelSpec):
        raise TypeError("spec must be a ModelSpec")

    try:
        plan = estimate_plan(data, spec)
    except (SpecValidationError, DataValidationError, UnsupportedAnalysisError, PlanValidationError) as exc:
        issue = _issue_for_exception(exc)
        return _result_for_failure(
            state=_failure_state(exc, "plan"),
            issue=issue,
            spec=spec,
            plan=None,
            fitted=None,
            stage="plan",
        )

    try:
        fitted = fit_system(data, plan)
    except (NodeFitError, GFormulaError) as exc:
        issue = _issue_for_exception(exc)
        return _result_for_failure(
            state=_failure_state(exc, "fit"),
            issue=issue,
            spec=spec,
            plan=plan,
            fitted=None,
            stage="fit",
        )

    if fitted.status is AnalysisStatus.INTEGRATION_FAILED:
        issue = fitted.issues[0] if fitted.issues else Issue(
            code="integration_unresolved",
            message="integration did not satisfy the configured tolerance",
            status=AnalysisStatus.INTEGRATION_FAILED,
            path="integration",
        )
        return _result_for_failure(
            state="integration_unresolved",
            issue=issue,
            spec=spec,
            plan=plan,
            fitted=fitted,
            stage="integration",
        )

    try:
        draws = _point_draws(plan, fitted)
        means = compute_regime_means(data, plan, fitted)
        units = (
            "probability_difference"
            if plan.nodes[-1].family.value == "bernoulli"
            else "outcome_units"
        )
        effects = natural_effects(
            means,
            exposure_reference=plan.contrast.reference,
            exposure_comparison=plan.contrast.comparison,
            units=units,
            interpretation=plan.contrast.interpretation,
            standardization_population="retained_analysis_rows",
            numerical_tolerance=plan.computation.integration_tolerance,
        )
        if any(effect.status is not AnalysisStatus.OK for effect in effects):
            reason = next(
                (effect.reason for effect in effects if effect.reason),
                "effect_evaluation_failed",
            )
            raise GFormulaError(
                code=str(reason),
                status=AnalysisStatus.INTEGRATION_FAILED,
                message="point natural-effect evaluation failed",
            )
        contributions = parallel_contributions(
            data,
            plan,
            fitted,
            draws,
            means.total_natural_indirect_effect,
            numerical_tolerance=plan.computation.integration_tolerance,
        )
    except GFormulaError as exc:
        issue = _issue_for_exception(exc)
        return _result_for_failure(
            state=_failure_state(exc, "point"),
            issue=issue,
            spec=spec,
            plan=plan,
            fitted=fitted,
            stage="point",
        )

    optional_warnings: list[Issue] = []
    if contributions is not None and not contributions.available:
        optional_warnings.append(
            Issue(
                code=contributions.reason_code or "contribution_unavailable",
                message=contributions.reason or "parallel contribution was unavailable",
                status=AnalysisStatus.WARNING,
                node=plan.nodes[-1].response,
                path="contributions",
            )
        )

    moderator_requests = _declared_moderator_requests(spec, plan)
    baseline_values = dict(plan.contrast.moderator_values)
    moderator_values: tuple[ModeratorContrast, ...] = ()
    moderation_reason: str | None = None
    if moderator_requests:
        try:
            moderator_values = moderator_contrasts(
                data,
                plan,
                fitted,
                draws,
                moderator_values=moderator_requests,
                baseline_values=baseline_values,
                units=units,
                numerical_tolerance=plan.computation.integration_tolerance,
            )
        except GFormulaError as exc:
            moderation_reason = exc.message
            optional_warnings.append(
                Issue(
                    code=exc.code,
                    message=exc.message,
                    status=AnalysisStatus.WARNING,
                    node=exc.node,
                    path=f"moderation.{exc.code}",
                )
            )
    moderation = _moderation_payload(
        moderator_requests,
        baseline_values,
        moderator_values,
        reason=moderation_reason,
    )

    point = PointAnalysis(
        fitted_system=fitted,
        regime_means=means,
        effects=effects,
        contributions=contributions,
        moderator_contrasts=moderator_values,
        draw_budget=fitted.draw_budget,
        metadata={
            "units": units,
            "interpretation": plan.contrast.interpretation,
            "standardization_population": "retained_analysis_rows",
            "integration_method": fitted.integration_method,
            "integration_status": fitted.status.value,
            "bootstrap_mode": plan.computation.bootstrap_mode,
        },
    )

    bootstrap: BootstrapResult | None = None
    if plan.computation.bootstrap > 0:
        try:
            from .uncertainty import bootstrap_analysis

            bootstrap = bootstrap_analysis(data, plan, point)
        except GFormulaError as exc:
            bootstrap = _bootstrap_failure(plan, _issue_for_exception(exc))

    state = _overall_state(
        plan,
        bootstrap,
        optional_warnings=optional_warnings,
        moderation=moderation,
        contributions=contributions,
    )
    diagnostics = assemble_diagnostics(
        plan,
        fitted,
        bootstrap=bootstrap,
        moderation=moderation,
        optional_warnings=optional_warnings,
        overall_status=state,
    )
    return MediationResult(
        specification_hash=plan.specification_hash,
        analysis_hash=plan.analysis_hash,
        effects=effects,
        contributions=contributions,
        diagnostics=diagnostics,
        bootstrap=bootstrap,
        provenance=_build_provenance(spec, plan, fitted, bootstrap),
        status=_analysis_status(state),
    )


__all__ = ["analyze_mediation"]
