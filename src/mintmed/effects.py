"""Named mediation effects and attribution helpers.

This module contains estimand-level calculations only.  It deliberately does
not own fitting, uncertainty, or the package-level analysis API.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .design import transform_design
from .diagnostics import NodeFitError
from .gformula import (
    CommonDraws,
    FittedSystem,
    GFormulaError,
    _iter_standardized_blocks,
    _mediator_order,
    standardize_regime,
)
from .spec import AnalysisPlan, Family
from .types import (
    AnalysisStatus,
    ContributionResult,
    EffectEstimate,
    RegimeMeans,
    _freeze_mapping,
)


@dataclass(frozen=True, slots=True)
class ModeratorContrast:
    """Effects and paired effect differences for one moderator value."""

    moderator: str
    value: object
    baseline_value: object
    effects: tuple[EffectEstimate, ...]
    differences: tuple[EffectEstimate, ...]
    status: AnalysisStatus = AnalysisStatus.OK
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "differences", tuple(self.differences))
        object.__setattr__(self, "status", AnalysisStatus(self.status))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


def _validate_tolerance(value: float) -> float:
    tolerance = float(value)
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("numerical_tolerance must be finite and nonnegative")
    return tolerance


def natural_effects(
    means: RegimeMeans,
    *,
    exposure_reference: object = 0,
    exposure_comparison: object = 1,
    units: str = "outcome_units",
    interpretation: str = "model_standardized",
    standardization_population: str = "retained_analysis_rows",
    numerical_tolerance: float = 1e-10,
) -> tuple[EffectEstimate, EffectEstimate, EffectEstimate]:
    """Return TE, PNDE, and TNIE using the primary mediation convention."""

    tolerance = _validate_tolerance(numerical_tolerance)
    te = float(means.mu_11 - means.mu_00)
    pnde = float(means.mu_10 - means.mu_00)
    tnie = float(means.mu_11 - means.mu_10)
    values = (te, pnde, tnie)
    finite = all(np.isfinite(value) for value in (means.mu_00, means.mu_10, means.mu_11))
    identity_residual = te - pnde - tnie
    identity_ok = np.isfinite(identity_residual) and abs(identity_residual) <= tolerance

    if not finite:
        status = AnalysisStatus.INTEGRATION_FAILED
        reason = "nonfinite_regime_mean"
    elif not identity_ok:
        status = AnalysisStatus.INTEGRATION_FAILED
        reason = "effect_decomposition_identity_failed"
    else:
        status = AnalysisStatus.OK
        reason = None

    metadata = {
        "exposure_reference": exposure_reference,
        "exposure_comparison": exposure_comparison,
        "interpretation": interpretation,
        "standardization_population": standardization_population,
        "decomposition": "TE = PNDE + TNIE",
        "identity_residual": identity_residual,
        "numerical_tolerance": tolerance,
    }
    return tuple(
        EffectEstimate(
            name=name,
            estimate=value,
            status=status,
            reason=reason,
            units=units,
            metadata=metadata,
        )
        for name, value in zip(("TE", "PNDE", "TNIE"), values, strict=True)
    )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class _OutcomeTermPartition:
    """Outcome design-column groups used by additive contribution evaluation."""

    baseline_slices: tuple[slice, ...]
    mediator_slices: Mapping[str, tuple[slice, ...]]
    mediator_columns: Mapping[str, tuple[str, ...]]
    term_labels: Mapping[str, tuple[str, ...]]


class _ContributionFailure(Exception):
    """Internal structured refusal for the contribution API."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _design_slice(design: Any, expression: str) -> slice:
    term_slices = design.design_info.term_name_slices
    candidates = [expression, expression.strip("()")]
    for candidate in candidates:
        if candidate in term_slices:
            return term_slices[candidate]
    raise _ContributionFailure(
        "contribution_term_mapping_failed",
        f"frozen design has no slice for declared expression {expression!r}",
        expression=expression,
        available=tuple(term_slices),
    )


