"""Pure contracts for the Task 14 runtime pilot and matrix forecast."""

from __future__ import annotations

import math
from dataclasses import asdict, replace

import pytest

from scripts.run_runtime_pilot import (
    PILOT_CELL_IDS,
    PilotMeasurement,
    _json_text,
    _pilot_config,
    _summarize_cases,
    forecast_cpu_hours,
    DEFAULT_CONFIG,
    load_config,
    render_markdown,
)


def _measurement(cell_id: str, *, cpu_seconds: float = 10.0, status: str = "complete") -> PilotMeasurement:
    return PilotMeasurement(
        cell_id=cell_id,
        repeat=0,
        n=100,
        data_seed=1,
        analysis_seed=2,
        bootstrap_requested=399,
        bootstrap_attempted=399,
        bootstrap_failed=0,
        point_fit_count=2,
        bootstrap_fit_count=399,
        wall_seconds=cpu_seconds,
        cpu_seconds=cpu_seconds,
        peak_rss_bytes=1024,
        draw_budget=256,
        integration_method="sobol_blocked",
        status=status,
        config_hash="config",
        git_commit="commit",
    )


def _complete_measurements(*, cpu_seconds: float = 10.0) -> list[PilotMeasurement]:
    return [_measurement(cell_id, cpu_seconds=cpu_seconds) for cell_id in PILOT_CELL_IDS]


def test_pilot_cell_set_covers_required_profiles() -> None:
    assert PILOT_CELL_IDS == (
        "cell01_linear_n100",
        "cell02_linear_n250",
        "cell07_serial_three_n200",
        "cell09_spline_n250",
        "cell12_mixed_binary_serial_n250",
    )


def test_pilot_config_hash_is_derived_from_one_cell_design() -> None:
    source = load_config(DEFAULT_CONFIG)
    pilot = _pilot_config(source, "cell01_linear_n100")

    assert pilot.replicates == 1
    assert pilot.cell_ids == ("cell01_linear_n100",)
    assert pilot.bootstrap_replicates == source.bootstrap_replicates == 399
    assert pilot.integration_draws == source.integration_draws == 256
    assert pilot.config_hash != source.config_hash


def test_pilot_measurement_rejects_negative_or_nonfinite_resources() -> None:
    with pytest.raises(ValueError, match="cpu_seconds"):
        PilotMeasurement(
            **{
                **asdict(_measurement("cell01_linear_n100")),
                "cpu_seconds": -1.0,
            }
        )
    with pytest.raises(ValueError, match="peak_rss_bytes"):
        PilotMeasurement(
            **{
                **asdict(_measurement("cell01_linear_n100")),
                "peak_rss_bytes": -1,
            }
        )
    with pytest.raises(ValueError, match="wall_seconds"):
        PilotMeasurement(
            **{
                **asdict(_measurement("cell01_linear_n100")),
                "wall_seconds": math.nan,
            }
        )


def test_forecast_multiplies_complete_case_cost_by_200_datasets() -> None:
    forecast = forecast_cpu_hours(_complete_measurements(cpu_seconds=10.0))

    assert forecast["matrix_point_fits"] == 2400
    assert forecast["matrix_bootstrap_refits"] == 957600
    assert forecast["matrix_complete_analyses"] == 960000
    assert forecast["base_cpu_seconds"] == pytest.approx(24000.0)


def test_forecast_adds_the_declared_five_percent_rerun_allowance() -> None:
    forecast = forecast_cpu_hours(_complete_measurements(cpu_seconds=10.0))

    assert forecast["rerun_fraction"] == pytest.approx(0.05)
    assert forecast["projected_cpu_seconds"] == pytest.approx(25200.0)
    assert forecast["projected_cpu_hours"] == pytest.approx(7.0)
    assert forecast["budget_pass"] is True


def test_forecast_counts_point_and_bootstrap_fits() -> None:
    measurements = _complete_measurements(cpu_seconds=1.0)
    forecast = forecast_cpu_hours(measurements)

    assert forecast["matrix_point_fits"] == sum(200 for _ in range(12))
    assert forecast["matrix_bootstrap_refits"] == sum(200 * 399 for _ in range(12))


