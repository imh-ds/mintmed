"""Compare percentile, BC and BCa bootstrap intervals on run-1 matrix datasets.

Diagnostic only: this script is not part of the package or the validation gates.
For each dataset of the selected cells it reproduces the exact run-1 analysis
(same data and analysis seeds, frozen config), keeps the 399 bootstrap
replicate estimates, computes a leave-one-out jackknife for the BCa
acceleration, and writes one row per (cell, replicate, effect). The results are
summarized in docs/validation/interval_correction_check.md.

Usage:
    python scripts/compare_bootstrap_intervals.py CELL[,CELL...] OUTPUT.csv [WORKERS]
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from mintmed.api import analyze_mediation
from mintmed.experiments.mediation_validation import (
    _prepare_spec,
    cell_definition,
    cell_truth,
    generate_cell,
    load_config,
    seed_pair,
)

CONFIG = load_config(Path("configs/mediation_validation.yaml"))
EFFECTS = ("TE", "PNDE", "TNIE")
ALPHA = 0.05


def _interval(replicates: np.ndarray, estimate: float, acceleration: float) -> tuple[float, float]:
    below = np.mean(replicates < estimate) + 0.5 * np.mean(replicates == estimate)
    below = min(max(below, 1.0 / (2 * len(replicates))), 1.0 - 1.0 / (2 * len(replicates)))
    z0 = norm.ppf(below)
    probabilities = []
    for z_alpha in (norm.ppf(ALPHA / 2), norm.ppf(1 - ALPHA / 2)):
        shifted = z0 + z_alpha
        probabilities.append(norm.cdf(z0 + shifted / (1.0 - acceleration * shifted)))
    lower, upper = np.percentile(replicates, [100 * probabilities[0], 100 * probabilities[1]], method="linear")
    return float(lower), float(upper)


def _acceleration(jackknife: np.ndarray) -> float:
    centered = jackknife.mean() - jackknife
    denominator = 6.0 * np.sum(centered**2) ** 1.5
    return float(np.sum(centered**3) / denominator) if denominator > 0 else 0.0


def run_one(task: tuple[str, int]) -> list[dict]:
    cell_id, replicate = task
    started = time.perf_counter()
    cell = cell_definition(cell_id)
    data_seed, analysis_seed = seed_pair(CONFIG.master_seed, cell.ordinal, replicate)
    fixture = generate_cell(cell_id, data_seed)
    spec = _prepare_spec(fixture, CONFIG, analysis_seed)
    result = analyze_mediation(fixture.data, spec)
    point = {effect.name: float(effect.estimate) for effect in result.effects}
    records = [record for record in result.bootstrap.replicates if record.get("status") == "ok"]
    percentile = {interval.name: (interval.lower, interval.upper) for interval in result.bootstrap.intervals}

    point_spec = replace(spec, computation=replace(spec.computation, bootstrap=0))
    jackknife: dict[str, list[float]] = {name: [] for name in EFFECTS}
    for row in range(len(fixture.data)):
        loo = fixture.data.drop(index=fixture.data.index[row])
        loo_result = analyze_mediation(loo, point_spec)
        estimates = {effect.name: float(effect.estimate) for effect in loo_result.effects}
        for name in EFFECTS:
            jackknife[name].append(estimates.get(name, np.nan))

    truth = dict(zip(EFFECTS, cell_truth(cell_id)))
    rows = []
    for name in EFFECTS:
        replicates = np.array([float(record[name]) for record in records if record.get(name) is not None])
        jack = np.array(jackknife[name], dtype=float)
        acceleration = _acceleration(jack[np.isfinite(jack)])
        bc = _interval(replicates, point[name], 0.0)
        bca = _interval(replicates, point[name], acceleration)
        rows.append(
            {
                "cell_id": cell_id,
                "replicate": replicate,
                "effect": name,
                "truth": truth[name],
                "estimate": point[name],
                "successful": len(replicates),
                "pct_lower": percentile[name][0],
                "pct_upper": percentile[name][1],
                "bc_lower": bc[0],
                "bc_upper": bc[1],
                "bca_lower": bca[0],
                "bca_upper": bca[1],
                "acceleration": acceleration,
                "overall_status": result.diagnostics["overall_status"],
                "seconds": time.perf_counter() - started,
            }
        )
    return rows


def main() -> None:
    cells = sys.argv[1].split(",")
    output = Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    tasks = [(cell_id, replicate) for cell_id in cells for replicate in range(CONFIG.replicates)]
    rows: list[dict] = []
    with Pool(workers) as pool:
        for index, result in enumerate(pool.imap_unordered(run_one, tasks, chunksize=1), start=1):
            rows.extend(result)
            if index % 25 == 0:
                print(f"{index}/{len(tasks)} datasets", flush=True)
                pd.DataFrame(rows).to_csv(output, index=False)
    pd.DataFrame(rows).sort_values(["cell_id", "replicate", "effect"]).to_csv(output, index=False)
    print(json.dumps({"datasets": len(tasks), "rows": len(rows)}))


if __name__ == "__main__":
    main()
