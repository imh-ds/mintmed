"""Contract and numerical tests for the shared g-formula engine."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mintmed.simulation import sample_fixture
from mintmed.spec import Family, TermKind, TermSpec, estimate_plan
from mintmed.types import AnalysisStatus, RegimeMeans


def _fixture(name: str, n: int = 160):
    fixture = sample_fixture(name, n, np.random.default_rng(20260920))
    return fixture, estimate_plan(fixture.data, fixture.spec)


def test_public_contracts_and_common_draws_are_immutable():
    from mintmed.gformula import CommonDraws, FittedSystem, GFormulaError

    draws = CommonDraws.from_seed(seed=17, draw_count=32, mediator_count=2)
    assert draws.uniforms.shape == (32, 2)
    assert draws.normals.shape == (32, 2)
    assert draws.for_rows(5, 0, Family.BERNOULLI).shape == (5, 32)
    assert draws.for_rows(5, 1, Family.GAUSSIAN).shape == (5, 32)
    assert np.array_equal(
        draws.uniforms,
        CommonDraws.from_seed(seed=17, draw_count=32, mediator_count=2).uniforms,
    )
    assert not draws.uniforms.flags.writeable
    assert not draws.normals.flags.writeable
    with pytest.raises(ValueError):
        CommonDraws.from_seed(seed=17, draw_count=0, mediator_count=2)
    with pytest.raises(ValueError):
        draws.for_rows(5, 2, Family.BERNOULLI)
    assert GFormulaError.__name__ == "GFormulaError"
    assert FittedSystem.__name__ == "FittedSystem"


def test_fitted_system_preserves_retained_rows_and_declared_order():
    from mintmed.gformula import fit_system

    fixture, plan = _fixture("serial_three", 120)
    data = fixture.data.copy()
    data.index = np.arange(1000, 1000 + len(data))
    plan = estimate_plan(data, fixture.spec)
    fitted = fit_system(data, plan)
    assert fitted.status is AnalysisStatus.OK
    assert tuple(node.response for node in fitted.nodes) == tuple(
        node.response for node in plan.nodes
    )
    assert tuple(node.response for node in fitted.mediator_nodes) == tuple(
        node.response for node in plan.nodes[:-1]
    )
    assert fitted.outcome_node.response == plan.nodes[-1].response
    assert plan.retained_row_indices == tuple(data.index)


def test_regime_means_result_contract_is_response_scale():
    assert RegimeMeans(1.0, 2.0, 4.0).total_effect == 3.0


def _fit(name: str, n: int = 80, *, tolerance: float | None = None):
    fixture = sample_fixture(name, n, np.random.default_rng(20260920 + n))
    spec = fixture.spec
    if tolerance is not None:
        spec = replace(
            spec,
            computation=replace(spec.computation, integration_tolerance=tolerance),
        )
    plan = estimate_plan(fixture.data, spec)
    from mintmed.gformula import fit_system

    return fixture, plan, fit_system(fixture.data, plan)


def test_parallel_gaussian_residual_dependence_is_nuisance_only():
    fixture, plan, fitted = _fit("parallel_correlated", 320, tolerance=1.0)
    assert fitted.mediator_residual_correlation is not None
    assert fitted.mediator_residual_correlation[0, 1] == pytest.approx(0.65, abs=0.10)
    assert all(
        "M1" not in node.scientific_parents and "M2" not in node.scientific_parents
        for node in plan.nodes
        if node.response in {"M1", "M2"}
    )
    assert fixture.metadata["rho"] == pytest.approx(0.65)


def test_serial_standardization_uses_generated_prior_mediators_and_is_block_stable():
    fixture, plan, fitted = _fit("serial_two", 90, tolerance=1.0)
    assert fitted.status is AnalysisStatus.OK
    from mintmed.gformula import (
        _standardize_regime_with_block,
        compute_regime_means,
    )

    means = compute_regime_means(fixture.data, plan, fitted)
    draws = fitted.draws
    assert draws is not None
    block_one = _standardize_regime_with_block(
        fixture.data,
        plan,
        fitted,
        outcome_exposure=1,
        mediator_exposure=0,
        moderator_values=plan.contrast.moderator_values,
        draws=draws,
        block_size=1,
    )
    public = _standardize_regime_with_block(
        fixture.data,
        plan,
        fitted,
        outcome_exposure=1,
        mediator_exposure=0,
        moderator_values=plan.contrast.moderator_values,
        draws=draws,
        block_size=256,
    )
    assert block_one == pytest.approx(public, abs=1e-12)
    assert public == pytest.approx(means.mu_10, abs=1e-12)

    altered = fixture.data.copy()
    altered["M1"] = altered["M1"].sample(frac=1.0, random_state=91).to_numpy()
    altered_means = compute_regime_means(altered, plan, fitted)
    assert altered_means == means


def test_common_draws_are_reused_for_deterministic_means_and_diagnostics():
    fixture, plan, fitted = _fit("parallel_correlated", 70, tolerance=1.0)
    from mintmed.gformula import compute_regime_means

    assert fitted.draws is not None
    assert fitted.draw_budget == fitted.draws.draw_count
    assert compute_regime_means(fixture.data, plan, fitted) == compute_regime_means(
        fixture.data, plan, fitted
    )
    assert fitted.integration_diagnostics["accepted_draw_count"] == fitted.draw_budget
    with pytest.raises(TypeError):
        fitted.integration_diagnostics["accepted_draw_count"] = 1
    with pytest.raises(TypeError):
        fitted.integration_diagnostics["candidate_checks"][0]["accepted"] = False


def test_exact_binary_path_returns_probability_means_and_ignores_draw_sequence():
    fixture, plan, fitted = _fit("binary_two_mediators", 120)
    from mintmed.gformula import CommonDraws, compute_regime_means, standardize_regime

    assert fitted.integration_method == "exact_binary_mediators"
    draws = CommonDraws.from_seed(seed=4, draw_count=8, mediator_count=2)
    means = compute_regime_means(fixture.data, plan, fitted)
    direct = standardize_regime(
        fixture.data,
        plan,
        fitted,
        outcome_exposure=1,
        mediator_exposure=1,
        moderator_values=plan.contrast.moderator_values,
        draws=draws,
    )
    assert 0.0 <= means.mu_00 <= 1.0
    assert 0.0 <= means.mu_10 <= 1.0
    assert 0.0 <= means.mu_11 <= 1.0
    assert direct == pytest.approx(means.mu_11)
    assert means.total_effect == pytest.approx(means.mu_11 - means.mu_00)


def test_gaussian_linear_anchor_is_exact_and_deterministic():
    fixture, plan, fitted = _fit("linear", 100)
    from mintmed.gformula import compute_regime_means

    assert fitted.integration_method == "gaussian_linear_exact"
    first = compute_regime_means(fixture.data, plan, fitted)
    second = compute_regime_means(fixture.data, plan, fitted)
    assert first == second
    assert np.isfinite([first.mu_00, first.mu_10, first.mu_11]).all()


def test_four_mediator_system_preserves_order_and_finite_regimes():
    fixture, plan, fitted = _fit("four_mediator_mixed", 60, tolerance=1.0)
    from mintmed.gformula import compute_regime_means

    assert len(fitted.mediator_nodes) == 4
    assert tuple(node.response for node in fitted.mediator_nodes) == ("M1", "M2", "M3", "M4")
    assert fitted.draws is not None
    means = compute_regime_means(fixture.data, plan, fitted)
    assert np.isfinite([means.mu_00, means.mu_10, means.mu_11]).all()


def test_invalid_draw_dimensions_and_failed_integration_are_typed():
    from mintmed.gformula import CommonDraws, GFormulaError, compute_regime_means, standardize_regime

    fixture, plan, fitted = _fit("serial_two", 70, tolerance=1.0)
    with pytest.raises(GFormulaError) as caught:
        standardize_regime(
            fixture.data,
            plan,
            fitted,
            outcome_exposure=1,
            mediator_exposure=1,
            moderator_values=plan.contrast.moderator_values,
            draws=CommonDraws.from_seed(seed=1, draw_count=fitted.draw_budget, mediator_count=1),
        )
    assert caught.value.code == "invalid_draws"

    failed_fixture, failed_plan, failed = _fit("parallel_correlated", 50, tolerance=1e-300)
    assert failed.status is AnalysisStatus.INTEGRATION_FAILED
    assert failed.issues[0].code == "integration_unresolved"
    with pytest.raises(GFormulaError) as unresolved:
        compute_regime_means(failed_fixture.data, failed_plan, failed)
    assert unresolved.value.status is AnalysisStatus.INTEGRATION_FAILED


def test_node_order_and_node_fit_failures_keep_typed_context():
    from mintmed.gformula import GFormulaError, fit_system

    fixture, plan = _fixture("serial_two", 80)
    reordered = replace(plan, nodes=(plan.nodes[1], plan.nodes[0], plan.nodes[2]))
    with pytest.raises(GFormulaError) as order_error:
        fit_system(fixture.data, reordered)
    assert order_error.value.code == "node_order_mismatch"
    assert order_error.value.status is AnalysisStatus.FIT_FAILED

    bad_first = replace(
        plan.nodes[0],
        terms=(TermSpec("not_in_analysis", TermKind.LINEAR),),
    )
    broken = replace(plan, nodes=(bad_first, *plan.nodes[1:]))
    with pytest.raises(GFormulaError) as fit_error:
        fit_system(fixture.data, broken)
    assert fit_error.value.node == "M1"
    assert fit_error.value.status is AnalysisStatus.FIT_FAILED
