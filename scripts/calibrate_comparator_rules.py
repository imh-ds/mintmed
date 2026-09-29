"""Pre-charter calibration of the Task 17 Stage 1 comparison rules (T17-S5).

This is NOT evidence. It runs Mintmed and both R comparators on datasets from
a SEPARATE calibration master seed (default 20260929; the evaluation seed
20260927 is refused) so that the Stage 1 charter (T17-S7) can choose how each
``stage1.comparison_rules`` limit is judged without looking at the evaluation
datasets. A temporary copy of ``configs/mediation_validation_v3.yaml`` with
the calibration seed, ``--replicates`` datasets and cells 01, 08 and 14 is
written under ``--output``; nothing under ``configs/`` changes.

Usage::

    python scripts/calibrate_comparator_rules.py --output DIR [--replicates 100] [--workers 10]
    python scripts/calibrate_comparator_rules.py --output DIR --analyze-only

``--output`` receives the config copy, one raw_metrics.csv per job and
``calibration.json`` (the numbers quoted in
``docs/validation/comparator_rule_calibration.md``).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mintmed.experiments import comparator_benchmark as cb  # noqa: E402
from mintmed.experiments import comparator_benchmark_reporting as rep  # noqa: E402
from mintmed.experiments.mediation_validation import cell_definition, load_config  # noqa: E402
from mintmed.experiments.mediation_validation_reporting import WILSON_Z, wilson  # noqa: E402

BASE_CONFIG = ROOT / "configs" / "mediation_validation_v3.yaml"
EVALUATION_SEED = 20260927
CALIBRATION_SEED = 20260929
CELLS = ("cell01_linear_n100", "cell08_quadratic_n100", "cell14_b_path_only_n100")
BLOCKS = 4
TARGET_N = 500


def write_config(output: Path, master_seed: int, replicates: int) -> Path:
    if master_seed == EVALUATION_SEED:
        raise ValueError("the calibration must not reuse the evaluation master seed 20260927")
    raw = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    raw.update(
        experiment="mintmed_comparator_rule_calibration",
        master_seed=int(master_seed),
        replicates=int(replicates),
        cell_ids=list(CELLS),
    )
    raw["stress"]["enabled"] = False
    path = output / "calibration_config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def jobs(config_path: Path, output: Path) -> list[tuple[str, list[str]]]:
    python = sys.executable
    items = []
    for cell in CELLS:
        for block in range(BLOCKS):
            shard = f"{cell}_{block}of{BLOCKS}"
            items.append((f"mintmed/{shard}", [
                python, "-m", "mintmed.experiments.mediation_validation", "--config", str(config_path),
                "--output", str(output / "mintmed" / shard), "--cell-id", cell,
                "--replicate-block", f"{block}of{BLOCKS}", "--no-report",
            ]))
            for tool in cb.R_RUNNERS:
                if not cb.is_supported(tool, cell):
                    continue
                items.append((f"{tool}/{shard}", [
                    python, "-m", "mintmed.experiments.comparator_benchmark", "--config", str(config_path),
                    "--output", str(output / tool / shard), "--cell-id", cell, "--tool", tool,
                    "--replicate-block", f"{block}of{BLOCKS}", "--no-report",
                ]))
    return items


def run_jobs(config_path: Path, output: Path, workers: int) -> None:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

    def launch(item: tuple[str, list[str]]) -> tuple[str, int, float]:
        name, command = item
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            print(f"{name} failed: {completed.stdout[-400:]} {completed.stderr[-800:]}", flush=True)
        return name, completed.returncode, time.perf_counter() - started

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name, code, seconds in pool.map(launch, jobs(config_path, output)):
            print(f"{name}: exit {code} in {seconds:.0f} s", flush=True)


# ---------------------------------------------------------------------------
# Analysis


def wilson_lower(successes: int, trials: int) -> float | None:
    return wilson(successes, trials)[0]


def min_rate_for_wilson_lower(limit: float, n: int) -> tuple[int, float]:
    """Smallest success count (and rate) at n trials whose Wilson lower bound reaches ``limit``."""

    for successes in range(n + 1):
        lower = wilson_lower(successes, n)
        if lower is not None and lower >= limit:
            return successes, successes / n
    return n + 1, math.nan


def trials_needed_perfect(limit: float) -> int:
    """Fewest trials for which k = n successes gives a Wilson lower bound >= ``limit``: n / (n + z^2)."""

    return math.ceil(limit * WILSON_Z**2 / (1.0 - limit) - 1e-12)


def pass_probability(true_rate: float, n: int, threshold_successes: int) -> float:
    """P(Binomial(n, true_rate) >= threshold_successes)."""

    from math import comb

    return float(sum(comb(n, k) * true_rate**k * (1 - true_rate) ** (n - k) for k in range(threshold_successes, n + 1)))


def load(output: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mintmed_paths = sorted((output / "mintmed").glob("*/raw_metrics.csv"))
    reference = rep.load_mintmed_reference(mintmed_paths)
    mintmed_raw = pd.concat([pd.read_csv(path) for path in mintmed_paths], ignore_index=True)
    frames = [cb.read_raw(path) for tool in cb.R_RUNNERS for path in sorted((output / tool).glob("*/raw_metrics.csv"))]
    raw = pd.concat(frames, ignore_index=True)
    return reference, mintmed_raw, rep.expand_records(raw)


def _extrapolated_upper(point: float | None, upper: float | None, n: int) -> float | None:
    if point is None or upper is None:
        return None
    return point + (upper - point) * math.sqrt(n / TARGET_N)


def _extrapolated_lower(point: float | None, lower: float | None, n: int) -> float | None:
    if point is None or lower is None:
        return None
    return point - (point - lower) * math.sqrt(n / TARGET_N)


def _agreement_bootstrap_lower(indicator: np.ndarray, key: str) -> float | None:
    if indicator.size == 0:
        return None
    _, lower, _ = rep._paired_bootstrap(lambda x: float(np.mean(x)), [indicator.astype(float)], key)
    return lower


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def genuine_agreement_characteristics(comparisons: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Noise floor of two methods that agree by construction, and pass probabilities at n = 500.

    Uses the cell-effects whose point estimates are identical to 1e-8 (lavaan
    and mediate in cells 01 and 14, mediate PNDE in cell 08): only the
    bootstrap resamples differ. A paired difference of two binary indicators
    with discordance rate d has SE ~ sqrt(d / n); the paired bootstrap upper
    bound is ~ point + z SE. Pass probabilities are normal approximations.
    """

    identical = [item for item in comparisons if item["max_abs_point_difference"] <= cb.EXACT_POINT_TOLERANCE
                 and item["decision_agreement"] is not None]
    pairs = sum(item["pairs"] for item in identical)
    null = [item for item in identical if item["false_positive_excess_pp"] is not None]
    rates = {
        "cell_effects": len(identical),
        "pairs": pairs,
        "decision_disagreement_rate": sum(item["decision_disagreements"] for item in identical) / pairs,
        "opposite_significant_pairs": sum(item["opposite_significant_pairs"] for item in identical),
        "coverage_discordance_rate": sum(item["coverage_discordant"] for item in identical) / pairs,
        "zero_exclusion_discordance_rate": sum(item["zero_exclusion_discordant"] for item in identical) / pairs,
        "null_zero_exclusion_discordance_rate": (
            sum(item["zero_exclusion_discordant"] for item in null) / sum(item["pairs"] for item in null) if null else None),
        "decision_agreement_min_observed": min(item["decision_agreement"] for item in identical),
        "decision_agreement_max_observed": max(item["decision_agreement"] for item in identical),
    }
    floor = 1.0 - rates["decision_disagreement_rate"]
    decision = {}
    for limit in (0.95, 0.90):
        k_wilson, _ = min_rate_for_wilson_lower(limit, TARGET_N)
        k_point = math.ceil(limit * TARGET_N - 1e-9)
        decision[str(limit)] = {
            "pass_probability_observed_rate_at_floor": pass_probability(floor, TARGET_N, k_point),
            "pass_probability_wilson_lower_at_floor": pass_probability(floor, TARGET_N, k_wilson),
        }
    guardrails = {}
    discordance = {
        "coverage_loss_pp": (rates["coverage_discordance_rate"], (2.5, 5.0)),
        "power_loss_pp": (rates["zero_exclusion_discordance_rate"], (5.0, 10.0)),
        "false_positive_excess_pp": (rates["null_zero_exclusion_discordance_rate"] or rates["zero_exclusion_discordance_rate"], (2.0, 3.0)),
    }
    for name, (d, (negligible, tolerable)) in discordance.items():
        se = 100.0 * math.sqrt(d / TARGET_N)
        entry = {"discordance_rate": d, "se_pp_at_500": se}
        for label, limit in (("negligible", negligible), ("tolerable", tolerable)):
            for true_loss in (0.0, negligible, tolerable, 2.0 * tolerable):
                key = f"{label}_limit_{limit}_true_{true_loss}"
                entry[key] = {
                    "pass_point": _normal_cdf((limit - true_loss) / se),
                    "pass_upper_bound": _normal_cdf((limit - true_loss) / se - WILSON_Z),
                }
        guardrails[name] = entry
    return {"rates": rates, "decision_agreement_floor": floor, "decision_agreement_at_500": decision,
            "guardrails_at_500": guardrails}


