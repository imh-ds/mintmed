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
    assert result.diagnostics["moderation"]["requested_values"] == {"W": (0, 1)}
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

    assert result.diagnostics["scientific"]["factorization_order"] == ("M1", "M2", "M3", "M4")
    assert result.diagnostics["integration"]["accepted_draw_budget"] >= 0
    assert result.diagnostics["integration"]["method"] in {
        "sobol_blocked",
        "exact_binary_mediators",
        "gaussian_linear_exact",
    }


def test_invalid_data_returns_typed_result_without_fitting() -> None:
    data, spec = _fixture(n=120)

    result = mintmed.analyze_mediation(data.drop(columns=["Y"]), spec)

    assert result.status is AnalysisStatus.UNSUPPORTED
    assert result.diagnostics["overall_status"] == "invalid_data"
    assert result.diagnostics["error"]["code"] == "missing_columns"
    assert result.diagnostics["error"]["path"] == "data.columns"
    assert result.effects == ()
    assert result.bootstrap is None


def test_invalid_specification_returns_canonical_hash_and_location() -> None:
    data, spec = _fixture(n=120)
    invalid = replace(spec, missing="invalid_policy")

    result = mintmed.analyze_mediation(data, invalid)

    assert result.status is AnalysisStatus.UNSUPPORTED
    assert result.diagnostics["overall_status"] == "invalid_specification"
    assert result.diagnostics["error"]["code"] == "invalid_plan_spec"
    assert result.diagnostics["error"]["path"] == "missing"
    assert result.specification_hash
    assert result.analysis_hash == ""


def test_fit_failure_preserves_typed_stage_and_skips_bootstrap(monkeypatch) -> None:
    import mintmed.api as api
    from mintmed.gformula import GFormulaError

    data, spec = _fixture(n=120, bootstrap=2)

    def fail_fit(_data, _plan):
        raise GFormulaError(
            code="rank_deficient",
            status=AnalysisStatus.FIT_FAILED,
            message="test fit failure",
            node="M",
        )

    monkeypatch.setattr(api, "fit_system", fail_fit)
    result = mintmed.analyze_mediation(data, spec)

    assert result.status is AnalysisStatus.FIT_FAILED
    assert result.diagnostics["overall_status"] == "fit_failed"
    assert result.diagnostics["stage"] == "fit"
    assert result.diagnostics["error"]["code"] == "rank_deficient"
    assert result.diagnostics["error"]["node"] == "M"
    assert result.bootstrap is None
    assert result.effects == ()


def test_unresolved_integration_preserves_fitted_diagnostics_without_effects(monkeypatch) -> None:
    import mintmed.api as api
    from dataclasses import replace as dataclass_replace
    from mintmed.gformula import fit_system
    from mintmed.types import Issue
    from mintmed.spec import estimate_plan

    data, spec = _fixture("four_mediator_mixed", n=100)
    real_plan = estimate_plan(data, spec)
    real_fitted = fit_system(data, real_plan)
    unresolved = dataclass_replace(
        real_fitted,
        status=AnalysisStatus.INTEGRATION_FAILED,
        issues=(
            Issue(
                code="integration_unresolved",
                message="test integration failure",
                status=AnalysisStatus.INTEGRATION_FAILED,
                path="integration",
            ),
        ),
    )

    monkeypatch.setattr(api, "fit_system", lambda _data, _plan: unresolved)
    result = mintmed.analyze_mediation(data, spec)

    assert result.status is AnalysisStatus.INTEGRATION_FAILED
    assert result.diagnostics["overall_status"] == "integration_unresolved"
    assert result.diagnostics["stage"] == "integration"
    assert result.diagnostics["integration"]["status"] == "integration_failed"
    assert result.diagnostics["integration"]["issues"][0]["code"] == "integration_unresolved"
    assert result.effects == ()
    assert result.bootstrap is None


def test_incomplete_bootstrap_retains_point_effects_and_failure_counts(monkeypatch) -> None:
    import mintmed.uncertainty as uncertainty

    data, spec = _fixture(n=120, bootstrap=3)

    def interrupt(_data, _plan, _point, _replicate):
        raise TimeoutError("test timeout")

    monkeypatch.setattr(uncertainty, "_run_replicate", interrupt)
    result = mintmed.analyze_mediation(data, spec)

    assert result.effects
    assert result.bootstrap is not None
    assert result.bootstrap.status is AnalysisStatus.INCOMPLETE
    assert result.bootstrap.failure_counts["bootstrap_interrupted"] == 1
    assert result.diagnostics["overall_status"] == "incomplete"
    assert result.diagnostics["bootstrap"]["status"] == "incomplete"


def test_unexpected_programmer_errors_propagate(monkeypatch) -> None:
    import mintmed.api as api

    data, spec = _fixture(n=120)
    monkeypatch.setattr(api, "estimate_plan", lambda _data, _spec: (_ for _ in ()).throw(RuntimeError("bug")))

    with pytest.raises(RuntimeError, match="bug"):
        mintmed.analyze_mediation(data, spec)


def test_nested_result_mappings_are_immutable() -> None:
    data, spec = _fixture(n=120)

    result = mintmed.analyze_mediation(data, spec)

    with pytest.raises(TypeError):
        result.diagnostics["rows"]["retained"] = 0


def test_unsupported_declared_moderator_level_is_visible_as_warning() -> None:
    data, spec = _fixture("moderated_serial", n=120)
    moderator = replace(spec.moderators[0], levels=(0, 1, 2))
    spec = replace(spec, moderators=(moderator,))

    result = mintmed.analyze_mediation(data, spec)

    assert result.effects
    assert result.diagnostics["overall_status"] == "complete_with_warnings"
    assert result.diagnostics["moderation"]["status"] == "unsupported"
    assert result.diagnostics["moderation"]["reason"]
    assert any(item["code"] == "unsupported_extrapolation" for item in result.diagnostics["warnings"])
