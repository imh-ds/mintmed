"""Run the complete-bootstrap Task 14 runtime pilot and forecast."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
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
DEFAULT_FORECAST_OUTPUT = ROOT / "results" / "generated" / "runtime-forecast.json"
FORECAST_EXPERIMENT = "mintmed_runtime_forecast"
# Every locked matrix cell is measured directly.  The earlier five-case proxy
# design forecast the Sobol-path cells (06, 10) from exact/quadrature proxies
# and understated their cost by more than an order of magnitude (audit BUG-03).
# This tuple is the run-1 default matrix; the pilot itself derives its cells
# from the loaded configuration's ``cell_ids``.
PILOT_CELL_IDS: tuple[str, ...] = (
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
# Matrix-shape defaults (run 1). ``--datasets-per-cell`` and
# ``--replicate-blocks`` override them; the cell count is the config's.
MATRIX_DATASETS_PER_CELL = 200
BOOTSTRAP_REPLICATES = 399
INTEGRATION_DRAWS = 256
INTEGRATION_TOLERANCE = 1.0e-3
RERUN_FRACTION = 0.05
# Task 14 budget, amended 2026-09-27 (see the decision log). The authoritative
# pilot runs on the reference GitHub runner. The aggregate ceiling guards total
# compute; the shard gate guards wall-clock feasibility of the sharded matrix
# (12 cells x SHARD_REPLICATE_BLOCKS replicate blocks) under GitHub's 6-hour
# job limit. The original ceiling was 12 aggregate CPU-hours on unspecified
# hardware. The ceilings stay fixed; the shard layout is a parameter.
REFERENCE_PLATFORM = "github-actions ubuntu-latest"
CPU_CEILING_HOURS = 36.0
SHARD_REPLICATE_BLOCKS = 4
SHARD_WALL_CEILING_HOURS = 4.0

PROXY_MAP: Mapping[str, tuple[str, ...]] = {cell_id: (cell_id,) for cell_id in PILOT_CELL_IDS}
WORKER_TIMEOUT_MARGIN_SECONDS = 900


def _worker_timeout_seconds(config: ValidationConfig) -> int:
    """Allow the full bootstrap time cap plus point fitting and serialization."""

    return int(config.max_seconds) + WORKER_TIMEOUT_MARGIN_SECONDS


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
            config_hash=pilot_config.config_hash,
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
            config_hash=pilot_config.config_hash,
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
            timeout=_worker_timeout_seconds(load_config(config_path)),
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


def _summarize_cases(
    measurements: Sequence[PilotMeasurement],
    records: Sequence[Mapping[str, Any]],
    cell_ids: Sequence[str] = PILOT_CELL_IDS,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for cell_id in cell_ids:
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


def _validate_forecast_settings(
    cell_ids: Sequence[str],
    *,
    datasets_per_cell: int,
    replicate_blocks: int,
    rerun_fraction: float,
    ceiling_hours: float,
) -> None:
    if datasets_per_cell <= 0 or rerun_fraction < 0.0 or ceiling_hours <= 0.0:
        raise ValueError("forecast settings must be positive and rerun_fraction nonnegative")
    if replicate_blocks <= 0 or replicate_blocks > datasets_per_cell:
        raise ValueError("replicate_blocks must be positive and at most datasets_per_cell")
    if not cell_ids or len(set(cell_ids)) != len(cell_ids):
        raise ValueError("cell_ids must be nonempty and unique")


def _matrix_fit_counts(cell_count: int, datasets_per_cell: int) -> dict[str, int]:
    return {
        "matrix_point_fits": cell_count * datasets_per_cell,
        "matrix_bootstrap_refits": cell_count * datasets_per_cell * BOOTSTRAP_REPLICATES,
        "matrix_complete_analyses": cell_count * datasets_per_cell * (BOOTSTRAP_REPLICATES + 1),
    }


def _budget_forecast(
    cell_ids: Sequence[str],
    cpu_seconds_per_dataset: Mapping[str, float],
    wall_seconds_per_dataset: Mapping[str, float],
    *,
    datasets_per_cell: int,
    replicate_blocks: int,
    rerun_fraction: float,
    ceiling_hours: float,
) -> dict[str, Any]:
    """Apply both budget gates to per-cell, per-dataset CPU and wall seconds."""

    base_cpu_seconds = sum(cpu_seconds_per_dataset[cell_id] * datasets_per_cell for cell_id in cell_ids)
    projected_cpu_seconds = base_cpu_seconds * (1.0 + rerun_fraction)
    projected_cpu_hours = projected_cpu_seconds / 3600.0
    # Each shard runs one cell's replicate block sequentially in one process,
    # so its wall time is the cell's per-dataset wall time times the block size.
    datasets_per_shard = math.ceil(datasets_per_cell / replicate_blocks)
    shard_wall_hours = {
        cell_id: wall_seconds_per_dataset[cell_id] * datasets_per_shard * (1.0 + rerun_fraction) / 3600.0
        for cell_id in cell_ids
    }
    slowest_shard_cell = max(shard_wall_hours, key=shard_wall_hours.__getitem__)
    max_shard_wall_hours = shard_wall_hours[slowest_shard_cell]
    aggregate_pass = projected_cpu_hours <= ceiling_hours
    shard_pass = max_shard_wall_hours <= SHARD_WALL_CEILING_HOURS
    budget_pass = aggregate_pass and shard_pass
    return {
        "status": "pass" if budget_pass else "over_budget",
        "budget_pass": budget_pass,
        "aggregate_pass": aggregate_pass,
        "shard_pass": shard_pass,
        "reference_platform": REFERENCE_PLATFORM,
        "cell_count": len(cell_ids),
        "shard_replicate_blocks": replicate_blocks,
        "shard_count": len(cell_ids) * replicate_blocks,
        "datasets_per_shard": datasets_per_shard,
        "shard_wall_hours_by_cell": shard_wall_hours,
        "slowest_shard_cell": slowest_shard_cell,
        "max_shard_wall_hours": max_shard_wall_hours,
        "shard_wall_ceiling_hours": SHARD_WALL_CEILING_HOURS,
        **_matrix_fit_counts(len(cell_ids), datasets_per_cell),
        "datasets_per_cell": datasets_per_cell,
        "base_cpu_seconds": base_cpu_seconds,
        "base_cpu_hours": base_cpu_seconds / 3600.0,
        "rerun_fraction": rerun_fraction,
        "projected_cpu_seconds": projected_cpu_seconds,
        "projected_cpu_hours": projected_cpu_hours,
        "ceiling_cpu_hours": ceiling_hours,
    }


def forecast_cpu_hours(
    measurements: Sequence[PilotMeasurement],
    *,
    cell_ids: Sequence[str] = PILOT_CELL_IDS,
    datasets_per_cell: int = MATRIX_DATASETS_PER_CELL,
    replicate_blocks: int = SHARD_REPLICATE_BLOCKS,
    rerun_fraction: float = RERUN_FRACTION,
    ceiling_hours: float = CPU_CEILING_HOURS,
) -> dict[str, Any]:
    cell_ids = tuple(cell_ids)
    _validate_forecast_settings(
        cell_ids,
        datasets_per_cell=datasets_per_cell,
        replicate_blocks=replicate_blocks,
        rerun_fraction=rerun_fraction,
        ceiling_hours=ceiling_hours,
    )
    proxy_map = {cell_id: [cell_id] for cell_id in cell_ids}
    by_cell: dict[str, list[PilotMeasurement]] = {cell_id: [] for cell_id in cell_ids}
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
            **_matrix_fit_counts(len(cell_ids), datasets_per_cell),
            "rerun_fraction": rerun_fraction,
            "ceiling_cpu_hours": ceiling_hours,
            "proxy_map": proxy_map,
        }

    median_cpu = {
        cell_id: statistics.median(item.cpu_seconds for item in values)
        for cell_id, values in by_cell.items()
    }
    integration_methods = {
        cell_id: sorted({item.integration_method for item in values})
        for cell_id, values in by_cell.items()
    }
    median_wall = {
        cell_id: statistics.median(item.wall_seconds for item in values)
        for cell_id, values in by_cell.items()
    }
    forecast = _budget_forecast(
        cell_ids,
        median_cpu,
        median_wall,
        datasets_per_cell=datasets_per_cell,
        replicate_blocks=replicate_blocks,
        rerun_fraction=rerun_fraction,
        ceiling_hours=ceiling_hours,
    )
    return {
        **forecast,
        "median_cpu_seconds_by_proxy": median_cpu,
        "integration_methods": integration_methods,
        "proxy_cpu_seconds": dict(median_cpu),
        "proxy_map": proxy_map,
    }


# ---------------------------------------------------------------------------
# Forecast-only mode: reuse measured per-dataset runtimes without fitting.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CellRuntime:
    """Measured per-dataset seconds for one cell and where they came from."""

    cell_id: str
    cpu_seconds_per_dataset: float
    wall_seconds_per_dataset: float
    source_kind: str
    source: str

    def __post_init__(self) -> None:
        for name in ("cpu_seconds_per_dataset", "wall_seconds_per_dataset"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{self.cell_id}: {name} must be finite and positive")
        if self.source_kind not in {"cell_summary", "pilot_json"}:
            raise ValueError(f"unknown runtime source kind: {self.source_kind}")


def _display_path(path: Path) -> str:
    """A repository-relative path, or the last two components outside it."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return "/".join(resolved.parts[-2:])


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cell_summary_runtimes(path: Path) -> dict[str, CellRuntime]:
    """Read ``runtime_mean_seconds`` from an aggregated ``cell_summary.csv``.

    The column is the mean wall-clock seconds of one complete dataset analysis
    and repeats across a cell's metric rows; the first row per cell is used for
    both the CPU and the wall forecast.
    """

    display = _display_path(path)
    runtimes: dict[str, CellRuntime] = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if "cell_id" not in fields or "runtime_mean_seconds" not in fields:
            raise ValueError(f"{display}: cell summary needs cell_id and runtime_mean_seconds columns")
        for row in reader:
            cell_id = str(row["cell_id"]).strip()
            if not cell_id or cell_id in runtimes:
                continue
            raw = str(row["runtime_mean_seconds"] or "").strip()
            try:
                seconds = float(raw)
            except ValueError as exc:
                raise ValueError(f"{display}: {cell_id} has no numeric runtime_mean_seconds ({raw!r})") from exc
            runtimes[cell_id] = CellRuntime(
                cell_id=cell_id,
                cpu_seconds_per_dataset=seconds,
                wall_seconds_per_dataset=seconds,
                source_kind="cell_summary",
                source=display,
            )
    return runtimes


