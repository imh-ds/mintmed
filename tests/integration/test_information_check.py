"""Residual CMIknn information check (Task 18 Phase 1, information arm, T18-S2)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import integrate, stats

from mintmed.experiments import information_check as ic
from mintmed.experiments.information_check import (
    MIN_STRATUM_SIZE,
    cmi_knn,
    information_check,
    k_cmi_for,
    local_permutation,
)

OUTCOME = "Y ~ A + M + C"


def _data(n: int, seed: int, *, quad: float = 0.0, mediator_interaction: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    A = rng.integers(0, 2, n)
    C = rng.normal(size=n)
    M = 0.5 * A + 0.5 * C + mediator_interaction * A * C + rng.normal(size=n)
    E = rng.normal(size=n)
    Y = 0.3 * A + 0.5 * M + 0.4 * C + quad * M**2 + E
    return pd.DataFrame({"A": A, "M": M, "Y": Y, "C": C, "E": E})


# ---------------------------------------------------------------------------
# Estimator sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rho", [0.0, 0.4, 0.6])
def test_cmi_knn_recovers_gaussian_conditional_mi(rho: float) -> None:
    rng = np.random.default_rng(11)
    n = 1000
    z = rng.normal(size=n)
    x = z + rng.normal(size=n)
    y = z + rho * (x - z) + math.sqrt(1 - rho**2) * rng.normal(size=n)
    truth = -0.5 * math.log(1 - rho**2)  # partial correlation of x and y given z is rho
    for k in (10, 50):
        assert cmi_knn(x, y, z, k) == pytest.approx(truth, abs=0.06)


def test_cmi_knn_is_invariant_to_monotone_marginal_transforms() -> None:
    rng = np.random.default_rng(12)
    z = rng.normal(size=400)
    x = z + rng.normal(size=400)
    y = z + 0.5 * x + rng.normal(size=400)
    base = cmi_knn(x, y, z, 20)
    assert cmi_knn(np.exp(x), y**3, np.arctan(z), 20) == pytest.approx(base, abs=1e-12)


def test_cmi_knn_mixed_binary_recovers_mutual_information() -> None:
    rng = np.random.default_rng(13)
    n, delta = 1000, 1.5
    a = rng.integers(0, 2, n)
    r = delta * a + rng.normal(size=n)
    c = rng.normal(size=n)  # independent of both, so I(r; A | C) = I(r; A)

    def mixture(t: float) -> float:
        p = 0.5 * stats.norm.pdf(t) + 0.5 * stats.norm.pdf(t, loc=delta)
        return -p * math.log(p)

    h_r = integrate.quad(mixture, -10, 12)[0]
    truth = h_r - 0.5 * math.log(2 * math.pi * math.e)
    estimate = cmi_knn(r, a, c, 50, discrete_y=True)
    assert estimate == pytest.approx(truth, abs=0.06)


def test_cmi_knn_keeps_negative_estimates() -> None:
    rng = np.random.default_rng(14)
    values = []
    for _ in range(20):
        x, y, z = rng.normal(size=(3, 120))
        values.append(cmi_knn(x, y, z, 12))
    assert min(values) < 0


def test_ties_are_deterministic_and_finite() -> None:
    rng = np.random.default_rng(15)
    z = rng.normal(size=200)
    x = np.round(z + rng.normal(size=200))
    y = np.round(rng.normal(size=200))
    first = cmi_knn(x, y, z, 5)
    assert math.isfinite(first)
    assert cmi_knn(x, y, z, 5) == first
    # all-discrete columns hit the zero-radius rule and stay finite
    assert math.isfinite(cmi_knn(np.round(x / 3), y, np.round(z), 5))


def test_k_cmi_rule_rounds_half_up_with_floor_of_five() -> None:
    assert k_cmi_for(30, 0.1) == 5
    assert k_cmi_for(125, 0.1) == 13
    assert k_cmi_for(250, 0.1) == 25
    assert k_cmi_for(250, 0.2) == 50


# ---------------------------------------------------------------------------
# Local permutation
# ---------------------------------------------------------------------------


def test_local_permutation_draws_from_conditioning_neighbours() -> None:
    rng = np.random.default_rng(16)
    z = np.sort(rng.normal(size=200))
    neighbours = ic._neighbour_lists(z, 200, 5)
    assert neighbours.shape == (200, 5)
    assert (neighbours[:, 0] == np.arange(200)).mean() > 0.99  # self first
    index = local_permutation(neighbours, 200, np.random.default_rng(1))
    assert all(index[i] in neighbours[i] for i in range(200))
    assert np.unique(index).size >= 180  # without replacement where possible
    assert (index != np.arange(200)).mean() > 0.5
    assert np.array_equal(index, local_permutation(neighbours, 200, np.random.default_rng(1)))
    full = local_permutation(None, 50, np.random.default_rng(2))
    assert np.array_equal(np.sort(full), np.arange(50))


def test_null_permutes_within_both_strata_every_replicate(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, np.ndarray]] = []
    original = ic.local_permutation

    def recording(neighbours, n, rng):
        index = original(neighbours, n, rng)
        calls.append((n, index))
        return index

    monkeypatch.setattr(ic, "local_permutation", recording)
    data = _data(160, 1)
    result = information_check(data, OUTCOME, "M", seed=5, permutations=7)
    sizes = [result.stratum_sizes["0"], result.stratum_sizes["1"]]
    assert len(calls) == 14
    assert [n for n, _ in calls] == sizes * 7
    for n, index in calls:
        assert index.min() >= 0 and index.max() < n
        assert (index != np.arange(n)).any()


def test_weights_are_stratum_shares_frozen_across_the_null(monkeypatch: pytest.MonkeyPatch) -> None:
    def constant(self, y):
        return float(self.n), 0  # T_a = n_a whatever the permutation

    monkeypatch.setattr(ic._CMIStratum, "estimate", constant)
    data = _data(150, 2)
    result = information_check(data, OUTCOME, "M", seed=1, permutations=9)
    n0, n1 = result.stratum_sizes["0"], result.stratum_sizes["1"]
    assert result.n == n0 + n1 == 150
    assert result.weights == {"0": n0 / 150, "1": n1 / 150}
    expected = (n0 * n0 + n1 * n1) / 150
    assert result.statistic == pytest.approx(expected)
    assert result.null_statistics == pytest.approx([expected] * 9)
    assert result.p_value == 1.0


# ---------------------------------------------------------------------------
# information_check behaviour
# ---------------------------------------------------------------------------


def test_outcome_check_result_contract() -> None:
    data = _data(200, 3)
    result = information_check(data, OUTCOME, "M", seed=4, permutations=19)
    assert result.status == "ok" and result.reason is None
    assert set(result.stratum_sizes) == {"0", "1"}
    assert sum(result.stratum_sizes.values()) == 200
    assert result.k_cmi == {a: k_cmi_for(n_a, 0.1) for a, n_a in result.stratum_sizes.items()}
    combined = sum(result.weights[a] * result.stratum_estimates[a] for a in ("0", "1"))
    assert result.statistic == pytest.approx(combined)
    assert len(result.null_statistics) == 19 == result.permutations
    expected_p = (1 + sum(t >= result.statistic for t in result.null_statistics)) / 20
    assert result.p_value == pytest.approx(expected_p)
    assert result.settings["role"] == "primary"
    assert result.settings["target"] == "I(r_Y ; M | A, C)"
    assert result.settings["residuals"] == "cross_fitted"
    assert result.runtime_seconds > 0
    assert set(result.ties["0"]) == {
        "residual_tied_rows",
        "parent_tied_rows",
        "conditioning_tied_rows",
        "zero_radius_points",
    }
    with pytest.raises(Exception):
        result.weights["0"] = 1.0  # type: ignore[index]


def test_determinism_with_seed() -> None:
    data = _data(150, 4)
    first = information_check(data, OUTCOME, "M", seed=9, permutations=19)
    again = information_check(data, OUTCOME, "M", seed=9, permutations=19)
    other = information_check(data, OUTCOME, "M", seed=10, permutations=19)
    assert (first.statistic, first.p_value, first.null_statistics) == (
        again.statistic,
        again.p_value,
        again.null_statistics,
    )
    assert first.null_statistics != other.null_statistics
    assert first.statistic != other.statistic  # different cross-fit folds


def test_in_sample_residuals_sensitivity() -> None:
    data = _data(150, 5)
    result = information_check(data, OUTCOME, "M", seed=9, permutations=9, residuals="in_sample")
    assert result.status == "ok"
    assert result.settings["residuals"] == "in_sample"


def test_negative_statistic_is_not_clipped() -> None:
    negatives = []
    for seed in range(12):
        result = information_check(_data(100, 100 + seed), OUTCOME, "M", seed=seed, permutations=1)
        if result.statistic < 0:
            negatives.append(result)
    assert negatives
    result = negatives[0]
    assert result.statistic == pytest.approx(
        sum(result.weights[a] * result.stratum_estimates[a] for a in result.weights)
    )


def test_unavailable_paths() -> None:
    small = _data(50, 6)
    result = information_check(small, OUTCOME, "M", seed=1)
    assert result.status == "diagnostic_unavailable"
    assert "below 30" in result.reason
    assert math.isnan(result.statistic) and math.isnan(result.p_value)
    assert min(result.stratum_sizes.values()) < MIN_STRATUM_SIZE

    data = _data(200, 7)
    data["C2"] = data["C"] ** 2
    two = information_check(data, "Y ~ A + M + C + C2", "M", conditioning=("C", "C2"), seed=1)
    assert two.status == "diagnostic_unavailable" and "at most one" in two.reason

    one_level = data.assign(A=1)
    single = information_check(one_level, "Y ~ M + C", "M", seed=1)
    assert single.status == "diagnostic_unavailable" and "both levels" in single.reason

    rare = data.copy()
    rare["A"] = (np.arange(200) < 20).astype(int)
    mediator = information_check(rare, "M ~ A + C", "A", stratify_by=None, seed=1)
    assert mediator.status == "diagnostic_unavailable"

    with pytest.raises(ValueError):
        information_check(data, OUTCOME, "M", seed=1, residuals="bogus")


def test_unconditional_variant_runs_without_conditioning() -> None:
    result = information_check(_data(120, 8), OUTCOME, "M", conditioning=(), seed=1, permutations=9)
    assert result.status == "ok"
    assert result.settings["target"] == "I(r_Y ; M | A)"


# ---------------------------------------------------------------------------
# Null calibration and power smoke checks (loose; S4 measures calibration)
# ---------------------------------------------------------------------------


def test_true_error_null_is_roughly_uniform() -> None:
    """Observed-variable null (r = true error, independent of M given A, C)."""

    p = np.array(
        [
            information_check(_data(100, 1000 + i), "E ~ 1", "M", seed=i, permutations=39, residuals="in_sample").p_value
            for i in range(100)
        ]
    )
    assert stats.kstest(p, "uniform").pvalue > 0.001
    assert (p <= 0.05).mean() <= 0.12
    assert 0.35 <= p.mean() <= 0.65


def test_fitted_residual_null_does_not_over_reject() -> None:
    """Correct linear outcome model: loose bounds, fitted residuals tend to be conservative."""

    p = np.array(
        [information_check(_data(100, 2000 + i), OUTCOME, "M", seed=i, permutations=39).p_value for i in range(100)]
    )
    assert (p <= 0.05).mean() <= 0.12
    assert (p <= 0.10).mean() <= 0.2
    assert 0.35 <= p.mean() <= 0.7


def test_outcome_check_detects_omitted_quadratic() -> None:
    p = np.array(
        [
            information_check(_data(200, 3000 + i, quad=0.5), OUTCOME, "M", seed=i, permutations=39).p_value
            for i in range(20)
        ]
    )
    assert (p <= 0.05).mean() >= 0.8


def test_mediator_check_is_secondary_and_detects_omitted_interaction() -> None:
    null = information_check(_data(200, 4000), "M ~ A + C", "A", stratify_by=None, seed=1, permutations=19)
    assert null.status == "ok"
    assert null.settings["role"] == "secondary"
    assert null.settings["experimental"] is True
    assert null.settings["tested_parent_kind"] == "binary"
    assert null.settings["target"] == "I(r_M ; A | C)"
    assert null.stratum_sizes == {"all": 200}
    assert null.weights == {"all": 1.0}
    p = np.array(
        [
            information_check(
                _data(200, 5000 + i, mediator_interaction=1.0), "M ~ A + C", "A", stratify_by=None, seed=i, permutations=39
            ).p_value
            for i in range(20)
        ]
    )
    assert (p <= 0.05).mean() >= 0.8
