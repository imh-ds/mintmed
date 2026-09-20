"""Typed validation errors shared by model-plan compilation and data preflight."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .types import AnalysisStatus, Issue


class PlanValidationError(ValueError):
    """Base error with a stable code and location for expected plan failures."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")

    def to_issue(self, *, node: str | None = None) -> Issue:
        """Convert the expected failure into the shared diagnostic vocabulary."""

        return Issue(
            code=self.code,
            message=str(self),
            status=AnalysisStatus.UNSUPPORTED,
            node=node,
        )


class DataValidationError(PlanValidationError):
    """The observed frame cannot satisfy the declared analysis contract."""


class UnsupportedAnalysisError(PlanValidationError):
    """The declared analysis is outside the supported data or counterfactual scope."""


class NodeFitError(PlanValidationError):
    """A compiled node cannot produce a valid frozen design or fit."""

    def __init__(
        self,
        *,
        code: str,
        response: str,
        message: str,
        variable: str | None = None,
        columns: tuple[str, ...] = (),
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(code, f"nodes.{response}", message)
        self.response = response
        self.variable = variable
        self.columns = tuple(columns)
        self.details = MappingProxyType(dict(details or {}))

    def to_issue(self, *, node: str | None = None) -> Issue:
        """Convert the fit failure into the shared fit-failed status."""

        return Issue(
            code=self.code,
            message=str(self),
            status=AnalysisStatus.FIT_FAILED,
            node=node or self.response,
        )


__all__ = [
    "DataValidationError",
    "NodeFitError",
    "PlanValidationError",
    "UnsupportedAnalysisError",
]