def load_pilot_runtimes(path: Path) -> dict[str, CellRuntime]:
    """Read per-cell median CPU and wall seconds from a runtime-pilot JSON.

    Only cells whose every pilot repeat completed are usable; a blocked or
    partial case is left out, so a forecast that needs it refuses.
    """

    display = _display_path(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, Mapping) else None
    if not isinstance(cases, list):
        raise ValueError(f"{display}: runtime-pilot JSON has no cases list")
    runtimes: dict[str, CellRuntime] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        cell_id = str(case.get("cell_id") or "")
        if not cell_id or case.get("statuses") != ["complete"]:
            continue
        cpu = case.get("median_cpu_seconds")
        wall = case.get("median_wall_seconds")
        if cpu is None or wall is None:
            continue
        runtimes[cell_id] = CellRuntime(
            cell_id=cell_id,
            cpu_seconds_per_dataset=float(cpu),
            wall_seconds_per_dataset=float(wall),
            source_kind="pilot_json",
            source=display,
        )
    return runtimes


def resolve_cell_runtimes(
    cell_ids: Sequence[str],
    sources: Sequence[Mapping[str, CellRuntime]],
) -> dict[str, CellRuntime]:
    """Take each cell from the first source that measured it; refuse gaps."""

    resolved: dict[str, CellRuntime] = {}
    for cell_id in cell_ids:
        for source in sources:
            if cell_id in source:
                resolved[cell_id] = source[cell_id]
                break
    missing = [cell_id for cell_id in cell_ids if cell_id not in resolved]
    if missing:
        raise ValueError(
            "no measured runtime for configured cell(s): "
            + ", ".join(missing)
            + "; supply a cell_summary.csv or a runtime-pilot JSON with a complete case for each"
        )
    return resolved


