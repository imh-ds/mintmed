"""Typed validation errors shared by model-plan compilation and data preflight."""

from __future__ import annotations

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


__all__ = [
    "DataValidationError",
    "PlanValidationError",
    "UnsupportedAnalysisError",
]
