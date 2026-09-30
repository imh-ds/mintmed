"""Measure the fixed-base-model point bias of the Task 18 mechanisms with Mintmed.

For every mechanism and N in ``SAMPLE_SIZES`` this fits the analyst's base
model with :func:`mintmed.analyze_mediation` (point estimates only, no
bootstrap) on ``--replicates`` datasets drawn at the calibration seed, and
prints a Markdown table of TNIE / PNDE bias with Monte Carlo standard errors.

Usage::

    python scripts/measure_mechanism_bias.py [--replicates 200] [--json out.json]
    python scripts/measure_mechanism_bias.py --outcome-sd
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mintmed.api import analyze_mediation  # noqa: E402
from mintmed.experiments.diagnostic_mechanisms import (  # noqa: E402
    CALIBRATION_SEED,
    MECHANISMS,
    SAMPLE_SIZES,
    dataset_seed,
    generate,
    mintmed_spec,
)


def _estimates(result) -> dict[str, float]:
    return {
        effect.name: float(effect.estimate)
        for effect in result.effects
        if effect.estimate is not None and math.isfinite(float(effect.estimate))
    }


def measure(replicates: int, master: int) -> list[dict]:
    rows: list[dict] = []
    for mechanism_id, mech in MECHANISMS.items():
        spec = mintmed_spec(mechanism_id)
        for n in SAMPLE_SIZES:
            biases: dict[str, list[float]] = {"TNIE": [], "PNDE": [], "TE": []}
            failures = 0
            started = time.perf_counter()
            for replicate in range(replicates):
                data = generate(mechanism_id, n, dataset_seed(master, mechanism_id, n, replicate))
                estimates = _estimates(analyze_mediation(data, spec))
                if not all(name in estimates for name in biases):
                    failures += 1
                    continue
                for name in biases:
                    biases[name].append(estimates[name] - mech.truth[name])
            row = {
                "mechanism": mechanism_id,
                "category": mech.category,
                "n": n,
                "replicates": replicates,
                "failures": failures,
                "outcome_sd": mech.outcome_sd,
                "seconds": time.perf_counter() - started,
            }
            for name, values in biases.items():
                arr = np.asarray(values, dtype=float)
                row[f"{name}_bias"] = float(arr.mean())
                row[f"{name}_bias_se"] = float(arr.std(ddof=1) / math.sqrt(arr.size))
                row[f"{name}_bias_sd_units"] = float(arr.mean() / mech.outcome_sd)
                row[f"{name}_empirical_sd"] = float(arr.std(ddof=1))
            rows.append(row)
            print(
                f"{mechanism_id:24s} n={n:3d} TNIE bias {row['TNIE_bias']:+.4f} "
                f"(SE {row['TNIE_bias_se']:.4f}) failures={failures} {row['seconds']:.1f}s",
                file=sys.stderr,
            )
    return rows


def markdown(rows: list[dict]) -> str:
    lines = [
        "| Mechanism | Category | N | TNIE bias (SE) | TNIE bias / SD(Y) | PNDE bias (SE) | TE bias (SE) | Failures |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['mechanism']} | {row['category']} | {row['n']} "
            f"| {row['TNIE_bias']:+.4f} ({row['TNIE_bias_se']:.4f}) "
            f"| {row['TNIE_bias_sd_units']:+.3f} "
            f"| {row['PNDE_bias']:+.4f} ({row['PNDE_bias_se']:.4f}) "
            f"| {row['TE_bias']:+.4f} ({row['TE_bias_se']:.4f}) "
            f"| {row['failures']} |"
        )
    return "\n".join(lines)


def outcome_sd_table(draws: int) -> str:
    lines = []
    for mechanism_id in MECHANISMS:
        sd = float(generate(mechanism_id, draws, 0)["Y"].std(ddof=1))
        lines.append(f'    "{mechanism_id}": {sd:.4f},')
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--master", type=int, default=CALIBRATION_SEED)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--outcome-sd", action="store_true", help="print the population outcome SD table")
    args = parser.parse_args(argv)
    if args.outcome_sd:
        print(outcome_sd_table(10**7))
        return 0
    rows = measure(args.replicates, args.master)
    if args.json is not None:
        args.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
