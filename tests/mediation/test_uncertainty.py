"""Contract tests for full-refit participant-bootstrap uncertainty."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mintmed.effects import natural_effects
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

    assert first.status is AnalysisStatus.WARNING
    assert first.requested == 4
    assert first.attempted == 4
    assert first.successful == 4
    assert first.failed == 0
    assert first.replicates == second.replicates
    assert first.intervals == second.intervals
    assert all(record["status"] == "ok" for record in first.replicates)
    assert all(record["row_seed"] != record["integration_seed"] for record in first.replicates)
    assert all(len(record["row_positions"]) == plan.retained_row_count for record in first.replicates)
    assert all(record["TE"] is not None for record in first.replicates)


@pytest.mark.parametrize(
    ("requested", "successful", "failed", "eligible"),
    ((400, 390, 10, False), (400, 390, 4, True), (400, 389, 11, False), (3, 3, 0, True), (3, 2, 1, False)),
)
def test_interval_eligibility_uses_declared_success_and_failure_rules(
    requested, successful, failed, eligible
):
    from mintmed.uncertainty import _interval_eligibility

    assert _interval_eligibility(requested, successful, failed) is eligible
