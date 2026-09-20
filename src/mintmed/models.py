"""Conditional Gaussian and Bernoulli node contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import warnings
from types import MappingProxyType
from typing import Any, Protocol

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .design import FrozenDesign, fit_design, transform_design
from .diagnostics import NodeFitError
from .spec import CompiledNodePlan, Family
from .types import AnalysisStatus


PredictorInput = pd.DataFrame | np.ndarray
NoiseArray = np.ndarray
SampleSize = int | tuple[int, ...] | None
NoiseSource = np.random.Generator | NoiseArray


@dataclass(frozen=True, slots=True)
class NodeFitDiagnostics:
    """Immutable fit metadata shared by all conditional node families."""

    response: str
    family: Family
    status: AnalysisStatus
    code: str
    message: str
    n_rows: int
    rank: int
    parameter_count: int
    converged: bool
    coefficients_finite: bool
    df_resid: float | None
    sigma: float | None
    log_likelihood: float | None
    deviance: float | None
    events: int | None
    non_events: int | None
    warnings: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", Family(self.family))
        object.__setattr__(self, "status", AnalysisStatus(self.status))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a defensive read-only metadata mapping."""

    return MappingProxyType(dict(value))


class FittedNode(Protocol):
    """Common response-scale interface for fitted conditional nodes."""

    response: str
    family: Family
    design: FrozenDesign
    parameter_count: int
    converged: bool

    def predict_mean(self, predictors: PredictorInput) -> np.ndarray:
        raise NotImplementedError

    def sample(
        self,
        predictors: PredictorInput,
        source: NoiseSource,
        size: SampleSize = None,
    ) -> np.ndarray:
        raise NotImplementedError

    def log_density(
        self,
        predictors: PredictorInput,
        observed: np.ndarray,
    ) -> np.ndarray:
        raise NotImplementedError

    def diagnostics(self) -> NodeFitDiagnostics:
        raise NotImplementedError

    def design_diagnostics(self) -> NodeFitDiagnostics:
        raise NotImplementedError


def _node_error(
    node: CompiledNodePlan | FrozenDesign,
    *,
    code: str,
    message: str,
    variable: str | None = None,
    columns: tuple[str, ...] = (),
    details: Mapping[str, Any] | None = None,
) -> NodeFitError:
    """Build one consistently contextualized node failure."""

    return NodeFitError(
        code=code,
        response=node.response,
        message=message,
        variable=variable,
        columns=columns,
        details=details,
    )


def _training_response(
    data: pd.DataFrame,
    node: CompiledNodePlan,
) -> np.ndarray:
    """Validate and return one finite numeric training response vector."""

    if not isinstance(data, pd.DataFrame):
        raise _node_error(
            node,
            code="invalid_response",
            message="node training data must be a pandas DataFrame",
        )
    if node.response not in data.columns:
        raise _node_error(
            node,
            code="missing_response",
            message=f"training data is missing response {node.response!r}",
            details={"available_columns": tuple(str(column) for column in data.columns)},
        )

    series = data[node.response]
    if not pd.api.types.is_numeric_dtype(series):
        raise _node_error(
            node,
            code="invalid_response",
            message=f"response {node.response!r} must be numeric",
            details={"dtype": str(series.dtype)},
        )
    values = series.to_numpy(dtype=float, copy=True)
    if values.ndim != 1 or values.size == 0:
        raise _node_error(
            node,
            code="invalid_response",
            message="response must be a non-empty one-dimensional vector",
            details={"shape": tuple(values.shape)},
        )
    finite = np.isfinite(values)
    if not finite.all():
        raise _node_error(
            node,
            code="nonfinite_response",
            message=f"response {node.response!r} contains nonfinite values",
            details={
                "nonfinite_count": int((~finite).sum()),
                "n_rows": int(values.size),
            },
        )
    return values


