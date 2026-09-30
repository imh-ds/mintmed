from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from mintmed.api import analyze_mediation
from mintmed.experiments import diagnostic_mechanisms as dm
from mintmed.experiments.diagnostic_mechanisms import (
    MECHANISMS,
    SAMPLE_SIZES,
    dataset_seed,
    generate,
    mintmed_spec,
    monte_carlo_truth,
)

EXPECTED_CATEGORIES = {
    "N1_linear": "effect_correct_null",
    "N2_curved_declared": "effect_correct_null",
    "N3_ties": "effect_correct_null",
    "N4_heavy_tail": "effect_correct_null",
    "A1_c_only": "attribution_null",
    "V1_outcome_variance": "density_only",
    "E1_omitted_quadratic": "effect_relevant",
    "E2_omitted_interaction": "effect_relevant",
    "E3_mediator_variance": "effect_relevant",
}


def test_mechanism_ids_and_categories():
    assert tuple(MECHANISMS) == tuple(EXPECTED_CATEGORIES)
    assert {k: m.category for k, m in MECHANISMS.items()} == EXPECTED_CATEGORIES
    assert SAMPLE_SIZES == (100, 250, 500)
    codes = [m.code for m in MECHANISMS.values()]
    assert len(set(codes)) == len(codes)


def test_mechanism_contract_fields():
    for mech in MECHANISMS.values():
        assert dataclasses.is_dataclass(mech)
        with pytest.raises(dataclasses.FrozenInstanceError):
            mech.id = "x"  # type: ignore[misc]
        assert mech.outcome_tested_parent == "M"
        assert mech.mediator_tested_parent == "A"
        assert mech.outcome_formula.startswith("Y ~ ")
        assert mech.mediator_formula == "M ~ A + C"
        assert set(mech.truth) == {"TE", "PNDE", "TNIE"}
        assert mech.truth["TE"] == pytest.approx(mech.truth["PNDE"] + mech.truth["TNIE"], abs=1e-12)
        assert mech.outcome_sd > 0


@pytest.mark.parametrize("mechanism_id", list(MECHANISMS))
def test_column_contract(mechanism_id):
    data = generate(mechanism_id, 250, 7)
    assert list(data.columns) == ["A", "M", "Y", "C"]
    assert all(data[c].dtype == np.float64 for c in data.columns)
    assert len(data) == 250
    assert set(np.unique(data["A"])) <= {0.0, 1.0}
    assert np.isfinite(data.to_numpy()).all()


def test_n3_uses_seven_point_scores():
    data = generate("N3_ties", 2000, 3)
    for column in ("M", "Y"):
        values = set(np.unique(data[column]))
        assert values <= {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0}
        assert len(values) >= 6
    np.testing.assert_array_equal(
        dm.score7(np.array([-10.0, 0.25, 0.25 + 0.374, 0.25 + 0.376, 10.0]), 0.25, 0.75),
        [1.0, 4.0, 4.0, 5.0, 7.0],
    )


def test_generate_is_deterministic_for_int_and_seed_sequence():
    first = generate("E2_omitted_interaction", 100, 11)
    pd.testing.assert_frame_equal(first, generate("E2_omitted_interaction", 100, 11))
    seq = dataset_seed(20261001, "E2_omitted_interaction", 100, 4)
    pd.testing.assert_frame_equal(
        generate("E2_omitted_interaction", 100, seq),
        generate("E2_omitted_interaction", 100, dataset_seed(20261001, "E2_omitted_interaction", 100, 4)),
    )
    assert not first.equals(generate("E2_omitted_interaction", 100, 12))


