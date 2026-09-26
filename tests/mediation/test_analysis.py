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


def test_bootstrap_reporting_mode_is_preserved_in_provenance() -> None:
    data, spec = _fixture(n=120)
    spec = replace(
        spec,
        computation=replace(spec.computation, bootstrap_mode="quick_diagnostic"),
    )

    result = mintmed.analyze_mediation(data, spec)

    assert result.provenance["bootstrap_mode"] == "quick_diagnostic"


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


def test_quick_diagnostic_intervals_are_attached_as_provisional() -> None:
    data, spec = _fixture(n=120, bootstrap=2)
    spec = replace(spec, computation=replace(spec.computation, bootstrap_mode="quick_diagnostic"))

    result = mintmed.analyze_mediation(data, spec)

    assert result.bootstrap is not None
    assert result.bootstrap.requested == 2
    assert result.bootstrap.attempted == 2
    assert result.bootstrap.successful == 2
    assert result.bootstrap.failed == 0
    assert result.bootstrap.status is AnalysisStatus.WARNING
    assert result.bootstrap.metadata["provisional"] is True
    primary = result.bootstrap.intervals[:3]
    assert all(interval.interval_available for interval in primary)
    assert all(interval.reason == "quick_diagnostic_provisional" for interval in primary)
    assert result.diagnostics["overall_status"] == "complete_with_warnings"


def test_standard_mode_small_bootstrap_reports_no_interval() -> None:
    data, spec = _fixture(n=120, bootstrap=2)

    result = mintmed.analyze_mediation(data, spec)

    assert result.bootstrap is not None
    assert result.bootstrap.successful == 2
    assert result.bootstrap.status is AnalysisStatus.INTERVAL_UNAVAILABLE
    assert result.bootstrap.metadata["reason"] == "bootstrap_too_few_replicates"
    assert all(interval.interval_available is False for interval in result.bootstrap.intervals)
    assert all(effect.estimate is not None for effect in result.effects)
    assert result.diagnostics["overall_status"] == "point_only"