def _fit_frozen_design(
    data: pd.DataFrame,
    node: CompiledNodePlan,
) -> tuple[np.ndarray, FrozenDesign]:
    """Validate response and construct exactly one frozen predictor design."""

    response = _training_response(data, node)
    design = fit_design(data, node)
    matrix = np.asarray(design.matrix, dtype=float)
    parameter_count = matrix.shape[1] if matrix.ndim == 2 else 0
    if matrix.ndim != 2 or matrix.shape[0] != response.size:
        raise _node_error(
            design,
            code="invalid_predictors",
            message="frozen design shape does not match the response",
            columns=design.columns,
            details={
                "response_shape": tuple(response.shape),
                "design_shape": tuple(matrix.shape),
            },
        )
    if not np.isfinite(matrix).all():
        raise _node_error(
            design,
            code="nonfinite_design",
            message="frozen design contains nonfinite values",
            columns=design.columns,
        )
    if design.rank != parameter_count:
        raise _node_error(
            design,
            code="rank_deficient",
            message=(
                f"rank {design.rank} is less than {parameter_count} design columns"
            ),
            columns=design.columns,
            details={
                "rank": design.rank,
                "parameter_count": parameter_count,
                "formula": design.formula,
            },
        )
    return response, design


def _prediction_matrix(
    design: FrozenDesign,
    predictors: PredictorInput,
) -> tuple[np.ndarray, int]:
    """Return a validated matrix in the frozen design column order."""

    if isinstance(predictors, pd.DataFrame):
        try:
            transformed = transform_design(design, predictors)
            matrix = transformed.to_numpy(dtype=float, copy=True)
        except NodeFitError as exc:
            if exc.code == "nonfinite_design":
                raise
            details = dict(exc.details)
            details["original_code"] = exc.code
            details["patsy_message"] = str(exc)
            raise _node_error(
                design,
                code="prediction_failed",
                message="Patsy could not transform the frozen node design",
                variable=exc.variable,
                columns=exc.columns,
                details=details,
            ) from exc
        except (TypeError, ValueError) as exc:
            raise _node_error(
                design,
                code="prediction_failed",
                message="prediction data could not be converted to the frozen design",
                details={"patsy_message": str(exc)},
            ) from exc
    else:
        try:
            matrix = np.asarray(predictors, dtype=float)
        except (TypeError, ValueError) as exc:
            raise _node_error(
                design,
                code="invalid_predictors",
                message="prediction matrix must be numeric",
                columns=design.columns,
                details={"observed_type": type(predictors).__name__},
            ) from exc

    if matrix.ndim != 2 or matrix.shape[1] != len(design.columns):
        observed_shape = tuple(matrix.shape)
        raise _node_error(
            design,
            code="invalid_predictors",
            message=(
                f"prediction matrix must have {len(design.columns)} columns"
            ),
            columns=design.columns,
            details={
                "expected_width": len(design.columns),
                "observed_shape": observed_shape,
            },
        )
    if not np.isfinite(matrix).all():
        raise _node_error(
            design,
            code="nonfinite_design",
            message="prediction matrix contains nonfinite values",
            columns=design.columns,
            details={"observed_shape": tuple(matrix.shape)},
        )
    return matrix, int(matrix.shape[0])


def _noise_shape(
    design: FrozenDesign,
    n_rows: int,
    size: SampleSize,
) -> tuple[int, ...]:
    """Resolve the participant-first sample shape."""

    if size is None:
        return (n_rows,)
    if isinstance(size, bool):
        raise _node_error(
            design,
            code="invalid_noise",
            message="sample size must be an integer or tuple of integers",
            details={"size": size},
        )
    if isinstance(size, int):
        if size < 0:
            raise _node_error(
                design,
                code="invalid_noise",
                message="sample size cannot be negative",
                details={"size": size},
            )
        return (n_rows, size)
    if not isinstance(size, tuple) or not size or size[0] != n_rows:
        raise _node_error(
            design,
            code="invalid_noise",
            message="sample-size tuple must begin with the prediction row count",
            details={"size": size, "n_rows": n_rows},
        )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in size):
        raise _node_error(
            design,
            code="invalid_noise",
            message="sample-size tuple values must be nonnegative integers",
            details={"size": size},
        )
    return size


