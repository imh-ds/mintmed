"""Task 14 population, integration, and compatibility acceptance tests."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy.special import expit
from statsmodels.stats.mediation import Mediation

from mintmed.api import analyze_mediation
from mintmed.effects import moderator_contrasts, parallel_contributions
from mintmed.gformula import CommonDraws, compute_regime_means, fit_system, standardize_regime
from mintmed.report import result_to_dict
from mintmed.simulation import analytic_effects, sample_fixture
from mintmed.spec import estimate_plan
from mintmed.experiments.mediation_validation import generate_cell


TRUTH_ATOL = 1e-12
IDENTITY_ATOL = 1e-10
GENERAL_REFERENCE_ATOL = 1e-10
STATSMODELS_N_REP = 2048
STATSMODELS_ATOL = 0.08
REFERENCE_DATA_SEED = 20260924
REFERENCE_ANALYSIS_SEED = 20260925

TASK7_FIXTURES = (
    "linear",
    "quadratic_b",
    "cancellation",
    "interaction",
    "ushape_a",
    "serial_two",
    "serial_three",
    "parallel_correlated",
    "binary_two_mediators",
    "moderated_serial",
    "binary_mediator_gaussian_outcome",
    "mixed_binary_serial",
    "four_mediator_mixed",
    "sparse_events",
    "tied_score",
    "missingness",
    "opposing_paths",
)


def _three_regime_contrast(mu):
    mu_00 = float(mu(0.0, 0.0))
    mu_10 = float(mu(1.0, 0.0))
    mu_11 = float(mu(1.0, 1.0))
    return mu_11 - mu_00, mu_10 - mu_00, mu_11 - mu_10


def _binary_two_mediator_mu(a: float, b: float) -> float:
    p_m1 = expit(-0.4 + 0.8 * b)
    total = 0.0
    for m1 in (0.0, 1.0):
        p1 = p_m1 if m1 else 1.0 - p_m1
        p_m2 = expit(-0.2 + 0.5 * b + 0.7 * m1)
        for m2 in (0.0, 1.0):
            p2 = p_m2 if m2 else 1.0 - p_m2
            total += p1 * p2 * expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.6 * m2)
    return float(total)


def _mixed_binary_serial_mu(a: float, b: float) -> float:
    nodes, weights = np.polynomial.hermite.hermgauss(64)
    m2_error = np.sqrt(2.0) * nodes
    m2_weights = weights / np.sqrt(np.pi)
    p_m1 = expit(-0.4 + 0.8 * b)
    total = 0.0
    for m1 in (0.0, 1.0):
        p1 = p_m1 if m1 else 1.0 - p_m1
        m2 = 0.3 * b + 0.5 * m1 + m2_error
        outcome_probability = expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.4 * m2)
        total += p1 * float(np.dot(m2_weights, outcome_probability))
    return float(total)


def _moderated_mu(a: float, b: float, w: float) -> float:
    m1 = (0.3 + 0.3 * w) * b + 0.2 * w
    m2 = 0.2 * b + 0.4 * m1
    return 0.2 * a + (0.3 + 0.3 * w) * m1 + (0.2 + 0.2 * w) * m2 + 0.2 * w


def _four_mediator_mu(a: float, b: float) -> float:
    m1 = 0.4 * b
    m2 = 0.2 * b + 0.3 * m1
    m3 = expit(-0.3 + 0.6 * b)
    m4 = 0.1 * b + 0.2 * m1 + 0.3 * m2 + 0.4 * m3
    return float(0.1 * a + 0.2 * m1 + 0.3 * m2 + 0.4 * m3 + 0.5 * m4)


def _independent_truths() -> dict[str, tuple[float, float, float]]:
    k = 0.8 / np.sqrt(2.0)
    references = {
        "linear": lambda a, b: 0.2 * a + 0.42 * b,
        "quadratic_b": lambda a, b: 0.2 * a + 0.5 * (0.49 * b**2 + 1.0),
        "cancellation": lambda a, b: b - a,
        "interaction": lambda a, b: 0.2 * a + 0.7 * b * (0.6 + 0.4 * a),
        "ushape_a": lambda a, b: 0.2 * a + 0.6 * k * (b**2 - 1.0),
        "serial_two": lambda a, b: 0.2 * a + 0.67 * b,
        "serial_three": lambda a, b: 0.1 * a + 0.49 * b,
        "parallel_correlated": lambda a, b: (
            0.15 * a
            + 0.4 * (0.5 * b)
            + 0.6 * (-0.3 * b)
            + 0.2 * (-0.15 * b**2 + 0.65)
        ),
        "binary_two_mediators": _binary_two_mediator_mu,
        "moderated_serial": lambda a, b: _moderated_mu(a, b, 0.0),
        "binary_mediator_gaussian_outcome": lambda a, b: 0.2 * a + 0.6 * expit(-0.4 + 0.8 * b),
        "mixed_binary_serial": _mixed_binary_serial_mu,
        "four_mediator_mixed": _four_mediator_mu,
        "sparse_events": lambda a, b: 0.2 * a + 0.6 * expit(-4.0 + 0.5 * b),
        "tied_score": lambda a, b: 0.2 * a + 0.42 * b,
        "missingness": lambda a, b: 0.2 * a + 0.42 * b,
        "opposing_paths": lambda a, b: -1.5 * a + 1.5 * b,
    }
    return {name: _three_regime_contrast(mu) for name, mu in references.items()}


@pytest.mark.parametrize("name", TASK7_FIXTURES)
def test_every_task7_truth_matches_an_independent_population_reference(name: str) -> None:
    expected = _independent_truths()[name]
    np.testing.assert_allclose(analytic_effects(name), expected, rtol=0, atol=TRUTH_ATOL)


def test_binary_two_mediator_truth_matches_independent_four_branch_enumeration() -> None:
    fixture = sample_fixture("binary_two_mediators", 100, np.random.default_rng(101))

    expected = _three_regime_contrast(_binary_two_mediator_mu)
    np.testing.assert_allclose(fixture.truth, expected, rtol=0, atol=TRUTH_ATOL)
    assert fixture.truth_method == "exact_enumeration"


def test_mixed_binary_serial_truth_matches_independent_hermite_64_quadrature() -> None:
    fixture = sample_fixture("mixed_binary_serial", 100, np.random.default_rng(102))

    expected = _three_regime_contrast(_mixed_binary_serial_mu)
    np.testing.assert_allclose(fixture.truth, expected, rtol=0, atol=TRUTH_ATOL)
    assert fixture.truth_method == "gauss_hermite_64"
    assert fixture.metadata["quadrature_order"] == 64


def test_binary_population_truth_is_not_a_generated_sample_average() -> None:
    fixture = sample_fixture("binary_two_mediators", 100, np.random.default_rng(103))
    before = fixture.truth
    fixture.data.loc[:, "Y"] = 0.0

    assert fixture.truth == before
    np.testing.assert_allclose(analytic_effects("binary_two_mediators"), before, rtol=0, atol=TRUTH_ATOL)


def test_moderated_population_truth_retains_both_fixed_moderator_regimes() -> None:
    fixture = sample_fixture("moderated_serial", 100, np.random.default_rng(104))

    expected_w0 = _three_regime_contrast(lambda a, b: _moderated_mu(a, b, 0.0))
    expected_w1 = _three_regime_contrast(lambda a, b: _moderated_mu(a, b, 1.0))
    assert fixture.metadata["truth_by_moderator"] == (
        (0.0, expected_w0),
        (1.0, expected_w1),
    )


def test_binary_and_mixed_fitted_systems_select_declared_integration_paths() -> None:
    for name, method in (
        ("binary_two_mediators", "exact_binary_mediators"),
        ("mixed_binary_serial", "sobol_blocked"),
    ):
        fixture = sample_fixture(name, 120, np.random.default_rng(105))
        spec = replace(
            fixture.spec,
            computation=replace(fixture.spec.computation, integration_tolerance=1.0),
        )
        plan = estimate_plan(fixture.data, spec)
        fitted = fit_system(fixture.data, plan)

        assert fitted.integration_method == method
        assert fitted.status.value == "ok"
        if method == "sobol_blocked":
            assert fitted.draw_budget in {256, 512, 1024, 2048, 4096}
            assert fitted.draw_budget >= 256


def test_exact_linear_and_balanced_general_simulator_agree() -> None:
    fixture = sample_fixture("linear", 100, np.random.default_rng(106))
    plan = estimate_plan(fixture.data, fixture.spec)
    exact = fit_system(fixture.data, plan)
    assert exact.integration_method == "gaussian_linear_exact"
    assert exact.draw_budget == 0

    balanced = CommonDraws(
        seed=107,
        draw_count=2,
        mediator_count=1,
        uniforms=np.full((2, 1), 0.5),
        normals=np.array([[-1.0], [1.0]]),
    )
    general = replace(
        exact,
        draws=balanced,
        draw_budget=2,
        integration_method="sobol_blocked",
    )

    regimes = ((0, 0), (1, 0), (1, 1))
    exact_values = tuple(
        standardize_regime(
            fixture.data,
            plan,
            exact,
            outcome_exposure=a,
            mediator_exposure=b,
            moderator_values=plan.contrast.moderator_values,
            draws=balanced,
        )
        for a, b in regimes
    )
    general_values = tuple(
        standardize_regime(
            fixture.data,
            plan,
            general,
            outcome_exposure=a,
            mediator_exposure=b,
            moderator_values=plan.contrast.moderator_values,
            draws=balanced,
        )
        for a, b in regimes
    )
    np.testing.assert_allclose(general_values, exact_values, rtol=0, atol=GENERAL_REFERENCE_ATOL)

    first = compute_regime_means(fixture.data, plan, exact)
    second = compute_regime_means(fixture.data, plan, exact)
    assert first == second
    assert first.total_effect == pytest.approx(
        first.pure_natural_direct_effect + first.total_natural_indirect_effect,
        abs=IDENTITY_ATOL,
    )


def test_serial_identity_holds_for_population_and_fitted_effects() -> None:
    fixture = sample_fixture("serial_two", 120, np.random.default_rng(108))
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, integration_tolerance=1.0, bootstrap=0),
    )
    result = analyze_mediation(fixture.data, spec)
    effects = {effect.name: effect.estimate for effect in result.effects}

    assert result.status.value in {"ok", "warning"}
    assert effects["TE"] == pytest.approx(effects["PNDE"] + effects["TNIE"], abs=IDENTITY_ATOL)


def test_parallel_correlated_residual_dependence_has_no_scientific_mediator_edge() -> None:
    fixture = sample_fixture("parallel_correlated", 4000, np.random.default_rng(109))

    assert fixture.metadata["rho"] == pytest.approx(0.65)
    assert ("M1", "M2") not in fixture.spec.scientific.edges
    assert ("M2", "M1") not in fixture.spec.scientific.edges


def _fit_parallel(name: str, *, additive: bool) -> tuple[pd.DataFrame, object, object]:
    fixture = sample_fixture(name, 140, np.random.default_rng(110))
    spec = fixture.spec
    if additive:
        outcome = replace(spec.nodes[-1], interactions=())
        spec = replace(spec, nodes=(*spec.nodes[:-1], outcome))
    spec = replace(spec, computation=replace(spec.computation, integration_tolerance=1.0, bootstrap=0))
    plan = estimate_plan(fixture.data, spec)
    return fixture.data, plan, fit_system(fixture.data, plan)


def test_parallel_interaction_disables_mediator_specific_contributions() -> None:
    data, plan, fitted = _fit_parallel("parallel_correlated", additive=False)
    means = compute_regime_means(data, plan, fitted)
    assert fitted.draws is not None
    result = parallel_contributions(
        data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )

    assert result.available is False
    assert result.reason_code == "contribution_cross_mediator_term"


def test_additive_parallel_contributions_sum_to_joint_tnie() -> None:
    data, plan, fitted = _fit_parallel("parallel_correlated", additive=True)
    means = compute_regime_means(data, plan, fitted)
    assert fitted.draws is not None
    result = parallel_contributions(
        data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )

    assert result.available is True
    assert sum(effect.estimate for effect in result.contributions.values()) == pytest.approx(
        means.total_natural_indirect_effect,
        abs=IDENTITY_ATOL,
    )


def test_opposing_direct_and_indirect_paths_keep_their_signs() -> None:
    fixture = sample_fixture("opposing_paths", 120, np.random.default_rng(111))
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, integration_tolerance=1.0, bootstrap=0),
    )
    result = analyze_mediation(fixture.data, spec)
    effects = {effect.name: effect.estimate for effect in result.effects}

    assert effects["PNDE"] < 0.0
    assert effects["TNIE"] > 0.0
    assert effects["TE"] == pytest.approx(effects["PNDE"] + effects["TNIE"], abs=IDENTITY_ATOL)


def test_moderator_contrasts_use_paired_draws_and_are_deterministic() -> None:
    fixture = sample_fixture("moderated_serial", 120, np.random.default_rng(112))
    data = fixture.data.copy()
    data["W"] = 0.0
    data.loc[data.index[:20], "W"] = 1.0
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, integration_tolerance=1.0, bootstrap=0),
    )
    plan = estimate_plan(data, spec)
    fitted = fit_system(data, plan)
    assert fitted.draws is not None

    first = moderator_contrasts(
        data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )
    second = moderator_contrasts(
        data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )

    assert first == second
    assert all(item.metadata["paired_draws"] is True for item in first)
    assert all(item.metadata["draw_seed"] == fitted.draws.seed for item in first)
    assert all(item.metadata["draw_budget"] == fitted.draws.draw_count for item in first)


@pytest.mark.parametrize("name", ("serial_two", "parallel_correlated"))
def test_serial_and_parallel_execution_are_deterministic(name: str) -> None:
    fixture = sample_fixture(name, 90, np.random.default_rng(113))
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, integration_tolerance=1.0, bootstrap=0, seed=114),
    )

    first = result_to_dict(analyze_mediation(fixture.data, spec))
    second = result_to_dict(analyze_mediation(fixture.data, spec))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_statsmodels_anchor_matches_mintmed_for_one_linear_model() -> None:
    fixture = generate_cell("cell01_linear_n100", REFERENCE_DATA_SEED)
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            seed=REFERENCE_ANALYSIS_SEED,
            bootstrap=0,
            integration_draws=256,
            integration_tolerance=1e-8,
        ),
    )
    mintmed_result = analyze_mediation(fixture.data, spec)
    mintmed_effects = {effect.name: float(effect.estimate) for effect in mintmed_result.effects}

    outcome_model = sm.OLS.from_formula("Y ~ A + M + C", fixture.data)
    mediator_model = sm.OLS.from_formula("M ~ A + C", fixture.data)
    state = np.random.get_state()
    try:
        np.random.seed(REFERENCE_ANALYSIS_SEED)
        statsmodels_result = Mediation(
            outcome_model,
            mediator_model,
            exposure="A",
            mediator="M",
        ).fit(method="parametric", n_rep=STATSMODELS_N_REP)
    finally:
        np.random.set_state(state)

    compared = {
        "TE": float(np.asarray(statsmodels_result.total_effect).mean()),
        "PNDE": float(np.asarray(statsmodels_result.ADE_avg).mean()),
        "TNIE": float(np.asarray(statsmodels_result.ACME_avg).mean()),
    }
    assert mintmed_result.status.value in {"ok", "warning"}
    np.testing.assert_allclose(
        [compared[name] for name in ("TE", "PNDE", "TNIE")],
        [mintmed_effects[name] for name in ("TE", "PNDE", "TNIE")],
        rtol=0,
        atol=STATSMODELS_ATOL,
    )
    assert mintmed_effects["TE"] == pytest.approx(
        mintmed_effects["PNDE"] + mintmed_effects["TNIE"],
        abs=IDENTITY_ATOL,
    )
