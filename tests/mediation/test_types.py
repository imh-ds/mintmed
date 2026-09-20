from dataclasses import FrozenInstanceError
from collections.abc import Mapping

import pytest

from mintmed.types import (
    AnalysisStatus,
    BootstrapResult,
    ContributionResult,
    EffectEstimate,
    Issue,
    MediationResult,
    PointAnalysis,
    RegimeMeans,
)


def test_analysis_status_values_are_stable_lowercase_strings() -> None:
    assert [status.value for status in AnalysisStatus] == [
        "ok",
        "warning",
        "inconclusive",
        "unsupported",
        "fit_failed",
        "integration_failed",
        "interval_unavailable",
        "incomplete",
    ]


def test_regime_means_define_primary_effect_identity() -> None:
    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)

    assert means.total_effect == pytest.approx(0.5)
    assert means.pure_natural_direct_effect == pytest.approx(0.2)
    assert means.total_natural_indirect_effect == pytest.approx(0.3)


def test_effect_estimate_explicitly_withholds_unavailable_interval() -> None:
    effect = EffectEstimate(
        name="TNIE",
        estimate=0.3,
        lower=None,
        upper=None,
        status=AnalysisStatus.INTERVAL_UNAVAILABLE,
        reason="2 of 400 bootstrap refits failed",
    )

    assert effect.interval_available is False
    assert effect.estimate == pytest.approx(0.3)
    assert effect.reason == "2 of 400 bootstrap refits failed"


def test_effect_estimate_preserves_negative_opposing_effects() -> None:
    effect = EffectEstimate(
        name="PNDE",
        estimate=-0.8,
        lower=-1.2,
        upper=-0.2,
        units="outcome_units",
    )

    assert effect.estimate == pytest.approx(-0.8)
    assert effect.lower == pytest.approx(-1.2)
    assert effect.upper == pytest.approx(-0.2)
    assert effect.interval_available is True


def test_issue_records_failed_regime_identity_without_mutating_effects() -> None:
    issue = Issue(
        code="regime_identity",
        message="TE does not equal PNDE plus TNIE within tolerance",
        status=AnalysisStatus.INTEGRATION_FAILED,
        node="outcome",
    )

    assert issue.status is AnalysisStatus.INTEGRATION_FAILED
    assert issue.code == "regime_identity"
    assert issue.node == "outcome"


def test_effect_and_result_objects_are_frozen() -> None:
    effect = EffectEstimate(name="TE", estimate=0.5)
    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)

    with pytest.raises(FrozenInstanceError):
        effect.estimate = 0.8  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        means.mu_00 = 0.0  # type: ignore[misc]


def test_metadata_and_failure_maps_are_read_only_and_not_shared() -> None:
    first = EffectEstimate(name="TE", estimate=0.5)
    second = EffectEstimate(name="TE", estimate=0.5)
    bootstrap = BootstrapResult(
        requested=400,
        attempted=400,
        successful=400,
        failed=0,
        failure_counts={"fit_failed": 0},
    )

    assert first.metadata is not second.metadata
    with pytest.raises(TypeError):
        first.metadata["source"] = "test"  # type: ignore[index]
    with pytest.raises(TypeError):
        bootstrap.failure_counts["fit_failed"] = 1  # type: ignore[index]


def test_result_containers_normalize_sequences_and_nested_mappings() -> None:
    effect = EffectEstimate(name="TNIE", estimate=0.3)
    contribution = ContributionResult(
        available=True,
        contributions={"coping": effect},
    )
    bootstrap = BootstrapResult(
        requested=2,
        attempted=2,
        successful=2,
        failed=0,
        replicates=[{"replicate": 0}, {"replicate": 1}],
        intervals=[effect],
        failure_counts={},
    )
    point = PointAnalysis(
        fitted_system=object(),
        regime_means=RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5),
        effects=[effect],
        contributions=contribution,
        moderator_contrasts=[{"moderator": "W", "value": 1}],
        draw_budget=512,
    )
    result = MediationResult(
        specification_hash="spec-hash",
        analysis_hash="analysis-hash",
        effects=[effect],
        contributions=contribution,
        diagnostics={"rows_used": 100},
        bootstrap=bootstrap,
        provenance={"mintmed_version": "0.1.0"},
    )

    assert isinstance(contribution.contributions, Mapping)
    with pytest.raises(TypeError):
        contribution.contributions["new"] = effect  # type: ignore[index]
    assert isinstance(bootstrap.replicates, tuple)
    assert isinstance(bootstrap.intervals, tuple)
    assert isinstance(point.effects, tuple)
    assert isinstance(point.moderator_contrasts, tuple)
    assert isinstance(result.effects, tuple)
    assert result.bootstrap is bootstrap
    assert result.diagnostics["rows_used"] == 100