def _materialize_noise(
    design: FrozenDesign,
    source: NoiseSource,
    n_rows: int,
    size: SampleSize,
    family: Family,
) -> np.ndarray:
    """Validate explicit noise or draw the requested block from a Generator."""

    shape = _noise_shape(design, n_rows, size)
    if isinstance(source, np.random.Generator):
        values = (
            source.normal(size=shape)
            if family is Family.GAUSSIAN
            else source.random(size=shape)
        )
    else:
        try:
            values = np.asarray(source, dtype=float)
        except (TypeError, ValueError) as exc:
            raise _node_error(
                design,
                code="invalid_noise",
                message="noise must be numeric",
                details={"observed_type": type(source).__name__},
            ) from exc
        if size is not None and tuple(values.shape) != shape:
            raise _node_error(
                design,
                code="invalid_noise",
                message="explicit noise shape does not match requested sample size",
                details={"expected_shape": shape, "observed_shape": tuple(values.shape)},
            )

    if values.ndim == 0 or values.ndim < 1 or values.shape[0] != n_rows:
        raise _node_error(
            design,
            code="invalid_noise",
            message="noise must preserve prediction rows as its first dimension",
            details={"expected_first_dimension": n_rows, "observed_shape": tuple(values.shape)},
        )
    if not np.isfinite(values).all():
        raise _node_error(
            design,
            code="invalid_noise",
            message="noise contains nonfinite values",
            details={"observed_shape": tuple(values.shape)},
        )
    if family is Family.BERNOULLI and (np.any(values < 0.0) or np.any(values > 1.0)):
        raise _node_error(
            design,
            code="invalid_noise",
            message="Bernoulli uniform noise must lie in [0, 1]",
            details={"observed_shape": tuple(values.shape)},
        )
    return values


class _NodeOperations:
    """Shared prediction, sampling, and diagnostics behavior."""

    design: FrozenDesign
    family: Family
    response: str
    _fit_diagnostics: NodeFitDiagnostics

    def _predictor_matrix(self, predictors: PredictorInput) -> tuple[np.ndarray, int]:
        return _prediction_matrix(self.design, predictors)

    def diagnostics(self) -> NodeFitDiagnostics:
        return self._fit_diagnostics

    def design_diagnostics(self) -> NodeFitDiagnostics:
        return self._fit_diagnostics


@dataclass(frozen=True, slots=True)
class GaussianNode(_NodeOperations):
    """Fitted Gaussian identity-link conditional node."""

    response: str
    family: Family
    design: FrozenDesign
    coefficients: np.ndarray
    parameter_count: int
    sigma: float
    converged: bool
    _fit_diagnostics: NodeFitDiagnostics = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", Family(self.family))
        coefficients = np.array(self.coefficients, dtype=float, copy=True)
        coefficients.setflags(write=False)
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(self, "parameter_count", int(self.parameter_count))
        object.__setattr__(self, "sigma", float(self.sigma))

    def predict_mean(self, predictors: PredictorInput) -> np.ndarray:
        matrix, _ = self._predictor_matrix(predictors)
        mean = matrix @ self.coefficients
        if mean.ndim != 1 or not np.isfinite(mean).all():
            raise _node_error(
                self.design,
                code="prediction_failed",
                message="Gaussian prediction is not a finite one-dimensional vector",
                columns=self.design.columns,
            )
        return np.asarray(mean, dtype=float)

    def sample(
        self,
        predictors: PredictorInput,
        source: NoiseSource,
        size: SampleSize = None,
    ) -> np.ndarray:
        mean = self.predict_mean(predictors)
        noise = _materialize_noise(
            self.design,
            source,
            len(mean),
            size,
            Family.GAUSSIAN,
        )
        mean_shape = (len(mean),) + (1,) * (noise.ndim - 1)
        return mean.reshape(mean_shape) + self.sigma * noise

    def log_density(
        self,
        predictors: PredictorInput,
        observed: np.ndarray,
    ) -> np.ndarray:
        mean = self.predict_mean(predictors)
        try:
            values = np.asarray(observed, dtype=float)
        except (TypeError, ValueError) as exc:
            raise _node_error(
                self.design,
                code="invalid_observed",
                message="observed Gaussian values must be numeric",
            ) from exc
        if values.shape != mean.shape or not np.isfinite(values).all():
            raise _node_error(
                self.design,
                code="invalid_observed",
                message="observed Gaussian values must be finite and row-aligned",
                details={
                    "expected_shape": tuple(mean.shape),
                    "observed_shape": tuple(values.shape),
                },
            )
        z = (values - mean) / self.sigma
        return -0.5 * (
            z * z + np.log(2.0 * np.pi * self.sigma * self.sigma)
        )