def forecast_from_runtimes(
    cell_ids: Sequence[str],
    runtimes: Mapping[str, CellRuntime],
    *,
    datasets_per_cell: int = MATRIX_DATASETS_PER_CELL,
    replicate_blocks: int = SHARD_REPLICATE_BLOCKS,
    rerun_fraction: float = RERUN_FRACTION,
    ceiling_hours: float = CPU_CEILING_HOURS,
) -> dict[str, Any]:
    """Forecast the matrix from measured runtimes, with the pilot's budget math."""

    cell_ids = tuple(cell_ids)
    _validate_forecast_settings(
        cell_ids,
        datasets_per_cell=datasets_per_cell,
        replicate_blocks=replicate_blocks,
        rerun_fraction=rerun_fraction,
        ceiling_hours=ceiling_hours,
    )
    resolved = resolve_cell_runtimes(cell_ids, [runtimes])
    forecast = _budget_forecast(
        cell_ids,
        {cell_id: resolved[cell_id].cpu_seconds_per_dataset for cell_id in cell_ids},
        {cell_id: resolved[cell_id].wall_seconds_per_dataset for cell_id in cell_ids},
        datasets_per_cell=datasets_per_cell,
        replicate_blocks=replicate_blocks,
        rerun_fraction=rerun_fraction,
        ceiling_hours=ceiling_hours,
    )
    return {
        **forecast,
        "cell_runtimes": {
            cell_id: {
                "cpu_seconds_per_dataset": resolved[cell_id].cpu_seconds_per_dataset,
                "wall_seconds_per_dataset": resolved[cell_id].wall_seconds_per_dataset,
                "base_cpu_hours": resolved[cell_id].cpu_seconds_per_dataset * datasets_per_cell / 3600.0,
                "source_kind": resolved[cell_id].source_kind,
                "source": resolved[cell_id].source,
            }
            for cell_id in cell_ids
        },
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
        f"- Reference platform: `{settings.get('reference_platform', REFERENCE_PLATFORM)}`; shard layout: `{len(settings.get('cell_ids') or PILOT_CELL_IDS)}` cells x "
        f"`{settings.get('shard_replicate_blocks', SHARD_REPLICATE_BLOCKS)}` replicate blocks; shard wall ceiling: "
        f"`{settings.get('shard_wall_ceiling_hours', SHARD_WALL_CEILING_HOURS)}` hours.",
        "",
        "## Environment",
        "",
        "| Component | Value |",
        "|---|---|",
    ]
    for key, value in sorted(environment.items()):
        rendered = json.dumps(value, sort_keys=True) if isinstance(value, Mapping) else str(value)
        lines.append(f"| `{key}` | `{rendered}` |")
    lines.extend(["", "## Measured cases", "", "| Cell | N | Repeats | Integration | Median CPU (s) | Median wall (s) | Peak RSS (bytes) | Status | Analysis status |", "|---|---:|---:|---|---:|---:|---:|---|---|"])
    for case in cases:
        status = ", ".join(case.get("statuses", [])) or "blocked"
        analysis_status = ", ".join(case.get("analysis_statuses", [])) or "unavailable"
        lines.append(
            "| `{cell_id}` | {n} | {repeat_count} | {method} | {cpu} | {wall} | {rss} | {status} | {analysis_status} |".format(
                cell_id=case.get("cell_id"),
                n=case.get("n"),
                repeat_count=case.get("repeat_count"),
                method=", ".join(sorted({str(item.get("integration_method")) for item in case.get("repeats", [])})) or "unavailable",
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
            f"- Projected CPU hours: `{_format_number(forecast.get('projected_cpu_hours'))}` (aggregate gate pass: `{forecast.get('aggregate_pass')}`).",
            f"- Slowest shard: `{forecast.get('slowest_shard_cell')}` at `{_format_number(forecast.get('max_shard_wall_hours'))}` wall hours "
            f"for `{forecast.get('datasets_per_shard')}` datasets (shard gate pass: `{forecast.get('shard_pass')}`).",
            f"- Budget pass: `{forecast.get('budget_pass')}`.",
            "",
            "Every locked matrix cell is measured directly (no proxy cells), so each cell is forecast from its own integration path. The forecast includes point fits, attempted bootstrap refits, failures, serialization, and the 5% targeted-rerun allowance. A blocked case blocks the forecast; a passing forecast is a runtime boundary, not statistical validation.",
            "",
            "## Proxy map",
            "",
        ]
    )
    for proxy, cells in sorted(forecast.get("proxy_map", {}).items()):
        lines.append(f"- `{proxy}` forecasts: {', '.join(f'`{cell}`' for cell in cells)}.")
    lines.extend(["", "## Handoff", "", "Task 15 may freeze the release charter only after this report, the raw JSON, the reference-agreement record, and supported-runtime verification agree on the configuration, seeds, fit counts, and runtime boundary.", ""])
    return "\n".join(lines)