def _partition_outcome_terms(
    plan: AnalysisPlan,
    fitted: FittedSystem,
) -> _OutcomeTermPartition:
    """Partition frozen outcome columns into baseline and mediator blocks."""

    mediator_names = tuple(_mediator_order(plan))
    mediator_set = set(mediator_names)
    for node in plan.nodes[:-1]:
        parents = set(node.scientific_parents).intersection(mediator_set)
        parents.discard(node.response)
        if parents:
            raise _ContributionFailure(
                "contribution_nonparallel",
                "parallel contributions require no mediator-to-mediator scientific edge",
                node=node.response,
                parents=tuple(sorted(parents)),
            )
    if fitted.outcome_node.family is not Family.GAUSSIAN:
        raise _ContributionFailure(
            "contribution_outcome_family",
            "parallel contributions require a Gaussian outcome node",
            family=fitted.outcome_node.family.value,
        )

    outcome_plan = plan.nodes[-1]
    design = fitted.outcome_node.design
    coefficients = np.asarray(getattr(fitted.outcome_node, "coefficients", ()), dtype=float)
    if coefficients.shape != (len(design.columns),) or not np.isfinite(coefficients).all():
        raise _ContributionFailure(
            "contribution_coefficients_unavailable",
            "Gaussian outcome coefficients do not match the frozen design",
            expected=len(design.columns),
            actual=tuple(coefficients.shape),
        )

    expressions: dict[str, str] = {
        term.variable: term.expression for term in design.term_metadata
    }
    baseline_slices: list[slice] = []
    mediator_slices: dict[str, list[slice]] = {name: [] for name in mediator_names}
    mediator_columns: dict[str, list[str]] = {name: [] for name in mediator_names}
    labels: dict[str, list[str]] = {name: [] for name in mediator_names}

    def add_group(group: str | None, expression: str, label: str) -> None:
        column_slice = _design_slice(design, expression)
        if group is None:
            baseline_slices.append(column_slice)
            return
        mediator_slices[group].append(column_slice)
        mediator_columns[group].extend(design.columns[column_slice])
        labels[group].append(label)

    if outcome_plan.intercept:
        add_group(None, "Intercept", "Intercept")
    for term in outcome_plan.terms:
        expression = expressions.get(term.variable)
        if expression is None:
            raise _ContributionFailure(
                "contribution_term_mapping_failed",
                f"no frozen design metadata for declared term {term.variable!r}",
                variable=term.variable,
            )
        group = term.variable if term.variable in mediator_set else None
        add_group(group, expression, term.variable)
    for interaction in outcome_plan.interactions:
        left_expression = expressions.get(interaction.left)
        right_expression = expressions.get(interaction.right)
        if left_expression is None or right_expression is None:
            raise _ContributionFailure(
                "contribution_term_mapping_failed",
                "no frozen design metadata for an interaction variable",
                interaction=(interaction.left, interaction.right),
            )
        mediator_sides = mediator_set.intersection((interaction.left, interaction.right))
        if len(mediator_sides) > 1:
            raise _ContributionFailure(
                "contribution_cross_mediator_term",
                "a single outcome block cannot contain multiple mediators",
                interaction=(interaction.left, interaction.right),
            )
        expression = f"{left_expression}:{right_expression}"
        if expression not in design.design_info.term_name_slices:
            reverse = f"{right_expression}:{left_expression}"
            if reverse in design.design_info.term_name_slices:
                expression = reverse
        group = next(iter(mediator_sides), None)
        add_group(group, expression, f"{interaction.left}:{interaction.right}")

    return _OutcomeTermPartition(
        baseline_slices=tuple(baseline_slices),
        mediator_slices={name: tuple(slices) for name, slices in mediator_slices.items()},
        mediator_columns={name: tuple(columns) for name, columns in mediator_columns.items()},
        term_labels={name: tuple(items) for name, items in labels.items()},
    )


def _contribution_failure(failure: _ContributionFailure) -> ContributionResult:
    details = dict(failure.details)
    detail_text = ", ".join(f"{key}={value!r}" for key, value in details.items())
    reason = failure.message if not detail_text else f"{failure.message} ({detail_text})"
    return ContributionResult(
        available=False,
        contributions={},
        reason_code=failure.code,
        reason=reason,
    )


def _validate_contribution_draws(
    plan: AnalysisPlan,
    fitted: FittedSystem,
    draws: CommonDraws,
) -> None:
    if fitted.status is not AnalysisStatus.OK:
        raise _ContributionFailure(
            "contribution_integration_unresolved",
            "the fitted system is not available for contribution evaluation",
            status=fitted.status.value,
        )
    if not isinstance(draws, CommonDraws):
        raise _ContributionFailure(
            "contribution_integration_unresolved",
            "supplied draws are not a CommonDraws instance",
        )
    if draws.mediator_count != len(_mediator_order(plan)):
        raise _ContributionFailure(
            "contribution_integration_unresolved",
            "supplied draw dimensions do not match the mediator plan",
        )
    if fitted.integration_method == "sobol_blocked" and draws.draw_count != fitted.draw_budget:
        raise _ContributionFailure(
            "contribution_integration_unresolved",
            "supplied draws do not match the accepted integration budget",
            expected=fitted.draw_budget,
            actual=draws.draw_count,
        )
    if not np.isfinite(draws.uniforms).all() or not np.isfinite(draws.normals).all():
        raise _ContributionFailure(
            "contribution_integration_unresolved",
            "supplied draws contain nonfinite values",
        )


