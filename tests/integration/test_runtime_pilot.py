"""Pure contracts for the Task 14 runtime pilot and matrix forecast."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path

import pytest
import yaml

from scripts.run_runtime_pilot import (
    PILOT_CELL_IDS,
    PROXY_MAP,
    PilotMeasurement,
    _json_text,
    _parse_args,
    _pilot_config,
    _summarize_cases,
    _worker_timeout_seconds,
    forecast_cpu_hours,
    forecast_from_runtimes,
    DEFAULT_CONFIG,
    DEFAULT_MARKDOWN,
    load_cell_summary_runtimes,
    load_config,
    load_pilot_runtimes,
    main,
    render_markdown,
    resolve_cell_runtimes,
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


def test_pilot_measures_every_matrix_cell_without_proxies() -> None:
    # Audit BUG-03: proxies hid the Sobol-path cost of cells 06 and 10, so
    # every locked matrix cell is now measured directly.
    source = load_config(DEFAULT_CONFIG)
    assert PILOT_CELL_IDS == source.cell_ids
    assert PROXY_MAP == {cell_id: (cell_id,) for cell_id in source.cell_ids}


def test_forecast_records_each_cell_integration_method() -> None:
    measurements = _complete_measurements(cpu_seconds=1.0)
    measurements[5] = replace(measurements[5], integration_method="gauss_hermite")
    forecast = forecast_cpu_hours(measurements)

    assert forecast["integration_methods"][PILOT_CELL_IDS[5]] == ["gauss_hermite"]
    assert forecast["integration_methods"][PILOT_CELL_IDS[0]] == ["sobol_blocked"]


def test_worker_timeout_exceeds_the_bootstrap_time_cap() -> None:
    source = load_config(DEFAULT_CONFIG)
    assert _worker_timeout_seconds(source) > source.max_seconds


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


# 2026-09-27 budget amendment: aggregate CPU ceiling on the reference GitHub
# runner plus a per-shard wall-clock gate for the declared 48-shard layout.
_GHA_PER_DATASET_SECONDS = {
    "cell01_linear_n100": 8.047,
    "cell02_linear_n250": 8.464,
    "cell03_no_a_to_m_n100": 7.249,
    "cell04_no_m_to_y_n100": 7.414,
    "cell05_no_mediation_n100": 7.437,
    "cell06_parallel_interaction_n150": 60.475,
    "cell07_serial_three_n200": 13.981,
    "cell08_quadratic_n100": 34.248,
    "cell09_spline_n250": 48.365,
    "cell10_moderated_n150": 165.269,
    "cell11_binary_mediator_n150": 20.583,
    "cell12_mixed_binary_serial_n250": 29.296,
}


def _measurements_from(seconds: dict[str, float]) -> list[PilotMeasurement]:
    return [_measurement(cell_id, cpu_seconds=seconds[cell_id]) for cell_id in PILOT_CELL_IDS]


def test_amended_budget_constants_are_declared() -> None:
    from scripts.run_runtime_pilot import (
        CPU_CEILING_HOURS,
        REFERENCE_PLATFORM,
        SHARD_REPLICATE_BLOCKS,
        SHARD_WALL_CEILING_HOURS,
    )

    assert CPU_CEILING_HOURS == 36.0
    assert SHARD_REPLICATE_BLOCKS == 4
    assert SHARD_WALL_CEILING_HOURS == 4.0
    assert REFERENCE_PLATFORM == "github-actions ubuntu-latest"


def test_measured_github_pilot_passes_the_amended_budget() -> None:
    forecast = forecast_cpu_hours(_measurements_from(_GHA_PER_DATASET_SECONDS))

    assert forecast["projected_cpu_hours"] == pytest.approx(23.965, abs=0.01)
    assert forecast["shard_count"] == 48
    assert forecast["datasets_per_shard"] == 50
    assert forecast["slowest_shard_cell"] == "cell10_moderated_n150"
    assert forecast["max_shard_wall_hours"] == pytest.approx(165.269 * 50 * 1.05 / 3600, rel=1e-6)
    assert forecast["aggregate_pass"] is True
    assert forecast["shard_pass"] is True
    assert forecast["status"] == "pass"
    assert forecast["budget_pass"] is True


def test_aggregate_cpu_above_the_ceiling_is_over_budget() -> None:
    forecast = forecast_cpu_hours(_complete_measurements(cpu_seconds=60.0))

    assert forecast["projected_cpu_hours"] == pytest.approx(42.0)
    assert forecast["aggregate_pass"] is False
    assert forecast["shard_pass"] is True
    assert forecast["status"] == "over_budget"


def test_one_slow_cell_can_fail_the_shard_wall_clock_gate() -> None:
    seconds = {cell_id: 5.0 for cell_id in PILOT_CELL_IDS}
    seconds["cell10_moderated_n150"] = 300.0

    forecast = forecast_cpu_hours(_measurements_from(seconds))

    assert forecast["aggregate_pass"] is True
    assert forecast["max_shard_wall_hours"] == pytest.approx(300.0 * 50 * 1.05 / 3600)
    assert forecast["shard_pass"] is False
    assert forecast["status"] == "over_budget"


# Task 16 (T16-S4): the matrix shape is a parameter and a forecast can be made
# from measured runtimes without fitting.


def test_matrix_shape_defaults_reproduce_the_run_one_layout() -> None:
    args = _parse_args([])

    assert args.datasets_per_cell == 200
    assert args.replicate_blocks == 4
    assert args.forecast_only is False
    assert args.output is None and args.markdown is None


def test_pilot_forecast_follows_the_given_cells_and_shard_layout() -> None:
    cells = ("cell01_linear_n100", "cell10_moderated_n150")
    measurements = [_measurement(cells[0], cpu_seconds=4.0), _measurement(cells[1], cpu_seconds=72.0)]

    forecast = forecast_cpu_hours(measurements, cell_ids=cells, datasets_per_cell=500, replicate_blocks=10)

    assert forecast["cell_count"] == 2
    assert forecast["shard_count"] == 20
    assert forecast["datasets_per_shard"] == 50
    assert forecast["matrix_point_fits"] == 1000
    assert forecast["base_cpu_seconds"] == pytest.approx((4.0 + 72.0) * 500)
    assert forecast["max_shard_wall_hours"] == pytest.approx(72.0 * 50 * 1.05 / 3600)
    with pytest.raises(ValueError, match="not in the pilot"):
        forecast_cpu_hours(_complete_measurements(), cell_ids=cells)


_FORECAST_CELLS = ("cell01_linear_n100", "cell06_parallel_interaction_n150", "cell10_moderated_n150")


def _write_cell_summary(path: Path, seconds: dict[str, float]) -> Path:
    # Two metric rows per cell; the first row per cell is the one used.
    lines = ["cell_id,metric,runtime_mean_seconds,coverage"]
    for cell_id, value in seconds.items():
        lines.append(f"{cell_id},PNDE,{value},0.95")
        lines.append(f"{cell_id},TE,{value + 1000.0},0.95")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_pilot_json(path: Path) -> Path:
    cases = [
        {"cell_id": "cell06_parallel_interaction_n150", "statuses": ["complete"], "median_cpu_seconds": 30.0, "median_wall_seconds": 36.0},
        # Also in the cell summary, which takes precedence.
        {"cell_id": "cell01_linear_n100", "statuses": ["complete"], "median_cpu_seconds": 99.0, "median_wall_seconds": 99.0},
        # A blocked case is never usable.
        {"cell_id": "cell02_linear_n250", "statuses": ["blocked"], "median_cpu_seconds": 1.0, "median_wall_seconds": 1.0},
    ]
    path.write_text(json.dumps({"status": "pass", "cases": cases}), encoding="utf-8")
    return path


def _forecast(tmp_path: Path, summary_seconds: dict[str, float], **kwargs: int) -> dict:
    sources = [
        load_cell_summary_runtimes(_write_cell_summary(tmp_path / "cell_summary.csv", summary_seconds)),
        load_pilot_runtimes(_write_pilot_json(tmp_path / "pilot.json")),
    ]
    return forecast_from_runtimes(_FORECAST_CELLS, resolve_cell_runtimes(_FORECAST_CELLS, sources), **kwargs)


def test_forecast_only_combines_cell_summary_and_pilot_runtimes(tmp_path: Path) -> None:
    forecast = _forecast(
        tmp_path,
        {"cell01_linear_n100": 6.0, "cell10_moderated_n150": 72.0},
        datasets_per_cell=500,
        replicate_blocks=10,
    )

    # (6 + 30 + 72) s x 500 datasets = 54000 s = 15 h; x 1.05 = 15.75 h.
    assert forecast["base_cpu_seconds"] == pytest.approx(54000.0)
    assert forecast["base_cpu_hours"] == pytest.approx(15.0)
    assert forecast["projected_cpu_hours"] == pytest.approx(15.75)
    assert forecast["shard_count"] == 30
    assert forecast["datasets_per_shard"] == 50
    # Pilot cells use wall seconds for the shard gate: 36 s x 50 x 1.05.
    assert forecast["shard_wall_hours_by_cell"]["cell06_parallel_interaction_n150"] == pytest.approx(0.525)
    assert forecast["slowest_shard_cell"] == "cell10_moderated_n150"
    assert forecast["max_shard_wall_hours"] == pytest.approx(1.05)
    assert forecast["aggregate_pass"] is True
    assert forecast["shard_pass"] is True
    assert forecast["status"] == "pass"
    runtimes = forecast["cell_runtimes"]
    assert runtimes["cell01_linear_n100"]["source_kind"] == "cell_summary"
    assert runtimes["cell01_linear_n100"]["cpu_seconds_per_dataset"] == 6.0
    assert runtimes["cell06_parallel_interaction_n150"]["source_kind"] == "pilot_json"
    assert runtimes["cell06_parallel_interaction_n150"]["source"].endswith("pilot.json")
    assert runtimes["cell10_moderated_n150"]["base_cpu_hours"] == pytest.approx(10.0)


def test_forecast_only_fails_each_ceiling_independently(tmp_path: Path) -> None:
    # 336 s x 500 / 3600 x 1.05 = 49 h; five-dataset shards stay short.
    aggregate = _forecast(
        tmp_path,
        {"cell01_linear_n100": 6.0, "cell10_moderated_n150": 300.0},
        datasets_per_cell=500,
        replicate_blocks=100,
    )
    assert aggregate["projected_cpu_hours"] == pytest.approx(49.0)
    assert aggregate["max_shard_wall_hours"] == pytest.approx(300.0 * 5 * 1.05 / 3600)
    assert (aggregate["aggregate_pass"], aggregate["shard_pass"], aggregate["status"]) == (False, True, "over_budget")

    # 236 s x 500 / 3600 x 1.05 = 34.4 h; 250-dataset shards of cell 10 do not fit.
    shard = _forecast(
        tmp_path,
        {"cell01_linear_n100": 6.0, "cell10_moderated_n150": 200.0},
        datasets_per_cell=500,
        replicate_blocks=2,
    )
    assert shard["projected_cpu_hours"] == pytest.approx(236.0 * 500 * 1.05 / 3600)
    assert shard["shard_count"] == 6
    assert shard["max_shard_wall_hours"] == pytest.approx(200.0 * 250 * 1.05 / 3600)
    assert (shard["aggregate_pass"], shard["shard_pass"], shard["budget_pass"]) == (True, False, False)


def test_forecast_only_rounds_uneven_replicate_blocks_up(tmp_path: Path) -> None:
    forecast = _forecast(
        tmp_path,
        {"cell01_linear_n100": 6.0, "cell10_moderated_n150": 72.0},
        datasets_per_cell=500,
        replicate_blocks=3,
    )

    assert forecast["datasets_per_shard"] == 167
    assert forecast["shard_count"] == 9


def test_forecast_only_refuses_a_cell_without_a_measurement(tmp_path: Path) -> None:
    summary = load_cell_summary_runtimes(_write_cell_summary(tmp_path / "cell_summary.csv", {"cell01_linear_n100": 6.0}))
    pilot = load_pilot_runtimes(_write_pilot_json(tmp_path / "pilot.json"))

    with pytest.raises(ValueError, match="cell10_moderated_n150"):
        resolve_cell_runtimes(_FORECAST_CELLS, [summary, pilot])
    with pytest.raises(ValueError, match="cell06_parallel_interaction_n150"):
        forecast_from_runtimes(_FORECAST_CELLS, summary)
    # The blocked pilot case does not count as a measurement.
    with pytest.raises(ValueError, match="cell02_linear_n250"):
        resolve_cell_runtimes(("cell02_linear_n250",), [pilot])


def test_cell_summary_requires_the_runtime_column(tmp_path: Path) -> None:
    path = tmp_path / "cell_summary.csv"
    path.write_text("cell_id,metric\ncell01_linear_n100,PNDE\n", encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_mean_seconds"):
        load_cell_summary_runtimes(path)


def test_forecast_only_cli_writes_json_and_optional_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({**source, "cell_ids": list(_FORECAST_CELLS)}, sort_keys=False), encoding="utf-8")
    summary = _write_cell_summary(tmp_path / "cell_summary.csv", {"cell01_linear_n100": 6.0, "cell10_moderated_n150": 72.0})
    pilot = _write_pilot_json(tmp_path / "pilot.json")
    output = tmp_path / "out" / "forecast.json"
    markdown = tmp_path / "out" / "forecast.md"

    code = main(
        [
            "--forecast-only",
            "--config", str(config_path),
            "--cell-summary", str(summary),
            "--pilot-json", str(pilot),
            "--datasets-per-cell", "500",
            "--replicate-blocks", "10",
            "--output", str(output),
            "--markdown", str(markdown),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "forecast_only"
    assert payload["forecast_settings"]["cell_ids"] == list(_FORECAST_CELLS)
    assert payload["forecast"]["projected_cpu_hours"] == pytest.approx(15.75)
    assert payload["forecast"]["shard_count"] == 30
    by_kind = {item["kind"]: item for item in payload["runtime_sources"]}
    assert by_kind["cell_summary"]["cells_used"] == ["cell01_linear_n100", "cell10_moderated_n150"]
    assert by_kind["pilot_json"]["cells_used"] == ["cell06_parallel_interaction_n150"]
    assert len(by_kind["pilot_json"]["sha256"]) == 64
    report = markdown.read_text(encoding="utf-8")
    assert "cell10_moderated_n150" in report and "15.750" in report
    assert "C:\\" not in report and str(tmp_path) not in report
    assert json.loads(capsys.readouterr().out)["forecast"]["slowest_shard_cell"] == "cell10_moderated_n150"

    with pytest.raises(SystemExit, match="cell06_parallel_interaction_n150"):
        main(["--forecast-only", "--config", str(config_path), "--cell-summary", str(summary), "--output", str(output)])
    with pytest.raises(SystemExit, match="runtime-pilot report"):
        main(
            [
                "--forecast-only", "--config", str(config_path), "--cell-summary", str(summary),
                "--pilot-json", str(pilot), "--output", str(output), "--markdown", str(DEFAULT_MARKDOWN),
            ]
        )
    with pytest.raises(SystemExit, match="require --forecast-only"):
        main(["--cell-summary", str(summary)])
