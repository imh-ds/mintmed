"""Contract tests for Gaussian and Bernoulli conditional nodes."""

from __future__ import annotations

import pytest

from mintmed.diagnostics import NodeFitError
from mintmed import models
from mintmed.models import FittedNode, NodeFitDiagnostics
from mintmed.spec import Family
from mintmed.types import AnalysisStatus


def test_node_module_exposes_task6_contract() -> None:
    assert FittedNode is not None
    assert NodeFitDiagnostics is not None
    assert hasattr(models, "GaussianNode")
    assert hasattr(models, "BernoulliNode")
    assert hasattr(models, "fit_node")


def test_node_fit_diagnostics_freezes_metadata() -> None:
    diagnostics = NodeFitDiagnostics(
        response="outcome",
        family=Family.GAUSSIAN,
        status=AnalysisStatus.OK,
        code="ok",
        message="fit succeeded",
        n_rows=8,
        rank=2,
        parameter_count=2,
        converged=True,
        coefficients_finite=True,
        df_resid=6.0,
        sigma=1.0,
        log_likelihood=-8.0,
        deviance=None,
        events=None,
        non_events=None,
        warnings=("a warning",),
        metadata={"iteration": 1},
    )

    assert diagnostics.metadata["iteration"] == 1
    with pytest.raises(TypeError):
        diagnostics.metadata["new"] = True  # type: ignore[index]


def test_node_fit_error_preserves_context_and_fit_failed_status() -> None:
    error = NodeFitError(
        code="separation",
        response="outcome",
        message="perfect separation",
        variable="x",
        columns=("Intercept", "x"),
        details={"statsmodels_message": "Perfect separation detected"},
    )

    issue = error.to_issue()

    assert error.response == "outcome"
    assert error.variable == "x"
    assert error.columns == ("Intercept", "x")
    assert error.details["statsmodels_message"] == "Perfect separation detected"
    assert issue.status is AnalysisStatus.FIT_FAILED
    assert issue.node == "outcome"
    with pytest.raises(TypeError):
        error.details["new"] = True  # type: ignore[index]


def test_node_fit_error_to_issue_honors_explicit_node_override() -> None:
    error = NodeFitError(
        code="nonconvergence",
        response="mediator",
        message="solver did not converge",
    )

    issue = error.to_issue(node="custom-node")

    assert issue.node == "custom-node"