def _fit_gaussian(
    response: np.ndarray,
    design: FrozenDesign,
) -> GaussianNode:
    """Fit and validate one Gaussian OLS result."""

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            result = sm.OLS(response, design.matrix, missing="raise").fit()
        except (TypeError, ValueError, np.linalg.LinAlgError) as exc:
            raise _node_error(
                design,
                code="numerical_overflow",
                message="Statsmodels OLS could not produce a fit",
                columns=design.columns,
                details={"statsmodels_message": str(exc)},
            ) from exc

    warning_text = tuple(str(item.message) for item in captured)
    coefficients = np.asarray(result.params, dtype=float)
    df_resid = float(result.df_resid)
    ssr = float(result.ssr)
    if (
        not np.isfinite(df_resid)
        or df_resid <= 0.0
        or not np.isfinite(ssr)
        or ssr < 0.0
    ):
        raise _node_error(
            design,
            code="invalid_residual_variance",
            message="Gaussian residual variance has invalid residual degrees of freedom",
            columns=design.columns,
            details={
                "ssr": ssr,
                "df_resid": df_resid,
                "parameter_count": len(design.columns),
                "n_rows": design.n_rows,
                "warnings": warning_text,
            },
        )
    sigma_squared = ssr / df_resid
    sigma = float(np.sqrt(sigma_squared))
    if not np.isfinite(sigma_squared) or not np.isfinite(sigma) or sigma <= 0.0:
        raise _node_error(
            design,
            code="invalid_residual_variance",
            message="Gaussian residual variance must be finite and positive",
            columns=design.columns,
            details={
                "ssr": ssr,
                "df_resid": df_resid,
                "sigma_squared": sigma_squared,
                "warnings": warning_text,
            },
        )
    covariance = np.asarray(result.cov_params(), dtype=float)
    if (
        coefficients.shape != (len(design.columns),)
        or not np.isfinite(coefficients).all()
        or not np.isfinite(covariance).all()
    ):
        raise _node_error(
            design,
            code="numerical_overflow",
            message="Gaussian fit contains nonfinite coefficients or covariance",
            columns=design.columns,
            details={"warnings": warning_text},
        )

    log_likelihood = float(result.llf)
    if not np.isfinite(log_likelihood):
        raise _node_error(
            design,
            code="numerical_overflow",
            message="Gaussian fit log likelihood is nonfinite",
            columns=design.columns,
            details={"log_likelihood": log_likelihood, "warnings": warning_text},
        )
    diagnostics = NodeFitDiagnostics(
        response=design.response,
        family=Family.GAUSSIAN,
        status=AnalysisStatus.OK,
        code="ok",
        message=f"Gaussian OLS fit succeeded for {design.response}",
        n_rows=design.n_rows,
        rank=design.rank,
        parameter_count=len(design.columns),
        converged=True,
        coefficients_finite=True,
        df_resid=df_resid,
        sigma=sigma,
        log_likelihood=log_likelihood,
        deviance=None,
        events=None,
        non_events=None,
        warnings=warning_text,
        metadata={
            "formula": design.formula,
            "ssr": ssr,
            "df_model": float(result.df_model),
            "aic": float(result.aic),
            "bic": float(result.bic),
        },
    )
    return GaussianNode(
        response=design.response,
        family=Family.GAUSSIAN,
        design=design,
        coefficients=coefficients,
        parameter_count=len(design.columns),
        sigma=sigma,
        converged=True,
        _fit_diagnostics=diagnostics,
    )


class BernoulliNode:
    """Placeholder concrete node filled by the Bernoulli implementation step."""


def fit_node(data: pd.DataFrame, node: CompiledNodePlan) -> FittedNode:
    """Fit one compiled Gaussian or Bernoulli conditional node."""

    response, design = _fit_frozen_design(data, node)
    if node.family is Family.GAUSSIAN:
        return _fit_gaussian(response, design)
    raise NotImplementedError("Bernoulli fitting is implemented in the next step")


__all__ = [
    "BernoulliNode",
    "FittedNode",
    "GaussianNode",
    "NodeFitDiagnostics",
    "fit_node",
]
