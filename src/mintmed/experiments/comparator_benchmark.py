"""Shardable runner for the Task 17 R comparators (``mediation::mediate()`` and lavaan).

The runner implements the aggregation contract of ``scripts/aggregate_shards.py``
so that ``.github/workflows/sharded_benchmark.yml`` can run the comparators
(dispatch with ``with_r: "true"``)::

    python -m mintmed.experiments.comparator_benchmark --config configs/mediation_validation_v3.yaml \\
        --output OUT --cell-id cell01_linear_n100 --replicate-block 0of4 [--tool mediation|lavaan|all]

For its selection it exports the exact datasets Mintmed analysed (reusing
``scripts/export_validation_datasets.py``) to a temporary directory, runs
``benchmarks/comparators/r/run_<tool>.R`` through ``Rscript`` and writes
``raw_metrics.csv`` plus ``metadata.json``.

Row contract: one row per ``(tool, cell_id, replicate)``. The combination key
includes the tool so that a shard may run one tool or both, and every tool
appears for every cell: a cell outside a tool's support matrix yields a row
with status ``not_estimable`` and the reason, never a missing row or an
imputed value. Per-mode, per-effect results live in ``records_json`` as
``{mode: {effect: record}}``, where a record is Mintmed's canonical
``metric_record`` (truth, estimate, bias, lower, upper, coverage, width,
zero_exclusion, interval_available, status, reason) plus the comparator's
runtime and draw counts.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import yaml

from .mediation_validation import (
    ValidationConfig,
    cell_definition,
    cell_truth,
    load_config,
    metric_record,
    replicate_block_range,
    seed_pair,
    selected_combinations,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
R_DIR = REPO_ROOT / "benchmarks" / "comparators" / "r"
SUPPORT_MATRIX_PATH = REPO_ROOT / "benchmarks" / "comparators" / "support_matrix.json"
EXPORTER_PATH = REPO_ROOT / "scripts" / "export_validation_datasets.py"

TOOLS: tuple[str, ...] = ("mediation", "lavaan")
MODES: tuple[str, ...] = ("primary", "secondary")
QUASI_BAYES_SIMS = 1000  # mediate()'s package default, the secondary (descriptive) mode
SEED_MODULUS = 2147483647  # R seed = analysis_seed mod (2^31 - 1); see common.R

COMBINATION_COLUMNS: tuple[str, str, str] = ("tool", "cell_id", "replicate")
RAW_COLUMNS: tuple[str, ...] = (
    "tool",
    "cell_id",
    "replicate",
    "data_seed",
    "analysis_seed",
    "r_seed",
    "config_hash",
    "supported",
    "status",
    "failure_message",
    "runtime_seconds",
    "dataset_sha256",
    "records_json",
    "provenance_json",
)
LONG_COLUMNS: tuple[str, ...] = (
    "tool", "mode", "cell_id", "replicate", "effect", "estimate", "lower", "upper",
    "status", "message", "runtime_seconds", "sims_requested", "sims_successful",
    "r_seed", "data_seed", "analysis_seed", "dataset_sha256", "model",
    "point_method", "interval_method", "r_version", "package", "package_version",
)
# Record statuses: ok / ok_warnings (estimate available), not_estimable (outside
# the support matrix), error (the comparator failed on this dataset),
# runner_failed (the R process failed) and missing_output (the R runner
# returned no row for this mode and effect).
ESTIMATED_STATUSES = frozenset({"ok", "ok_warnings"})
FAILED_STATUSES = frozenset({"error", "runner_failed", "missing_output"})

# Cell 10 moderated-mediation truths (mediation_validation.extract_metrics).
_MODERATED_TRUTHS = {"TNIE_W0": 0.09, "TNIE_W1": 0.36, "TNIE_difference": 0.27}

# ---------------------------------------------------------------------------
# Harness agreement tolerances (T17-S5). Declared before the Stage 1 run and
# enforced by tests/integration/test_comparator_harness.py against Mintmed
# point estimates computed fresh on the same exported datasets. They validate
# the harness (estimand mapping, model specification, data transfer); they are
# not Stage 1 comparison margins, which live in comparator_benchmark_reporting.

EXACT_POINT_TOLERANCE = 1e-8
"""Absolute tolerance where a comparator's point estimate is Mintmed's plug-in value.

