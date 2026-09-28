"""Compare candidate small-sample interval fixes on validation-matrix datasets.

Diagnostic only: this script is not part of the package or the validation gates.
For each dataset it reproduces the validation analysis (same generators and
frozen v2 settings, with a chosen master seed), keeps the bootstrap replicate
estimates, and computes several intervals from the same replicates:

- ``pct``: the current percentile interval (2.5%, 97.5%);
- ``exp``: the expanded percentile interval (Hesterberg 2015), whose tail
  probability is 2 * Phi(-sqrt(n / (n - 1)) * t_{0.975, n - 1}) for sample size n;
- ``tse``: estimate +/- t_{0.975, n - 1} * bootstrap SD;
- ``bc``: the bias-corrected percentile interval.

Usage:
    python scripts/compare_interval_fixes.py CONFIG MASTER_SEED CELL[,CELL...] OUTPUT.csv [WORKERS]
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
from scipy.stats import norm, t

from mintmed.api import analyze_mediation
from mintmed.experiments.mediation_validation import (
    _prepare_spec,
    cell_definition,
    cell_truth,
    generate_cell,
    load_config,
    seed_pair,
)

ALPHA = 0.05
_STATE: dict[str, object] = {}


def _init(config_path: str, master_seed: int) -> None:
    _STATE["config"] = replace(load_config(Path(config_path)), master_seed=master_seed)


def _bc(replicates: np.ndarray, estimate: float) -> tuple[float, float]:
    below = np.mean(replicates < estimate) + 0.5 * np.mean(replicates == estimate)
    below = min(max(below, 1.0 / (2 * len(replicates))), 1.0 - 1.0 / (2 * len(replicates)))
    z0 = norm.ppf(below)
    probabilities = [norm.cdf(2 * z0 + norm.ppf(q)) for q in (ALPHA / 2, 1 - ALPHA / 2)]
    lower, upper = np.percentile(replicates, [100 * p for p in probabilities])
    return float(lower), float(upper)


def intervals(replicates: np.ndarray, estimate: float, n: int) -> dict[str, tuple[float, float]]:
    t_crit = t.ppf(1 - ALPHA / 2, n - 1)
    tail = norm.cdf(-np.sqrt(n / (n - 1)) * t_crit)
    sd = float(np.std(replicates, ddof=1))
    return {
        "pct": tuple(float(v) for v in np.percentile(replicates, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])),
        "exp": tuple(float(v) for v in np.percentile(replicates, [100 * tail, 100 * (1 - tail)])),
        "tse": (estimate - t_crit * sd, estimate + t_crit * sd),
        "bc": _bc(replicates, estimate),
    }


def run_one(task: tuple[str, int]) -> list[dict]:
    cell_id, replicate = task
    config = _STATE["config"]
    started = time.perf_counter()
    cell = cell_definition(cell_id)
    data_seed, analysis_seed = seed_pair(config.master_seed, cell.ordinal, replicate)
    fixture = generate_cell(cell_id, data_seed)
    spec = _prepare_spec(fixture, config, analysis_seed)
    result = analyze_mediation(fixture.data, spec)
    point = {effect.name: float(effect.estimate) for effect in result.effects}
    records = [record for record in result.bootstrap.replicates if record.get("status") == "ok"]
    truth = dict(zip(("TE", "PNDE", "TNIE"), cell_truth(cell_id)))
    rows = []
    for name in ("TE", "PNDE", "TNIE"):
        values = np.array([float(record[name]) for record in records if record.get(name) is not None])
        row = {
            "master_seed": config.master_seed,
            "cell_id": cell_id,
            "replicate": replicate,
            "effect": name,
            "truth": truth[name],
            "estimate": point[name],
            "successful": len(values),
            "n": len(fixture.data),
            "seconds": time.perf_counter() - started,
        }
        for method, (lower, upper) in intervals(values, point[name], len(fixture.data)).items():
            row[f"{method}_lower"] = lower
            row[f"{method}_upper"] = upper
        rows.append(row)
    return rows


def main() -> None:
    config_path, master_seed = sys.argv[1], int(sys.argv[2])
    cells = sys.argv[3].split(",")
    output = Path(sys.argv[4])
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 16
    replicates = load_config(Path(config_path)).replicates
    tasks = [(cell_id, replicate) for cell_id in cells for replicate in range(replicates)]
    rows: list[dict] = []
    with Pool(workers, initializer=_init, initargs=(config_path, master_seed)) as pool:
        for index, result in enumerate(pool.imap_unordered(run_one, tasks, chunksize=1), start=1):
            rows.extend(result)
            if index % 100 == 0:
                print(f"{index}/{len(tasks)} datasets", flush=True)
                pd.DataFrame(rows).to_csv(output, index=False)
    pd.DataFrame(rows).sort_values(["cell_id", "replicate", "effect"]).to_csv(output, index=False)
    print(json.dumps({"datasets": len(tasks), "rows": len(rows)}))


if __name__ == "__main__":
    main()
