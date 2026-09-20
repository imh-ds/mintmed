"""Contract and oracle tests for structural-equation mediation fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from mintmed.simulation import SimulationFixture, analytic_effects, sample_fixture
from mintmed.spec import Family


FIXTURE_NAMES = (
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


def test_public_fixture_contract_and_copy_semantics() -> None:
    fixture = sample_fixture("linear", 20, np.random.default_rng(7))

    assert isinstance(fixture, SimulationFixture)
    assert fixture.name == "linear"
    assert tuple(fixture.data.columns) == ("A", "M", "Y")
    assert fixture.truth == (0.62, 0.20, 0.42)
    assert fixture.truth_method == "closed_form"
    assert fixture.spec.canonical_json()

    with pytest.raises(TypeError):
        fixture.metadata["new_key"] = True  # type: ignore[index]


def test_unknown_name_and_invalid_size_do_not_consume_rng() -> None:
    for call in (
        lambda rng: sample_fixture("not_registered", 20, rng),
        lambda rng: sample_fixture("linear", 1, rng),
        lambda rng: sample_fixture("linear", True, rng),
        lambda rng: sample_fixture("linear", 10.5, rng),
    ):
        rng = np.random.default_rng(11)
        before = rng.bit_generator.state
        with pytest.raises(ValueError):
            call(rng)
        assert rng.bit_generator.state == before


def test_audited_truths_are_pinned() -> None:
    expected = {
        "linear": (0.62, 0.20, 0.42),
        "quadratic_b": (0.445, 0.20, 0.245),
        "cancellation": (0.0, -1.0, 1.0),
        "interaction": (0.90, 0.20, 0.70),
    }
    for name, truth in expected.items():
        np.testing.assert_allclose(analytic_effects(name), truth, rtol=0, atol=1e-12)

    k = 0.8 / np.sqrt(2)
    np.testing.assert_allclose(
        analytic_effects("ushape_a"),
        (0.2 + 0.6 * k, 0.2, 0.6 * k),
        rtol=0,
        atol=1e-12,
    )


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_every_fixture_has_a_complete_compiled_spec(name: str) -> None:
    fixture = sample_fixture(name, 50, np.random.default_rng(100))

    assert fixture.name == name
    assert len(fixture.truth) == 3
    assert fixture.spec.node_by_response
    assert tuple(fixture.spec.scientific.mediator_order) == tuple(
        variable.name for variable in fixture.spec.mediators
    )
    assert set(fixture.spec.node_by_response) == {
        variable.name for variable in (*fixture.spec.mediators, fixture.spec.outcome)
    }
    assert fixture.spec.canonical_json() == fixture.spec.canonical_json()


def test_interaction_and_quadratic_terms_are_explicit() -> None:
    interaction = sample_fixture("interaction", 30, np.random.default_rng(3))
    outcome_interactions = interaction.spec.node_by_response["Y"].interactions
    assert {(item.left, item.right) for item in outcome_interactions} == {("A", "M")}

    ushape = sample_fixture("ushape_a", 30, np.random.default_rng(3))
    mediator_terms = ushape.spec.node_by_response["M"].terms
    assert any(term.variable == "A" and term.kind.value == "quadratic" for term in mediator_terms)


def test_serial_graphs_preserve_order_and_parents() -> None:
    two = sample_fixture("serial_two", 40, np.random.default_rng(2))
    assert two.spec.scientific.arrangement == "sequential"
    assert two.spec.scientific.mediator_order == ("M1", "M2")
    assert two.spec.scientific.edges == (
        ("A", "M1"),
        ("A", "M2"),
        ("M1", "M2"),
        ("A", "Y"),
        ("M1", "Y"),
        ("M2", "Y"),
    )

    three = sample_fixture("serial_three", 40, np.random.default_rng(2))
    assert three.spec.scientific.mediator_order == ("M1", "M2", "M3")
    assert set(three.spec.scientific.edges) == {
        ("A", "M1"),
        ("A", "M2"),
        ("M1", "M2"),
        ("A", "M3"),
        ("M1", "M3"),
        ("M2", "M3"),
        ("A", "Y"),
        ("M1", "Y"),
        ("M2", "Y"),
        ("M3", "Y"),
    }


def test_parallel_correlation_is_data_dependence_not_a_scientific_edge() -> None:
    fixture = sample_fixture("parallel_correlated", 4000, np.random.default_rng(44))
    data = fixture.data
    design = np.column_stack([np.ones(len(data)), data["A"].to_numpy()])

    def residual(values: np.ndarray) -> np.ndarray:
        coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
        return values - design @ coefficients

    residuals = np.column_stack(
        [residual(data["M1"].to_numpy()), residual(data["M2"].to_numpy())]
    )
    assert abs(np.corrcoef(residuals.T)[0, 1] - 0.65) < 0.08
    assert ("M1", "M2") not in fixture.spec.scientific.edges
    assert ("M2", "M1") not in fixture.spec.scientific.edges
    assert fixture.metadata["rho"] == 0.65


def test_binary_columns_are_exactly_binary() -> None:
    binary_fixtures = (
        "binary_two_mediators",
        "binary_mediator_gaussian_outcome",
        "mixed_binary_serial",
        "four_mediator_mixed",
        "sparse_events",
    )
    for name in binary_fixtures:
        fixture = sample_fixture(name, 100, np.random.default_rng(101))
        for variable in fixture.spec.mediators + (fixture.spec.outcome,):
            if variable.observed_type == "binary":
                assert set(fixture.data[variable.name].unique()) <= {0.0, 1.0}


def test_binary_enumeration_truth_is_not_a_sample_average() -> None:
    fixture = sample_fixture("binary_two_mediators", 100, np.random.default_rng(8))

    def population_mean(a: float, b: float) -> float:
        p1 = expit(-0.4 + 0.8 * b)
        total = 0.0
        for m1 in (0.0, 1.0):
            p_m1 = p1 if m1 else 1.0 - p1
            p2 = expit(-0.2 + 0.5 * b + 0.7 * m1)
            for m2 in (0.0, 1.0):
                p_m2 = p2 if m2 else 1.0 - p2
                total += p_m1 * p_m2 * expit(-0.5 + 0.2 * a + 0.4 * m1 + 0.6 * m2)
        return total

    expected = (
        population_mean(1, 1) - population_mean(0, 0),
        population_mean(1, 0) - population_mean(0, 0),
        population_mean(1, 1) - population_mean(1, 0),
    )
    np.testing.assert_allclose(fixture.truth, expected, rtol=0, atol=1e-12)
    assert fixture.truth_method == "exact_enumeration"


def test_mixed_quadrature_and_moderator_truth_metadata() -> None:
    mixed = sample_fixture("mixed_binary_serial", 60, np.random.default_rng(5))
    assert mixed.truth_method == "gauss_hermite_64"
    assert mixed.metadata["quadrature_order"] == 64

    moderated = sample_fixture("moderated_serial", 60, np.random.default_rng(5))
    assert moderated.spec.contrast.moderator_values == {"W": 0.0}
    assert len(moderated.metadata["truth_by_moderator"]) == 2
    assert moderated.metadata["truth_by_moderator"][0][0] == 0.0
    np.testing.assert_allclose(moderated.truth, moderated.metadata["truth_by_moderator"][0][1])


def test_four_mediator_fixture_is_mixed_and_ordered() -> None:
    fixture = sample_fixture("four_mediator_mixed", 50, np.random.default_rng(12))

    assert tuple(fixture.data.columns) == ("A", "M1", "M2", "M3", "M4", "Y")
    assert fixture.spec.scientific.mediator_order == ("M1", "M2", "M3", "M4")
    assert fixture.spec.node_by_response["M3"].family is Family.BERNOULLI
    assert fixture.spec.node_by_response["M1"].family is Family.GAUSSIAN
    assert ("M1", "M3") not in fixture.spec.scientific.edges
    assert ("M2", "M3") not in fixture.spec.scientific.edges
    assert fixture.metadata["mediator_count"] == 4


def test_stress_fixtures_preserve_declared_edge_conditions() -> None:
    tied = sample_fixture("tied_score", 100, np.random.default_rng(9))
    assert len(np.unique(tied.data["A"])) == 3
    assert tuple(tied.metadata["tie_values"]) == (0.0, 1.0, 2.0)

    missing = sample_fixture("missingness", 50, np.random.default_rng(9))
    assert missing.spec.missing == "complete_case"
    assert missing.data["M"].isna().sum() == len(range(0, 50, 7))
    assert missing.data["Y"].isna().sum() == len(range(0, 50, 11))
    assert tuple(missing.metadata["missing_columns"]) == ("M", "Y")

    opposing = sample_fixture("opposing_paths", 40, np.random.default_rng(9))
    np.testing.assert_allclose(opposing.truth, (0.0, -1.5, 1.5), rtol=0, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_same_injected_seed_reproduces_every_fixture(name: str) -> None:
    first = sample_fixture(name, 50, np.random.default_rng(2026))
    second = sample_fixture(name, 50, np.random.default_rng(2026))

    pd.testing.assert_frame_equal(first.data, second.data)
    assert first.spec.canonical_json() == second.spec.canonical_json()
    assert first.truth == second.truth
    assert first.truth_method == second.truth_method
    assert first.metadata == second.metadata


def test_generation_does_not_use_global_numpy_rng() -> None:
    np.random.seed(1)
    first = sample_fixture("serial_three", 50, np.random.default_rng(77))
    np.random.seed(999)
    second = sample_fixture("serial_three", 50, np.random.default_rng(77))

    pd.testing.assert_frame_equal(first.data, second.data)
    assert first.spec.canonical_json() == second.spec.canonical_json()


def test_truth_is_independent_of_fixture_data_mutation() -> None:
    fixture = sample_fixture("linear", 20, np.random.default_rng(13))
    before = fixture.data.copy(deep=True)
    fixture.data.loc[:, "Y"] = 999.0

    assert analytic_effects("linear") == (0.62, 0.20, 0.42)
    pd.testing.assert_frame_equal(fixture.data.drop(columns="Y"), before.drop(columns="Y"))


def test_simulation_module_has_no_estimator_or_selection_dependencies() -> None:
    module_path = Path(__file__).parents[2] / "src" / "mintmed" / "simulation" / "mediation.py"
    source = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "mintmed.models",
        "mintmed.gformula",
        "statsmodels",
        "sklearn",
        "g_computation",
    ):
        assert forbidden not in source


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_all_fixtures_support_small_and_validation_sample_sizes(name: str) -> None:
    for n in (2, 50, 100, 200, 400):
        fixture = sample_fixture(name, n, np.random.default_rng(n))
        assert len(fixture.data) == n