def parallel_contributions(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    draws: CommonDraws,
    joint_tnie: float,
    *,
    numerical_tolerance: float = 1e-10,
) -> ContributionResult:
    """Return additive mediator TNIE blocks when the model is admissible."""

    tolerance = _validate_tolerance(numerical_tolerance)
    try:
        partition = _partition_outcome_terms(plan, fitted)
        _validate_contribution_draws(plan, fitted, draws)
    except _ContributionFailure as failure:
        return _contribution_failure(failure)

    if not np.isfinite(float(joint_tnie)):
        return _contribution_failure(
            _ContributionFailure(
                "contribution_identity_failed",
                "joint TNIE is nonfinite",
                joint_tnie=joint_tnie,
            )
        )

    mediator_names = tuple(_mediator_order(plan))
    component_sums = {
        exposure: {name: 0.0 for name in mediator_names}
        for exposure in (plan.contrast.reference, plan.contrast.comparison)
    }
    component_counts = {exposure: 0 for exposure in component_sums}
    try:
        for mediator_exposure in component_sums:
            for outcome_frame in _iter_standardized_blocks(
                data,
                plan,
                fitted,
                outcome_exposure=plan.contrast.comparison,
                mediator_exposure=mediator_exposure,
                moderator_values=plan.contrast.moderator_values,
                draws=draws,
            ):
                matrix = transform_design(fitted.outcome_node.design, outcome_frame).to_numpy(
                    dtype=float,
                    copy=False,
                )
                component_counts[mediator_exposure] += len(outcome_frame)
                coefficients = np.asarray(fitted.outcome_node.coefficients, dtype=float)
                for name in mediator_names:
                    component = np.zeros(len(outcome_frame), dtype=float)
                    for column_slice in partition.mediator_slices[name]:
                        component += matrix[:, column_slice] @ coefficients[column_slice]
                    component_sums[mediator_exposure][name] += float(component.sum())
    except (GFormulaError, NodeFitError, ValueError, TypeError) as exc:
        return _contribution_failure(
            _ContributionFailure(
                "contribution_term_mapping_failed",
                "standardized component evaluation failed",
                error=str(exc),
            )
        )

    if any(count <= 0 for count in component_counts.values()):
        return _contribution_failure(
            _ContributionFailure(
                "contribution_integration_unresolved",
                "standardized component evaluation produced no cells",
            )
        )
    component_means = {
        exposure: {
            name: component_sums[exposure][name] / component_counts[exposure]
            for name in mediator_names
        }
        for exposure in component_sums
    }
    values = {
        name: component_means[plan.contrast.comparison][name]
        - component_means[plan.contrast.reference][name]
        for name in mediator_names
    }
    residual = float(sum(values.values()) - float(joint_tnie))
    if not np.isclose(sum(values.values()), float(joint_tnie), atol=tolerance, rtol=0.0):
        return _contribution_failure(
            _ContributionFailure(
                "contribution_identity_failed",
                "mediator component estimates do not reproduce the supplied joint TNIE",
                residual=residual,
                contributions=values,
            )
        )
    contributions = {
        f"TNIE_{name}": EffectEstimate(
            name=f"TNIE_{name}",
            estimate=float(values[name]),
            units="outcome_units",
            metadata={
                "mediator": name,
                "decomposition": "parallel_additive_outcome_blocks",
                "joint_tnie": float(joint_tnie),
                "identity_residual": residual,
                "exposure_reference": plan.contrast.reference,
                "exposure_comparison": plan.contrast.comparison,
                "standardization_population": "retained_analysis_rows",
                "numerical_tolerance": tolerance,
            },
        )
        for name in mediator_names
    }
    return ContributionResult(available=True, contributions=contributions)


