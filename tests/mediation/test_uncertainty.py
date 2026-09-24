"""Contract tests for full-refit participant-bootstrap uncertainty."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mintmed.effects import moderator_contrasts, natural_effects, parallel_contributions
from mintmed.gformula import compute_regime_means, fit_system
from mintmed.simulation import sample_fixture
from mintmed.spec import estimate_plan
from mintmed.types import AnalysisStatus, PointAnalysis


def _point_fixture(name: str = "linear", *, n: int = 80, bootstrap: int = 4):
    fixture = sample_fixture(name, n, np.random.default_rng(20260924 + n))
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            bootstrap=bootstrap,
            integration_tolerance=1.0,
        ),
    )
    plan = estimate_plan(fixture.data, spec)
    fitted = fit_system(fixture.data, plan)
    means = compute_regime_means(fixture.data, plan, fitted)
    point = PointAnalysis(
        fitted_system=fitted,
        regime_means=means,
        effects=natural_effects(means),
        draw_budget=fitted.draw_budget,
        metadata={"bootstrap_mode": "quick_diagnostic"},
    )
    return fixture, plan, point


def test_bootstrap_exports_the_baseline_contract():
    from mintmed.uncertainty import bootstrap_analysis

    assert bootstrap_analysis.__name__ == "bootstrap_analysis"


def test_streams_are_replicate_specific_and_independent():
    from mintmed.uncertainty import _stream_seeds

    first = _stream_seeds(20260919, 0)
    second = _stream_seeds(20260919, 1)

    assert first[0] != first[1]
    assert first != second
    assert first == _stream_seeds(20260919, 0)


def test_bootstrap_refits_exact_system_and_repeats_scientific_records():
    from mintmed.uncertainty import bootstrap_analysis

    fixture, plan, point = _point_fixture()
    first = bootstrap_analysis(fixture.data, plan, point)
    second = bootstrap_analysis(fixture.data, plan, point)

    assert first.status is AnalysisStatus.OK
    assert first.requested == 4
    assert first.attempted == 4
    assert first.successful == 4
    assert first.failed == 0
    assert [
        {key: value for key, value in record.items() if key != "runtime_seconds"}
        for record in first.replicates
    ] == [
        {key: value for key, value in record.items() if key != "runtime_seconds"}
        for record in second.replicates
    ]
    assert first.intervals == second.intervals
    assert all(record["status"] == "ok" for record in first.replicates)
    assert all(record["row_seed"] != record["integration_seed"] for record in first.replicates)
    assert all(len(record["row_positions"]) == plan.retained_row_count for record in first.replicates)
    assert all(record["TE"] is not None for record in first.replicates)


def test_bootstrap_recomputes_admissible_parallel_contributions():
    fixture = sample_fixture("parallel_correlated", 100, np.random.default_rng(20261010))
    outcome = replace(fixture.spec.nodes[-1], interactions=())
    spec = replace(
        fixture.spec,
        nodes=(*fixture.spec.nodes[:-1], outcome),
        computation=replace(fixture.spec.computation, bootstrap=2, integration_tolerance=1.0),
    )
    plan = estimate_plan(fixture.data, spec)
    fitted = fit_system(fixture.data, plan)
    assert fitted.draws is not None
    means = compute_regime_means(fixture.data, plan, fitted)
    point_contributions = parallel_contributions(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        means.total_natural_indirect_effect,
    )
    assert point_contributions.available is True
    point = PointAnalysis(
        fitted_system=fitted,
        regime_means=means,
        effects=natural_effects(means),
        contributions=point_contributions,
        draw_budget=fitted.draw_budget,
        metadata={"bootstrap_mode": "quick_diagnostic"},
    )

    from mintmed.uncertainty import bootstrap_analysis

    result = bootstrap_analysis(fixture.data, plan, point)

    assert result.successful == 2
    assert all(record["contribution_available"] is True for record in result.replicates)
    assert all("TNIE_M1" in record and "TNIE_M2" in record for record in result.replicates)
    contribution_intervals = {
        interval.name: interval
        for interval in result.intervals
        if interval.name in {"TNIE_M1", "TNIE_M2"}
    }
    assert set(contribution_intervals) == {"TNIE_M1", "TNIE_M2"}
    assert all(interval.interval_available for interval in contribution_intervals.values())


def test_resampling_preserves_declared_category_schema_with_fresh_local_rows():
    fixture = sample_fixture("binary_two_mediators", 40, np.random.default_rng(20261012))
    plan = estimate_plan(fixture.data, fixture.spec)

    from mintmed.uncertainty import _replicate_identity

    identity, replicate_frame, replicate_plan = _replicate_identity(fixture.data, plan, 0)

    assert list(replicate_frame.index) == list(range(plan.retained_row_count))
    assert len(identity["row_positions"]) == plan.retained_row_count
    assert replicate_plan.retained_row_indices == tuple(range(plan.retained_row_count))
    assert replicate_plan.nodes[0].category_levels["A"] == (0, 1)
    assert replicate_plan.nodes[0].category_levels["M1"] == (0, 1)
    assert replicate_plan.nodes[-1].category_levels["Y"] == (0, 1)


def test_unavailable_parallel_attribution_does_not_fail_primary_bootstrap():
    fixture, plan, point = _point_fixture("serial_two", n=90, bootstrap=2)
    from mintmed.types import ContributionResult

    point = replace(
        point,
        contributions=ContributionResult(
            available=False,
            reason_code="contribution_nonparallel",
            reason="serial mediator structure is not admissible",
        ),
    )

    from mintmed.uncertainty import bootstrap_analysis

    result = bootstrap_analysis(fixture.data, plan, point)

    assert result.successful == 2
    assert result.failed == 0
    assert all(record["status"] == "ok" for record in result.replicates)
    assert all(record["contribution_available"] is False for record in result.replicates)
    assert all(
        record["contribution_reason_code"] == "contribution_nonparallel"
        for record in result.replicates
    )


def test_bootstrap_recomputes_paired_moderator_differences():
    fixture = sample_fixture("moderated_serial", 120, np.random.default_rng(20261011))
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, bootstrap=2, integration_tolerance=1.0),
    )
    plan = estimate_plan(fixture.data, spec)
    fitted = fit_system(fixture.data, plan)
    assert fitted.draws is not None
    means = compute_regime_means(fixture.data, plan, fitted)
    point_moderators = moderator_contrasts(
        fixture.data,
        plan,
        fitted,
        fitted.draws,
        moderator_values={"W": (0.0, 1.0)},
    )
    point = PointAnalysis(
        fitted_system=fitted,
        regime_means=means,
        effects=natural_effects(means),
        moderator_contrasts=point_moderators,
        draw_budget=fitted.draw_budget,
        metadata={"bootstrap_mode": "quick_diagnostic"},
    )

    from mintmed.uncertainty import bootstrap_analysis

    result = bootstrap_analysis(fixture.data, plan, point)

    assert result.successful == 2
    required = {
        "moderator_difference__W__0__TE",
        "moderator_difference__W__0__PNDE",
        "moderator_difference__W__0__TNIE",
        "moderator_difference__W__1__TE",
        "moderator_difference__W__1__PNDE",
        "moderator_difference__W__1__TNIE",
    }
    assert all(required.issubset(record) for record in result.replicates)
    assert all(
        len({record["integration_seed"] for record in result.replicates}) == result.successful
        for record in result.replicates
    )


def _effect_record(value: float, *, status: str = "ok") -> dict[str, object]:
    return {
        "status": status,
        "TE": value,
        "PNDE": value / 2.0,
        "TNIE": value / 2.0,
        "error_code": None if status == "ok" else "fit_failed",
    }


def test_intervals_withhold_when_400_replicates_miss_the_failure_threshold():
    from mintmed.uncertainty import _intervals_from_records

    _fixture, _plan, point = _point_fixture(bootstrap=400)
    records = tuple(
        _effect_record(float(index)) if index < 389 else _effect_record(float(index), status="fit_failed")
        for index in range(400)
    )

    intervals, status, metadata = _intervals_from_records(
        records,
        400,
        point,
        complete=True,
        quick_diagnostic=False,
    )

    assert status is AnalysisStatus.INTERVAL_UNAVAILABLE
    assert metadata["reason"] == "bootstrap_failure_threshold"
    assert all(interval.interval_available is False for interval in intervals)


def test_quick_diagnostic_can_label_a_provisional_interval():
    from mintmed.uncertainty import _intervals_from_records

    _fixture, _plan, point = _point_fixture(bootstrap=3)
    records = (
        _effect_record(1.0),
        _effect_record(2.0),
        _effect_record(3.0, status="fit_failed"),
    )

    intervals, status, metadata = _intervals_from_records(
        records,
        3,
        point,
        complete=True,
        quick_diagnostic=True,
    )

    assert status is AnalysisStatus.WARNING
    assert metadata["provisional"] is True
    assert all(interval.status is AnalysisStatus.WARNING for interval in intervals)
    assert all(interval.reason == "quick_diagnostic_provisional" for interval in intervals)


def test_bootstrap_records_typed_failures_without_retrying_for_a_success_quota(monkeypatch):
    import mintmed.uncertainty as uncertainty
    from mintmed.gformula import GFormulaError

    fixture, plan, point = _point_fixture(bootstrap=3)
    calls: list[int] = []

    def always_fails(_data, _plan, _point, replicate):
        calls.append(replicate)
        raise GFormulaError(
            code="missing_category",
            status=AnalysisStatus.FIT_FAILED,
            message="resampled data omitted a declared category",
        )

    monkeypatch.setattr(uncertainty, "_run_replicate", always_fails)
    result = uncertainty.bootstrap_analysis(fixture.data, plan, point)

    assert calls == [0, 1, 2]
    assert result.attempted == 3
    assert result.successful == 0
    assert result.failed == 3
    assert result.failure_counts["missing_category"] == 3
    assert all(record["error_code"] == "missing_category" for record in result.replicates)


def test_timeout_marks_run_incomplete_and_stops_without_an_interval(monkeypatch):
    import mintmed.uncertainty as uncertainty

    fixture, plan, point = _point_fixture(bootstrap=3)
    real_runner = uncertainty._run_replicate

    def stop_on_second(data, current_plan, current_point, replicate):
        if replicate == 1:
            raise TimeoutError("test timeout")
        return real_runner(data, current_plan, current_point, replicate)

    monkeypatch.setattr(uncertainty, "_run_replicate", stop_on_second)
    result = uncertainty.bootstrap_analysis(fixture.data, plan, point)

    assert result.status is AnalysisStatus.INCOMPLETE
    assert result.attempted == 2
    assert result.successful == 1
    assert result.failed == 0
    assert result.failure_counts["bootstrap_interrupted"] == 1
    assert result.replicates[-1]["status"] == "incomplete"
    assert result.intervals
    assert all(interval.interval_available is False for interval in result.intervals)


def test_keyboard_interrupt_has_the_same_no_retry_contract(monkeypatch):
    import mintmed.uncertainty as uncertainty

    fixture, plan, point = _point_fixture(bootstrap=3)
    real_runner = uncertainty._run_replicate

    def stop_on_second(data, current_plan, current_point, replicate):
        if replicate == 1:
            raise KeyboardInterrupt()
        return real_runner(data, current_plan, current_point, replicate)

    monkeypatch.setattr(uncertainty, "_run_replicate", stop_on_second)
    result = uncertainty.bootstrap_analysis(fixture.data, plan, point)

    assert result.status is AnalysisStatus.INCOMPLETE
    assert result.attempted == 2
    assert result.successful == 1
    assert result.failed == 0
    assert result.replicates[-1]["error_code"] == "bootstrap_interrupted"


@pytest.mark.parametrize(
    ("requested", "successful", "failed", "eligible"),
    ((400, 390, 10, False), (400, 390, 4, True), (400, 389, 11, False), (3, 3, 0, True), (3, 2, 1, False)),
)
def test_interval_eligibility_uses_declared_success_and_failure_rules(
    requested, successful, failed, eligible
):
    from mintmed.uncertainty import _interval_eligibility

    assert _interval_eligibility(requested, successful, failed) is eligible
