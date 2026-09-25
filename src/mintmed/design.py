"""Frozen Patsy design matrices for compiled mediation nodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
import patsy

from .diagnostics import NodeFitError
from .spec import CompiledNodePlan, Family, InteractionSpec, TermKind, TermSpec


_PATSY_NAMESPACE = {
    "Q": patsy.builtins.Q,
    "_mintmed_categorical": patsy.builtins.C,
    "I": patsy.builtins.I,
    "cr": patsy.builtins.cr,
}


@dataclass(frozen=True, slots=True)
class DesignTerm:
    """Generated expression metadata for one declared main-effect term."""

    variable: str
    kind: TermKind
    expression: str


@dataclass(frozen=True, slots=True)
class FrozenDesign:
    """Fit-time design matrix and the metadata required to transform it."""

    response: str
    family: Family
    formula: str
    design_info: patsy.DesignInfo
    columns: tuple[str, ...]
    matrix: np.ndarray
    rank: int
    term_metadata: tuple[DesignTerm, ...]
    interactions: tuple[InteractionSpec, ...]
    category_levels: Mapping[str, tuple[Any, ...]]
    n_rows: int

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=float)
        if matrix.ndim != 2:
            raise ValueError("FrozenDesign.matrix must be two-dimensional")
        matrix = np.array(matrix, dtype=float, copy=True, order="C")
        columns = tuple(str(column) for column in self.columns)
        if matrix.shape != (self.n_rows, len(columns)):
            raise ValueError(
                "FrozenDesign matrix shape must match n_rows and columns"
            )
        matrix.setflags(write=False)
        object.__setattr__(self, "matrix", matrix)
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "term_metadata", tuple(self.term_metadata))
        object.__setattr__(self, "interactions", tuple(self.interactions))
        object.__setattr__(
            self,
            "category_levels",
            MappingProxyType(
                {
                    name: tuple(levels)
                    for name, levels in self.category_levels.items()
                }
            ),
        )


class _FormulaConstructionError(ValueError):
    """Internal structured-term error with its offending variable."""

    def __init__(self, message: str, *, variable: str | None = None) -> None:
        super().__init__(message)
        self.variable = variable


def _patsy_eval_environment() -> patsy.EvalEnvironment:
    """Return an explicit environment for generated Patsy expressions."""

    return patsy.EvalEnvironment.capture(0).with_outer_namespace(
        _PATSY_NAMESPACE
    )


def _quote_variable(variable: str) -> str:
    """Quote one DataFrame column name as a Patsy ``Q`` expression."""

    return f"Q({json.dumps(variable)})"


def _render_levels(levels: tuple[Any, ...]) -> str:
    """Render declared scalar category levels as a safe Python literal."""

    normalized: list[Any] = []
    for level in levels:
        if isinstance(level, np.generic):
            level = level.item()
        if level is not None and not isinstance(level, (str, int, float, bool)):
            raise ValueError("category levels must be scalar values")
        if isinstance(level, float) and not np.isfinite(level):
            raise ValueError("category levels must be finite")
        normalized.append(level)
    return repr(normalized)


def _term_expression(
    term: TermSpec,
    category_levels: Mapping[str, tuple[Any, ...]],
) -> str:
    """Generate one main-effect expression from one structured term."""

    variable = term.variable
    quoted = _quote_variable(variable)
    try:
        kind = TermKind(term.kind)
    except (TypeError, ValueError) as exc:
        raise _FormulaConstructionError(
            f"unsupported term kind for {variable!r}", variable=variable
        ) from exc

    if kind is TermKind.LINEAR:
        return quoted
    if kind is TermKind.QUADRATIC:
        return f"I({quoted} ** 2)"
    if kind is TermKind.NATURAL_SPLINE:
        if isinstance(term.df, bool) or not isinstance(term.df, int) or term.df <= 0:
            raise _FormulaConstructionError(
                f"natural spline term {variable!r} requires a positive integer df",
                variable=variable,
            )
        return f'cr({quoted}, df={term.df}, constraints="center")'
    if kind is TermKind.CATEGORICAL:
        if variable not in category_levels:
            raise _FormulaConstructionError(
                f"categorical term {variable!r} has no declared levels",
                variable=variable,
            )
        levels = tuple(category_levels[variable])
        if not levels:
            raise _FormulaConstructionError(
                f"categorical term {variable!r} has no declared levels",
                variable=variable,
            )
        try:
            rendered_levels = _render_levels(levels)
        except ValueError as exc:
            raise _FormulaConstructionError(str(exc), variable=variable) from exc
        return f"_mintmed_categorical({quoted}, levels={rendered_levels})"
    raise _FormulaConstructionError(
        f"unsupported term kind for {variable!r}", variable=variable
    )


def _build_formula(
    node: CompiledNodePlan,
) -> tuple[str, tuple[DesignTerm, ...]]:
    """Build deterministic formula text and metadata from a compiled node."""

    expressions: list[str] = []
    metadata: list[DesignTerm] = []
    expression_by_variable: dict[str, str] = {}
    for term in node.terms:
        if term.variable in expression_by_variable:
            raise _FormulaConstructionError(
                f"duplicate term variable {term.variable!r}",
                variable=term.variable,
            )
        expression = _term_expression(term, node.category_levels)
        expression_by_variable[term.variable] = expression
        expressions.append(expression)
        metadata.append(DesignTerm(term.variable, TermKind(term.kind), expression))

    interaction_expressions: list[str] = []
    for interaction in node.interactions:
        try:
            left = expression_by_variable[interaction.left]
            right = expression_by_variable[interaction.right]
        except KeyError as exc:
            missing = str(exc.args[0])
            raise _FormulaConstructionError(
                f"interaction references undeclared term {missing!r}",
                variable=missing,
            ) from exc
        interaction_expressions.append(f"({left}):({right})")

    intercept = "1" if node.intercept else "0"
    formula = " + ".join([intercept, *expressions, *interaction_expressions])
    return formula, tuple(metadata)


def _required_columns(node: CompiledNodePlan) -> tuple[str, ...]:
    """Return all variables needed to evaluate a compiled node formula."""

    values = list(node.factorization_predictors)
    values.extend(term.variable for term in node.terms)
    values.extend(
        variable
        for interaction in node.interactions
        for variable in (interaction.left, interaction.right)
    )
    return tuple(dict.fromkeys(values))


def _required_design_columns(design: FrozenDesign) -> tuple[str, ...]:
    """Return all variables needed to evaluate a frozen design."""

    values = [term.variable for term in design.term_metadata]
    values.extend(
        variable
        for interaction in design.interactions
        for variable in (interaction.left, interaction.right)
    )
    return tuple(dict.fromkeys(values))


def _missing_columns(data: pd.DataFrame, required: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(column for column in required if column not in data.columns)


def _error_variable(message: str, required: tuple[str, ...]) -> str | None:
    """Find a required variable named in an expected Patsy error message."""

    for variable in required:
        if variable in message or _quote_variable(variable) in message:
            return variable
    return required[0] if len(required) == 1 else None


def _fit_error(
    *,
    code: str,
    response: str,
    message: str,
    variable: str | None = None,
    columns: tuple[str, ...] = (),
) -> NodeFitError:
    return NodeFitError(
        code=code,
        response=response,
        message=message,
        variable=variable,
        columns=columns,
    )


def _check_finite(
    matrix: np.ndarray,
    *,
    response: str,
    columns: tuple[str, ...],
) -> None:
    if not np.isfinite(matrix).all():
        raise _fit_error(
            code="nonfinite_design",
            response=response,
            columns=columns,
            message="design matrix contains nonfinite values",
        )


def fit_design(data: pd.DataFrame, node: CompiledNodePlan) -> FrozenDesign:
    """Fit and freeze one compiled node's Patsy predictor design."""

    if not isinstance(data, pd.DataFrame):
        raise _fit_error(
            code="invalid_data",
            response=node.response,
            message="design data must be a pandas DataFrame",
        )
    if data.empty:
        raise _fit_error(
            code="empty_design",
            response=node.response,
            message="design data must contain at least one row",
        )

    required = _required_columns(node)
    missing = _missing_columns(data, required)
    if missing:
        raise _fit_error(
            code="missing_columns",
            response=node.response,
            variable=missing[0],
            message=f"missing required design columns: {', '.join(missing)}",
        )

    try:
        formula, term_metadata = _build_formula(node)
    except _FormulaConstructionError as exc:
        raise _fit_error(
            code="formula_error",
            response=node.response,
            variable=exc.variable,
            message=str(exc),
        ) from exc

    try:
        matrix_frame = patsy.dmatrix(
            formula,
            data,
            return_type="dataframe",
            NA_action="raise",
            eval_env=_patsy_eval_environment(),
        )
    except (patsy.PatsyError, KeyError, TypeError, ValueError) as exc:
        raise _fit_error(
            code="formula_error",
            response=node.response,
            message="Patsy could not construct the declared design",
        ) from exc

    columns = tuple(str(column) for column in matrix_frame.columns)
    try:
        matrix = matrix_frame.to_numpy(dtype=float, copy=True)
    except (TypeError, ValueError) as exc:
        raise _fit_error(
            code="formula_error",
            response=node.response,
            columns=columns,
            message="Patsy design matrix is not numeric",
        ) from exc
    _check_finite(matrix, response=node.response, columns=columns)

    rank = int(np.linalg.matrix_rank(matrix))
    if rank != len(columns):
        raise _fit_error(
            code="rank_deficient",
            response=node.response,
            columns=columns,
            message=(
                f"{node.response}: rank {rank} is less than "
                f"{len(columns)} design columns {columns!r}"
            ),
        )

    return FrozenDesign(
        response=node.response,
        family=node.family,
        formula=formula,
        design_info=matrix_frame.design_info,
        columns=columns,
        matrix=matrix,
        rank=rank,
        term_metadata=term_metadata,
        interactions=tuple(node.interactions),
        category_levels={
            name: tuple(levels)
            for name, levels in node.category_levels.items()
        },
        n_rows=len(data),
    )


