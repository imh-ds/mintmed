from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
import pandas as pd

from mintmed.experiments.mediation_validation import (
    COMBINATION_COLUMNS,
    EVIDENCE_ARTIFACTS,
    RAW_COLUMNS,
    ValidationConfig,
    cell_definition,
    cell_truth,
    expected_combinations,
    expected_row_count,
    extract_metrics,
    generate_cell,
    load_config,
    metric_record,
    selected_combinations,
    seed_pair,
)
from mintmed.experiments.mediation_validation_reporting import (
    expand_metrics,
    summarize_metrics,
    wilson,
    write_report,
)


ROOT = Path(__file__).parents[2]
SMOKE = ROOT / "configs" / "mediation_validation_smoke.yaml"
FULL = ROOT / "configs" / "mediation_validation.yaml"


def test_smoke_config_has_unique_combinations_and_locked_cells() -> None:
    config = load_config(SMOKE)

    assert config.cell_ids == (
        "cell01_linear_n100",
        "cell06_parallel_interaction_n150",
        "cell10_moderated_n150",
        "cell11_binary_mediator_n150",
        "cell12_mixed_binary_serial_n250",
    )
    combinations = expected_combinations(config)
    assert len(combinations) == 10
    assert len(combinations) == len(set(combinations))
    assert expected_row_count(config) == 10
    assert config.bootstrap_mode == "quick_diagnostic"
    assert config.integration_draws == 256


def test_full_config_is_exactly_the_locked_twelve_cell_matrix() -> None:
    config = load_config(FULL)

    assert config.cell_ids == (
        "cell01_linear_n100",
        "cell02_linear_n250",
        "cell03_no_a_to_m_n100",
        "cell04_no_m_to_y_n100",
        "cell05_no_mediation_n100",
        "cell06_parallel_interaction_n150",
        "cell07_serial_three_n200",
        "cell08_quadratic_n100",
        "cell09_spline_n250",
        "cell10_moderated_n150",
        "cell11_binary_mediator_n150",
        "cell12_mixed_binary_serial_n250",
    )
    assert expected_row_count(config) == 2_400
    assert len(expected_combinations(config)) == 2_400
    assert config.replicates == 200
    assert config.bootstrap_replicates == 399
    assert config.stress_enabled is True


def test_configuration_hash_excludes_source_path_and_output_location(tmp_path: Path) -> None:
    first = load_config(SMOKE)
    copied = tmp_path / "copied.yaml"
    copied.write_text(SMOKE.read_text(encoding="utf-8"), encoding="utf-8")
    second = load_config(copied)

    assert first.config_hash == second.config_hash
    assert first.source_path != second.source_path


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unknown", 1, "unknown configuration key"),
        ("bootstrap_mode", "invalid", "bootstrap_mode"),
        ("integration_draws", 123, "integration_draws"),
        ("cell_ids", ["cell01_linear_n100", "cell01_linear_n100"], "duplicate"),
        ("cell_ids", ["not_a_cell"], "unknown cell"),
    ],
)
def test_config_rejects_invalid_design_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    raw = yaml.safe_load(SMOKE.read_text(encoding="utf-8"))
    if field == "unknown":
        raw[field] = value
    else:
        raw[field] = value
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_config(path)


