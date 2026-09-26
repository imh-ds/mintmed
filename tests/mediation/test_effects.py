"""Contract tests for named mediation effects and Task 9 outputs."""

from __future__ import annotations

import numpy as np
import pytest
from dataclasses import replace

from mintmed.effects import (
    ModeratorContrast,
    moderator_contrasts,
    natural_effects,
    parallel_contributions,
)
from mintmed.gformula import CommonDraws, compute_regime_means, fit_system
from mintmed.simulation import sample_fixture
from mintmed.spec import Family, estimate_plan
from mintmed.types import AnalysisStatus, RegimeMeans


def test_effect_module_exports_task9_contracts():
    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)
    effects = natural_effects(
        means,
        exposure_reference=0,
        exposure_comparison=1,
        units="outcome_units",
    )
    assert tuple(effect.name for effect in effects) == ("TE", "PNDE", "TNIE")
    assert tuple(effect.estimate for effect in effects) == pytest.approx((0.5, 0.2, 0.3))
    assert ModeratorContrast.__name__ == "ModeratorContrast"


def test_natural_effects_preserves_cancellation_and_metadata():
    effects = natural_effects(
        RegimeMeans(mu_00=1.0, mu_10=0.0, mu_11=1.0),
        units="probability_difference",
        interpretation="model_standardized",
    )
    assert effects[0].estimate == pytest.approx(0.0)
    assert effects[0].units == "probability_difference"
    assert effects[0].metadata["standardization_population"] == "retained_analysis_rows"
    assert effects[1].estimate == pytest.approx(-1.0)
    assert effects[2].estimate == pytest.approx(1.0)


def test_nonfinite_means_are_explicit_failures_not_silent_zeroes():
    effects = natural_effects(RegimeMeans(np.nan, 0.0, 1.0))
    assert all(effect.status is AnalysisStatus.INTEGRATION_FAILED for effect in effects)
    assert all(effect.reason == "nonfinite_regime_mean" for effect in effects)


def test_decomposition_identity_failure_keeps_arithmetic_values():
    effects = natural_effects(
        RegimeMeans(mu_00=0.1, mu_10=0.3, mu_11=0.6),
        numerical_tolerance=0.0,
    )
    assert all(effect.status is AnalysisStatus.INTEGRATION_FAILED for effect in effects)
    assert all(effect.reason == "effect_decomposition_identity_failed" for effect in effects)
    assert tuple(effect.estimate for effect in effects) == pytest.approx((0.5, 0.19999999999999998, 0.3))


def _fit_fixture(name: str, *, n: int = 120, tolerance: float = 1.0):
    fixture = sample_fixture(name, n, np.random.default_rng(20260920 + n))
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            integration_tolerance=tolerance,
        ),
    )
    plan = estimate_plan(fixture.data, spec)
    return fixture, plan, fit_system(fixture.data, plan)


def _additive_parallel_fixture():
    fixture = sample_fixture("parallel_correlated", 120, np.random.default_rng(20261009))
    outcome = replace(fixture.spec.nodes[-1], interactions=())
    spec = replace(
        fixture.spec,
        nodes=(*fixture.spec.nodes[:-1], outcome),
        computation=replace(fixture.spec.computation, integration_tolerance=1.0),
    )
    plan = estimate_plan(fixture.data, spec)
    fitted = fit_system(fixture.data, plan)
    assert fitted.draws is not None
    return fixture, plan, fitted


def _parallel_binary_outcome_fixture():
    fixture = sample_fixture("binary_two_mediators", 140, np.random.default_rng(20261010))
    m2 = replace(
        fixture.spec.nodes[1],
        terms=tuple(term for term in fixture.spec.nodes[1].terms if term.variable == "A"),
    )
    edges = tuple(edge for edge in fixture.spec.scientific.edges if edge != ("M1", "M2"))
    scientific = replace(fixture.spec.scientific, edges=edges, arrangement="parallel")
    spec = replace(
        fixture.spec,
        nodes=(fixture.spec.nodes[0], m2, fixture.spec.nodes[2]),
        scientific=scientific,
    )
    plan = estimate_plan(fixture.data, spec)
    return fixture, plan, fit_system(fixture.data, plan)


def _moderated_fit():
    fixture = sample_fixture("moderated_serial", 120, np.random.default_rng(20261011))
    data = fixture.data.copy(deep=True)
    data["W"] = 0.0
    data.loc[data.index[:15], "W"] = 1.0
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, integration_tolerance=1.0),
    )
    plan = estimate_plan(data, spec)
    fitted = fit_system(data, plan)
    assert fitted.draws is not None
    return replace(fixture, data=data), plan, fitted