def test_dataset_seed_is_stable_and_distinct():
    seq = dataset_seed(20261001, "N1_linear", 100, 0)
    assert isinstance(seq, np.random.SeedSequence)
    # Frozen value: a change here means the seed stream changed.
    assert tuple(seq.entropy) == (20261001, 1800, 1, 100, 0)
    states = {
        tuple(dataset_seed(master, mid, n, r).generate_state(2))
        for master in (20261001, 20261002)
        for mid in MECHANISMS
        for n in SAMPLE_SIZES
        for r in range(3)
    }
    assert len(states) == 2 * len(MECHANISMS) * len(SAMPLE_SIZES) * 3
    with pytest.raises(ValueError):
        dataset_seed(1, "not_a_mechanism", 100, 0)


def test_closed_form_truths():
    assert MECHANISMS["N1_linear"].truth == pytest.approx({"TE": 0.45, "PNDE": 0.2, "TNIE": 0.25})
    assert MECHANISMS["N2_curved_declared"].truth["TNIE"] == pytest.approx(0.25 * 1.25)
    assert MECHANISMS["E1_omitted_quadratic"].truth["TNIE"] == pytest.approx(0.30)
    assert MECHANISMS["E2_omitted_interaction"].truth["TNIE"] == pytest.approx(0.45)
    assert MECHANISMS["E3_mediator_variance"].truth["TNIE"] == pytest.approx(0.125 * (1.25 + 0.8))


def test_n3_quadrature_is_converged():
    assert dm._n3_truth(64) == pytest.approx(dm._n3_truth(32), abs=1e-10)


@pytest.mark.parametrize(
    "mechanism_id",
    ["N2_curved_declared", "N3_ties", "E1_omitted_quadratic", "E2_omitted_interaction", "E3_mediator_variance"],
)
def test_truth_matches_large_sample_monte_carlo(mechanism_id):
    mc = monte_carlo_truth(mechanism_id, 400_000, seed=20260930)
    truth = MECHANISMS[mechanism_id].truth
    for name in ("TE", "PNDE", "TNIE"):
        assert abs(mc[name] - truth[name]) <= 4.0 * mc[f"{name}_se"] + 1e-4, name


@pytest.mark.parametrize("mechanism_id", list(MECHANISMS))
def test_base_formulas_fit_with_statsmodels(mechanism_id):
    mech = MECHANISMS[mechanism_id]
    data = generate(mechanism_id, 100, 5)
    outcome = smf.ols(mech.outcome_formula, data=data).fit()
    mediator = smf.ols(mech.mediator_formula, data=data).fit()
    assert np.isfinite(outcome.params).all() and np.isfinite(mediator.params).all()
    assert any(mech.outcome_tested_parent in name for name in outcome.model.exog_names)
    assert mech.mediator_tested_parent in mediator.model.exog_names


@pytest.mark.parametrize("mechanism_id", ["N1_linear", "N2_curved_declared", "E3_mediator_variance"])
def test_mintmed_spec_gives_point_estimates_only(mechanism_id):
    result = analyze_mediation(generate(mechanism_id, 250, 9), mintmed_spec(mechanism_id))
    estimates = {effect.name: effect.estimate for effect in result.effects}
    assert {"TE", "PNDE", "TNIE"} <= set(estimates)
    assert all(np.isfinite(estimates[name]) for name in ("TE", "PNDE", "TNIE"))
    assert result.bootstrap is None


def test_mintmed_design_matches_patsy_base_formula():
    """Mintmed's fitted outcome coefficients equal OLS on the patsy base formula."""

    from mintmed.gformula import fit_system
    from mintmed.spec import estimate_plan

    for mechanism_id in ("N1_linear", "N2_curved_declared"):
        data = generate(mechanism_id, 250, 13)
        spec = mintmed_spec(mechanism_id)
        fitted = fit_system(data, estimate_plan(data, spec))
        ols = smf.ols(MECHANISMS[mechanism_id].outcome_formula, data=data).fit()
        node = next(node for node in fitted.nodes if node.response == "Y")
        mintmed_params = np.sort(np.asarray(node.coefficients, dtype=float))
        np.testing.assert_allclose(mintmed_params, np.sort(ols.params.to_numpy()), rtol=1e-8, atol=1e-10)
