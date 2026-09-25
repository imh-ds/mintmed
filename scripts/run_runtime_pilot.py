"""Run the complete-bootstrap Task 14 runtime pilot and forecast."""

from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mintmed import __version__ as MINTMED_VERSION  # noqa: E402
from mintmed.api import analyze_mediation  # noqa: E402
from mintmed.experiments.mediation_validation import (  # noqa: E402
    ValidationConfig,
    cell_definition,
    generate_cell,
    load_config,
    seed_pair,
)
from mintmed.report import result_to_dict, write_reports  # noqa: E402


SCHEMA_VERSION = 1
EXPERIMENT = "mintmed_task14_runtime_pilot"
SUPPORTED_PYTHON = ">=3.11,<3.12"
DEFAULT_CONFIG = ROOT / "configs" / "mediation_validation.yaml"
DEFAULT_OUTPUT = ROOT / "results" / "generated" / "runtime-pilot.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "validation" / "runtime_pilot.md"
PILOT_CELL_IDS: tuple[str, ...] = (
    "cell01_linear_n100",
    "cell02_linear_n250",
    "cell07_serial_three_n200",
    "cell09_spline_n250",
    "cell12_mixed_binary_serial_n250",
)
MATRIX_CELL_COUNT = 12
MATRIX_DATASETS_PER_CELL = 200
BOOTSTRAP_REPLICATES = 399
INTEGRATION_DRAWS = 256
INTEGRATION_TOLERANCE = 1.0e-8
RERUN_FRACTION = 0.05
CPU_CEILING_HOURS = 12.0

PROXY_MAP: Mapping[str, tuple[str, ...]] = {
    "cell01_linear_n100": (
        "cell01_linear_n100",
        "cell03_no_a_to_m_n100",
        "cell04_no_m_to_y_n100",
        "cell05_no_mediation_n100",
    ),
    "cell02_linear_n250": ("cell02_linear_n250",),
    "cell07_serial_three_n200": (
        "cell06_parallel_interaction_n150",
        "cell07_serial_three_n200",
    ),
    "cell09_spline_n250": ("cell08_quadratic_n100", "cell09_spline_n250"),
    "cell12_mixed_binary_serial_n250": (
        "cell10_moderated_n150",
        "cell11_binary_mediator_n150",
        "cell12_mixed_binary_serial_n250",
    ),
}


@dataclass(frozen=True, slots=True)
class PilotMeasurement:
    """One isolated complete-case measurement or an explicit blocked attempt."""

    cell_id: str
    repeat: int
    n: int
    data_seed: int
    analysis_seed: int
    bootstrap_requested: int
    bootstrap_attempted: int
    bootstrap_failed: int
    point_fit_count: int
    bootstrap_fit_count: int
    wall_seconds: float
    cpu_seconds: float
    peak_rss_bytes: int
    draw_budget: int
    integration_method: str
    status: str
    config_hash: str
    git_commit: str

    def __post_init__(self) -> None:
        if not self.cell_id or self.repeat < 0 or self.n <= 0:
            raise ValueError("cell_id, repeat, and n are invalid")
        for name in ("bootstrap_requested", "bootstrap_attempted", "bootstrap_failed", "point_fit_count", "bootstrap_fit_count", "peak_rss_bytes", "draw_budget"):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) != value or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.bootstrap_attempted > self.bootstrap_requested:
            raise ValueError("bootstrap_attempted cannot exceed bootstrap_requested")
        if self.bootstrap_failed > self.bootstrap_attempted:
            raise ValueError("bootstrap_failed cannot exceed bootstrap_attempted")
        for name in ("wall_seconds", "cpu_seconds"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not self.integration_method or not self.status or not self.config_hash or not self.git_commit:
            raise ValueError("integration_method, status, config_hash, and git_commit are required")


def _json_text(payload: Mapping[str, Any]) -> str:
    """Serialize a payload while rejecting nonfinite values."""

    try:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ValueError(f"payload contains non-JSON or nonfinite values: {exc}") from exc


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _version(name: str, fallback: str | None = None) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return fallback or "unavailable"


def _package_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "mintmed": MINTMED_VERSION,
        "statsmodels": _version("statsmodels"),
        "numpy": _version("numpy"),
        "scipy": _version("scipy"),
        "pandas": _version("pandas"),
        "patsy": _version("patsy"),
        "platform": platform.platform(),
    }


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("git rev-parse did not return a full commit hash")
    return commit


