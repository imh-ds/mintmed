"""Match the Task 18 warning thresholds on the calibration-seed run (T18-S4).

Input: the aggregated ``raw_metrics.csv`` of the calibration run of
``mintmed.experiments.information_diagnostic`` (seed 20261001) and its config.

For every arm and node (outcome: information, conventional, and the two
information sensitivities; mediator: information, conventional) and every
nominal threshold ``t`` of the grid (0.001 to 0.200 in steps of 0.001), the
false-warning rate is computed on every effect-correct null mechanism
(N1-N4) at every N. The warning rule is the one of
``information_diagnostic_reporting``: status ``ok`` and p-value ``<= t``;
an unavailable check is no warning and stays in the denominator.

Frozen-threshold rule (lead-agent refinement of the plan's pooled rule): the
frozen threshold is the **largest** grid value ``t`` whose false-warning rate is
``<= 0.05`` on **every** effect-correct null mechanism at **every** N.

Reported descriptively: the plan's pooled-rule threshold (largest ``t`` whose
rate pooled over N1-N4 and all N is ``<= 0.05``), per-N thresholds (the frozen
rule at one N), the binding (mechanism, N) cell, and, at the frozen
thresholds, the warning rates of all nine mechanisms by N and arm with Wilson
intervals. No gate outcome is declared: calibration results are not
evaluation evidence.

The script is deterministic (no randomness)::

    python scripts/calibrate_diagnostic_thresholds.py \\
        --raw results/generated/archive/github/<id>/aggregated-benchmark/raw_metrics.csv \\
        --config configs/information_diagnostic_calibration.yaml --output OUT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mintmed.experiments import diagnostic_mechanisms as dm
from mintmed.experiments import information_diagnostic as idg
from mintmed.experiments.information_diagnostic_reporting import (
    ARMS,
    arm_available,
    arm_warnings,
    check_complete_grid,
    wilson,
)

TARGET_RATE = 0.05
GRID = tuple(round(0.001 * i, 3) for i in range(1, 201))
ARM_NODES: tuple[tuple[str, str], ...] = (
    ("information", "outcome"),
    ("conventional", "outcome"),
    ("information_insample", "outcome"),
    ("information_k20", "outcome"),
    ("information", "mediator"),
    ("conventional", "mediator"),
)
NULL_CATEGORY = "effect_correct_null"


def null_mechanisms() -> list[str]:
    return [mid for mid, mech in dm.MECHANISMS.items() if mech.category == NULL_CATEGORY]


def _p_values(frame: pd.DataFrame, arm: str) -> np.ndarray:
    """p-values with unavailable checks set to +inf (never warn)."""

    p = pd.to_numeric(frame[ARMS[arm][0]], errors="coerce").to_numpy(dtype=float)
    ok = arm_available(frame, arm)
    return np.where(ok & ~np.isnan(p), p, np.inf)


def false_warning_curves(raw: pd.DataFrame, grid: tuple[float, ...] = GRID) -> pd.DataFrame:
    """Warnings at every grid threshold for every arm, node, null mechanism and N."""

    thresholds = np.asarray(grid)
    records = []
    nulls = null_mechanisms()
    for arm, node in ARM_NODES:
        node_rows = raw.loc[raw["node"] == node]
        for (mechanism, n), group in node_rows.groupby(["mechanism", "n"]):
            if mechanism not in nulls:
                continue
            p = _p_values(group, arm)
            warnings = (p[:, None] <= thresholds[None, :]).sum(axis=0)
            for t, count in zip(grid, warnings, strict=True):
                records.append(
                    {"arm": arm, "node": node, "mechanism": mechanism, "n": int(n), "threshold": t,
                     "warnings": int(count), "datasets": int(len(group)),
                     "unavailable": int((~arm_available(group, arm)).sum())}
                )
    curves = pd.DataFrame.from_records(records)
    curves["rate"] = curves["warnings"] / curves["datasets"]
    return curves


def _largest(ok_by_threshold: pd.Series) -> float | None:
    passing = [t for t, ok in ok_by_threshold.items() if ok]
    # Monotone in t, so "largest passing" equals "closest to the target without exceeding".
    return float(max(passing)) if passing else None


def match_thresholds(curves: pd.DataFrame, target: float = TARGET_RATE) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for (arm, node), frame in curves.groupby(["arm", "node"], sort=False):
        worst = frame.groupby("threshold")["rate"].max()
        frozen = _largest(worst <= target + 1e-12)
        pooled_rate = frame.groupby("threshold")["warnings"].sum() / frame.groupby("threshold")["datasets"].sum()
        pooled = _largest(pooled_rate <= target + 1e-12)
        per_n = {}
        for n, sub in frame.groupby("n"):
            per_n[str(int(n))] = _largest(sub.groupby("threshold")["rate"].max() <= target + 1e-12)
        binding = None
        if frozen is not None:
            above = sorted(t for t in worst.index if t > frozen)
            if above:
                nxt = frame.loc[frame["threshold"] == above[0]]
                row = nxt.sort_values("rate", ascending=False).iloc[0]
                binding = {"next_threshold": float(above[0]), "mechanism": row["mechanism"], "n": int(row["n"]),
                           "rate_at_next": float(row["rate"])}
        at_frozen = {}
        if frozen is not None:
            sel = frame.loc[np.isclose(frame["threshold"], frozen)]
            at_frozen = {f"{r.mechanism}@{int(r.n)}": float(r.rate) for r in sel.itertuples()}
        results[f"{arm}:{node}"] = {
            "arm": arm,
            "node": node,
            "frozen_threshold": frozen,
            "pooled_rule_threshold": pooled,
            "per_n_thresholds": per_n,
            "binding_cell": binding,
            "null_rates_at_frozen": at_frozen,
            "pooled_rate_at_frozen": None if frozen is None else float(pooled_rate.loc[frozen]),
        }
    return results


def rates_at_thresholds(raw: pd.DataFrame, thresholds: dict[str, Any]) -> pd.DataFrame:
    """Warning rates of every mechanism by N at the frozen thresholds (Wilson 95%)."""

    records = []
    for key, entry in thresholds.items():
        t = entry["frozen_threshold"]
        if t is None:
            continue
        arm, node = entry["arm"], entry["node"]
        node_rows = raw.loc[raw["node"] == node]
        for (mechanism, n), group in node_rows.groupby(["mechanism", "n"]):
            warns = arm_warnings(group, arm, t)
            low, high = wilson(int(warns.sum()), len(group))
            records.append(
                {"arm": arm, "node": node, "threshold": t, "mechanism": mechanism,
                 "category": dm.mechanism(mechanism).category, "n": int(n), "warnings": int(warns.sum()),
                 "datasets": int(len(group)), "rate": float(warns.mean()), "wilson_low": low, "wilson_high": high,
                 "unavailable": int((~arm_available(group, arm)).sum())}
            )
    order = {mid: i for i, mid in enumerate(dm.MECHANISMS)}
    frame = pd.DataFrame.from_records(records)
    frame["_o"] = frame["mechanism"].map(order)
    return frame.sort_values(["node", "arm", "_o", "n"], kind="stable").drop(columns="_o").reset_index(drop=True)


def _fmt_t(value: float | None) -> str:
    return "none" if value is None else f"{value:.3f}"


def _report(meta: dict[str, Any], thresholds: dict[str, Any], rates: pd.DataFrame) -> str:
    lines = [
        "# Task 18 threshold matching (calibration seed)",
        "",
        f"- Raw rows: {meta['rows']}; complete grid: {meta['grid']['complete']}; master seed {meta['master_seed']}; "
        f"config hash `{meta['config_hash']}`.",
        f"- Rule: largest grid t (0.001-0.200, step 0.001) with false-warning rate <= {TARGET_RATE} on every "
        "effect-correct null mechanism (N1-N4) at every N. Warning: status ok and p <= t.",
        "- Calibration results are not evaluation evidence; no gate outcome is declared.",
        "",
        "## Thresholds",
        "",
        "| Arm | Node | Frozen t | Binding cell (rate at next t) | Pooled-rule t | Per-N t (100 / 250 / 500) |",
        "|---|---|---:|---|---:|---|",
    ]
    for entry in thresholds.values():
        binding = entry["binding_cell"]
        btxt = "—" if binding is None else (
            f"{binding['mechanism']} N={binding['n']} ({binding['rate_at_next']:.3f} at {binding['next_threshold']:.3f})"
        )
        per_n = " / ".join(_fmt_t(entry["per_n_thresholds"].get(str(n))) for n in (100, 250, 500))
        lines.append(
            f"| {entry['arm']} | {entry['node']} | {_fmt_t(entry['frozen_threshold'])} | {btxt} | "
            f"{_fmt_t(entry['pooled_rule_threshold'])} | {per_n} |"
        )
    lines += ["", "## Warning rates at the frozen thresholds (count/datasets, rate [Wilson 95%])", ""]
    for (node, arm), frame in rates.groupby(["node", "arm"], sort=False):
        t = frame["threshold"].iloc[0]
        lines += [f"### {arm}, {node} node (t = {t:.3f})", "", "| Mechanism | Category | N = 100 | N = 250 | N = 500 |",
                  "|---|---|---|---|---|"]
        for mechanism, sub in frame.groupby("mechanism", sort=False):
            cells = []
            for n in (100, 250, 500):
                r = sub.loc[sub["n"] == n]
                if r.empty:
                    cells.append("—")
                    continue
                r = r.iloc[0]
                cells.append(f"{r.warnings}/{r.datasets} = {r.rate:.3f} [{r.wilson_low:.3f}, {r.wilson_high:.3f}]")
            lines.append(f"| {mechanism} | {sub['category'].iloc[0]} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def calibrate(raw_paths: list[Path], config_path: Path, output: Path, *, any_seed: bool = False) -> dict[str, Any]:
    config = idg.load_config(config_path)
    if config.master_seed != dm.CALIBRATION_SEED and not any_seed:
        raise SystemExit(f"threshold matching needs the calibration seed {dm.CALIBRATION_SEED}, got {config.master_seed}")
    raw = pd.concat([idg.read_raw(path) for path in raw_paths], ignore_index=True)
    if set(raw["config_hash"].astype(str)) != {config.config_hash}:
        raise SystemExit("raw rows do not belong to this configuration")
    grid = check_complete_grid(raw, config)
    if not grid["complete"]:
        raise SystemExit(f"incomplete grid: {grid}")
    curves = false_warning_curves(raw)
    thresholds = match_thresholds(curves)
    rates = rates_at_thresholds(raw, thresholds)
    meta = {
        "rows": int(len(raw)),
        "grid": {k: v for k, v in grid.items() if k != "missing_examples"},
        "master_seed": config.master_seed,
        "config_hash": config.config_hash,
        "experiment": config.experiment,
        "target_rate": TARGET_RATE,
        "threshold_grid": {"start": GRID[0], "stop": GRID[-1], "step": 0.001, "count": len(GRID)},
        "warning_rule": "status ok and p <= t (information: permutation p; conventional: min Holm-adjusted p)",
        "rule": "frozen t = largest grid t with false-warning rate <= target on every effect-correct null mechanism at every N",
        "null_mechanisms": null_mechanisms(),
    }
    output.mkdir(parents=True, exist_ok=True)
    payload = {**meta, "thresholds": thresholds}
    (output / "thresholds.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    curves.to_csv(output / "false_warning_curves.csv", index=False, lineterminator="\n")
    rates.to_csv(output / "rates_at_frozen_thresholds.csv", index=False, lineterminator="\n")
    (output / "threshold_report.md").write_text(_report(meta, thresholds, rates), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", required=True, type=Path, action="append")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--any-seed", action="store_true", help="allow a non-calibration seed (tests and pilots only)")
    arguments = parser.parse_args(argv)
    payload = calibrate(arguments.raw, arguments.config, arguments.output, any_seed=arguments.any_seed)
    for key, entry in payload["thresholds"].items():
        print(f"{key}: frozen {_fmt_t(entry['frozen_threshold'])}, pooled {_fmt_t(entry['pooled_rule_threshold'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

