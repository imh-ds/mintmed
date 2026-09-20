"""Contract tests for frozen Patsy design matrices."""

from __future__ import annotations

from dataclasses import fields

import numpy as np
import pandas as pd
import pytest

from mintmed.design import FrozenDesign, NodeFitError, fit_design
from mintmed.spec import CompiledNodePlan, Family, TermKind, TermSpec


def make_node(
    *,
    terms: tuple[TermSpec, ...],
    response: str = "outcome",
    intercept: bool = True,
    factorization_predictors: tuple[str, ...] | None = None,
) -> CompiledNodePlan:
    predictors = factorization_predictors or tuple(term.variable for term in terms)
    return CompiledNodePlan(
        response=response,
        family=Family.GAUSSIAN,
        terms=terms,
        interactions=(),
        scientific_parents=(),
        factorization_predictors=predictors,
        intercept=intercept,
        category_levels={},
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