def _peak_rss_bytes() -> int:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        process = kernel32.GetCurrentProcess()
        get_info = psapi.GetProcessMemoryInfo
        get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
        get_info.restype = ctypes.c_int
        if not get_info(process, ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.PeakWorkingSetSize)

    import resource

    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value * (1024 if sys.platform != "darwin" else 1)


def _redact_message(message: str, paths: Sequence[Path]) -> str:
    result = str(message)
    for path in paths:
        result = result.replace(str(path), "[temporary-path]")
    result = result.replace(str(ROOT), "[repository]")
    return result


def _bootstrap_summary(payload: Mapping[str, Any]) -> tuple[int, int, int, Mapping[str, Any]]:
    bootstrap = payload.get("bootstrap")
    if not isinstance(bootstrap, Mapping):
        return 0, 0, 0, {}
    return (
        int(bootstrap.get("requested") or 0),
        int(bootstrap.get("attempted") or 0),
        int(bootstrap.get("failed") or 0),
        bootstrap,
    )


def _pilot_config(config: ValidationConfig, cell_id: str) -> ValidationConfig:
    """Derive the one-cell/one-dataset config without changing frozen settings."""

    return replace(config, replicates=1, cell_ids=(cell_id,))


def _worker_record(
    *,
    config_path: Path,
    cell_id: str,
    repeat: int,
    output_dir: Path,
    worker_output: Path,
) -> None:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    config = load_config(config_path)
    definition = cell_definition(cell_id)
    pilot_config = _pilot_config(config, cell_id)
    data_seed, analysis_seed = seed_pair(config.master_seed, definition.ordinal, 0)
    try:
        fixture = generate_cell(cell_id, data_seed)
        computation = replace(
            fixture.spec.computation,
            seed=analysis_seed,
            bootstrap=BOOTSTRAP_REPLICATES,
            bootstrap_mode="standard",
            integration_draws=INTEGRATION_DRAWS,
            integration_tolerance=INTEGRATION_TOLERANCE,
            max_seconds=config.max_seconds,
            memory_budget_mb=config.memory_budget_mb,
        )
        spec = replace(fixture.spec, computation=computation)
        result = analyze_mediation(fixture.data, spec)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_reports(result, output_dir)
        payload = result_to_dict(result)
        persisted = json.loads((output_dir / "analysis.json").read_text(encoding="utf-8"))
        if json.dumps(payload, sort_keys=True, allow_nan=False) != json.dumps(persisted, sort_keys=True, allow_nan=False):
            raise RuntimeError("analysis JSON did not round-trip from the public result payload")

        requested, attempted, failed, bootstrap = _bootstrap_summary(payload)
        diagnostics = payload.get("diagnostics")
        diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
        nodes = diagnostics.get("nodes")
        nodes = nodes if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)) else ()
        point_fit_count = sum(1 for node in nodes if isinstance(node, Mapping) and node.get("status") != "not_run")
        provenance = payload.get("provenance")
        provenance = provenance if isinstance(provenance, Mapping) else {}
        integration = diagnostics.get("integration")
        integration = integration if isinstance(integration, Mapping) else {}
        draw_budget = provenance.get("accepted_draw_budget")
        if draw_budget is None:
            draw_budget = integration.get("accepted_draw_budget")
        method = provenance.get("integration_method") or integration.get("method") or "unavailable"
        status = "complete" if attempted == requested == BOOTSTRAP_REPLICATES and payload.get("overall_status") in {"complete", "complete_with_warnings"} else "blocked"
        measurement = PilotMeasurement(
            cell_id=cell_id,
            repeat=repeat,
            n=definition.n,
            data_seed=data_seed,
            analysis_seed=analysis_seed,
            bootstrap_requested=requested,
            bootstrap_attempted=attempted,
            bootstrap_failed=failed,
            point_fit_count=point_fit_count,
            bootstrap_fit_count=attempted,
            wall_seconds=time.perf_counter() - started_wall,
            cpu_seconds=time.process_time() - started_cpu,
            peak_rss_bytes=_peak_rss_bytes(),
            draw_budget=int(draw_budget or 0),
            integration_method=str(method),
            status=status,
            config_hash=config.config_hash,
            git_commit=_git_commit(),
        )
        record = {
            "measurement": asdict(measurement),
            "source_config_hash": config.config_hash,
            "pilot_config_hash": pilot_config.config_hash,
            "status": status,
            "analysis_status": payload.get("overall_status"),
            "bootstrap_status": bootstrap.get("status"),
            "failure_counts": bootstrap.get("failure_counts", {}),
            "report_serialized": True,
        }
    except Exception as exc:  # pragma: no cover - exercised by pilot failures
        message = _redact_message(str(exc), (config_path, output_dir, worker_output))
        measurement = PilotMeasurement(
            cell_id=cell_id,
            repeat=repeat,
            n=definition.n,
            data_seed=data_seed,
            analysis_seed=analysis_seed,
            bootstrap_requested=BOOTSTRAP_REPLICATES,
            bootstrap_attempted=0,
            bootstrap_failed=0,
            point_fit_count=0,
            bootstrap_fit_count=0,
            wall_seconds=time.perf_counter() - started_wall,
            cpu_seconds=time.process_time() - started_cpu,
            peak_rss_bytes=_peak_rss_bytes(),
            draw_budget=0,
            integration_method="unavailable",
            status="blocked",
            config_hash=config.config_hash,
            git_commit=_git_commit(),
        )
        record = {
            "measurement": asdict(measurement),
            "source_config_hash": config.config_hash,
            "pilot_config_hash": pilot_config.config_hash,
            "status": "blocked",
            "report_serialized": False,
            "error_type": type(exc).__name__,
            "error_message": message,
        }
    _atomic_write(worker_output, _json_text(record))