def analyse(output: Path, config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    reference, mintmed_raw, long = load(output)
    rep.check_reference_seeds(reference, config.master_seed)
    comparisons = []
    primary = long.loc[long["mode"] == "primary"]
    for (tool, cell_id, effect), group in primary.groupby(["tool", "cell_id", "effect"], sort=True):
        if (group["status"] == "not_estimable").all():
            continue
        mine = reference.loc[(reference["cell_id"] == cell_id) & (reference["effect"] == effect)]
        definition = cell_definition(str(cell_id))
        comparison = rep.paired_comparison(
            mine, group, tool=str(tool), cell_id=str(cell_id), effect=str(effect),
            population_sd=definition.population_outcome_sd, null_effect=rep.is_null_effect(str(cell_id), str(effect)),
        )
        merged = mine.merge(group, on="replicate", suffixes=("_m", "_c"))
        decision_m = rep.decisions(merged["lower_m"], merged["upper_m"])
        decision_c = rep.decisions(merged["lower_c"], merged["upper_c"])
        agree = np.isfinite(decision_m) & np.isfinite(decision_c) & (decision_m == decision_c)
        either = (np.abs(np.nan_to_num(decision_m)) == 1.0) | (np.abs(np.nan_to_num(decision_c)) == 1.0)
        signs = np.sign(merged["estimate_m"].to_numpy(float)) == np.sign(merged["estimate_c"].to_numpy(float))
        n = comparison["pairs"]
        k_sig = int(either.sum())
        entry: dict[str, Any] = {
            "tool": tool, "cell_id": cell_id, "effect": effect, "pairs": n,
            "mintmed_zero_exclusion": comparison.get("mintmed_zero_exclusion"),
            "comparator_zero_exclusion": comparison.get("comparator_zero_exclusion"),
            "max_abs_point_difference": float(np.nanmax(np.abs(merged["estimate_m"] - merged["estimate_c"]))),
            "decision_agreement": comparison["decision_agreement"],
            "decision_agreement_wilson_lower": comparison["decision_agreement_lower"],
            "decision_agreement_bootstrap_lower": _agreement_bootstrap_lower(agree, f"{tool}|{cell_id}|{effect}|da"),
            "decision_disagreements": int(n - agree.sum()),
            "one_sided_disagreements": int(((decision_m == 0) != (decision_c == 0)).sum()),
            "opposite_significant_pairs": int(comparison.get("opposite_significant_pairs") or 0),
            "coverage_discordant": int((merged["coverage_m"].astype(bool) != merged["coverage_c"].astype(bool)).sum()),
            "zero_exclusion_discordant": int(
                (merged["zero_exclusion_m"].astype(bool) != merged["zero_exclusion_c"].astype(bool)).sum()),
            "mintmed_coverage": comparison.get("mintmed_coverage"),
            "comparator_coverage": comparison.get("comparator_coverage"),
            "significant_pairs": k_sig,
            "sign_agreement": comparison["sign_agreement"],
            "sign_agreement_wilson_lower": comparison["sign_agreement_lower"],
            "sign_agreement_bootstrap_lower": _agreement_bootstrap_lower(signs[either], f"{tool}|{cell_id}|{effect}|sa"),
        }
        # n = 500 extrapolation at the same observed rates.
        if comparison["decision_agreement"] is not None:
            rate = comparison["decision_agreement"]
            entry["decision_agreement_wilson_lower_at_500"] = wilson_lower(round(rate * TARGET_N), TARGET_N)
            entry["decision_agreement_bootstrap_lower_at_500"] = _extrapolated_lower(
                rate, entry["decision_agreement_bootstrap_lower"], n)
        if comparison["sign_agreement"] is not None and k_sig:
            k500 = round(k_sig * TARGET_N / n)
            entry["significant_pairs_at_500"] = k500
            entry["sign_agreement_wilson_lower_at_500"] = wilson_lower(round(comparison["sign_agreement"] * k500), k500)
        for name in ("bias_excess_sd", "coverage_loss_pp", "false_positive_excess_pp", "power_loss_pp", "width_ratio"):
            entry[name] = comparison.get(name)
            entry[f"{name}_upper"] = comparison.get(f"{name}_upper")
            entry[f"{name}_upper_at_500"] = _extrapolated_upper(comparison.get(name), comparison.get(f"{name}_upper"), n)
        entry["tier_bound"] = rep.classify_tier(comparison)["tier"]
        entry["tier_point"] = rep.classify_tier(comparison, primary_basis="point")["tier"]
        comparisons.append(entry)

    timing = []
    mintmed_raw["runtime_seconds"] = mintmed_raw["runtime_seconds"].astype(float)
    for cell_id, group in mintmed_raw.groupby("cell_id"):
        timing.append({"tool": "mintmed", "mode": "percentile bootstrap 399", "cell_id": cell_id,
                       "datasets": len(group), "median_seconds": float(group["runtime_seconds"].median()),
                       "mean_seconds": float(group["runtime_seconds"].mean())})
    per_mode = long.drop_duplicates(subset=["tool", "mode", "cell_id", "replicate"])
    per_mode = per_mode.loc[per_mode["status"] != "not_estimable"]
    for (tool, mode, cell_id), group in per_mode.groupby(["tool", "mode", "cell_id"]):
        runtime = group["runtime_seconds"].dropna()
        timing.append({"tool": tool, "mode": mode, "cell_id": cell_id, "datasets": len(group),
                       "median_seconds": float(runtime.median()), "mean_seconds": float(runtime.mean())})

    analytic = {
        "wilson_z": WILSON_Z,
        "min_observed_for_wilson_lower_at_500": {
            str(limit): dict(zip(("successes", "rate"), min_rate_for_wilson_lower(limit, TARGET_N)))
            for limit in (0.95, 0.90, 0.99)
        },
        "significant_pairs_needed_perfect_agreement": {
            str(limit): trials_needed_perfect(limit) for limit in (0.99, 0.95, 0.90)
        },
    }
    # Operating characteristics of each judging option for decision agreement at n = 500.
    oc = {}
    for limit in (0.95, 0.90):
        k_wilson, _ = min_rate_for_wilson_lower(limit, TARGET_N)
        k_point = math.ceil(limit * TARGET_N - 1e-9)
        oc[str(limit)] = {
            str(true_rate): {
                "pass_probability_observed_rate": pass_probability(true_rate, TARGET_N, k_point),
                "pass_probability_wilson_lower": pass_probability(true_rate, TARGET_N, k_wilson),
            }
            for true_rate in (0.99, 0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.90, 0.88, 0.85)
        }
    analytic["decision_agreement_pass_probability_at_500"] = oc
    analytic["genuine_agreement"] = genuine_agreement_characteristics(comparisons)
    payload = {
        "note": "pre-charter calibration on a separate master seed; not evidence",
        "master_seed": config.master_seed,
        "config_hash": config.config_hash,
        "replicates": config.replicates,
        "comparisons": rep._json_safe(comparisons),
        "timing": timing,
        "analytic": analytic,
    }
    (output / "calibration.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replicates", type=int, default=100)
    parser.add_argument("--master-seed", type=int, default=CALIBRATION_SEED)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--analyze-only", action="store_true")
    arguments = parser.parse_args(argv)
    config_path = write_config(arguments.output, arguments.master_seed, arguments.replicates)
    if not arguments.analyze_only:
        run_jobs(config_path, arguments.output, arguments.workers)
    payload = analyse(arguments.output, config_path)
    print(json.dumps(payload, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