def test_valid_parallel_single_mediator_terms_sum_to_joint_tnie():
    fixture, plan, fitted = _additive_parallel_fixture()
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is True
    assert tuple(result.contributions) == ("TNIE_M1", "TNIE_M2")
    assert sum(effect.estimate for effect in result.contributions.values()) == pytest.approx(
        means.total_natural_indirect_effect,
        abs=1e-10,
    )


def test_valid_single_mediator_interaction_remains_admissible():
    fixture, plan, fitted = _fit_fixture("interaction")
    assert fitted.draws is not None
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is True
    assert tuple(result.contributions) == ("TNIE_M",)
    assert result.contributions["TNIE_M"].estimate == pytest.approx(
        means.total_natural_indirect_effect,
        abs=1e-10,
    )


def test_moderator_values_use_all_rows_and_paired_draws():
    fixture, plan, fitted = _moderated_fit()
    contrasts = moderator_contrasts(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )
    assert tuple((item.moderator, item.value) for item in contrasts) == (("W", 0.0), ("W", 1.0))
    assert all(len(item.differences) == 3 for item in contrasts)
    assert contrasts[1].metadata["paired_draws"] is True
    assert contrasts[1].metadata["draw_seed"] == fitted.draws.seed
    assert contrasts[1].metadata["draw_budget"] == fitted.draws.draw_count
    assert contrasts == moderator_contrasts(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )


def test_moderator_contrasts_reject_unsupported_values_with_typed_error():
    from mintmed.gformula import GFormulaError

    fixture, plan, fitted = _moderated_fit()
    with pytest.raises(GFormulaError) as caught:
        moderator_contrasts(
            fixture.data,
            plan,
            fitted,
            fitted.draws,
            moderator_values={"W": (2.0,)},
        )
    assert caught.value.code == "unsupported_extrapolation"


def test_parallel_contributions_refuse_nonparallel_structure():
    fixture, plan, fitted = _fit_fixture("serial_two")
    means = compute_regime_means(fixture.data, plan, fitted)
    assert fitted.draws is not None
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is False
    assert result.contributions == {}
    assert result.reason_code == "contribution_nonparallel"


def test_parallel_contributions_refuse_cross_mediator_terms():
    fixture, plan, fitted = _fit_fixture("parallel_correlated")
    means = compute_regime_means(fixture.data, plan, fitted)
    assert fitted.draws is not None
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is False
    assert result.contributions == {}
    assert result.reason_code == "contribution_cross_mediator_term"


def test_parallel_contributions_refuse_non_gaussian_outcome():
    fixture, plan, fitted = _parallel_binary_outcome_fixture()
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        CommonDraws.from_seed(seed=17, draw_count=1, mediator_count=2),
        0.0,
    )
    assert result.available is False
    assert result.contributions == {}
    assert result.reason_code == "contribution_outcome_family"


# BUG-01 regression contracts: additive contributions must be evaluated with
# the same integrator as the joint TNIE, never with placeholder draws.
_NON_SOBOL_SINGLE_MEDIATOR_CASES = (
    ("linear", "gaussian_linear_exact"),
    ("quadratic_b", "gauss_hermite"),
    ("binary_mediator_gaussian_outcome", "exact_binary_mediators"),
)


@pytest.mark.parametrize("tolerance", (1e-8, 1.0))
@pytest.mark.parametrize(("name", "method"), _NON_SOBOL_SINGLE_MEDIATOR_CASES)
def test_single_mediator_contribution_equals_joint_tnie_on_exact_paths(name, method, tolerance):
    fixture, plan, fitted = _fit_fixture(name, tolerance=tolerance)
    assert fitted.integration_method == method
    assert fitted.draws is None
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is True, result.reason
    assert tuple(result.contributions) == ("TNIE_M",)
    assert result.contributions["TNIE_M"].estimate == pytest.approx(
        means.total_natural_indirect_effect,
        abs=1e-10,
    )
    assert result.contributions["TNIE_M"].metadata["integration_method"] == method