def _run_case(config_path: Path, cell_id: str, repeat: int, *, allow_unsupported_runtime: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"mintmed-task14-{cell_id}-") as temporary:
        temporary_path = Path(temporary)
        case_output = temporary_path / "reports"
        worker_output = temporary_path / "worker.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--config",
            str(config_path.resolve()),
            "--cell-id",
            cell_id,
            "--repeat",
            str(repeat),
            "--case-output",
            str(case_output),
            "--worker-output",
            str(worker_output),
        ]
        if allow_unsupported_runtime:
            command.append("--allow-unsupported-runtime")
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        parent_wall = time.perf_counter() - started
        if completed.returncode != 0 or not worker_output.is_file():
            definition = cell_definition(cell_id)
            config = load_config(config_path)
            pilot_config = _pilot_config(config, cell_id)
            _git = _git_commit()
            measurement = PilotMeasurement(
                cell_id=cell_id,
                repeat=repeat,
                n=definition.n,
                data_seed=0,
                analysis_seed=0,
                bootstrap_requested=BOOTSTRAP_REPLICATES,
                bootstrap_attempted=0,
                bootstrap_failed=0,
                point_fit_count=0,
                bootstrap_fit_count=0,
                wall_seconds=parent_wall,
                cpu_seconds=0.0,
                peak_rss_bytes=0,
                draw_budget=0,
                integration_method="unavailable",
                status="blocked",
                config_hash=pilot_config.config_hash,
                git_commit=_git,
            )
            return {
                "measurement": asdict(measurement),
                "source_config_hash": config.config_hash,
                "pilot_config_hash": pilot_config.config_hash,
                "status": "blocked",
                "report_serialized": False,
                "error_type": "worker_failed",
                "error_message": _redact_message(completed.stderr[-2000:], (config_path,)),
            }
        record = json.loads(worker_output.read_text(encoding="utf-8"))
        record["parent_wall_seconds"] = parent_wall
        return record