def _regime_means_at_moderators(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    draws: CommonDraws,
    moderator_values: Mapping[str, object],
) -> RegimeMeans:
    """Evaluate the three primary regimes at one moderator configuration."""

    reference = plan.contrast.reference
    comparison = plan.contrast.comparison
    return RegimeMeans(
        mu_00=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=reference,
            mediator_exposure=reference,
            moderator_values=moderator_values,
            draws=draws,
        ),
        mu_10=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=comparison,
            mediator_exposure=reference,
            moderator_values=moderator_values,
            draws=draws,
        ),
        mu_11=standardize_regime(
            data,
            plan,
            fitted,
            outcome_exposure=comparison,
            mediator_exposure=comparison,
            moderator_values=moderator_values,
            draws=draws,
        ),
    )


def _effect_difference(
    current: EffectEstimate,
    baseline: EffectEstimate,
    *,
    moderator: str,
    value: object,
    baseline_value: object,
    numerical_tolerance: float,
) -> EffectEstimate:
    status = current.status if current.status is not AnalysisStatus.OK else baseline.status
    reason = current.reason or baseline.reason
    estimate = float(current.estimate - baseline.estimate)
    metadata = dict(current.metadata)
    metadata.update(
        {
            "moderator": moderator,
            "value": value,
            "baseline_value": baseline_value,
            "numerical_tolerance": numerical_tolerance,
        }
    )
    return EffectEstimate(
        name=current.name,
        estimate=estimate,
        status=status,
        reason=reason,
        units=current.units,
        metadata=metadata,
    )


def moderator_contrasts(
    data: pd.DataFrame,
    plan: AnalysisPlan,
    fitted: FittedSystem,
    draws: CommonDraws,
    *,
    moderator_values: Mapping[str, Sequence[object]],
    baseline_values: Mapping[str, object] | None = None,
    units: str = "outcome_units",
    numerical_tolerance: float = 1e-10,
) -> tuple[ModeratorContrast, ...]:
    """Evaluate ordered moderator effects and paired effect differences."""

    tolerance = _validate_tolerance(numerical_tolerance)
    if not isinstance(moderator_values, Mapping):
        raise TypeError("moderator_values must be a mapping")
    if not moderator_values:
        return ()
    baseline = dict(plan.contrast.moderator_values if baseline_values is None else baseline_values)
    missing = tuple(name for name in moderator_values if name not in baseline)
    if missing:
        raise GFormulaError(
            code="missing_moderators",
            status=AnalysisStatus.FIT_FAILED,
            message="baseline_values is missing requested moderators",
            details={"missing": missing},
        )

    contrasts: list[ModeratorContrast] = []
    for moderator, values in moderator_values.items():
        if isinstance(values, (str, bytes)):
            raise TypeError("moderator value sequences must not be strings")
        baseline_configuration = dict(baseline)
        baseline_effects = natural_effects(
            _regime_means_at_moderators(data, plan, fitted, draws, baseline_configuration),
            exposure_reference=plan.contrast.reference,
            exposure_comparison=plan.contrast.comparison,
            units=units,
            interpretation=plan.contrast.interpretation,
            numerical_tolerance=tolerance,
        )
        for value in values:
            configuration = dict(baseline)
            configuration[moderator] = value
            effects = natural_effects(
                _regime_means_at_moderators(data, plan, fitted, draws, configuration),
                exposure_reference=plan.contrast.reference,
                exposure_comparison=plan.contrast.comparison,
                units=units,
                interpretation=plan.contrast.interpretation,
                numerical_tolerance=tolerance,
            )
            baseline_effects_by_name = {effect.name: effect for effect in baseline_effects}
            differences = tuple(
                _effect_difference(
                    effect,
                    baseline_effects_by_name[effect.name],
                    moderator=moderator,
                    value=value,
                    baseline_value=baseline[moderator],
                    numerical_tolerance=tolerance,
                )
                for effect in effects
            )
            status = (
                AnalysisStatus.OK
                if all(effect.status is AnalysisStatus.OK for effect in (*effects, *differences))
                else AnalysisStatus.INTEGRATION_FAILED
            )
            reason = None if status is AnalysisStatus.OK else "moderator_effect_failed"
            contrasts.append(
                ModeratorContrast(
                    moderator=moderator,
                    value=value,
                    baseline_value=baseline[moderator],
                    effects=effects,
                    differences=differences,
                    status=status,
                    reason=reason,
                    metadata={
                        "units": units,
                        "interpretation": plan.contrast.interpretation,
                        "standardization_population": "retained_analysis_rows",
                        "numerical_tolerance": tolerance,
                    },
                )
            )
    return tuple(contrasts)


__all__ = [
    "ModeratorContrast",
    "moderator_contrasts",
    "natural_effects",
    "parallel_contributions",
]