def _is_missing_scalar(value: Any) -> bool:
    missing = pd.isna(value)
    return isinstance(missing, (bool, np.bool_)) and bool(missing)


def _matches_level(value: Any, level: Any) -> bool:
    try:
        result = value == level
    except (TypeError, ValueError):
        return False
    if result is pd.NA:
        return False
    if isinstance(result, (bool, np.bool_)):
        return bool(result)
    return False


def _check_frozen_categories(design: FrozenDesign, data: pd.DataFrame) -> None:
    for variable, levels in design.category_levels.items():
        if variable not in data.columns:
            continue
        for value in data[variable].tolist():
            if _is_missing_scalar(value):
                continue
            if not any(_matches_level(value, level) for level in levels):
                raise _fit_error(
                    code="unseen_category",
                    response=design.response,
                    variable=variable,
                    message=(
                        f"{variable} contains a value outside its frozen "
                        "category levels"
                    ),
                )


def _fast_linear_transform(
    design: FrozenDesign,
    data: pd.DataFrame,
) -> pd.DataFrame | None:
    """Transform a frozen all-linear design without rebuilding Patsy matrices.

    A design containing only quoted linear main effects has no fit-time state
    beyond its column order and intercept.  Reconstructing that matrix
    directly avoids repeatedly asking Patsy to evaluate the same expression
    during large Monte Carlo or bootstrap workloads.  Return ``None`` for any
    design whose metadata is not sufficient to prove that this shortcut is
    exact; the caller then uses the general frozen ``DesignInfo`` path.
    """

    if design.interactions or design.category_levels:
        return None
    if any(term.kind is not TermKind.LINEAR for term in design.term_metadata):
        return None

    expected_columns = tuple(
        (["Intercept"] if design.columns and design.columns[0] == "Intercept" else [])
        + [term.expression for term in design.term_metadata]
    )
    if design.columns != expected_columns:
        return None

    values: list[np.ndarray] = []
    if design.columns and design.columns[0] == "Intercept":
        values.append(np.ones(len(data), dtype=float))
    try:
        values.extend(
            data[term.variable].to_numpy(dtype=float, copy=False)
            for term in design.term_metadata
        )
        matrix = np.column_stack(values)
    except (TypeError, ValueError):
        return None
    return pd.DataFrame(matrix, columns=design.columns, index=data.index)