def test_four_mediator_analysis_records_factorization_and_budget() -> None:
    data, spec = _fixture("four_mediator_mixed", n=100)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["scientific"]["factorization_order"] == ("M1", "M2", "M3", "M4")
    assert result.diagnostics["integration"]["accepted_draw_budget"] >= 0
    assert result.diagnostics["integration"]["method"] in {
        "sobol_blocked",
        "exact_binary_mediators",
        "gaussian_linear_exact",
        "gauss_hermite",
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


def test_uncanonicalizable_invalid_specification_uses_empty_hash() -> None:
    data, spec = _fixture(n=120)
    invalid = replace(
        spec,
        contrast=replace(spec.contrast, moderator_values={"unknown": object()}),
    )

    result = mintmed.analyze_mediation(data, invalid)

    assert result.status is AnalysisStatus.UNSUPPORTED
    assert result.diagnostics["overall_status"] == "invalid_specification"
    assert result.specification_hash == ""
    assert result.provenance["specification_hash"] == ""


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


def test_loose_tolerance_cannot_publish_single_draw_contributions() -> None:
    # Audit BUG-01: with integration_tolerance=1.0 the Hermite path used to
    # publish a one-draw contribution far from the joint TNIE.
    fixture = sample_fixture("quadratic_b", 150, np.random.default_rng(20260925))
    spec = replace(
        fixture.spec,
        computation=replace(fixture.spec.computation, bootstrap=0, integration_tolerance=1.0),
    )
    result = mintmed.analyze_mediation(fixture.data, spec)
    assert result.diagnostics["integration"]["method"] == "gauss_hermite"
    tnie = next(effect.estimate for effect in result.effects if effect.name == "TNIE")
    assert result.contributions is not None and result.contributions.available is True
    assert result.contributions.contributions["TNIE_M"].estimate == pytest.approx(tnie, abs=1e-10)


def test_primary_effects_conditional_on_moderators_are_labelled_everywhere() -> None:
    from mintmed.report import effects_rows, render_markdown

    data, spec = _fixture("moderated_serial", n=120)

    result = mintmed.analyze_mediation(data, spec)

    for effect in result.effects:
        assert effect.metadata["moderator_values"] == {"W": 0.0}
        assert effect.metadata["standardization_population"] == "retained_analysis_rows_with_W=0"
    primary_rows = [row for row in effects_rows(result) if row["source"] == "primary"]
    assert primary_rows
    assert all(row["evaluated_at"] == "W=0" for row in primary_rows)
    report = render_markdown(result)
    assert "- Evaluated at moderator values: `W=0`" in report
    assert "not averaged over the observed moderator distribution" in report


def test_unmoderated_primary_effects_have_no_conditioning_label() -> None:
    from mintmed.report import effects_rows, render_markdown

    data, spec = _fixture(n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert all(effect.metadata["moderator_values"] == {} for effect in result.effects)
    assert all(row["evaluated_at"] in (None, "") for row in effects_rows(result))
    assert "Evaluated at moderator values" not in render_markdown(result)


def test_complete_case_report_shows_the_excluded_row_count() -> None:
    from mintmed.report import render_markdown

    data, spec = _fixture(n=120)
    data = data.copy()
    data.loc[data.index[:2], "M"] = np.nan
    data.loc[data.index[5], "Y"] = np.nan
    spec = replace(spec, missing="complete_case")

    result = mintmed.analyze_mediation(data, spec)
    report = render_markdown(result)

    assert result.diagnostics["exclusions"]["excluded_rows"] == 3
    assert "- Excluded rows: 3 (missing values by column:" in report
    assert "M: 2" in report
    assert "Y: 1" in report


def _moderator_difference_rows(result) -> dict[tuple[object, str], dict]:
    from mintmed.report import effects_rows

    return {
        (row["moderator_value"], row["name"]): row
        for row in effects_rows(result)
        if row["source"] == "moderator_difference"
    }


def test_baseline_self_contrast_and_structural_zero_differences_have_no_interval() -> None:
    data, spec = _fixture("moderated_serial", n=120, bootstrap=2)
    spec = replace(spec, computation=replace(spec.computation, bootstrap_mode="quick_diagnostic"))

    result = mintmed.analyze_mediation(data, spec)
    rows = _moderator_difference_rows(result)

    for name in ("TE", "PNDE", "TNIE"):
        baseline_row = rows[(0.0, name)]
        assert baseline_row["reason"] == "baseline_reference"
        assert baseline_row["interval_available"] is False
    # W does not interact with A in the outcome model, so the direct effect
    # cannot differ by W; floating-point noise must not look like evidence.
    pnde = rows[(1.0, "PNDE")]
    assert pnde["estimate"] == 0.0
    assert pnde["reason"] == "structurally_zero"
    assert pnde["interval_available"] is False
    tnie = rows[(1.0, "TNIE")]
    assert tnie["estimate"] != 0.0
    assert tnie["reason"] == "quick_diagnostic_provisional"
    assert tnie["interval_available"] is True


def test_continuous_moderator_is_contrasted_at_declared_evaluation_values() -> None:
    from mintmed.spec import Role, VariableSpec

    data, spec = _fixture("moderated_serial", n=160)
    data = data.copy()
    data["W"] = data["W"] + np.random.default_rng(7).normal(0.0, 0.1, len(data))
    spec = replace(
        spec,
        moderators=(VariableSpec("W", Role.MODERATOR, "continuous"),),
        contrast=replace(spec.contrast, moderator_evaluation={"W": (0.0, 1.0)}),
    )

    result = mintmed.analyze_mediation(data, spec)

    moderation = result.diagnostics["moderation"]
    assert moderation["status"] == "ok"
    assert moderation["requested_values"] == {"W": (0.0, 1.0)}
    assert tuple(contrast["value"] for contrast in moderation["contrasts"]) == (0.0, 1.0)
    rows = _moderator_difference_rows(result)
    assert rows[(1.0, "TNIE")]["estimate"] != 0.0


def test_continuous_moderator_without_evaluation_values_is_not_contrasted() -> None:
    from mintmed.spec import Role, VariableSpec

    data, spec = _fixture("moderated_serial", n=160)
    data = data.copy()
    data["W"] = data["W"] + np.random.default_rng(7).normal(0.0, 0.1, len(data))
    spec = replace(spec, moderators=(VariableSpec("W", Role.MODERATOR, "continuous"),))

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["moderation"]["requested"] is False


def test_invalid_draw_budget_is_reported_as_an_invalid_specification() -> None:
    from mintmed.api import _failure_state
    from mintmed.gformula import GFormulaError

    error = GFormulaError(
        code="invalid_draw_budget",
        status=AnalysisStatus.INTEGRATION_FAILED,
        message="integration_draws must be one of 256, 512, 1024, 2048, or 4096",
    )

    assert _failure_state(error, "point") == "invalid_specification"


def test_point_only_state_no_longer_hides_warnings() -> None:
    # Contribution refused (serial) and intervals withheld (standard mode, 2 replicates).
    data, spec = _fixture("serial_two", n=120, bootstrap=2)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["overall_status"] == "point_only"
    assert result.diagnostics["uncertainty_state"] == "unavailable"
    assert result.diagnostics["warning_state"] == "warnings"


def test_warnings_without_bootstrap_still_say_no_uncertainty_was_computed() -> None:
    data, spec = _fixture("serial_two", n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["overall_status"] == "complete_with_warnings"
    assert result.diagnostics["uncertainty_state"] == "not_requested"
    assert result.diagnostics["warning_state"] == "warnings"


def test_clean_point_analysis_reports_no_warnings_and_no_uncertainty() -> None:
    data, spec = _fixture(n=120)

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["overall_status"] == "point_only"
    assert result.diagnostics["uncertainty_state"] == "not_requested"
    assert result.diagnostics["warning_state"] == "none"


def test_quick_diagnostic_uncertainty_is_provisional() -> None:
    data, spec = _fixture(n=120, bootstrap=2)
    spec = replace(spec, computation=replace(spec.computation, bootstrap_mode="quick_diagnostic"))

    result = mintmed.analyze_mediation(data, spec)

    assert result.diagnostics["uncertainty_state"] == "provisional"


def test_failed_analysis_reports_uncertainty_not_run() -> None:
    data, spec = _fixture(n=120, bootstrap=2)

    result = mintmed.analyze_mediation(data.drop(columns=["M"]), spec)

    assert result.diagnostics["overall_status"] == "invalid_data"
    assert result.diagnostics["uncertainty_state"] == "not_run"
    assert result.diagnostics["warning_state"] == "none"


def test_report_exposes_both_state_components() -> None:
    from mintmed.report import render_markdown, result_to_dict

    data, spec = _fixture("serial_two", n=120, bootstrap=2)
    result = mintmed.analyze_mediation(data, spec)

    payload = result_to_dict(result)
    assert payload["uncertainty_state"] == "unavailable"
    assert payload["warning_state"] == "warnings"
    assert "uncertainty `unavailable`, warnings `warnings`" in render_markdown(result)


_IDENTIFICATION_TERMS = (
    "consistency",
    "positivity",
    "no interference",
    "exposure-outcome confounding",
    "exposure-mediator confounding",
    "mediator-outcome confounding",
    "exposure-induced mediator-outcome confounders",
    "temporal ordering",
    "cross-world independence",
    "measurement error",
)


def test_model_standardized_assumptions_do_not_claim_causal_identification() -> None:
    data, spec = _fixture(n=120)

    assumptions = mintmed.analyze_mediation(data, spec).diagnostics["assumptions"]
    text = " ".join(assumptions).lower()

    assert spec.contrast.interpretation == "model_standardized"
    assert "model-standardized contrasts, not identified causal effects" in text
    assert "assumption-based under the declared model" not in text
    assert "correctly specified" in text
    assert "factorization order" in text


def test_causal_interpretation_lists_the_full_identification_set() -> None:
    data, spec = _fixture(n=120)
    spec = replace(
        spec,
        interpretation="assumption_based_causal",
        contrast=replace(spec.contrast, interpretation="assumption_based_causal"),
    )

    assumptions = mintmed.analyze_mediation(data, spec).diagnostics["assumptions"]
    text = " ".join(assumptions).lower()

    for term in _IDENTIFICATION_TERMS:
        assert term in text, term
    assert "correctly specified" in text
    assert "factorization order" in text


def test_assumptions_name_the_moderator_conditioning() -> None:
    data, spec = _fixture("moderated_serial", n=120)

    assumptions = mintmed.analyze_mediation(data, spec).diagnostics["assumptions"]

    assert any("retained_analysis_rows_with_W=0" in item for item in assumptions)
