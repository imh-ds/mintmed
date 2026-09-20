"""Conditional Gaussian and Bernoulli node contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd

from .design import FrozenDesign
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

    from types import MappingProxyType

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


class GaussianNode:
    """Placeholder concrete node filled by the Gaussian implementation step."""


class BernoulliNode:
    """Placeholder concrete node filled by the Bernoulli implementation step."""


def fit_node(data: pd.DataFrame, node: CompiledNodePlan) -> FittedNode:
    """Fit one conditional node; implementation follows in Task 6 commits."""

    raise NotImplementedError


__all__ = [
    "BernoulliNode",
    "FittedNode",
    "GaussianNode",
    "NodeFitDiagnostics",
    "fit_node",
]