def test_forecast_marks_incomplete_case_as_blocked() -> None:
    measurements = _complete_measurements(cpu_seconds=1.0)
    measurements[-1] = _measurement("cell12_mixed_binary_serial_n250", status="blocked")

    forecast = forecast_cpu_hours(measurements)

    assert forecast["status"] == "blocked"
    assert forecast["budget_pass"] is False


def test_case_summary_preserves_worker_block_reason() -> None:
    measurements = _complete_measurements(cpu_seconds=1.0)
    measurements[-2] = replace(
        measurements[-2],
        cell_id="cell09_spline_n250",
        status="blocked",
        bootstrap_requested=0,
        bootstrap_attempted=0,
        bootstrap_fit_count=0,
        draw_budget=4096,
        integration_method="sobol_blocked",
    )
    records = [
        {
            "measurement": {"cell_id": "cell09_spline_n250"},
            "status": "blocked",
            "analysis_status": "integration_unresolved",
            "bootstrap_status": None,
            "report_serialized": True,
        }
    ]

    case = next(
        item for item in _summarize_cases(measurements, records) if item["cell_id"] == "cell09_spline_n250"
    )

    assert case["analysis_statuses"] == ["integration_unresolved"]
    assert case["bootstrap_statuses"] == []
    assert case["report_serialized"] is True


def test_markdown_is_deterministic_and_contains_no_absolute_path() -> None:
    payload = {
        "schema_version": 1,
        "experiment": "mintmed_task14_runtime_pilot",
        "status": "pass",
        "supported_python": ">=3.11,<3.12",
        "environment": {"python": "3.11.9", "packages": {"mintmed": "0.1.0"}},
        "git_commit": "abc123",
        "source_config": "configs/mediation_validation.yaml",
        "source_config_hash": "config",
        "pilot_settings": {
            "cell_ids": list(PILOT_CELL_IDS),
            "repeats": 2,
            "bootstrap_replicates": 399,
            "integration_draws": 256,
            "integration_tolerance": 1e-8,
            "rerun_fraction": 0.05,
            "ceiling_cpu_hours": 12.0,
        },
        "cases": [],
        "forecast": forecast_cpu_hours(_complete_measurements(cpu_seconds=1.0)),
    }

    first = render_markdown(payload)
    second = render_markdown(payload)
    assert first == second
    assert "C:\\Users" not in first
    assert "configs/mediation_validation.yaml" in first


def test_markdown_includes_blocked_analysis_status() -> None:
    payload = {
        "status": "blocked",
        "supported_python": ">=3.11,<3.12",
        "source_config": "configs/mediation_validation.yaml",
        "source_config_hash": "config",
        "git_commit": "abc123",
        "environment": {"python": "3.12.14"},
        "pilot_settings": {"repeats": 1, "bootstrap_replicates": 399, "integration_draws": 256, "integration_tolerance": 1e-8, "rerun_fraction": 0.05, "ceiling_cpu_hours": 12.0},
        "cases": [
            {
                "cell_id": "cell09_spline_n250",
                "n": 250,
                "repeat_count": 1,
                "median_cpu_seconds": 1.0,
                "median_wall_seconds": 1.0,
                "max_peak_rss_bytes": 1024,
                "statuses": ["blocked"],
                "analysis_statuses": ["integration_unresolved"],
            }
        ],
        "forecast": {"matrix_point_fits": 2400, "matrix_bootstrap_refits": 957600, "matrix_complete_analyses": 960000, "budget_pass": False, "proxy_map": {}},
    }

    report = render_markdown(payload)

    assert "Analysis status" in report
    assert "integration_unresolved" in report


def test_json_projection_rejects_nonfinite_values() -> None:
    payload = {"value": float("nan")}

    with pytest.raises(ValueError, match="nonfinite"):
        _json_text(payload)