def _summarize_cases(measurements: Sequence[PilotMeasurement], records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for cell_id in PILOT_CELL_IDS:
        cell_measurements = [item for item in measurements if item.cell_id == cell_id]
        cell_records = [record for record in records if record.get("measurement", {}).get("cell_id") == cell_id]
        cpu_values = [item.cpu_seconds for item in cell_measurements]
        wall_values = [item.wall_seconds for item in cell_measurements]
        analysis_statuses = sorted(
            {
                str(record["analysis_status"])
                for record in cell_records
                if record.get("analysis_status")
            }
        )
        bootstrap_statuses = sorted(
            {
                str(record["bootstrap_status"])
                for record in cell_records
                if record.get("bootstrap_status")
            }
        )
        error_types = sorted(
            {
                str(record["error_type"])
                for record in cell_records
                if record.get("error_type")
            }
        )
        error_messages = sorted(
            {
                str(record["error_message"])
                for record in cell_records
                if record.get("error_message")
            }
        )
        output.append(
            {
                "cell_id": cell_id,
                "n": cell_measurements[0].n if cell_measurements else cell_definition(cell_id).n,
                "repeat_count": len(cell_measurements),
                "repeats": [asdict(item) for item in cell_measurements],
                "median_cpu_seconds": statistics.median(cpu_values) if cpu_values else None,
                "median_wall_seconds": statistics.median(wall_values) if wall_values else None,
                "max_peak_rss_bytes": max((item.peak_rss_bytes for item in cell_measurements), default=None),
                "statuses": sorted({item.status for item in cell_measurements}),
                "report_serialized": all(bool(record.get("report_serialized")) for record in cell_records),
                "analysis_statuses": analysis_statuses,
                "bootstrap_statuses": bootstrap_statuses,
                "error_types": error_types,
                "error_messages": error_messages,
            }
        )
    return output


def forecast_cpu_hours(
    measurements: Sequence[PilotMeasurement],
    *,
    datasets_per_cell: int = MATRIX_DATASETS_PER_CELL,
    rerun_fraction: float = RERUN_FRACTION,
    ceiling_hours: float = CPU_CEILING_HOURS,
) -> dict[str, Any]:
    if datasets_per_cell <= 0 or rerun_fraction < 0.0 or ceiling_hours <= 0.0:
        raise ValueError("forecast settings must be positive and rerun_fraction nonnegative")
    by_cell: dict[str, list[PilotMeasurement]] = {cell_id: [] for cell_id in PILOT_CELL_IDS}
    for measurement in measurements:
        if measurement.cell_id not in by_cell:
            raise ValueError(f"measurement cell is not in the pilot: {measurement.cell_id}")
        by_cell[measurement.cell_id].append(measurement)
    missing = [cell_id for cell_id, values in by_cell.items() if not values]
    incomplete = [cell_id for cell_id, values in by_cell.items() if any(item.status != "complete" for item in values)]
    if missing or incomplete:
        return {
            "status": "blocked",
            "budget_pass": False,
            "reason": "incomplete_pilot_case",
            "missing_pilot_cells": missing,
            "incomplete_pilot_cells": incomplete,
            "matrix_point_fits": MATRIX_CELL_COUNT * datasets_per_cell,
            "matrix_bootstrap_refits": MATRIX_CELL_COUNT * datasets_per_cell * BOOTSTRAP_REPLICATES,
            "matrix_complete_analyses": MATRIX_CELL_COUNT * datasets_per_cell * (BOOTSTRAP_REPLICATES + 1),
            "rerun_fraction": rerun_fraction,
            "ceiling_cpu_hours": ceiling_hours,
            "proxy_map": {proxy: list(cells) for proxy, cells in PROXY_MAP.items()},
        }

    median_cpu = {
        cell_id: statistics.median(item.cpu_seconds for item in values)
        for cell_id, values in by_cell.items()
    }
    proxy_cpu_seconds = {proxy: median_cpu[proxy] for proxy in PILOT_CELL_IDS}
    base_cpu_seconds = sum(proxy_cpu_seconds[proxy] * len(cells) * datasets_per_cell for proxy, cells in PROXY_MAP.items())
    projected_cpu_seconds = base_cpu_seconds * (1.0 + rerun_fraction)
    projected_cpu_hours = projected_cpu_seconds / 3600.0
    return {
        "status": "pass" if projected_cpu_hours <= ceiling_hours else "over_budget",
        "budget_pass": projected_cpu_hours <= ceiling_hours,
        "matrix_point_fits": MATRIX_CELL_COUNT * datasets_per_cell,
        "matrix_bootstrap_refits": MATRIX_CELL_COUNT * datasets_per_cell * BOOTSTRAP_REPLICATES,
        "matrix_complete_analyses": MATRIX_CELL_COUNT * datasets_per_cell * (BOOTSTRAP_REPLICATES + 1),
        "datasets_per_cell": datasets_per_cell,
        "median_cpu_seconds_by_proxy": median_cpu,
        "proxy_cpu_seconds": proxy_cpu_seconds,
        "base_cpu_seconds": base_cpu_seconds,
        "rerun_fraction": rerun_fraction,
        "projected_cpu_seconds": projected_cpu_seconds,
        "projected_cpu_hours": projected_cpu_hours,
        "ceiling_cpu_hours": ceiling_hours,
        "proxy_map": {proxy: list(cells) for proxy, cells in PROXY_MAP.items()},
    }


def _format_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "blocked"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _find_absolute_path(value: Any) -> str | None:
    if isinstance(value, str):
        if re.search(r"^[A-Za-z]:[\\/]", value) or value.startswith("/"):
            return value
        return None
    if isinstance(value, Mapping):
        for item in value.values():
            found = _find_absolute_path(item)
            if found:
                return found
    if isinstance(value, (tuple, list)):
        for item in value:
            found = _find_absolute_path(item)
            if found:
                return found
    return None


def render_markdown(payload: Mapping[str, Any]) -> str:
    absolute = _find_absolute_path(payload)
    if absolute:
        raise ValueError(f"runtime report contains an absolute path: {absolute}")
    settings = payload.get("pilot_settings", {})
    environment = payload.get("environment", {})
    cases = payload.get("cases", [])
    forecast = payload.get("forecast", {})
    lines = [
        "# Task 14 runtime pilot",
        "",
        "This report is generated from `results/generated/runtime-pilot.json`. It measures complete analysis cases, including point fitting, the full participant bootstrap, integration, failure accounting, and report serialization.",
        "",
        f"- Status: `{payload.get('status')}`.",
        f"- Supported runtime: `{payload.get('supported_python')}`.",
        f"- Source configuration: `{payload.get('source_config')}` (`{payload.get('source_config_hash')}`).",
        f"- Git commit: `{payload.get('git_commit')}`.",
        "",
        "## Settings",
        "",
        f"- Pilot repeats: `{settings.get('repeats')}`; bootstrap replicates per case: `{settings.get('bootstrap_replicates')}`.",
        f"- Integration draws: `{settings.get('integration_draws')}`; tolerance: `{settings.get('integration_tolerance')}`.",
        f"- Targeted-rerun allowance: `{settings.get('rerun_fraction')}`; CPU ceiling: `{settings.get('ceiling_cpu_hours')}` hours.",
        "",
        "## Environment",
        "",
        "| Component | Value |",
        "|---|---|",
    ]
    for key, value in sorted(environment.items()):
        rendered = json.dumps(value, sort_keys=True) if isinstance(value, Mapping) else str(value)
        lines.append(f"| `{key}` | `{rendered}` |")
    lines.extend(["", "## Measured cases", "", "| Cell | N | Repeats | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |", "|---|---:|---:|---:|---:|---:|---|---|"])
    for case in cases:
        status = ", ".join(case.get("statuses", [])) or "blocked"
        analysis_status = ", ".join(case.get("analysis_statuses", [])) or "unavailable"
        lines.append(
            "| `{cell_id}` | {n} | {repeat_count} | {cpu} | {wall} | {rss} | {status} | {analysis_status} |".format(
                cell_id=case.get("cell_id"),
                n=case.get("n"),
                repeat_count=case.get("repeat_count"),
                cpu=_format_number(case.get("median_cpu_seconds")),
                wall=_format_number(case.get("median_wall_seconds")),
                rss=case.get("max_peak_rss_bytes") if case.get("max_peak_rss_bytes") is not None else "blocked",
                status=status,
                analysis_status=analysis_status,
            )
        )
        for message in case.get("error_messages", []):
            lines.append(f"  - `{case.get('cell_id')}` worker error: {message}")
    lines.extend(
        [
            "",
            "## Locked-matrix forecast",
            "",
            f"- Point fits: `{forecast.get('matrix_point_fits')}`.",
            f"- Bootstrap refits: `{forecast.get('matrix_bootstrap_refits')}`.",
            f"- Complete analyses: `{forecast.get('matrix_complete_analyses')}`.",
            f"- Base CPU seconds: `{_format_number(forecast.get('base_cpu_seconds'))}`.",
            f"- Projected CPU seconds including reruns: `{_format_number(forecast.get('projected_cpu_seconds'))}`.",
            f"- Projected CPU hours: `{_format_number(forecast.get('projected_cpu_hours'))}`; budget pass: `{forecast.get('budget_pass')}`.",
            "",
            "The forecast uses the declared conservative proxy map and includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.",
            "",
            "## Proxy map",
            "",
        ]
    )
    for proxy, cells in sorted(forecast.get("proxy_map", {}).items()):
        lines.append(f"- `{proxy}` forecasts: {', '.join(f'`{cell}`' for cell in cells)}.")
    lines.extend(["", "## Handoff", "", "Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.", ""])
    return "\n".join(lines)


def _run_parent(args: argparse.Namespace) -> int:
    supported = sys.version_info[:2] == (3, 11)
    if not supported and not args.allow_unsupported_runtime:
        print(f"Task 14 requires Python {SUPPORTED_PYTHON}; running {platform.python_version()}", file=sys.stderr)
        return 2
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    git_commit = _git_commit()
    measurements: list[PilotMeasurement] = []
    records: list[Mapping[str, Any]] = []
    for cell_id in PILOT_CELL_IDS:
        for repeat in range(args.repeats):
            record = _run_case(config_path, cell_id, repeat, allow_unsupported_runtime=args.allow_unsupported_runtime)
            records.append(record)
            measurements.append(PilotMeasurement(**record["measurement"]))

    cases = _summarize_cases(measurements, records)
    forecast = forecast_cpu_hours(measurements)
    status = forecast["status"]
    if not supported:
        status = "blocked"
        forecast = {**forecast, "runtime_supported": False, "reason": "unsupported_python_runtime"}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "experiment": EXPERIMENT,
        "status": status,
        "supported_python": SUPPORTED_PYTHON,
        "runtime_supported": supported,
        "environment": _package_versions(),
        "git_commit": git_commit,
        "source_config": "configs/mediation_validation.yaml",
        "source_config_hash": config.config_hash,
        "pilot_settings": {
            "cell_ids": list(PILOT_CELL_IDS),
            "repeats": args.repeats,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "integration_draws": INTEGRATION_DRAWS,
            "integration_tolerance": INTEGRATION_TOLERANCE,
            "rerun_fraction": RERUN_FRACTION,
            "ceiling_cpu_hours": CPU_CEILING_HOURS,
        },
        "cases": cases,
        "forecast": forecast,
    }
    output = Path(args.output).resolve()
    markdown = Path(args.markdown).resolve()
    _atomic_write(output, _json_text(payload))
    persisted = json.loads(output.read_text(encoding="utf-8"))
    _atomic_write(markdown, render_markdown(persisted))
    print(_json_text({"status": status, "output": str(output.relative_to(ROOT)), "markdown": str(markdown.relative_to(ROOT)), "forecast": forecast}))
    return 0 if status == "pass" else 2


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--allow-unsupported-runtime", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cell-id", help=argparse.SUPPRESS)
    parser.add_argument("--repeat", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--case-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.worker:
        if not all((args.cell_id, args.repeat is not None, args.case_output, args.worker_output)):
            raise SystemExit("worker mode requires cell, repeat, case output, and worker output")
        _worker_record(
            config_path=Path(args.config),
            cell_id=str(args.cell_id),
            repeat=int(args.repeat),
            output_dir=Path(args.case_output),
            worker_output=Path(args.worker_output),
        )
        return 0
    if args.repeats <= 0:
        raise SystemExit("--repeats must be positive")
    return _run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