def transform_design(
    design: FrozenDesign,
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Transform data through the exact frozen design representation."""

    if not isinstance(data, pd.DataFrame):
        raise _fit_error(
            code="invalid_data",
            response=design.response,
            message="design data must be a pandas DataFrame",
        )
    if data.empty:
        raise _fit_error(
            code="empty_design",
            response=design.response,
            message="design data must contain at least one row",
        )

    required = _required_design_columns(design)
    missing = _missing_columns(data, required)
    if missing:
        raise _fit_error(
            code="missing_columns",
            response=design.response,
            variable=missing[0],
            message=f"missing required design columns: {', '.join(missing)}",
        )
    _check_frozen_categories(design, data)

    transformed = _fast_linear_transform(design, data)
    if transformed is None:
        try:
            transformed = patsy.build_design_matrices(
                [design.design_info],
                data,
                return_type="dataframe",
                NA_action="raise",
            )[0]
        except (patsy.PatsyError, KeyError, TypeError, ValueError) as exc:
            raise _fit_error(
                code="transform_failed",
                response=design.response,
                variable=_error_variable(str(exc), required),
                message="Patsy could not transform the frozen design",
            ) from exc

    actual_columns = tuple(str(column) for column in transformed.columns)
    if actual_columns != design.columns:
        raise _fit_error(
            code="column_mismatch",
            response=design.response,
            columns=actual_columns,
            message=(
                f"frozen design expected {design.columns!r}, "
                f"received {actual_columns!r}"
            ),
        )
    try:
        transformed_values = transformed.to_numpy(dtype=float, copy=False)
    except (TypeError, ValueError) as exc:
        raise _fit_error(
            code="transform_failed",
            response=design.response,
            columns=actual_columns,
            message="frozen design transform is not numeric",
        ) from exc
    _check_finite(
        transformed_values,
        response=design.response,
        columns=actual_columns,
    )
    return transformed.copy()


__all__ = [
    "DesignTerm",
    "FrozenDesign",
    "NodeFitError",
    "fit_design",
    "transform_design",
]
