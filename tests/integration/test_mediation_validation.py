from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from mintmed.experiments.mediation_validation import (
    COMBINATION_COLUMNS,
    EVIDENCE_ARTIFACTS,
    RAW_COLUMNS,
    ValidationConfig,
    expected_combinations,
    expected_row_count,
    load_config,
    metric_record,
    seed_pair,
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
