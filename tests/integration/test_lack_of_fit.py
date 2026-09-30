"""Tests for the Task 18 conventional lack-of-fit battery."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from mintmed.experiments.lack_of_fit import (
    holm_adjust,
    lack_of_fit_battery,
    nested_f_test,
)

OUTCOME = "Y ~ A + M + C"
MEDIATOR = "M ~ A + C"


def _data(
    n: int,
    seed: int,
    *,
    quad: float = 0.0,
    interaction: float = 0.0,
    y_sd_a: float = 0.0,
    m_sd_a: float = 0.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = rng.normal(size=n)
    a = rng.binomial(1, 0.5, size=n).astype(float)
    m = 0.5 * a + 0.4 * c + (1.0 + m_sd_a * a) * rng.normal(size=n)
    y = (
        0.3 * a
        + 0.5 * m
        + 0.3 * c
        + quad * m**2
        + interaction * a * m
        + (1.0 + y_sd_a * a) * rng.normal(size=n)
    )
    return pd.DataFrame({"A": a, "M": m, "Y": y, "C": c})


def _components(result):
    return {component.name: component for component in result.components}


def test_outcome_components_and_df_from_ranks():
    data = _data(200, 1)
    result = lack_of_fit_battery(data, OUTCOME, "M")
    parts = _components(result)
    assert result.status == "ok"
    assert list(parts) == ["mean_curvature_M", "mean_interaction_AM", "variance_BP"]
    # base rank 4; spline basis spans {1, M, 2 nonlinear directions}
    assert parts["mean_curvature_M"].df == (2, 200 - 6)
    assert parts["mean_interaction_AM"].df == (1, 200 - 5)
    assert parts["variance_BP"].df == (3,)
    adjusted = holm_adjust([c.p_value for c in result.components])
    assert [c.adjusted_p_value for c in result.components] == pytest.approx(adjusted)
    assert result.min_adjusted_p == pytest.approx(min(adjusted))
    assert result.warning is (result.min_adjusted_p < 0.05)
    assert result.runtime_seconds >= 0


def test_nested_f_matches_statsmodels_and_ignores_collinear_columns():
    data = _data(150, 2)
    import statsmodels.formula.api as smf

    small = smf.ols("Y ~ A + M + C", data).fit()
    large = smf.ols("Y ~ A + M + C + A:M", data).fit()
    expected_f, expected_p, expected_df = large.compare_f_test(small)
    base = small.model.exog
    am = (data["A"] * data["M"]).to_numpy()[:, None]
    # duplicate and linear-combination columns must not change the df
    added = np.column_stack([am, 2.0 * am, data["M"].to_numpy() + 3.0])
    f_stat, df_num, df_den, p = nested_f_test(base, added, data["Y"].to_numpy())
    assert (df_num, df_den) == (1, 150 - 5)
    assert f_stat == pytest.approx(expected_f)
    assert p == pytest.approx(expected_p)
    assert expected_df == 1


def test_declared_interaction_is_not_applicable():
    data = _data(150, 3)
    result = lack_of_fit_battery(data, "Y ~ A * M + C", "M")
    parts = _components(result)
    assert parts["mean_interaction_AM"].status == "not_applicable"
    assert math.isnan(parts["mean_interaction_AM"].adjusted_p_value)
    applicable = [c for c in result.components if c.status == "ok"]
    assert len(applicable) == 2
    assert [c.adjusted_p_value for c in applicable] == pytest.approx(
        holm_adjust([c.p_value for c in applicable])
    )


def test_declared_quadratic_tests_spline_beyond_declared_terms():
    data = _data(300, 4, quad=0.4)
    linear = lack_of_fit_battery(data, OUTCOME, "M")
    declared = lack_of_fit_battery(data, "Y ~ A + M + I(M ** 2) + C", "M")
    curv_linear = _components(linear)["mean_curvature_M"]
    curv_declared = _components(declared)["mean_curvature_M"]
    assert curv_linear.p_value < 1e-6
    # Base rank is 5. The natural spline is piecewise cubic (not a quadratic),
    # so it adds 2 directions beyond {1, A, M, M^2, C}: rank 7 in all.
    assert curv_declared.df[0] == 2
    assert curv_declared.df[1] == 300 - 7
    assert curv_declared.p_value > 0.001


def test_mediator_node_components():
    data = _data(200, 5)
    result = lack_of_fit_battery(data, MEDIATOR, "A")
    parts = _components(result)
    assert list(parts) == ["mean_curvature_C", "variance_BP"]
    assert parts["mean_curvature_C"].df == (2, 200 - 5)
    assert parts["variance_BP"].df == (2,)
    power = lack_of_fit_battery(_data(250, 6, m_sd_a=1.0), MEDIATOR, "A")
    assert power.warning
    assert _components(power)["variance_BP"].adjusted_p_value < 1e-4


def test_mediator_node_without_covariate():
    data = _data(120, 7)
    result = lack_of_fit_battery(data, "M ~ A", "A", conditioning=())
    parts = _components(result)
    assert parts["mean_curvature_C"].status == "not_applicable"
    assert parts["variance_BP"].df == (1,)
    assert result.status == "ok"


def test_unavailable_with_two_conditioning_columns():
    data = _data(100, 8)
    data["C2"] = data["C"] ** 2
    result = lack_of_fit_battery(data, "Y ~ A + M + C + C2", "M", conditioning=("C", "C2"))
    assert result.status == "diagnostic_unavailable"
    assert result.warning is False
    assert math.isnan(result.min_adjusted_p)
    assert result.components == ()
    assert result.reason


def test_invalid_parent_rejected():
    with pytest.raises(ValueError):
        lack_of_fit_battery(_data(50, 9), OUTCOME, "C")


def test_deterministic():
    data = _data(250, 10, quad=0.1)
    first = lack_of_fit_battery(data, OUTCOME, "M")
    second = lack_of_fit_battery(data.copy(), OUTCOME, "M")
    assert first.components == second.components
    assert first.min_adjusted_p == second.min_adjusted_p


def test_holm_adjust():
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([0.5, 0.9]) == pytest.approx([1.0, 1.0])


@pytest.mark.parametrize(
    ("formula", "parent", "names"),
    [
        (OUTCOME, "M", ("mean_curvature_M", "mean_interaction_AM", "variance_BP")),
        (MEDIATOR, "A", ("mean_curvature_C", "variance_BP")),
    ],
)
def test_size_under_correct_linear_gaussian_model(formula, parent, names):
    reps, alpha = 300, 0.05
    warnings = 0
    raw = {name: [] for name in names}
    for seed in range(reps):
        result = lack_of_fit_battery(_data(100, 1000 + seed), formula, parent, alpha=alpha)
        warnings += result.warning
        for component in result.components:
            raw[component.name].append(component.p_value)
    rate = warnings / reps
    # Holm is conservative up to dependence; exact binomial 99.9% upper band
    assert 0.005 <= rate <= 0.10
    for name, values in raw.items():
        assert stats.kstest(values, "uniform").pvalue > 0.001, name


@pytest.mark.parametrize(
    ("kwargs", "component"),
    [
        ({"quad": 0.3}, "mean_curvature_M"),
        ({"interaction": 0.6}, "mean_interaction_AM"),
        ({"y_sd_a": 1.0}, "variance_BP"),
    ],
)
def test_power_against_outcome_departures(kwargs, component):
    rejections = 0
    for seed in range(20):
        result = lack_of_fit_battery(_data(250, 5000 + seed, **kwargs), OUTCOME, "M")
        rejections += _components(result)[component].adjusted_p_value < 0.05
    assert rejections >= 18
