"""Contract tests for Gaussian and Bernoulli conditional nodes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from mintmed.diagnostics import NodeFitError
from mintmed.design import fit_design, transform_design
from mintmed import models
from mintmed.models import (
    FittedNode,
    GaussianNode,
    NodeFitDiagnostics,
    fit_node,
)
from mintmed.spec import CompiledNodePlan, Family, TermKind, TermSpec
from mintmed.types import AnalysisStatus


def make_node(
    *,
    family: Family = Family.GAUSSIAN,
    response: str = "outcome",
    terms: tuple[TermSpec, ...] = (TermSpec("x", TermKind.LINEAR),),
    intercept: bool = True,
) -> CompiledNodePlan:
    return CompiledNodePlan(
        response=response,
        family=family,
        terms=terms,
        interactions=(),
        scientific_parents=(),
        factorization_predictors=tuple(term.variable for term in terms),
        intercept=intercept,
        category_levels={},
    )


def gaussian_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "outcome": [1.2, 2.1, 2.7, 3.8, 4.4, 5.3, 6.2, 7.1],
            "x": [-2.0, -1.5, -1.0, -0.25, 0.5, 1.0, 1.75, 2.5],
        }
    )


def test_node_module_exposes_task6_contract() -> None:
    assert FittedNode is not None
    assert NodeFitDiagnostics is not None
    assert hasattr(models, "GaussianNode")
    assert hasattr(models, "BernoulliNode")
    assert hasattr(models, "fit_node")


def test_gaussian_fit_matches_statsmodels_and_freezes_diagnostics() -> None:
    data = gaussian_data()
    node = make_node()

    fitted = fit_node(data, node)
    expected = sm.OLS(
        data["outcome"].to_numpy(),
        fitted.design.matrix,
    ).fit()

    np.testing.assert_allclose(fitted.coefficients, expected.params)
    np.testing.assert_allclose(
        fitted.predict_mean(data),
        expected.predict(fitted.design.matrix),
    )
    assert isinstance(fitted, GaussianNode)
    assert fitted.family is Family.GAUSSIAN
    assert fitted.parameter_count == fitted.design.matrix.shape[1]
    assert fitted.converged is True
    assert fitted.sigma == pytest.approx(
        np.sqrt(expected.ssr / expected.df_resid)
    )
    assert fitted.diagnostics().status is AnalysisStatus.OK
    assert fitted.diagnostics().rank == fitted.design.rank
    assert fitted.diagnostics().n_rows == len(data)
    assert fitted.diagnostics().coefficients_finite is True


def test_gaussian_prediction_accepts_frozen_matrix_and_data_frame() -> None:
    data = gaussian_data()
    fitted = fit_node(data, make_node())
    prediction_frame = data.iloc[[0, 3, 7]].copy()
    prediction_matrix = transform_for_test(fitted.design, prediction_frame)

    np.testing.assert_allclose(
        fitted.predict_mean(prediction_frame),
        fitted.predict_mean(prediction_matrix),
    )


def transform_for_test(design, data: pd.DataFrame) -> np.ndarray:
    """Build the oracle matrix without reaching into the node implementation."""

    return transform_design(design, data).to_numpy(dtype=float)


def test_gaussian_sampling_uses_explicit_standard_normal_noise() -> None:
    data = gaussian_data()
    fitted = fit_node(data, make_node())
    noise = np.arange(len(data), dtype=float) / 10.0
    block_noise = np.stack([noise, -noise], axis=1)

    expected_mean = fitted.predict_mean(data)
    np.testing.assert_allclose(
        fitted.sample(data, noise),
        expected_mean + fitted.sigma * noise,
    )
    np.testing.assert_allclose(
        fitted.sample(data, block_noise),
        expected_mean[:, None] + fitted.sigma * block_noise,
    )


def test_gaussian_generator_sampling_is_deterministic_and_isolated() -> None:
    data = gaussian_data()
    fitted = fit_node(data, make_node())

    np.random.seed(123)
    first = fitted.sample(data, np.random.default_rng(41), size=3)
    np.random.seed(999)
    second = fitted.sample(data, np.random.default_rng(41), size=3)

    assert first.shape == (len(data), 3)
    np.testing.assert_allclose(first, second)


def test_gaussian_log_density_matches_normal_formula() -> None:
    data = gaussian_data()
    fitted = fit_node(data, make_node())
    observed = data["outcome"].to_numpy()
    mean = fitted.predict_mean(data)
    z = (observed - mean) / fitted.sigma
    expected = -0.5 * (
        z * z + np.log(2.0 * np.pi * fitted.sigma * fitted.sigma)
    )

    np.testing.assert_allclose(fitted.log_density(data, observed), expected)


def test_gaussian_rejects_missing_response() -> None:
    data = gaussian_data().drop(columns=["outcome"])

    with pytest.raises(NodeFitError) as error:
        fit_node(data, make_node())

    assert error.value.code == "missing_response"
    assert error.value.response == "outcome"
    assert "available_columns" in error.value.details


def test_gaussian_rejects_nonfinite_response() -> None:
    data = gaussian_data()
    data.loc[2, "outcome"] = np.nan

    with pytest.raises(NodeFitError) as error:
        fit_node(data, make_node())

    assert error.value.code == "nonfinite_response"
    assert error.value.response == "outcome"


def test_gaussian_rejects_rank_deficient_design() -> None:
    data = pd.DataFrame(
        {
            "outcome": [1.0, 2.0, 3.0, 4.0],
            "x": [1.0, 1.0, 1.0, 1.0],
        }
    )

    with pytest.raises(NodeFitError) as error:
        fit_node(data, make_node())

    assert error.value.code == "rank_deficient"
    assert error.value.response == "outcome"
    assert error.value.columns == ("Intercept", 'Q("x")')


def test_gaussian_rejects_nonpositive_residual_degrees_of_freedom() -> None:
    data = pd.DataFrame({"outcome": [1.0, 2.0], "x": [0.0, 1.0]})

    with pytest.raises(NodeFitError) as error:
        fit_node(data, make_node())

    assert error.value.code == "invalid_residual_variance"
    assert error.value.details["df_resid"] == 0.0


def test_gaussian_rejects_invalid_prediction_matrix() -> None:
    fitted = fit_node(gaussian_data(), make_node())

    with pytest.raises(NodeFitError) as error:
        fitted.predict_mean(np.ones((2, 1)))

    assert error.value.code == "invalid_predictors"
    assert error.value.response == "outcome"


def test_gaussian_rejects_invalid_noise_shape_and_values() -> None:
    fitted = fit_node(gaussian_data(), make_node())

    with pytest.raises(NodeFitError) as shape_error:
        fitted.sample(gaussian_data(), np.ones((2, 2)))
    with pytest.raises(NodeFitError) as value_error:
        fitted.sample(gaussian_data(), np.full(len(gaussian_data()), np.nan))

    assert shape_error.value.code == "invalid_noise"
    assert value_error.value.code == "invalid_noise"


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