def test_config_rejects_nonmapping_yaml(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- not a mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        load_config(path)


def test_raw_contract_preserves_two_key_and_evidence_artifact_contract() -> None:
    assert COMBINATION_COLUMNS == ("cell_id", "replicate")
    assert RAW_COLUMNS == (
        "cell_id",
        "replicate",
        "data_seed",
        "analysis_seed",
        "config_hash",
        "truth_method",
        "outcome_kind",
        "estimand",
        "truth",
        "estimate",
        "bias",
        "lower",
        "upper",
        "coverage",
        "width",
        "zero_exclusion",
        "interval_available",
        "status",
        "failure_code",
        "failure_message",
        "runtime_seconds",
        "fit_count",
        "draw_budget",
        "metrics_json",
        "provenance_json",
    )
    assert EVIDENCE_ARTIFACTS == (
        "raw_metrics.csv",
        "cell_summary.csv",
        "summary.json",
        "report.md",
    )


def test_metric_record_keeps_unavailable_intervals_out_of_false_positive_logic() -> None:
    record = metric_record(0.0, 0.02, None, None, status="point_only", reason="no_interval")

    assert record["truth"] == 0.0
    assert record["estimate"] == 0.02
    assert record["bias"] == 0.02
    assert record["coverage"] is False
    assert record["width"] is None
    assert record["zero_exclusion"] is False
    assert record["interval_available"] is False


def test_seed_pair_is_independent_of_output_path_and_dispatch_order() -> None:
    left = seed_pair(20260919, 6, 17)
    right = seed_pair(20260919, 6, 17)

    assert left == right
    assert left[0] != left[1]
    assert seed_pair(20260919, 7, 17) != left
    assert seed_pair(20260919, 6, 18) != left


def test_config_canonical_hash_is_json_serializable() -> None:
    config = load_config(SMOKE)

    encoded = json.dumps(config.canonical_dict, sort_keys=True)

    assert "source_path" not in encoded
    assert "output" not in encoded


@pytest.mark.parametrize(
    ("cell_id", "truth"),
    [
        ("cell01_linear_n100", (0.45, 0.20, 0.25)),
        ("cell02_linear_n250", (0.45, 0.20, 0.25)),
        ("cell03_no_a_to_m_n100", (0.20, 0.20, 0.00)),
        ("cell04_no_m_to_y_n100", (0.20, 0.20, 0.00)),
        ("cell05_no_mediation_n100", (0.20, 0.20, 0.00)),
        ("cell06_parallel_interaction_n150", (0.60, 0.20, 0.40)),
        ("cell07_serial_three_n200", (0.56, 0.20, 0.36)),
        ("cell08_quadratic_n100", (0.30, 0.20, 0.10)),
        ("cell09_spline_n250", (0.30, 0.20, 0.10)),
    ],
)
def test_continuous_cell_truths_are_fixed_population_values(
    cell_id: str, truth: tuple[float, float, float]
) -> None:
    assert cell_truth(cell_id) == pytest.approx(truth)


def test_generated_fixture_uses_locked_equation_metadata_not_sample_moments() -> None:
    fixture = generate_cell("cell08_quadratic_n100", 12345)
    population_sd = fixture.metadata["population_outcome_sd"]
    fixture.data.loc[:, "Y"] = 0.0

    assert fixture.metadata["population_outcome_sd"] == population_sd
    assert fixture.truth == pytest.approx((0.30, 0.20, 0.10))


def test_parallel_interaction_keeps_mediators_parallel_in_scientific_graph() -> None:
    fixture = generate_cell("cell06_parallel_interaction_n150", 12345)

    assert ("M1", "M2") not in fixture.spec.scientific.edges
    assert ("M2", "M1") not in fixture.spec.scientific.edges
    assert fixture.metadata["covariance"] == ((1.0, 0.4), (0.4, 1.0))
    assert fixture.spec.node_by_response["Y"].interactions[0].left == "M1"


def test_spline_cell_declares_three_df_natural_spline() -> None:
    fixture = generate_cell("cell09_spline_n250", 12345)
    outcome_node = fixture.spec.node_by_response["Y"]

    assert outcome_node.terms[2].kind.value == "natural_spline"
    assert outcome_node.terms[2].df == 3


def test_moderated_cell_retains_both_regimes_and_paired_truth() -> None:
    fixture = generate_cell("cell10_moderated_n150", 12345)

    assert fixture.truth == pytest.approx((0.29, 0.20, 0.09))
    assert fixture.metadata["truth_by_moderator"] == {
        "W=0": pytest.approx((0.29, 0.20, 0.09)),
        "W=1": pytest.approx((0.56, 0.20, 0.36)),
        "difference_W1_minus_W0_TNIE": pytest.approx(0.27),
    }
    assert tuple(fixture.spec.contrast.moderator_values) == ("W",)


def test_binary_cells_preserve_both_exposure_levels_in_first_rows() -> None:
    for cell_id in ("cell11_binary_mediator_n150", "cell12_mixed_binary_serial_n250"):
        fixture = generate_cell(cell_id, 12345)
        assert tuple(fixture.data["A"].iloc[:2]) == (0.0, 1.0)
        assert set(fixture.data["A"]) == {0.0, 1.0}
        assert fixture.metadata["quadrature_order"] == 64


def test_binary_truths_use_probability_difference_units_and_quadrature() -> None:
    for cell_id in ("cell11_binary_mediator_n150", "cell12_mixed_binary_serial_n250"):
        definition = cell_definition(cell_id)
        assert definition.outcome_kind == "binary"
        assert definition.truth_method == "gauss_hermite_64"
        assert definition.population_outcome_sd is None
        assert all(-1.0 <= value <= 1.0 for value in cell_truth(cell_id))


def test_standard_payload_extracts_point_effects_and_bootstrap_intervals() -> None:
    payload = {
        "overall_status": "complete",
        "effects": [
            {"name": "TE", "estimate": 0.4, "lower": None, "upper": None, "status": "ok", "reason": None},
            {"name": "PNDE", "estimate": 0.2, "lower": None, "upper": None, "status": "ok", "reason": None},
            {"name": "TNIE", "estimate": 0.2, "lower": None, "upper": None, "status": "ok", "reason": None},
        ],
        "bootstrap": {
            "intervals": [
                {"name": "TE", "lower": 0.1, "upper": 0.7, "status": "ok", "reason": None},
                {"name": "PNDE", "lower": 0.0, "upper": 0.4, "status": "ok", "reason": None},
                {"name": "TNIE", "lower": -0.1, "upper": 0.5, "status": "ok", "reason": None},
            ]
        },
        "diagnostics": {},
        "provenance": {},
    }

    metrics = extract_metrics(payload, "cell01_linear_n100")

    assert tuple(metrics) == ("TE", "PNDE", "TNIE")
    assert metrics["TNIE"]["estimate"] == pytest.approx(0.2)
    assert metrics["TNIE"]["lower"] == pytest.approx(-0.1)
    assert metrics["TNIE"]["upper"] == pytest.approx(0.5)


def test_cell_ten_payload_extracts_direct_points_and_paired_difference_interval() -> None:
    payload = {
        "overall_status": "complete_with_warnings",
        "effects": [],
        "bootstrap": {
            "intervals": [
                {
                    "name": "moderator_difference__W__1__TNIE",
                    "lower": 0.01,
                    "upper": 0.52,
                    "status": "ok",
                    "reason": None,
                }
            ]
        },
        "diagnostics": {
            "moderation": {
                "contrasts": [
                    {
                        "moderator": "W",
                        "value": 0,
                        "effects": [{"name": "TNIE", "estimate": 0.09, "lower": None, "upper": None, "status": "ok", "reason": "bootstrap_interval_not_reported_for_moderator_effect"}],
                        "differences": [],
                    },
                    {
                        "moderator": "W",
                        "value": 1,
                        "effects": [{"name": "TNIE", "estimate": 0.36, "lower": None, "upper": None, "status": "ok", "reason": "bootstrap_interval_not_reported_for_moderator_effect"}],
                        "differences": [],
                    },
                ]
            }
        },
        "provenance": {},
    }

    metrics = extract_metrics(payload, "cell10_moderated_n150")

    assert metrics["TNIE_W0"]["estimate"] == pytest.approx(0.09)
    assert metrics["TNIE_W0"]["lower"] is None
    assert metrics["TNIE_W1"]["estimate"] == pytest.approx(0.36)
    assert metrics["TNIE_difference"]["lower"] == pytest.approx(0.01)
    assert metrics["TNIE_difference"]["upper"] == pytest.approx(0.52)


def test_structured_failure_extraction_preserves_error_and_null_estimates() -> None:
    payload = {
        "overall_status": "fit_failed",
        "effects": [],
        "bootstrap": None,
        "diagnostics": {
            "error": {"code": "node_fit_failed", "message": "locked node could not be fitted"},
            "nodes": [],
        },
        "provenance": {},
    }

    metrics = extract_metrics(payload, "cell01_linear_n100")

    assert metrics["TE"]["estimate"] is None
    assert metrics["TE"]["lower"] is None
    assert metrics["TE"]["status"] == "fit_failed"
    assert metrics["TE"]["reason"] == "node_fit_failed"


def _raw_row(cell_id: str, replicate: int, metrics: dict[str, dict[str, object]], config_hash: str) -> dict[str, object]:
    first = next(iter(metrics.values()))
    return {
        "cell_id": cell_id,
        "replicate": replicate,
        "data_seed": 1,
        "analysis_seed": 2,
        "config_hash": config_hash,
        "truth_method": "closed_form",
        "outcome_kind": "continuous",
        "estimand": next(iter(metrics)),
        "truth": first["truth"],
        "estimate": first["estimate"],
        "bias": first["bias"],
        "lower": first["lower"],
        "upper": first["upper"],
        "coverage": first["coverage"],
        "width": first["width"],
        "zero_exclusion": first["zero_exclusion"],
        "interval_available": first["interval_available"],
        "status": first["status"],
        "failure_code": None,
        "failure_message": None,
        "runtime_seconds": 0.1,
        "fit_count": 2,
        "draw_budget": 256,
        "metrics_json": json.dumps(metrics),
        "provenance_json": json.dumps({"config_hash": config_hash}),
    }


def test_wilson_handles_empty_and_boundary_counts() -> None:
    assert wilson(0, 0) == (None, None)
    lower, upper = wilson(0, 10)
    assert lower == pytest.approx(0.0)
    assert 0.0 < upper < 1.0
    lower, upper = wilson(10, 10)
    assert 0.0 < lower < 1.0
    assert upper == pytest.approx(1.0)


def test_metric_expansion_and_summary_count_unavailable_intervals_as_noncoverage() -> None:
    config = load_config(SMOKE)
    metrics = {
        "TE": metric_record(0.45, 0.44, 0.2, 0.7, status="complete"),
        "PNDE": metric_record(0.2, 0.21, None, None, status="point_only", reason="no_interval"),
        "TNIE": metric_record(0.25, 0.23, 0.1, 0.5, status="complete"),
    }
    raw = pd.DataFrame([_raw_row("cell01_linear_n100", 0, metrics, config.config_hash)])

    long = expand_metrics(raw, config)
    summary = summarize_metrics(long, raw, config)

    pnde = summary.loc[(summary.cell_id == "cell01_linear_n100") & (summary.metric == "PNDE")].iloc[0]
    assert int(pnde.attempted_rows) == 1
    assert int(pnde.unavailable_interval_rows) == 1
    assert int(pnde.coverage_trials) == 1
    assert int(pnde.coverage_successes) == 0
    assert pnde.coverage == pytest.approx(0.0)


def test_write_report_emits_required_artifacts_without_private_row_fields(tmp_path: Path) -> None:
    config = load_config(SMOKE)
    metrics = {
        "TNIE": metric_record(0.25, None, None, None, status="fit_failed", reason="node_fit_failed")
    }
    raw = pd.DataFrame([_raw_row("cell06_parallel_interaction_n150", 0, metrics, config.config_hash)])
    write_report(raw, config, tmp_path)

    for artifact in ("raw_metrics.csv", "cell_summary.csv", "summary.json", "report.md"):
        assert (tmp_path / artifact).is_file()
    summary_text = (tmp_path / "summary.json").read_text(encoding="utf-8")
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "row_positions" not in summary_text
    assert "row_indices" not in summary_text
    assert "participant" not in summary_text.lower()
    assert "Stress diagnostics" in report_text


def test_selected_combinations_are_registry_ordered_and_filterable() -> None:
    config = load_config(SMOKE)

    selected = selected_combinations(
        config,
        cell_ids=("cell12_mixed_binary_serial_n250", "cell01_linear_n100"),
        replicate_start=0,
        replicate_stop=1,
    )

    assert selected == (
        ("cell01_linear_n100", 0),
        ("cell12_mixed_binary_serial_n250", 0),
    )


def test_selected_combinations_reject_conflicting_or_empty_filters() -> None:
    config = load_config(SMOKE)

    with pytest.raises(ValueError, match="cannot be combined"):
        selected_combinations(config, replicate=0, replicate_start=0, replicate_stop=1)
    with pytest.raises(ValueError, match="nonempty"):
        selected_combinations(config, replicate_start=1, replicate_stop=1)
