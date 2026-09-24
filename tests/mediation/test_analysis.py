"""Contract tests for the public mediation analysis API."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect

import numpy as np
import pytest

import mintmed
from mintmed.simulation import sample_fixture
from mintmed.types import AnalysisStatus, BootstrapResult, EffectEstimate


def _fixture(name: str = "linear", *, n: int = 80, bootstrap: int = 0):
    fixture = sample_fixture(name, n, np.random.default_rng(20261111 + n))
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            bootstrap=bootstrap,
            integration_tolerance=1.0,
        ),
    )
    return fixture.data, spec


def test_public_package_exports_analysis_entry_points() -> None:
    assert callable(mintmed.analyze_mediation)
    assert callable(mintmed.compile_template)
    assert callable(mintmed.estimate_plan)
    assert callable(mintmed.load_model_spec)
    assert mintmed.MediationResult.__name__ == "MediationResult"
    assert list(inspect.signature(mintmed.analyze_mediation).parameters) == ["data", "spec"]


def test_linear_analysis_returns_named_immutable_point_result() -> None:
    data, spec = _fixture(n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert isinstance(result, mintmed.MediationResult)
    assert tuple(effect.name for effect in result.effects) == ("TE", "PNDE", "TNIE")
    assert all(effect.units == "outcome_units" for effect in result.effects)
    assert result.bootstrap is None
    assert result.diagnostics["overall_status"] == "point_only"
    with pytest.raises(TypeError):
        result.diagnostics["overall_status"] = "complete"
    with pytest.raises(FrozenInstanceError):
        result.effects += (result.effects[0],)


def test_linear_result_contains_auditable_hashes_and_provenance() -> None:
    data, spec = _fixture()

    first = mintmed.analyze_mediation(data, spec)
    second = mintmed.analyze_mediation(data, spec)

    assert first.specification_hash == second.specification_hash
    assert first.analysis_hash == second.analysis_hash
    assert first.provenance == second.provenance
    assert first.provenance["mintmed_version"] == mintmed.__version__
    assert first.provenance["specification_hash"] == first.specification_hash
    assert first.provenance["analysis_hash"] == first.analysis_hash
    serialized = repr(first.diagnostics) + repr(first.provenance)
    assert "C:\\Users\\" not in serialized
    assert "row_values" not in serialized


def test_wrong_public_input_types_are_programmer_errors() -> None:
    data, spec = _fixture()

    with pytest.raises(TypeError, match="data must be a pandas DataFrame"):
        mintmed.analyze_mediation(data.to_dict(), spec)
    with pytest.raises(TypeError, match="spec must be a ModelSpec"):
        mintmed.analyze_mediation(data, spec.to_canonical_dict())


def test_diagnostics_assembly_copies_plan_fit_and_integration_contracts() -> None:
    from mintmed.diagnostics import assemble_diagnostics
    from mintmed.gformula import fit_system
    from mintmed.spec import estimate_plan

    data, spec = _fixture(n=80)
    plan = estimate_plan(data, spec)
    fitted = fit_system(data, plan)

    diagnostics = assemble_diagnostics(
        plan,
        fitted,
        overall_status="point_only",
    )

    assert set(
        (
            "overall_status",
            "rows",
            "missing",
            "participant_id",
            "support",
            "binary_counts",
            "scientific",
            "nodes",
            "integration",
            "bootstrap",
            "moderation",
            "warnings",
            "assumptions",
            "exclusions",
            "error",
            "stage",
        )
    ).issubset(diagnostics)
    assert diagnostics["overall_status"] == "point_only"
    assert diagnostics["rows"] == plan.diagnostics["rows"]
    assert diagnostics["scientific"]["factorization_order"] == ["M"]
    assert diagnostics["nodes"][0]["response"] == "M"
    assert diagnostics["nodes"][0]["parameter_count"] == fitted.nodes[0].parameter_count
    assert diagnostics["integration"]["method"] == fitted.integration_method
    assert diagnostics["integration"]["accepted_draw_budget"] == fitted.draw_budget
    assert diagnostics["bootstrap"]["status"] == "not_requested"
    assert any("observed-variable" in item for item in diagnostics["assumptions"])


def test_diagnostics_assembly_preserves_bootstrap_failures_and_intervals() -> None:
    from mintmed.diagnostics import assemble_diagnostics
    from mintmed.gformula import fit_system
    from mintmed.spec import estimate_plan

    data, spec = _fixture(n=80)
    plan = estimate_plan(data, spec)
    fitted = fit_system(data, plan)
    bootstrap = BootstrapResult(
        requested=4,
        attempted=4,
        successful=3,
        failed=1,
        intervals=(
            EffectEstimate(
                name="TE",
                estimate=0.3,
                lower=None,
                upper=None,
                status=AnalysisStatus.INTERVAL_UNAVAILABLE,
                reason="bootstrap_failure_threshold",
            ),
        ),
        status=AnalysisStatus.INTERVAL_UNAVAILABLE,
        failure_counts={"fit_failed": 1},
        metadata={"eligible": False},
    )

    diagnostics = assemble_diagnostics(
        plan,
        fitted,
        bootstrap=bootstrap,
        overall_status="point_only",
    )

    assert diagnostics["bootstrap"]["requested"] == 4
    assert diagnostics["bootstrap"]["successful"] == 3
    assert diagnostics["bootstrap"]["failed"] == 1
    assert diagnostics["bootstrap"]["failure_counts"] == {"fit_failed": 1}
    assert diagnostics["bootstrap"]["intervals"][0]["interval_available"] is False


def test_binary_analysis_reports_probability_units_and_event_counts() -> None:
    data, spec = _fixture("binary_two_mediators", n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert all(effect.units == "probability_difference" for effect in result.effects)
    assert result.diagnostics["scientific"]["units"] == "probability_difference"
    assert result.diagnostics["binary_counts"]["Y"]["events"] > 0
    assert result.diagnostics["binary_counts"]["Y"]["non_events"] > 0
    assert result.diagnostics["nodes"][-1]["events"] == result.diagnostics["binary_counts"]["Y"]["events"]


def test_moderated_analysis_preserves_declared_standardized_contrasts() -> None:
    data, spec = _fixture("moderated_serial", n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["moderation"]["requested"] is True
    assert result.diagnostics["moderation"]["requested_values"] == {"W": [0.0, 1.0]}
    assert result.diagnostics["moderation"]["status"] == "ok"
    assert tuple(
        (contrast["moderator"], contrast["value"])
        for contrast in result.diagnostics["moderation"]["contrasts"]
    ) == (("W", 0.0), ("W", 1.0))


def test_parallel_attribution_unavailability_does_not_remove_primary_effects() -> None:
    data, spec = _fixture("serial_two", n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert tuple(effect.name for effect in result.effects) == ("TE", "PNDE", "TNIE")
    assert result.contributions is not None
    assert result.contributions.available is False
    assert result.contributions.reason_code == "contribution_nonparallel"
    assert result.diagnostics["overall_status"] == "complete_with_warnings"


def test_bootstrap_intervals_are_attached_to_the_public_result() -> None:
    data, spec = _fixture(n=120, bootstrap=2)

    result = mintmed.analyze_mediation(data, spec)

    assert result.bootstrap is not None
    assert result.bootstrap.requested == 2
    assert result.bootstrap.attempted == 2
    assert result.bootstrap.successful == 2
    assert result.bootstrap.failed == 0
    assert result.bootstrap.status is AnalysisStatus.OK
    assert all(interval.interval_available for interval in result.bootstrap.intervals[:3])
    assert result.diagnostics["overall_status"] == "complete"


def test_four_mediator_analysis_records_factorization_and_budget() -> None:
    data, spec = _fixture("four_mediator_mixed", n=100)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["scientific"]["factorization_order"] == ["M1", "M2", "M3", "M4"]
    assert result.diagnostics["integration"]["accepted_draw_budget"] >= 0
    assert result.diagnostics["integration"]["method"] in {
        "sobol_blocked",
        "exact_binary_mediators",
        "gaussian_linear_exact",
    }
