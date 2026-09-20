"""Contract tests for compiled mediation plans and data preflight."""

from __future__ import annotations

from mintmed.spec import (
    AnalysisPlan,
    CompiledNodePlan,
    DataValidationError,
    UnsupportedAnalysisError,
    estimate_plan,
)


def test_task4_public_plan_contract_is_importable() -> None:
    assert AnalysisPlan is not None
    assert CompiledNodePlan is not None
    assert DataValidationError is not None
    assert UnsupportedAnalysisError is not None
    assert estimate_plan is not None