def _parallel_binary_mediators_gaussian_outcome():
    fixture, plan, _ = _parallel_binary_outcome_fixture()
    spec = fixture.spec
    m2 = replace(
        spec.nodes[1],
        terms=tuple(term for term in spec.nodes[1].terms if term.variable == "A"),
    )
    edges = tuple(edge for edge in spec.scientific.edges if edge != ("M1", "M2"))
    outcome_variable = replace(spec.outcome, observed_type="continuous", family=Family.GAUSSIAN, levels=())
    outcome_node = replace(spec.nodes[2], family=Family.GAUSSIAN)
    spec = replace(
        spec,
        outcome=outcome_variable,
        nodes=(spec.nodes[0], m2, outcome_node),
        scientific=replace(spec.scientific, edges=edges, arrangement="parallel"),
    )
    plan = estimate_plan(fixture.data, spec)
    return fixture, plan, fit_system(fixture.data, plan)


def test_exact_binary_parallel_contributions_match_closed_form():
    fixture, plan, fitted = _parallel_binary_mediators_gaussian_outcome()
    assert fitted.integration_method == "exact_binary_mediators"
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert result.available is True, result.reason

    # Linear outcome: contribution_j = beta_j * standardized change in P(Mj = 1).
    outcome = fitted.outcome_node
    beta = dict(zip(outcome.design.columns, outcome.coefficients))
    frame = fixture.data.loc[list(plan.retained_row_indices)]
    for name in ("M1", "M2"):
        node = fitted.node_by_response[name]
        shift = np.mean(node.predict_mean(frame.assign(A=1.0))) - np.mean(
            node.predict_mean(frame.assign(A=0.0))
        )
        expected = beta[f'Q("{name}")'] * shift
        assert result.contributions[f"TNIE_{name}"].estimate == pytest.approx(expected, abs=1e-10)
    assert sum(effect.estimate for effect in result.contributions.values()) == pytest.approx(
        means.total_natural_indirect_effect,
        abs=1e-10,
    )


def test_sobol_contributions_still_require_the_accepted_draws():
    fixture, plan, fitted = _additive_parallel_fixture()
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        CommonDraws.from_seed(seed=3, draw_count=1, mediator_count=2),
        means.total_natural_indirect_effect,
    )
    assert result.available is False
    assert result.reason_code == "contribution_integration_unresolved"


def test_placeholder_draws_cannot_change_exact_path_contributions():
    # Reproduces the audited failure: a one-draw placeholder and a loose
    # tolerance previously published a single-draw value as a contribution.
    fixture, plan, fitted = _fit_fixture("quadratic_b", tolerance=1.0)
    assert fitted.integration_method == "gauss_hermite"
    means = compute_regime_means(fixture.data, plan, fitted)
    result = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        CommonDraws.from_seed(seed=17, draw_count=1, mediator_count=1),
        means.total_natural_indirect_effect,
    )
    assert result.available is True, result.reason
    assert result.contributions["TNIE_M"].estimate == pytest.approx(
        means.total_natural_indirect_effect,
        abs=1e-10,
    )


def test_moderator_contrasts_reuse_identical_regime_configurations(monkeypatch):
    # Audit BUG-03: the baseline configuration was re-evaluated for the
    # baseline effects, for the equal-to-baseline value, and again after the
    # primary effects. Reuse must not change any estimate.
    fixture, plan, fitted = _moderated_fit()
    import mintmed.effects as effects_module

    baseline_values = dict(plan.contrast.moderator_values)
    uncached = moderator_contrasts(
        fixture.data, plan, fitted, fitted.draws, moderator_values={"W": (0.0, 1.0)}
    )
    reference = compute_regime_means(fixture.data, plan, fitted)

    calls = 0
    original = effects_module.standardize_regime

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(effects_module, "standardize_regime", counting)
    cached = moderator_contrasts(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
        baseline_values=baseline_values,
        reference_means=reference,
    )
    assert cached == uncached
    assert calls == 3  # only the W=1 configuration is new


def test_primary_effects_record_their_moderator_conditioning() -> None:
    from mintmed.effects import natural_effects

    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)

    conditioned = natural_effects(means, moderator_values={"W": 0.0, "Z": 1.5})
    unconditioned = natural_effects(means)

    for effect in conditioned:
        assert effect.metadata["moderator_values"] == {"W": 0.0, "Z": 1.5}
        assert effect.metadata["standardization_population"] == "retained_analysis_rows_with_W=0,Z=1.5"
    for effect in unconditioned:
        assert effect.metadata["moderator_values"] == {}
        assert effect.metadata["standardization_population"] == "retained_analysis_rows"
