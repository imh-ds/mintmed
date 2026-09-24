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
from mintmed.spec import estimate_plan
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
    assert contrasts == moderator_contrasts(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )


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