Applies to lavaan (both modes) in every supported cell and to ``mediate()``'s
bootstrap-mode point estimate in the cells whose outcome is linear in the
mediator (01-05, 10, 13-16). There both reduce algebraically to the OLS path
products Mintmed reports: lavaan's ML regression coefficients equal OLS in a
recursive observed-variable model, and ``med.fun``'s single shared mediator
draw cancels from every contrast when Y is linear in M. Measured differences
are below 1e-15 (docs/validation/comparator_support.md), so 1e-8 leaves seven
orders of magnitude for BLAS, platform and optimizer-stopping differences
(lavaan's nlminb on Linux CI) while any estimand or specification error, which
moves an effect by at least ~1e-3 on these datasets, still fails.
"""

QUASI_BAYES_TOLERANCE_MULTIPLIER = 5.0
"""Multiple of the Monte Carlo SE allowed between ``mediate()``'s quasi-Bayesian point and Mintmed.

In the linear-in-M cells the quasi-Bayesian point is the mean of ``sims``
independent simulated effects whose expectation is the plug-in value (the
simulated coefficients of the two node models are independent, so
E[a* b*] = a b). Its Monte Carlo SE is SD(draws) / sqrt(sims), with SD(draws)
estimated from the run's own percentile interval (see
:func:`quasi_bayes_tolerance`). Five SEs gives a two-sided false-alarm rate of
about 6e-7 per comparison under normality (about 1e-4 over the ~150 checked
effects) and still leaves slack for the interval-based SD estimate being off
by tens of percent, since the draws of a product are not exactly normal.
"""

QUASI_BAYES_INTERVAL_Z = 1.959963984540054
"""Normal quantile converting a 95% percentile interval width into a draw SD: SD ~ width / (2 z)."""

MONTE_CARLO_AVERAGE_SEEDS = 200
"""Seeds averaged in the nonlinear-cell harness check of ``mediate()`` (cells 08, 09, 11).

There the bootstrap-mode point estimate carries Monte Carlo error from one set
of ``n`` simulated mediator values (seed-to-seed SD 0.015-0.044 on replicate 0,
docs/validation/comparator_support.md) that does not shrink with ``sims``. The
average over 200 seeds has SE 0.001-0.003, tight enough to detect a model or
basis mismatch of the size of the TNIE itself (0.04-0.24).
"""

MONTE_CARLO_AVERAGE_TOLERANCE_MULTIPLIER = 4.0
"""Multiple of the seed-average's own SE (sample SD / sqrt(seeds)) allowed from Mintmed's exact value.

Four SEs: a false-alarm rate of about 6e-5 per checked effect (two effects in
three cells), with the SE measured on the same run rather than assumed. This
is a harness check on one dataset, not a verdict on either method.
"""


def quasi_bayes_tolerance(lower: float, upper: float, sims: int) -> float:
    """Allowed |quasi-Bayesian point - Mintmed| for one effect of one dataset.

    ``QUASI_BAYES_TOLERANCE_MULTIPLIER * SD(draws) / sqrt(sims)`` with
    ``SD(draws) = (upper - lower) / (2 * QUASI_BAYES_INTERVAL_Z)``, floored at
    :data:`EXACT_POINT_TOLERANCE` (a structural zero has a [0, 0] interval).
    """

    if sims <= 0 or not (math.isfinite(lower) and math.isfinite(upper)) or upper < lower:
        raise ValueError("quasi-Bayesian tolerance needs a finite interval and a positive draw count")
    draw_sd = (upper - lower) / (2.0 * QUASI_BAYES_INTERVAL_Z)
    return max(EXACT_POINT_TOLERANCE, QUASI_BAYES_TOLERANCE_MULTIPLIER * draw_sd / math.sqrt(sims))


def monte_carlo_average_tolerance(values: Sequence[float]) -> float:
    """Allowed |mean(values) - Mintmed| for a seed average: multiplier x sample SD / sqrt(len)."""

    count = len(values)
    if count < 2:
        raise ValueError("a Monte Carlo average needs at least two seeds")
    mean = math.fsum(values) / count
    sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (count - 1))
    return max(EXACT_POINT_TOLERANCE, MONTE_CARLO_AVERAGE_TOLERANCE_MULTIPLIER * sd / math.sqrt(count))


REQUIRE_R_ENV = "MINTMED_REQUIRE_R"
"""When set to ``1``, the R-dependent tests fail instead of skipping if R is unavailable (CI)."""


def r_packages_available(rscript: str | None) -> bool:
    """Whether ``rscript`` runs and loads mediation, lavaan and jsonlite."""

    if rscript is None:
        return False
    try:
        completed = subprocess.run(
            [rscript, "-e", "suppressWarnings(suppressPackageStartupMessages({library(mediation); library(lavaan); library(jsonlite)}))"],
            capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def effect_truths(cell_id: str) -> dict[str, float]:
    """Return the population truth of every effect Mintmed reports for ``cell_id``."""

    definition = cell_definition(cell_id)
    if set(definition.metric_names) == set(_MODERATED_TRUTHS):
        return {name: _MODERATED_TRUTHS[name] for name in definition.metric_names}
    truth = dict(zip(("TE", "PNDE", "TNIE"), cell_truth(cell_id), strict=True))
    return {name: truth[name] for name in definition.metric_names}


def r_seed(analysis_seed: int | str) -> int:
    """Return the R ``set.seed`` value derived from a dataset's analysis seed."""

    return int(str(analysis_seed)) % SEED_MODULUS


