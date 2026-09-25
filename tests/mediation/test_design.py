"""Contract tests for frozen Patsy design matrices."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Mapping

import numpy as np
import pandas as pd
import pytest

import mintmed.design as design_module
from mintmed.design import (
    FrozenDesign,
    NodeFitError,
    fit_design,
    transform_design,
)
from mintmed.spec import (
    CompiledNodePlan,
    Family,
    InteractionSpec,
    TermKind,
    TermSpec,
)


def make_node(
    *,
    terms: tuple[TermSpec, ...],
    interactions: tuple[InteractionSpec, ...] = (),
    category_levels: Mapping[str, tuple[Any, ...]] | None = None,
    response: str = "outcome",
    intercept: bool = True,
    factorization_predictors: tuple[str, ...] | None = None,
) -> CompiledNodePlan:
    variables = tuple(term.variable for term in terms)
    interaction_variables = tuple(
        variable
        for interaction in interactions
        for variable in (interaction.left, interaction.right)
    )
    predictors = factorization_predictors or tuple(
        dict.fromkeys(variables + interaction_variables)
    )
    return CompiledNodePlan(
        response=response,
        family=Family.GAUSSIAN,
        terms=terms,
        interactions=interactions,
        scientific_parents=(),
        factorization_predictors=predictors,
        intercept=intercept,
        category_levels=category_levels or {},
    )


def test_design_module_exposes_frozen_design_contract() -> None:
    assert callable(fit_design)
    assert issubclass(NodeFitError, ValueError)
    assert {field.name for field in fields(FrozenDesign)} == {
        "response",
        "family",
        "formula",
        "design_info",
        "columns",
        "matrix",
        "rank",
        "term_metadata",
        "interactions",
        "category_levels",
        "n_rows",
    }


def test_fit_design_builds_simple_intercept_and_linear_matrix() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))
    data = pd.DataFrame({"x": [0.0, 1.0, 2.0]})

    design = fit_design(data, node)

    assert design.response == "outcome"
    assert design.columns == ("Intercept", 'Q("x")')
    assert design.matrix.shape == (3, 2)
    assert design.rank == 2
    assert design.n_rows == 3
    np.testing.assert_allclose(design.matrix[:, 0], 1.0)
    np.testing.assert_allclose(design.matrix[:, 1], data["x"])


def test_frozen_design_matrix_cannot_be_mutated() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))
    design = fit_design(pd.DataFrame({"x": [0.0, 1.0, 2.0]}), node)

    assert design.matrix.flags.writeable is False
    with pytest.raises(ValueError):
        design.matrix[0, 0] = 99.0
    with pytest.raises((AttributeError, TypeError)):
        design.columns = ("changed",)


def test_fit_design_rejects_non_dataframe_input() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))

    with pytest.raises(NodeFitError) as error:
        fit_design([{"x": 1.0}], node)  # type: ignore[arg-type]

    assert error.value.code == "invalid_data"
    assert error.value.response == "outcome"


def test_fit_design_reports_missing_required_column() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))

    with pytest.raises(NodeFitError) as error:
        fit_design(pd.DataFrame({"other": [1.0, 2.0]}), node)

    assert error.value.code == "missing_columns"
    assert error.value.variable == "x"


def test_structured_terms_render_declared_expressions() -> None:
    node = make_node(
        terms=(
            TermSpec("linear", TermKind.LINEAR),
            TermSpec("quadratic", TermKind.QUADRATIC),
            TermSpec("condition", TermKind.CATEGORICAL),
        ),
        category_levels={"condition": (0, 1)},
    )
    data = pd.DataFrame(
        {
            "linear": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "quadratic": [1.0, 0.0, 2.0, 1.5, 3.0, 2.5],
            "condition": [0, 1, 0, 1, 0, 1],
        }
    )

    design = fit_design(data, node)

    assert 'Q("linear")' in design.formula
    assert 'I(Q("quadratic") ** 2)' in design.formula
    assert 'C(Q("condition"), levels=[0, 1])' in design.formula
    assert [term.variable for term in design.term_metadata] == [
        "linear",
        "quadratic",
        "condition",
    ]


def test_no_intercept_design_has_no_intercept_column() -> None:
    node = make_node(
        terms=(TermSpec("x", TermKind.LINEAR),),
        intercept=False,
    )

    design = fit_design(pd.DataFrame({"x": [0.0, 1.0, 2.0]}), node)

    assert design.formula.startswith("0 + ")
    assert "Intercept" not in design.columns


def test_variable_names_are_quoted_as_patsy_values() -> None:
    variable = "dose + age"
    node = make_node(terms=(TermSpec(variable, TermKind.LINEAR),))

    design = fit_design(pd.DataFrame({variable: [0.0, 1.0, 2.0]}), node)

    assert f'Q("{variable}")' in design.formula
    assert design.columns == ("Intercept", f'Q("{variable}")')


def test_declared_interaction_is_present_after_main_effects() -> None:
    node = make_node(
        terms=(
            TermSpec("exposure", TermKind.LINEAR),
            TermSpec("mediator", TermKind.LINEAR),
        ),
        interactions=(InteractionSpec("exposure", "mediator"),),
    )
    data = pd.DataFrame(
        {
            "exposure": [0.0, 1.0, 2.0, 0.5, 1.5, 2.5],
            "mediator": [0.0, 2.0, 1.0, 3.0, 0.5, 2.5],
        }
    )

    design = fit_design(data, node)

    assert design.formula.index(":") > design.formula.index('Q("mediator")')
    assert sum(":" in column for column in design.columns) == 1


def test_categorical_interaction_design_is_constructible() -> None:
    node = make_node(
        terms=(
            TermSpec("exposure", TermKind.CATEGORICAL),
            TermSpec("moderator", TermKind.CATEGORICAL),
        ),
        interactions=(InteractionSpec("moderator", "exposure"),),
        category_levels={"exposure": (0, 1), "moderator": (0, 1)},
    )
    data = pd.DataFrame(
        {
            "exposure": [0, 0, 1, 1, 0, 0, 1, 1],
            "moderator": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    design = fit_design(data, node)

    assert design.formula.count("C(") == 4
    assert sum(":" in column for column in design.columns) == 1


def test_spline_design_uses_frozen_columns_for_transform() -> None:
    node = make_node(terms=(TermSpec("time", TermKind.NATURAL_SPLINE, df=3),))
    data = pd.DataFrame({"time": np.arange(10, dtype=float)})
    counterfactual = pd.DataFrame({"time": [1.5, 3.5, 7.5]})

    design = fit_design(data, node)
    transformed = transform_design(design, counterfactual)

    assert transformed.columns.tolist() == list(design.columns)
    assert transformed.shape[1] == design.matrix.shape[1]
    assert np.isfinite(transformed.to_numpy()).all()


def test_transform_design_uses_design_info_without_refitting(monkeypatch) -> None:
    node = make_node(terms=(TermSpec("time", TermKind.NATURAL_SPLINE, df=3),))
    design = fit_design(
        pd.DataFrame({"time": np.arange(10, dtype=float)}),
        node,
    )

    def fail_if_refit(*args, **kwargs):
        raise AssertionError("transform must use DesignInfo, not dmatrix")

    monkeypatch.setattr(design_module.patsy, "dmatrix", fail_if_refit)

    transformed = transform_design(design, pd.DataFrame({"time": [2.5, 6.5]}))

    assert transformed.columns.tolist() == list(design.columns)


def test_exposure_replacement_updates_main_and_interaction_columns() -> None:
    node = make_node(
        terms=(
            TermSpec("exposure", TermKind.LINEAR),
            TermSpec("mediator", TermKind.LINEAR),
        ),
        interactions=(InteractionSpec("exposure", "mediator"),),
    )
    fit_frame = pd.DataFrame(
        {
            "exposure": [0.0, 1.0, 2.0, 0.5, 1.5, 2.5],
            "mediator": [0.0, 2.0, 1.0, 3.0, 0.5, 2.5],
        }
    )
    original = fit_frame.copy(deep=True)
    changed = fit_frame.assign(exposure=fit_frame["exposure"] + 10.0)

    design = fit_design(fit_frame, node)
    before = transform_design(design, fit_frame)
    after = transform_design(design, changed)
    exposure_column = 'Q("exposure")'
    interaction_column = next(column for column in design.columns if ":" in column)

    assert after.columns.tolist() == before.columns.tolist()
    assert not np.array_equal(before[exposure_column], after[exposure_column])
    assert not np.array_equal(before[interaction_column], after[interaction_column])
    assert np.array_equal(before['Q("mediator")'], after['Q("mediator")'])
    pd.testing.assert_frame_equal(fit_frame, original)


def test_moderator_replacement_updates_moderator_interaction_columns() -> None:
    node = make_node(
        terms=(
            TermSpec("exposure", TermKind.LINEAR),
            TermSpec("moderator", TermKind.LINEAR),
        ),
        interactions=(InteractionSpec("exposure", "moderator"),),
    )
    frame = pd.DataFrame(
        {
            "exposure": [0.0, 1.0, 2.0, 0.5, 1.5, 2.5],
            "moderator": [0.0, 2.0, 1.0, 3.0, 0.5, 2.5],
        }
    )
    changed = frame.assign(moderator=frame["moderator"] + 5.0)

    design = fit_design(frame, node)
    before = transform_design(design, frame)
    after = transform_design(design, changed)
    interaction_column = next(column for column in design.columns if ":" in column)

    assert after.columns.tolist() == before.columns.tolist()
    assert not np.array_equal(before['Q("moderator")'], after['Q("moderator")'])
    assert not np.array_equal(before[interaction_column], after[interaction_column])
    assert np.array_equal(before['Q("exposure")'], after['Q("exposure")'])


def test_quadratic_replacement_rebuilds_square_without_overwriting_linear() -> None:
    node = make_node(
        terms=(
            TermSpec("age_linear", TermKind.LINEAR),
            TermSpec("age_squared_source", TermKind.QUADRATIC),
        )
    )
    frame = pd.DataFrame(
        {
            "age_linear": [0.0, 1.0, 2.0, 3.0],
            "age_squared_source": [1.0, 2.0, 3.0, 4.0],
        }
    )
    changed = frame.assign(age_squared_source=[4.0, 5.0, 6.0, 7.0])

    design = fit_design(frame, node)
    before = transform_design(design, frame)
    after = transform_design(design, changed)
    square_column = next(column for column in design.columns if "** 2" in column)

    assert np.array_equal(before['Q("age_linear")'], after['Q("age_linear")'])
    assert not np.array_equal(before[square_column], after[square_column])
    assert changed["age_squared_source"].tolist() == [4.0, 5.0, 6.0, 7.0]


def test_frozen_categorical_levels_are_stable_and_unseen_values_are_typed() -> None:
    node = make_node(
        terms=(
            TermSpec("condition", TermKind.CATEGORICAL),
            TermSpec("x", TermKind.LINEAR),
        ),
        category_levels={"condition": (0, 1)},
    )
    frame = pd.DataFrame(
        {
            "condition": [0, 1, 0, 1],
            "x": [0.0, 1.0, 2.0, 3.0],
        }
    )
    design = fit_design(frame, node)

    only_one_level = transform_design(
        design,
        pd.DataFrame({"condition": [1, 1], "x": [4.0, 5.0]}),
    )
    assert design.category_levels["condition"] == (0, 1)
    assert only_one_level.columns.tolist() == list(design.columns)

    with pytest.raises(NodeFitError) as error:
        transform_design(
            design,
            pd.DataFrame({"condition": [2], "x": [4.0]}),
        )

    assert error.value.code == "unseen_category"
    assert error.value.variable == "condition"


def test_category_missing_from_fit_raises_rank_deficient() -> None:
    node = make_node(
        terms=(
            TermSpec("condition", TermKind.CATEGORICAL),
            TermSpec("x", TermKind.LINEAR),
        ),
        category_levels={"condition": (0, 1)},
    )

    with pytest.raises(NodeFitError) as error:
        fit_design(
            pd.DataFrame({"condition": [0, 0, 0], "x": [0.0, 1.0, 2.0]}),
            node,
        )

    assert error.value.code == "rank_deficient"
    assert node.response in error.value.message
    assert "Intercept" in error.value.columns


def test_constant_linear_term_raises_rank_deficient_with_columns() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))

    with pytest.raises(NodeFitError) as error:
        fit_design(pd.DataFrame({"x": [1.0, 1.0, 1.0]}), node)

    assert error.value.code == "rank_deficient"
    assert node.response in error.value.message
    assert error.value.columns == ("Intercept", 'Q("x")')


def test_transform_design_rejects_missing_columns() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))
    design = fit_design(pd.DataFrame({"x": [0.0, 1.0, 2.0]}), node)

    with pytest.raises(NodeFitError) as error:
        transform_design(design, pd.DataFrame({"other": [1.0]}))

    assert error.value.code == "missing_columns"
    assert error.value.variable == "x"


def test_transform_patsy_failure_includes_variable_context(monkeypatch) -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))
    design = fit_design(pd.DataFrame({"x": [0.0, 1.0, 2.0]}), node)

    def fail_transform(*args, **kwargs):
        raise design_module.patsy.PatsyError('failed while evaluating Q("x")')

    monkeypatch.setattr(
        design_module.patsy,
        "build_design_matrices",
        fail_transform,
    )

    with pytest.raises(NodeFitError) as error:
        transform_design(design, pd.DataFrame({"x": [3.0]}))

    assert error.value.code == "transform_failed"
    assert error.value.response == "outcome"
    assert error.value.variable == "x"


def test_transform_design_rejects_nonfinite_transformed_values() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))
    design = fit_design(pd.DataFrame({"x": [0.0, 1.0, 2.0]}), node)

    with pytest.raises(NodeFitError) as error:
        transform_design(design, pd.DataFrame({"x": [np.inf]}))

    assert error.value.code == "nonfinite_design"


def test_empty_fit_frame_is_rejected() -> None:
    node = make_node(terms=(TermSpec("x", TermKind.LINEAR),))

    with pytest.raises(NodeFitError) as error:
        fit_design(pd.DataFrame({"x": []}), node)

    assert error.value.code == "empty_design"