def render_forecast_markdown(payload: Mapping[str, Any]) -> str:
    """Render a forecast-only payload; no cases are measured in this mode."""

    absolute = _find_absolute_path(payload)
    if absolute:
        raise ValueError(f"runtime forecast contains an absolute path: {absolute}")
    settings = payload.get("forecast_settings", {})
    forecast = payload.get("forecast", {})
    lines = [
        "# Runtime forecast from measured runtimes",
        "",
        "This forecast reuses measured per-dataset runtimes; no analysis was fitted to produce it. It applies the runtime pilot's budget arithmetic: aggregate CPU hours include the targeted-rerun allowance, and each shard runs one cell's replicate block sequentially.",
        "",
        f"- Status: `{payload.get('status')}`.",
        f"- Source configuration: `{payload.get('source_config')}` (`{payload.get('source_config_hash')}`).",
        f"- Git commit: `{payload.get('git_commit')}`.",
        "",
        "## Settings",
        "",
        f"- Cells: `{len(settings.get('cell_ids', []))}`; datasets per cell: `{settings.get('datasets_per_cell')}`; replicate blocks: `{settings.get('replicate_blocks')}`.",
        f"- Targeted-rerun allowance: `{settings.get('rerun_fraction')}`; CPU ceiling: `{settings.get('ceiling_cpu_hours')}` hours.",
        f"- Reference platform: `{settings.get('reference_platform')}`; shard wall ceiling: `{settings.get('shard_wall_ceiling_hours')}` hours.",
        "",
        "## Runtime sources",
        "",
        "| Kind | Source | SHA-256 | Cells used |",
        "|---|---|---|---:|",
    ]
    for source in payload.get("runtime_sources", []):
        lines.append(f"| {source.get('kind')} | `{source.get('source')}` | `{source.get('sha256')}` | {len(source.get('cells_used', []))} |")
    lines.extend(
        [
            "",
            "## Per-cell forecast",
            "",
            "| Cell | CPU s/dataset | Wall s/dataset | Base CPU hours | Shard wall hours | Source |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    shard_hours = forecast.get("shard_wall_hours_by_cell", {})
    for cell_id, runtime in forecast.get("cell_runtimes", {}).items():
        lines.append(
            f"| `{cell_id}` | {_format_number(runtime.get('cpu_seconds_per_dataset'))} | {_format_number(runtime.get('wall_seconds_per_dataset'))} | "
            f"{_format_number(runtime.get('base_cpu_hours'))} | {_format_number(shard_hours.get(cell_id))} | {runtime.get('source_kind')} |"
        )
    lines.extend(
        [
            "",
            "## Matrix forecast",
            "",
            f"- Shards: `{forecast.get('shard_count')}` (`{forecast.get('cell_count')}` cells x `{forecast.get('shard_replicate_blocks')}` blocks of up to `{forecast.get('datasets_per_shard')}` datasets).",
            f"- Complete analyses: `{forecast.get('matrix_complete_analyses')}`.",
            f"- Base CPU hours: `{_format_number(forecast.get('base_cpu_hours'))}`.",
            f"- Projected CPU hours including reruns: `{_format_number(forecast.get('projected_cpu_hours'))}` (aggregate gate pass: `{forecast.get('aggregate_pass')}`).",
            f"- Slowest shard: `{forecast.get('slowest_shard_cell')}` at `{_format_number(forecast.get('max_shard_wall_hours'))}` wall hours (shard gate pass: `{forecast.get('shard_pass')}`).",
            f"- Budget pass: `{forecast.get('budget_pass')}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _run_forecast_only(args: argparse.Namespace) -> int:
    if args.cell_summary is None and not args.pilot_json:
        raise SystemExit("--forecast-only needs --cell-summary and/or --pilot-json")
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    cell_ids = tuple(config.cell_ids)
    loaded: list[tuple[str, Path, dict[str, CellRuntime]]] = []
    if args.cell_summary is not None:
        loaded.append(("cell_summary", Path(args.cell_summary), load_cell_summary_runtimes(Path(args.cell_summary))))
    for pilot_path in args.pilot_json or ():
        loaded.append(("pilot_json", Path(pilot_path), load_pilot_runtimes(Path(pilot_path))))
    try:
        resolved = resolve_cell_runtimes(cell_ids, [runtimes for _, _, runtimes in loaded])
        forecast = forecast_from_runtimes(
            cell_ids,
            resolved,
            datasets_per_cell=args.datasets_per_cell,
            replicate_blocks=args.replicate_blocks,
        )
    except ValueError as exc:
        raise SystemExit(f"forecast refused: {exc}") from exc
    runtime_sources = [
        {
            "kind": kind,
            "source": _display_path(path),
            "sha256": _sha256(path),
            "cells_measured": sorted(runtimes),
            "cells_used": [cell_id for cell_id in cell_ids if resolved[cell_id] is runtimes.get(cell_id)],
        }
        for kind, path, runtimes in loaded
    ]
    status = forecast["status"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "experiment": FORECAST_EXPERIMENT,
        "mode": "forecast_only",
        "status": status,
        "git_commit": _git_commit(),
        "source_config": _display_path(config_path),
        "source_config_hash": config.config_hash,
        "forecast_settings": {
            "cell_ids": list(cell_ids),
            "datasets_per_cell": args.datasets_per_cell,
            "replicate_blocks": args.replicate_blocks,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "rerun_fraction": RERUN_FRACTION,
            "ceiling_cpu_hours": CPU_CEILING_HOURS,
            "reference_platform": REFERENCE_PLATFORM,
            "shard_wall_ceiling_hours": SHARD_WALL_CEILING_HOURS,
        },
        "runtime_sources": runtime_sources,
        "forecast": forecast,
    }
    output = Path(args.output or DEFAULT_FORECAST_OUTPUT).resolve()
    _atomic_write(output, _json_text(payload))
    summary: dict[str, Any] = {"status": status, "output": _display_path(output)}
    if args.markdown is not None:
        markdown = Path(args.markdown).resolve()
        if markdown == DEFAULT_MARKDOWN.resolve():
            raise SystemExit("forecast-only mode must not overwrite the runtime-pilot report")
        persisted = json.loads(output.read_text(encoding="utf-8"))
        _atomic_write(markdown, render_forecast_markdown(persisted))
        summary["markdown"] = _display_path(markdown)
    summary["forecast"] = {
        key: forecast[key]
        for key in (
            "cell_count",
            "datasets_per_cell",
            "shard_replicate_blocks",
            "shard_count",
            "datasets_per_shard",
            "base_cpu_hours",
            "projected_cpu_hours",
            "aggregate_pass",
            "slowest_shard_cell",
            "max_shard_wall_hours",
            "shard_pass",
            "budget_pass",
        )
    }
    print(_json_text(summary))
    return 0 if status == "pass" else 2


def _run_parent(args: argparse.Namespace) -> int:
    supported = sys.version_info[:2] == (3, 11)
    if not supported and not args.allow_unsupported_runtime:
        print(f"Task 14 requires Python {SUPPORTED_PYTHON}; running {platform.python_version()}", file=sys.stderr)
        return 2
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    cell_ids = tuple(config.cell_ids)
    if args.pilot_cells:
        unknown = sorted(set(args.pilot_cells) - set(cell_ids))
        if unknown:
            raise SystemExit(f"--pilot-cell is not in the configuration: {', '.join(unknown)}")
        cell_ids = tuple(cell_id for cell_id in cell_ids if cell_id in set(args.pilot_cells))
    git_commit = _git_commit()
    measurements: list[PilotMeasurement] = []
    records: list[Mapping[str, Any]] = []
    for cell_id in cell_ids:
        for repeat in range(args.repeats):
            record = _run_case(config_path, cell_id, repeat, allow_unsupported_runtime=args.allow_unsupported_runtime)
            records.append(record)
            measurements.append(PilotMeasurement(**record["measurement"]))

    cases = _summarize_cases(measurements, records, cell_ids)
    forecast = forecast_cpu_hours(
        measurements,
        cell_ids=cell_ids,
        datasets_per_cell=args.datasets_per_cell,
        replicate_blocks=args.replicate_blocks,
    )
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
        "source_config": _display_path(config_path),
        "source_config_hash": config.config_hash,
        "pilot_settings": {
            "cell_ids": list(cell_ids),
            "datasets_per_cell": args.datasets_per_cell,
            "repeats": args.repeats,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "integration_draws": INTEGRATION_DRAWS,
            "integration_tolerance": INTEGRATION_TOLERANCE,
            "rerun_fraction": RERUN_FRACTION,
            "ceiling_cpu_hours": CPU_CEILING_HOURS,
            "reference_platform": REFERENCE_PLATFORM,
            "shard_replicate_blocks": args.replicate_blocks,
            "shard_wall_ceiling_hours": SHARD_WALL_CEILING_HOURS,
        },
        "cases": cases,
        "forecast": forecast,
    }
    output = Path(args.output or DEFAULT_OUTPUT).resolve()
    markdown = Path(args.markdown or DEFAULT_MARKDOWN).resolve()
    _atomic_write(output, _json_text(payload))
    persisted = json.loads(output.read_text(encoding="utf-8"))
    _atomic_write(markdown, render_markdown(persisted))
    print(_json_text({"status": status, "output": _display_path(output), "markdown": _display_path(markdown), "forecast": forecast}))
    return 0 if status == "pass" else 2


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON output (default: results/generated/runtime-pilot.json, or runtime-forecast.json with --forecast-only)",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Markdown output (default: docs/validation/runtime_pilot.md; with --forecast-only, written only when given)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--datasets-per-cell", type=int, default=MATRIX_DATASETS_PER_CELL)
    parser.add_argument("--replicate-blocks", type=int, default=SHARD_REPLICATE_BLOCKS)
    parser.add_argument(
        "--pilot-cell",
        action="append",
        dest="pilot_cells",
        help="Pilot only this configured cell (repeatable; default: every configured cell)",
    )
    parser.add_argument(
        "--forecast-only",
        action="store_true",
        help="Forecast from measured runtimes (--cell-summary, --pilot-json) without fitting",
    )
    parser.add_argument("--cell-summary", type=Path, help="Aggregated validation cell_summary.csv (runtime_mean_seconds)")
    parser.add_argument(
        "--pilot-json",
        type=Path,
        action="append",
        help="Runtime-pilot JSON used for cells the cell summary lacks (repeatable; earlier sources win)",
    )
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
    if args.datasets_per_cell <= 0:
        raise SystemExit("--datasets-per-cell must be positive")
    if args.replicate_blocks <= 0 or args.replicate_blocks > args.datasets_per_cell:
        raise SystemExit("--replicate-blocks must be positive and at most --datasets-per-cell")
    if args.forecast_only:
        if args.pilot_cells:
            raise SystemExit("--pilot-cell applies to a pilot run, not --forecast-only")
        return _run_forecast_only(args)
    if args.cell_summary is not None or args.pilot_json:
        raise SystemExit("--cell-summary and --pilot-json require --forecast-only")
    if args.repeats <= 0:
        raise SystemExit("--repeats must be positive")
    return _run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