@lru_cache(maxsize=1)
def load_support_matrix(path: str | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{tool: {"supported": frozenset, "not_estimable": {cell: reason}}}``."""

    source = Path(path) if path is not None else SUPPORT_MATRIX_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    tools = payload["tools"]
    if set(tools) != set(TOOLS):
        raise ValueError(f"support matrix must list exactly the tools {TOOLS}")
    matrix = {}
    for tool, entry in tools.items():
        supported = frozenset(entry["supported"])
        reasons = dict(entry["not_estimable"])
        if supported & set(reasons):
            raise ValueError(f"{tool}: a cell is both supported and not estimable")
        matrix[tool] = {"supported": supported, "not_estimable": reasons}
    return matrix


def is_supported(tool: str, cell_id: str) -> bool:
    return cell_id in load_support_matrix()[tool]["supported"]


def not_estimable_reason(tool: str, cell_id: str) -> str:
    reasons = load_support_matrix()[tool]["not_estimable"]
    return reasons.get(cell_id, f"{cell_id} is not in the {tool} support matrix")


def expected_combinations(config: ValidationConfig) -> set[tuple[str, str, int]]:
    """Every tool x cell x replicate, supported or not (unsupported rows are explicit)."""

    return {
        (tool, cell_id, replicate)
        for tool in TOOLS
        for cell_id in config.cell_ids
        for replicate in range(config.replicates)
    }


def expected_row_count(config: ValidationConfig) -> int:
    return len(expected_combinations(config))


def comparator_record(
    truth: float,
    estimate: float | None,
    lower: float | None,
    upper: float | None,
    *,
    status: str,
    reason: str | None = None,
    runtime_seconds: float | None = None,
    sims_requested: int | None = None,
    sims_successful: int | None = None,
) -> dict[str, Any]:
    """Mintmed's canonical metric record plus comparator bookkeeping.

    Estimates and intervals are only kept for estimated statuses, so a failed
    or unsupported record can never contribute a value.
    """

    estimated = status in ESTIMATED_STATUSES
    finite = lambda value: value is not None and math.isfinite(float(value))  # noqa: E731
    point = float(estimate) if estimated and finite(estimate) else None
    has_interval = estimated and finite(lower) and finite(upper)
    record = metric_record(
        truth,
        point,
        float(lower) if has_interval else None,
        float(upper) if has_interval else None,
        status=status,
        reason=reason or None,
    )
    record.update(
        {
            "runtime_seconds": runtime_seconds,
            "sims_requested": sims_requested,
            "sims_successful": sims_successful,
        }
    )
    return record


def not_estimable_records(tool: str, cell_id: str, modes: Sequence[str] = MODES) -> dict[str, dict[str, Any]]:
    reason = not_estimable_reason(tool, cell_id)
    truths = effect_truths(cell_id)
    return {
        mode: {
            effect: comparator_record(truth, None, None, None, status="not_estimable", reason=reason)
            for effect, truth in truths.items()
        }
        for mode in modes
    }


def row_status(records: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> str:
    """Summarise a row's record statuses into one row status."""

    statuses = [str(record["status"]) for effects in records.values() for record in effects.values()]
    if not statuses:
        return "missing_output"
    if all(status == "not_estimable" for status in statuses):
        return "not_estimable"
    if all(status == "runner_failed" for status in statuses):
        return "runner_failed"
    failed = [status for status in statuses if status in FAILED_STATUSES]
    if failed and len(failed) == len(statuses):
        return "failed"
    if failed:
        return "partial"
    if any(status == "ok_warnings" for status in statuses):
        return "ok_warnings"
    return "ok"


def _optional_float(text: Any) -> float | None:
    if text is None:
        return None
    value = str(text).strip()
    if not value or value.upper() == "NA":
        return None
    return float(value)  # Python's float() is correctly rounded for %.17g text


def _optional_int(text: Any) -> int | None:
    value = _optional_float(text)
    return None if value is None else int(value)


def read_long_output(path: Path) -> pd.DataFrame:
    """Read an R runner's long CSV with every column as text (seeds stay exact)."""

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(LONG_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: R runner output lacks columns {sorted(missing)}")
    return frame


def records_from_long(
    long: pd.DataFrame,
    tool: str,
    cell_id: str,
    replicate: int,
    modes: Sequence[str] = MODES,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Build ``{mode: {effect: record}}`` for one dataset from the runner's long rows.

    Every expected mode and effect gets a record; a row the runner did not
    write becomes ``missing_output``. Returns the records and per-row details.
    """

    truths = effect_truths(cell_id)
    subset = long.loc[
        (long["tool"] == tool) & (long["cell_id"] == cell_id) & (long["replicate"].astype(int) == int(replicate))
    ]
    records: dict[str, dict[str, Any]] = {}
    details: dict[str, Any] = {"models": {}, "point_methods": {}, "interval_methods": {}, "messages": []}
    for mode in modes:
        records[mode] = {}
        for effect, truth in truths.items():
            match = subset.loc[(subset["mode"] == mode) & (subset["effect"] == effect)]
            if len(match) != 1:
                records[mode][effect] = comparator_record(
                    truth, None, None, None, status="missing_output",
                    reason=f"R runner wrote {len(match)} row(s) for {mode}/{effect}",
                )
                continue
            item = match.iloc[0]
            records[mode][effect] = comparator_record(
                truth,
                _optional_float(item["estimate"]),
                _optional_float(item["lower"]),
                _optional_float(item["upper"]),
                status=str(item["status"]),
                reason=str(item["message"]) or None,
                runtime_seconds=_optional_float(item["runtime_seconds"]),
                sims_requested=_optional_int(item["sims_requested"]),
                sims_successful=_optional_int(item["sims_successful"]),
            )
            if item["model"]:
                details["models"][mode] = str(item["model"])
            if item["point_method"]:
                details["point_methods"][f"{mode}/{effect}"] = str(item["point_method"])
            if item["interval_method"]:
                details["interval_methods"][f"{mode}/{effect}"] = str(item["interval_method"])
            for key in ("r_version", "package", "package_version", "dataset_sha256", "r_seed"):
                if item[key]:
                    details[key] = str(item[key])
    return records, details


def _runtime(records: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> float | None:
    """Sum of per-mode runtimes (every effect of a mode repeats the mode's runtime)."""

    total = 0.0
    seen = False
    for effects in records.values():
        values = [record.get("runtime_seconds") for record in effects.values() if record.get("runtime_seconds") is not None]
        if values:
            total += float(values[0])
            seen = True
    return total if seen else None


def build_row(
    *,
    config: ValidationConfig,
    tool: str,
    cell_id: str,
    replicate: int,
    records: Mapping[str, Mapping[str, Mapping[str, Any]]],
    provenance: Mapping[str, Any],
    failure_message: str | None = None,
    dataset_sha256: str | None = None,
) -> dict[str, Any]:
    cell = cell_definition(cell_id)
    data_seed, analysis_seed = seed_pair(config.master_seed, cell.ordinal, replicate)
    status = row_status(records)
    if failure_message is None and status in {"failed", "partial", "runner_failed", "missing_output"}:
        messages = sorted(
            {
                str(record.get("reason"))
                for effects in records.values()
                for record in effects.values()
                if record.get("status") in FAILED_STATUSES and record.get("reason")
            }
        )
        failure_message = " | ".join(messages)[:1000] or None
    return {
        "tool": tool,
        "cell_id": cell_id,
        "replicate": int(replicate),
        "data_seed": str(data_seed),
        "analysis_seed": str(analysis_seed),
        "r_seed": r_seed(analysis_seed),
        "config_hash": config.config_hash,
        "supported": is_supported(tool, cell_id),
        "status": status,
        "failure_message": failure_message,
        "runtime_seconds": _runtime(records),
        "dataset_sha256": dataset_sha256,
        "records_json": json.dumps(records, sort_keys=True, separators=(",", ":")),
        "provenance_json": json.dumps(dict(provenance), sort_keys=True, separators=(",", ":")),
    }


def find_rscript(explicit: str | None = None) -> str | None:
    """Locate Rscript: --rscript, $MINTMED_RSCRIPT, PATH, then the standard Windows install."""

    for candidate in (explicit, os.environ.get("MINTMED_RSCRIPT")):
        if candidate:
            return candidate
    found = shutil.which("Rscript")
    if found:
        return found
    if sys.platform == "win32":
        installs = sorted(Path("C:/Program Files/R").glob("R-*/bin/Rscript.exe"))
        if installs:
            return str(installs[-1])
    return None


def _load_exporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_mintmed_dataset_exporter", EXPORTER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {EXPORTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r_environment(rscript: str) -> dict[str, Any]:
    """Return versions.R's JSON, or an error description (never raises)."""

    try:
        completed = subprocess.run(
            [rscript, str(R_DIR / "versions.R")], capture_output=True, text=True, timeout=300, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": f"versions.R could not run: {exc}"}
    if completed.returncode != 0:
        return {"error": f"versions.R exited {completed.returncode}: {completed.stderr.strip()[-500:]}"}
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"error": "versions.R printed no JSON"}


def run_r_tool(
    rscript: str,
    tool: str,
    manifest_path: Path,
    output_path: Path,
    *,
    boot_sims: int,
    qb_sims: int,
    modes: Sequence[str] = MODES,
    timeout: float | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    """Run one R runner; return its long output, or ``None`` and the failure message."""

    script = R_DIR / f"run_{tool}.R"
    command = [rscript, str(script), "--manifest", str(manifest_path), "--output", str(output_path),
               "--modes", ",".join(modes)]
    if tool == "mediation":
        command += ["--boot-sims", str(boot_sims), "--qb-sims", str(qb_sims)]
    else:
        command += ["--bootstrap", str(boot_sims)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{script.name} could not run: {exc}"
    if completed.returncode != 0 or not output_path.is_file():
        tail = (completed.stderr or completed.stdout or "").strip()[-800:]
        return None, f"{script.name} exited {completed.returncode}: {tail}"
    try:
        return read_long_output(output_path), None
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return None, f"{script.name} output unreadable: {exc}"


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.is_file() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS, extrasaction="raise", lineterminator="\n")
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in RAW_COLUMNS})
        handle.flush()
        os.fsync(handle.fileno())


def read_raw(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"config_hash": str, "data_seed": str, "analysis_seed": str, "cell_id": str, "tool": str})


def _existing_rows(path: Path, config: ValidationConfig) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=RAW_COLUMNS)
    raw = read_raw(path)
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError("raw_metrics.csv columns do not match the comparator raw-row contract")
    if raw.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    if set(raw["config_hash"].astype(str)) != {config.config_hash}:
        raise ValueError("raw_metrics.csv holds rows from another configuration; use a fresh --output")
    raw["replicate"] = raw["replicate"].astype(int)
    if raw.duplicated(subset=list(COMBINATION_COLUMNS)).any():
        raise ValueError("raw_metrics.csv contains duplicate combination keys")
    return raw


def _script_hashes() -> dict[str, str]:
    files = [R_DIR / name for name in ("common.R", "run_mediation.R", "run_lavaan.R", "pins.R")]
    files.append(SUPPORT_MATRIX_PATH)
    return {path.name: _sha256(path) for path in files if path.is_file()}


def run(
    config: ValidationConfig,
    output_dir: Path,
    *,
    config_path: str | Path,
    cell_ids: Sequence[str] | None = None,
    replicate: int | None = None,
    replicate_start: int = 0,
    replicate_stop: int | None = None,
    tools: Sequence[str] = TOOLS,
    rscript: str | None = None,
    boot_sims: int | None = None,
    qb_sims: int = QUASI_BAYES_SIMS,
    keep_datasets: Path | None = None,
    no_report: bool = False,
    r_timeout: float | None = None,
) -> pd.DataFrame:
    """Run the selected comparators and append one raw row per tool x cell x replicate."""

    unknown = set(tools) - set(TOOLS)
    if unknown or not tools:
        raise ValueError(f"--tool must be one of {TOOLS} or all")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_text(output / "resolved_config.yaml", yaml.safe_dump(config.canonical_dict, sort_keys=False))
    started = time.perf_counter()
    boot = int(config.bootstrap_replicates if boot_sims is None else boot_sims)
    selected = selected_combinations(
        config,
        cell_ids=cell_ids,
        replicate=replicate,
        replicate_start=replicate_start,
        replicate_stop=replicate_stop,
    )
    raw_path = output / "raw_metrics.csv"
    existing = _existing_rows(raw_path, config)
    done = set(existing[list(COMBINATION_COLUMNS)].itertuples(index=False, name=None))
    pending = {
        tool: [(cell_id, rep) for cell_id, rep in selected if (tool, cell_id, rep) not in done]
        for tool in tools
    }
    settings = {
        "boot_sims": boot,
        "qb_sims": int(qb_sims),
        "config_bootstrap_replicates": int(config.bootstrap_replicates),
        "modes": list(MODES),
        "seed_rule": "set.seed(int(analysis_seed) mod 2147483647), Mersenne-Twister/Inversion/Rejection, before every fit",
    }
    base_provenance = {"settings": settings, "scripts_sha256": _script_hashes()}

    # Unsupported cells need no R: write their explicit not_estimable rows first.
    rows: list[dict[str, Any]] = []
    for tool, combos in pending.items():
        for cell_id, rep in combos:
            if not is_supported(tool, cell_id):
                rows.append(
                    build_row(
                        config=config, tool=tool, cell_id=cell_id, replicate=rep,
                        records=not_estimable_records(tool, cell_id),
                        provenance={**base_provenance, "reason": not_estimable_reason(tool, cell_id)},
                    )
                )
    _append_rows(raw_path, rows)
    written = len(rows)

    needed = {tool: [combo for combo in combos if is_supported(tool, combo[0])] for tool, combos in pending.items()}
    r_env: dict[str, Any] = {}
    if any(needed.values()):
        rscript_path = find_rscript(rscript)
        with tempfile.TemporaryDirectory(prefix="mintmed-comparators-") as scratch:
            dataset_dir = Path(keep_datasets) if keep_datasets is not None else Path(scratch) / "datasets"
            if rscript_path is not None:
                r_env = r_environment(rscript_path)
            manifest = _export_needed(config, config_path, dataset_dir, needed)
            for tool, combos in needed.items():
                if not combos:
                    continue
                tool_rows = _run_tool_rows(
                    config, tool, combos, manifest, dataset_dir, Path(scratch), rscript_path,
                    boot=boot, qb_sims=qb_sims, provenance={**base_provenance, "r_environment": r_env},
                    timeout=r_timeout,
                )
                _append_rows(raw_path, tool_rows)
                written += len(tool_rows)

    final = _existing_rows(raw_path, config)
    metadata = {
        "schema_version": 1,
        "experiment": config.experiment,
        "runner": "mintmed.experiments.comparator_benchmark",
        "config_hash": config.config_hash,
        "combination_columns": list(COMBINATION_COLUMNS),
        "expected_rows": expected_row_count(config),
        "observed_rows": int(len(final)),
        "rows_written_this_run": int(written),
        "tools": list(tools),
        "settings": settings,
        "r_environment": r_env,
        "scripts_sha256": base_provenance["scripts_sha256"],
        "runtime_seconds": float(time.perf_counter() - started),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": None,
        "charter_sha256": None,
    }
    _atomic_text(output / "metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    if not no_report:
        from .comparator_benchmark_reporting import write_report

        write_report(final, config, output)
    return final


def _export_needed(
    config: ValidationConfig,
    config_path: str | Path,
    dataset_dir: Path,
    needed: Mapping[str, Sequence[tuple[str, int]]],
) -> dict[str, Any]:
    combos = sorted({combo for items in needed.values() for combo in items})
    cells = sorted({cell_id for cell_id, _ in combos}, key=lambda value: cell_definition(value).ordinal)
    replicates = [rep for _, rep in combos]
    exporter = _load_exporter()
    return exporter.export(
        config,
        dataset_dir,
        config_path=str(config_path),
        cell_ids=cells,
        replicate_start=min(replicates),
        replicate_stop=max(replicates) + 1,
    )


def _run_tool_rows(
    config: ValidationConfig,
    tool: str,
    combos: Sequence[tuple[str, int]],
    manifest: Mapping[str, Any],
    dataset_dir: Path,
    scratch: Path,
    rscript: str | None,
    *,
    boot: int,
    qb_sims: int,
    provenance: Mapping[str, Any],
    timeout: float | None,
) -> list[dict[str, Any]]:
    wanted = set(combos)
    entries = [entry for entry in manifest["datasets"] if (entry["cell_id"], int(entry["replicate"])) in wanted]
    sha_by_key = {(entry["cell_id"], int(entry["replicate"])): entry["sha256"] for entry in entries}
    long: pd.DataFrame | None = None
    failure: str | None = None
    if rscript is None:
        failure = "Rscript not found (set MINTMED_RSCRIPT or put Rscript on PATH)"
    else:
        tool_manifest = dataset_dir / f"manifest_{tool}.json"
        tool_manifest.write_text(json.dumps({**manifest, "datasets": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        long, failure = run_r_tool(
            rscript, tool, tool_manifest, scratch / f"long_{tool}.csv",
            boot_sims=boot, qb_sims=qb_sims, timeout=timeout,
        )
    rows = []
    for cell_id, rep in combos:
        truths = effect_truths(cell_id)
        if long is None:
            records = {
                mode: {
                    effect: comparator_record(truth, None, None, None, status="runner_failed", reason=failure)
                    for effect, truth in truths.items()
                }
                for mode in MODES
            }
            details: dict[str, Any] = {}
        else:
            records, details = records_from_long(long, tool, cell_id, rep)
        rows.append(
            build_row(
                config=config, tool=tool, cell_id=cell_id, replicate=rep, records=records,
                provenance={**provenance, **details}, failure_message=failure,
                dataset_sha256=sha_by_key.get((cell_id, rep)),
            )
        )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell-id", action="append", dest="cell_ids")
    parser.add_argument("--replicate", type=int)
    parser.add_argument("--replicate-start", type=int, default=0)
    parser.add_argument("--replicate-stop", type=int)
    parser.add_argument("--replicate-block", help="shard block INDEX:COUNT (or INDEXofCOUNT) of the replicates")
    parser.add_argument("--tool", default="all", choices=[*TOOLS, "all"])
    parser.add_argument("--rscript", help="path to Rscript (default: $MINTMED_RSCRIPT, then PATH)")
    parser.add_argument("--boot-sims", type=int, help="bootstrap refits (default: the config's bootstrap_replicates)")
    parser.add_argument("--qb-sims", type=int, default=QUASI_BAYES_SIMS)
    parser.add_argument("--keep-datasets", type=Path, help="export the datasets here instead of a temporary directory")
    parser.add_argument("--no-report", action="store_true")
    try:
        arguments = parser.parse_args(argv)
        config = load_config(arguments.config)
        if arguments.replicate_block is not None:
            if arguments.replicate is not None or arguments.replicate_start != 0 or arguments.replicate_stop is not None:
                raise ValueError("--replicate-block cannot be combined with --replicate or explicit bounds")
            arguments.replicate_start, arguments.replicate_stop = replicate_block_range(
                config.replicates, arguments.replicate_block
            )
        run(
            config,
            arguments.output,
            config_path=arguments.config,
            cell_ids=arguments.cell_ids,
            replicate=arguments.replicate,
            replicate_start=arguments.replicate_start,
            replicate_stop=arguments.replicate_stop,
            tools=TOOLS if arguments.tool == "all" else (arguments.tool,),
            rscript=arguments.rscript,
            boot_sims=arguments.boot_sims,
            qb_sims=arguments.qb_sims,
            keep_datasets=arguments.keep_datasets,
            no_report=arguments.no_report,
        )
    except (OSError, ValueError) as exc:
        parser.print_usage()
        print(f"error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMBINATION_COLUMNS",
    "EXACT_POINT_TOLERANCE",
    "MODES",
    "MONTE_CARLO_AVERAGE_SEEDS",
    "MONTE_CARLO_AVERAGE_TOLERANCE_MULTIPLIER",
    "QUASI_BAYES_TOLERANCE_MULTIPLIER",
    "RAW_COLUMNS",
    "REQUIRE_R_ENV",
    "TOOLS",
    "comparator_record",
    "monte_carlo_average_tolerance",
    "quasi_bayes_tolerance",
    "r_packages_available",
    "effect_truths",
    "expected_combinations",
    "expected_row_count",
    "is_supported",
    "load_config",
    "load_support_matrix",
    "not_estimable_records",
    "r_seed",
    "records_from_long",
    "row_status",
    "run",
]
