"""Typed validation errors and diagnostics assembly for analysis results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import numpy as np

from .types import AnalysisStatus, Issue

if TYPE_CHECKING:
    from .gformula import FittedSystem
    from .spec import AnalysisPlan
    from .types import BootstrapResult


class PlanValidationError(ValueError):
    """Base error with a stable code and location for expected plan failures."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")

    def to_issue(self, *, node: str | None = None) -> Issue:
        """Convert the expected failure into the shared diagnostic vocabulary."""

        return Issue(
            code=self.code,
            message=str(self),
            status=AnalysisStatus.UNSUPPORTED,
            node=node,
            path=self.path,
        )


class DataValidationError(PlanValidationError):
    """The observed frame cannot satisfy the declared analysis contract."""


class UnsupportedAnalysisError(PlanValidationError):
    """The declared analysis is outside the supported data or counterfactual scope."""


class NodeFitError(PlanValidationError):
    """A compiled node cannot produce a valid frozen design or fit."""

    def __init__(
        self,
        *,
        code: str,
        response: str,
        message: str,
        variable: str | None = None,
        columns: tuple[str, ...] = (),
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(code, f"nodes.{response}", message)
        self.response = response
        self.variable = variable
        self.columns = tuple(columns)
        self.details = MappingProxyType(dict(details or {}))

    def to_issue(self, *, node: str | None = None) -> Issue:
        """Convert the fit failure into the shared fit-failed status."""

        return Issue(
            code=self.code,
            message=str(self),
            status=AnalysisStatus.FIT_FAILED,
            node=node or self.response,
            path=self.path,
        )


def _json_safe(value: Any) -> Any:
    """Normalize diagnostic values without retaining NumPy or enum objects."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _issue_record(issue: Issue) -> dict[str, Any]:
    """Return the stable serializable portion of one typed issue."""

    record = {
        "code": issue.code,
        "message": issue.message,
        "status": issue.status.value,
        "node": issue.node,
    }
    path = getattr(issue, "path", None)
    if path is not None:
        record["path"] = path
    return record


def _node_record(node: Any) -> dict[str, Any]:
    """Copy fit and frozen-design metadata from one fitted node."""

    fit = node.diagnostics()
    design = node.design
    return {
        "response": fit.response,
        "family": fit.family.value,
        "status": fit.status.value,
        "code": fit.code,
        "message": fit.message,
        "n_rows": fit.n_rows,
        "parameter_count": fit.parameter_count,
        "rank": fit.rank,
        "converged": fit.converged,
        "coefficients_finite": fit.coefficients_finite,
        "df_resid": _json_safe(fit.df_resid),
        "sigma": _json_safe(fit.sigma),
        "log_likelihood": _json_safe(fit.log_likelihood),
        "deviance": _json_safe(fit.deviance),
        "events": fit.events,
        "non_events": fit.non_events,
        "warnings": list(fit.warnings),
        "metadata": _json_safe(fit.metadata),
        "formula": design.formula,
        "design_columns": list(design.columns),
    }


def _planned_node_record(node: Any) -> dict[str, Any]:
    """Describe a node that was planned but not fitted."""

    return {
        "response": node.response,
        "family": node.family.value,
        "status": "not_run",
        "code": None,
        "message": None,
        "terms": [term.variable for term in node.terms],
        "interactions": [[item.left, item.right] for item in node.interactions],
        "factorization_predictors": list(node.factorization_predictors),
    }


def _bootstrap_record(bootstrap: BootstrapResult | None) -> dict[str, Any]:
    """Summarize bootstrap results without copying participant row records."""

    if bootstrap is None:
        return {
            "requested": 0,
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "status": "not_requested",
            "failure_counts": {},
            "intervals": [],
            "metadata": {},
        }
    intervals = []
    for interval in bootstrap.intervals:
        intervals.append(
            {
                "name": interval.name,
                "estimate": _json_safe(interval.estimate),
                "lower": _json_safe(interval.lower),
                "upper": _json_safe(interval.upper),
                "status": interval.status.value,
                "reason": interval.reason,
                "units": interval.units,
                "interval_available": interval.interval_available,
                "metadata": _json_safe(interval.metadata),
            }
        )
    return {
        "requested": bootstrap.requested,
        "attempted": bootstrap.attempted,
        "successful": bootstrap.successful,
        "failed": bootstrap.failed,
        "status": bootstrap.status.value,
        "failure_counts": _json_safe(bootstrap.failure_counts),
        "intervals": intervals,
        "metadata": _json_safe(bootstrap.metadata),
    }


def assemble_diagnostics(
    plan: AnalysisPlan | None,
    fitted: FittedSystem | None,
    *,
    bootstrap: BootstrapResult | None = None,
    moderation: Mapping[str, object] | None = None,
    optional_warnings: Sequence[Issue] = (),
    overall_status: str,
    error: Issue | None = None,
    stage: str | None = None,
) -> Mapping[str, object]:
    """Assemble serializable, non-sensitive diagnostics for one result."""

    plan_diagnostics = dict(plan.diagnostics) if plan is not None else {}
    rows = _json_safe(plan_diagnostics.get("rows", {}))
    missing = _json_safe(plan_diagnostics.get("missing", {}))
    participant_id = _json_safe(plan_diagnostics.get("participant_id", {"column": None, "unique": True}))
    support = _json_safe(plan_diagnostics.get("support", {}))
    binary_counts = _json_safe(plan_diagnostics.get("binary_counts", {}))
    plan_issues = tuple(plan.issues) if plan is not None else ()

    if plan is None:
        nodes: list[dict[str, Any]] = []
        scientific: dict[str, Any] = {
            "contrast": {},
            "units": None,
            "interpretation": None,
            "standardization_population": "retained_analysis_rows",
            "scientific_edges": [],
            "factorization_order": [],
            "factorization_predictors": {},
            "requested_effects": [],
        }
        integration: dict[str, Any] = {
            "method": None,
            "status": "not_run",
            "initial_draw_budget": None,
            "accepted_draw_budget": None,
            "draw_seed": None,
            "tolerance": None,
            "diagnostics": {},
            "issues": [],
        }
    else:
        nodes = (
            [_node_record(node) for node in fitted.nodes]
            if fitted is not None
            else [_planned_node_record(node) for node in plan.nodes]
        )
        outcome_family = plan.nodes[-1].family.value if plan.nodes else None
        scientific = {
            "contrast": {
                "reference": _json_safe(plan.contrast.reference),
                "comparison": _json_safe(plan.contrast.comparison),
                "moderator_values": _json_safe(plan.contrast.moderator_values),
            },
            "units": "probability_difference" if outcome_family == "bernoulli" else "outcome_units",
            "interpretation": plan.contrast.interpretation,
            "standardization_population": "retained_analysis_rows",
            "outcome_family": outcome_family,
            "scientific_edges": _json_safe(plan_diagnostics.get("scientific_edges", ())),
            "factorization_order": _json_safe(plan_diagnostics.get("factorization_order", ())),
            "factorization_predictors": {
                node.response: list(node.factorization_predictors) for node in plan.nodes
            },
            "requested_effects": list(plan.contrast.primary_effects),
        }
        integration = {
            "method": fitted.integration_method if fitted is not None else None,
            "status": fitted.status.value if fitted is not None else "not_run",
            "initial_draw_budget": plan.computation.integration_draws,
            "accepted_draw_budget": fitted.draw_budget if fitted is not None else None,
            "draw_seed": (
                fitted.draws.seed
                if fitted is not None and fitted.draws is not None
                else None
            ),
            "tolerance": (
                fitted.integration_diagnostics.get("tolerance", plan.computation.integration_tolerance)
                if fitted is not None
                else plan.computation.integration_tolerance
            ),
            "diagnostics": _json_safe(
                fitted.integration_diagnostics if fitted is not None else {}
            ),
            "issues": [
                _issue_record(issue) for issue in (fitted.issues if fitted is not None else ())
            ],
        }

    warnings = [_issue_record(issue) for issue in (*plan_issues, *optional_warnings)]
    moderation_record = _json_safe(moderation) if moderation is not None else {
        "requested": False,
        "status": "not_requested",
        "baseline_values": {},
        "requested_values": {},
        "contrasts": [],
        "reason": None,
    }
    assumptions = [
        "observed-variable mediation analysis",
        "rows are treated as independent observations",
        "endogenous nodes use supported Gaussian or Bernoulli families",
        "effects are model-standardized over retained_analysis_rows",
        "interpretation is assumption-based under the declared model",
        "latent variables, clustered rows, ordinal nodes, and count nodes are unsupported",
    ]
    if plan is not None and plan.missing == "complete_case":
        assumptions.append("complete-case population after declared missingness exclusion")
    exclusions = {
        "excluded_rows": int(rows.get("excluded", 0)) if isinstance(rows, Mapping) else 0,
        "reasons": _json_safe(missing.get("counts", {})) if isinstance(missing, Mapping) else {},
        "unsupported_features": ["latent_variables", "clustered_rows", "ordinal_nodes", "count_nodes"],
    }
    return {
        "overall_status": overall_status,
        "rows": rows,
        "missing": missing,
        "participant_id": participant_id,
        "support": support,
        "binary_counts": binary_counts,
        "scientific": scientific,
        "nodes": nodes,
        "integration": integration,
        "bootstrap": _bootstrap_record(bootstrap),
        "moderation": moderation_record,
        "warnings": warnings,
        "assumptions": assumptions,
        "exclusions": exclusions,
        "error": _issue_record(error) if error is not None else None,
        "stage": stage,
    }


__all__ = [
    "assemble_diagnostics",
    "DataValidationError",
    "NodeFitError",
    "PlanValidationError",
    "UnsupportedAnalysisError",
]
