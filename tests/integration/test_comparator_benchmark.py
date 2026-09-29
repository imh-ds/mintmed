"""Shard contract, not-estimable handling and reporting maths of the comparator runner.

None of these tests needs R: supported cells are exercised with a missing
Rscript (runner_failed rows) or with synthetic long outputs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mintmed.experiments import comparator_benchmark as cb
from mintmed.experiments import comparator_benchmark_reporting as rep
from mintmed.experiments.mediation_validation import _CELL_REGISTRY, load_config, seed_pair
from scripts.aggregate_shards import aggregate

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "configs" / "mediation_validation_v3.yaml"
ALL_CELLS = {cell.cell_id for cell in _CELL_REGISTRY}

PLAN_SUPPORT = {  # outline/plan/task-17-comparator-benchmark.md stage1.support_matrix
    "mediation": {1, 2, 3, 4, 5, 8, 9, 10, 11, 13, 14, 15, 16},
    "lavaan": {1, 2, 3, 4, 5, 7, 10, 13, 14, 15, 16},
}


@pytest.fixture(scope="module")
def v3():
    return load_config(V3)


def _small_config(tmp_path: Path, cells: list[str], replicates: int = 2) -> Path:
    text = V3.read_text(encoding="utf-8")
    head, _, rest = text.partition("cell_ids:")
    _, _, tail = rest.partition("stress:")
    body = "cell_ids:\n" + "".join(f"  - {cell}\n" for cell in cells) + "stress:" + tail
    path = tmp_path / "small.yaml"
    path.write_text(head.replace("replicates: 500", f"replicates: {replicates}") + body, encoding="utf-8")
    return path


# --- shard contract -------------------------------------------------------------


def test_contract_covers_every_tool_cell_and_replicate(v3) -> None:
    assert cb.COMBINATION_COLUMNS == ("tool", "cell_id", "replicate")
    assert cb.TOOLS == ("mediation", "lavaan", "mediation_reseed")
    combos = cb.expected_combinations(v3)
    assert cb.expected_row_count(v3) == len(combos) == 3 * 16 * 500
    assert {tool for tool, _, _ in combos} == set(cb.TOOLS)
    assert {cell for _, cell, _ in combos} == set(v3.cell_ids)


def test_noise_floor_tool_reuses_the_mediation_runner_with_a_shifted_seed() -> None:
    assert cb.base_tool("mediation_reseed") == "mediation"
    assert cb.tool_modes("mediation_reseed") == ("primary",)
    assert cb.tool_modes("mediation") == cb.tool_modes("lavaan") == cb.MODES
    assert cb.seed_offset("mediation") == cb.seed_offset("lavaan") == 0
    assert cb.seed_offset("mediation_reseed") == cb.RESEED_SEED_OFFSET == 1_000_000_007
    assert 0 < cb.RESEED_SEED_OFFSET < cb.SEED_MODULUS
    with pytest.raises(ValueError, match="unknown tool"):
        cb.base_tool("stata")
    # Same support matrix as mediate(), never its own entry.
    matrix = cb.load_support_matrix()
    assert set(matrix) == set(cb.R_RUNNERS)
    for cell in ALL_CELLS:
        assert cb.is_supported("mediation_reseed", cell) == cb.is_supported("mediation", cell)
    # Seeds: deterministic, exact for uint64 analysis seeds, and always different from the primary run's.
    for seed in (0, 1, 2147483646, 18446744073709551557, 2**64 - 1):
        shifted = cb.r_seed(str(seed), cb.RESEED_SEED_OFFSET)
        assert shifted == (seed + 1_000_000_007) % 2147483647
        assert shifted != cb.r_seed(str(seed))
    with pytest.raises(ValueError):
        cb.r_seed(1, cb.SEED_MODULUS)


def test_noise_floor_rows_have_the_primary_mode_and_the_shifted_seed(tmp_path: Path, v3, monkeypatch) -> None:
    monkeypatch.setattr(cb, "find_rscript", lambda explicit=None: None)
    raw = cb.run(v3, tmp_path / "out", config_path=V3,
                 cell_ids=["cell01_linear_n100", "cell07_serial_three_n200"], replicate=0,
                 tools=("mediation_reseed",), no_report=True)
    assert len(raw) == 2
    rows = {row.cell_id: row for row in raw.itertuples()}
    unsupported = rows["cell07_serial_three_n200"]
    assert unsupported.status == "not_estimable"
    assert pd.isna(unsupported.failure_message)
    supported = rows["cell01_linear_n100"]
    assert supported.status == "runner_failed"  # no Rscript: explicit rows, never dropped
    _, analysis_seed = seed_pair(v3.master_seed, 1, 0)
    assert int(supported.r_seed) == (analysis_seed + cb.RESEED_SEED_OFFSET) % 2147483647
    for row in rows.values():
        assert set(json.loads(row.records_json)) == {"primary"}
    metadata = json.loads((tmp_path / "out" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["settings"]["seed_offsets"] == {"mediation_reseed": cb.RESEED_SEED_OFFSET}
    assert metadata["settings"]["tool_modes"] == {"mediation_reseed": ["primary"]}
    # The reporting expands one mode for the rerun and both for the comparators.
    long = rep.expand_records(raw)
    assert set(long["mode"]) == {"primary"}


def test_noise_floor_tool_passes_its_id_and_offset_to_the_runner(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        raise OSError("not really running R")

    monkeypatch.setattr(cb.subprocess, "run", fake_run)
    long, failure = cb.run_r_tool("Rscript", "mediation_reseed", tmp_path / "m.json", tmp_path / "o.csv",
                                  boot_sims=399, qb_sims=1000)
    assert long is None and "could not run" in failure
    command = calls[0]
    assert Path(command[1]).name == "run_mediation.R"
    assert command[command.index("--modes") + 1] == "primary"
    assert command[command.index("--tool-id") + 1] == "mediation_reseed"
    assert command[command.index("--seed-offset") + 1] == str(cb.RESEED_SEED_OFFSET)
    cb.run_r_tool("Rscript", "mediation", tmp_path / "m.json", tmp_path / "o.csv", boot_sims=399, qb_sims=1000)
    assert "--tool-id" not in calls[1] and calls[1][calls[1].index("--modes") + 1] == "primary,secondary"


def test_support_matrix_matches_the_plan_and_covers_every_cell() -> None:
    matrix = cb.load_support_matrix()
    ordinal = {cell.cell_id: cell.ordinal for cell in _CELL_REGISTRY}
    for tool, expected in PLAN_SUPPORT.items():
        supported = {ordinal[cell] for cell in matrix[tool]["supported"]}
        assert supported == expected
        assert matrix[tool]["supported"] | set(matrix[tool]["not_estimable"]) == ALL_CELLS
        assert all(reason.strip() for reason in matrix[tool]["not_estimable"].values())


def test_r_seed_rule_is_exact_for_uint64_seeds() -> None:
    seed = 18446744073709551557  # > 2**63, would lose digits as a double
    assert cb.r_seed(str(seed)) == seed % 2147483647
    assert cb.r_seed(seed) == cb.r_seed(str(seed))
    assert 0 <= cb.r_seed(2**64 - 1) < 2**31 - 1


def test_effect_truths_match_mintmed_metrics() -> None:
    assert cb.effect_truths("cell01_linear_n100") == {"TE": 0.45, "PNDE": 0.20, "TNIE": 0.25}
    assert cb.effect_truths("cell06_parallel_interaction_n150") == {"TNIE": 0.40}
    assert cb.effect_truths("cell10_moderated_n150") == {"TNIE_W0": 0.09, "TNIE_W1": 0.36, "TNIE_difference": 0.27}


# --- not_estimable and failures are explicit rows ----------------------------------


def test_unsupported_cells_yield_explicit_not_estimable_rows(tmp_path: Path, v3) -> None:
    raw = cb.run(v3, tmp_path / "out", config_path=V3, cell_ids=["cell06_parallel_interaction_n150", "cell12_mixed_binary_serial_n250"],
                 replicate_start=0, replicate_stop=2, rscript="does-not-exist", no_report=True)
    assert len(raw) == 3 * 2 * 2
    assert set(raw["status"]) == {"not_estimable"}
    assert not raw["supported"].astype(bool).any()
    for row in raw.itertuples():
        records = json.loads(row.records_json)
        assert set(records) == set(cb.tool_modes(row.tool))
        for effects in records.values():
            assert set(effects) == set(cb.effect_truths(row.cell_id))
            for record in effects.values():
                assert record["status"] == "not_estimable"
                assert record["estimate"] is None and record["lower"] is None
                assert record["reason"] == cb.not_estimable_reason(row.tool, row.cell_id)
        data_seed, analysis_seed = seed_pair(v3.master_seed, 6 if "cell06" in row.cell_id else 12, row.replicate)
        assert row.analysis_seed == str(analysis_seed) and row.data_seed == str(data_seed)
    metadata = json.loads((tmp_path / "out" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["combination_columns"] == list(cb.COMBINATION_COLUMNS)
    assert metadata["observed_rows"] == len(raw)


def test_missing_rscript_gives_runner_failed_rows_not_dropped_rows(tmp_path: Path, v3, monkeypatch) -> None:
    monkeypatch.setattr(cb, "find_rscript", lambda explicit=None: None)
    raw = cb.run(v3, tmp_path / "out", config_path=V3, cell_ids=["cell01_linear_n100"], replicate=3,
                 tools=("lavaan",), no_report=True)
    assert len(raw) == 1
    row = raw.iloc[0]
    assert row["status"] == "runner_failed" and "Rscript not found" in row["failure_message"]
    records = json.loads(row["records_json"])
    assert all(record["estimate"] is None for effects in records.values() for record in effects.values())
    # A rerun resumes: the existing row is kept, not duplicated.
    again = cb.run(v3, tmp_path / "out", config_path=V3, cell_ids=["cell01_linear_n100"], replicate=3,
                   tools=("lavaan",), no_report=True)
    assert len(again) == 1


def _long(rows: list[dict]) -> pd.DataFrame:
    base = {column: "" for column in cb.LONG_COLUMNS}
    return pd.DataFrame([{**base, **row} for row in rows], dtype=str)


def test_records_from_long_marks_missing_and_never_keeps_failed_values() -> None:
    long = _long(
        [
            {"tool": "mediation", "mode": "primary", "cell_id": "cell01_linear_n100", "replicate": "0", "effect": "TNIE",
             "estimate": "0.25", "lower": "0.1", "upper": "0.4", "status": "ok", "runtime_seconds": "2.5",
             "sims_requested": "399", "sims_successful": "399"},
            {"tool": "mediation", "mode": "primary", "cell_id": "cell01_linear_n100", "replicate": "0", "effect": "PNDE",
             "estimate": "0.3", "lower": "0.1", "upper": "0.5", "status": "error", "message": "boom"},
            {"tool": "mediation", "mode": "primary", "cell_id": "cell01_linear_n100", "replicate": "0", "effect": "TE",
             "estimate": "0.5", "lower": "0.2", "upper": "0.8", "status": "ok_warnings", "message": "glm warning"},
        ]
    )
    records, _ = cb.records_from_long(long, "mediation", "cell01_linear_n100", 0)
    tnie = records["primary"]["TNIE"]
    assert tnie["estimate"] == 0.25 and tnie["coverage"] and tnie["zero_exclusion"]
    assert math.isclose(tnie["bias"], 0.0, abs_tol=1e-15) and tnie["sims_successful"] == 399
    pnde = records["primary"]["PNDE"]
    assert pnde["status"] == "error" and pnde["estimate"] is None and pnde["lower"] is None and not pnde["coverage"]
    assert records["primary"]["TE"]["status"] == "ok_warnings" and records["primary"]["TE"]["estimate"] == 0.5
    assert all(record["status"] == "missing_output" for record in records["secondary"].values())
    assert cb.row_status(records) == "partial"


def test_row_status_summaries() -> None:
    ok = {"status": "ok"}
    assert cb.row_status({"primary": {"TE": ok}, "secondary": {"TE": ok}}) == "ok"
    assert cb.row_status({"primary": {"TE": ok}, "secondary": {"TE": {"status": "ok_warnings"}}}) == "ok_warnings"
    assert cb.row_status({"primary": {"TE": {"status": "error"}}}) == "failed"
    assert cb.row_status({"primary": {"TE": {"status": "not_estimable"}}}) == "not_estimable"
    assert cb.row_status({"primary": {"TE": {"status": "runner_failed"}}}) == "runner_failed"


def test_aggregate_shards_accepts_comparator_shards(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(rep.REFERENCE_ENV, raising=False)
    cells = ["cell06_parallel_interaction_n150", "cell12_mixed_binary_serial_n250"]  # not estimable by both tools
    config_path = _small_config(tmp_path, cells, replicates=2)
    config = load_config(config_path)
    for block in ("0of2", "1of2"):
        assert cb.main(["--config", str(config_path), "--output", str(tmp_path / "shards" / block),
                        "--replicate-block", block, "--no-report"]) == 0
    raw = aggregate("mintmed.experiments.comparator_benchmark", config_path, tmp_path / "shards", tmp_path / "agg")
    assert len(raw) == cb.expected_row_count(config) == 3 * 2 * 2
    summary = json.loads((tmp_path / "agg" / "summary.json").read_text(encoding="utf-8"))
    assert summary["complete_grid"] is True
    assert all(item["estimable"] is False for item in summary["summaries"])
    # mediation and lavaan write two modes, the noise-floor rerun one; cells 06 and 12 have 1 and 3 effects.
    assert (tmp_path / "agg" / "report.md").read_text(encoding="utf-8").count("not estimable") == (2 * 2 + 1) * (1 + 3)


# --- reporting maths -------------------------------------------------------------


def _effect_frame(estimates, lowers, uppers, truth, *, status="ok") -> pd.DataFrame:
    estimates = np.asarray(estimates, float)
    lowers = np.asarray(lowers, float)
    uppers = np.asarray(uppers, float)
    available = np.isfinite(lowers) & np.isfinite(uppers)
    return pd.DataFrame(
        {
            "replicate": np.arange(len(estimates)),
            "estimate": estimates,
            "bias": estimates - truth,
            "lower": lowers,
            "upper": uppers,
            "coverage": available & (lowers <= truth) & (truth <= uppers),
            "width": np.where(available, uppers - lowers, np.nan),
            "zero_exclusion": available & ((lowers > 0) | (uppers < 0)),
            "interval_available": available,
            "status": status,
        }
    )


def test_summarize_computes_bias_rmse_coverage_and_wilson() -> None:
    frame = _effect_frame([0.3, 0.1, 0.4, np.nan], [0.1, -0.1, 0.3, np.nan], [0.5, 0.3, 0.4, np.nan], 0.25)
    frame.loc[3, "status"] = "error"
    frame = frame.assign(tool="lavaan", mode="primary", cell_id="cell01_linear_n100", effect="TNIE",
                         truth=0.25, reason=None, runtime_seconds=[1.0, 2.0, 3.0, np.nan],
                         sims_requested=399.0, sims_successful=399.0, population_outcome_sd=2.0,
                         outcome_kind="continuous")
    row = rep.summarize(frame).iloc[0]
    biases = np.array([0.05, -0.15, 0.15])
    assert row["attempted"] == 4 and row["failed_rows"] == 1 and row["failure_rate"] == 0.25
    assert math.isclose(row["mean_bias"], biases.mean())
    assert math.isclose(row["abs_bias_sd"], abs(biases.mean()) / 2.0)
    assert math.isclose(row["bias_mc_se"], biases.std(ddof=1) / math.sqrt(3))
    assert math.isclose(row["rmse"], math.sqrt(np.mean(biases**2)))
    assert row["coverage_successes"] == 2 and row["coverage_trials"] == 4 and row["coverage"] == 0.5
    lower, upper = rep.wilson(2, 4)
    assert row["coverage_wilson_lower"] == lower and row["coverage_wilson_upper"] == upper
    assert math.isclose(row["mean_width"], np.mean([0.4, 0.4, 0.1]))
    assert row["zero_exclusion_successes"] == 2
    assert math.isclose(row["runtime_mean_seconds"], 2.0)


def test_decisions_classify_interval_signs() -> None:
    out = rep.decisions(np.array([0.1, -0.5, -0.2, np.nan]), np.array([0.4, -0.1, 0.3, 0.2]))
    assert out[:3].tolist() == [1.0, -1.0, 0.0] and math.isnan(out[3])


def test_identical_methods_are_negligible() -> None:
    rng = np.random.default_rng(1)
    # Every interval excludes zero, so the sign-agreement Wilson bound can reach 0.99.
    estimates = 0.6 + 0.1 * rng.standard_normal(500)
    frame = _effect_frame(estimates, estimates - 0.2, estimates + 0.2, 0.6)
    comparison = rep.paired_comparison(frame, frame.copy(), tool="lavaan", cell_id="cell01_linear_n100",
                                       effect="TNIE", population_sd=1.2, null_effect=False)
    assert comparison["pairs"] == 500 and comparison["decision_agreement"] == 1.0
    assert comparison["bias_excess_sd"] == 0.0 and comparison["coverage_loss_pp"] == 0.0
    assert comparison["width_ratio"] == 1.0 and comparison["width_ratio_upper"] == 1.0
    assert comparison["false_positive_excess_pp"] is None and comparison["power_loss_pp"] == 0.0
    assert rep.classify_tier(comparison)["tier"] == "negligible"


def test_wider_mintmed_intervals_move_the_tier() -> None:
    rng = np.random.default_rng(2)
    estimates = 0.25 + 0.1 * rng.standard_normal(500)
    comparator = _effect_frame(estimates, estimates - 0.2, estimates + 0.2, 0.25)
    tolerable = rep.paired_comparison(_effect_frame(estimates, estimates - 0.23, estimates + 0.23, 0.25), comparator,
                                      tool="lavaan", cell_id="cell01_linear_n100", effect="PNDE",
                                      population_sd=1.2, null_effect=False)
    assert math.isclose(tolerable["width_ratio"], 1.15)
    assert rep.classify_tier(tolerable)["negligible_checks"]["width_ratio"] is False
    substantive = rep.paired_comparison(_effect_frame(estimates, estimates - 0.3, estimates + 0.3, 0.25), comparator,
                                        tool="lavaan", cell_id="cell01_linear_n100", effect="PNDE",
                                        population_sd=1.2, null_effect=False)
    assert rep.classify_tier(substantive)["tier"] == "substantive"
    # Width alone decides here: agreement and coverage are unaffected or better.
    verdicts = rep.classify_tier(tolerable)
    assert verdicts["tolerable_checks"]["width_ratio"] is True


def test_null_effect_uses_false_positive_excess() -> None:
    n = 500
    zeros = np.zeros(n)
    comparator = _effect_frame(zeros + 0.01, zeros - 0.1, zeros + 0.1, 0.0)
    lowers = zeros - 0.1
    lowers[:40] = 0.005  # Mintmed excludes zero in 8% of datasets, the comparator never
    mintmed = _effect_frame(zeros + 0.01, lowers, zeros + 0.1, 0.0)
    comparison = rep.paired_comparison(mintmed, comparator, tool="mediation", cell_id="cell13_a_path_only_n100",
                                       effect="TNIE", population_sd=1.05, null_effect=True)
    assert comparison["power_loss_pp"] is None
    assert math.isclose(comparison["false_positive_excess_pp"], 8.0)
    assert comparison["false_positive_excess_pp_upper"] > 3.0
    assert math.isclose(comparison["decision_agreement"], 460 / 500)
    assert rep.classify_tier(comparison)["tier"] == "substantive"


def test_classify_tier_thresholds_and_not_applicable_checks() -> None:
    base = {
        "decision_agreement": 0.99, "decision_agreement_lower": 0.98,
        "sign_agreement": 1.0, "sign_agreement_lower": 0.995,
        "bias_excess_sd_upper": 0.01, "coverage_loss_pp_upper": 1.0, "false_positive_excess_pp_upper": None,
        "power_loss_pp_upper": 2.0, "width_ratio_upper": 1.05, "mintmed_coverage": 0.95,
    }
    assert rep.classify_tier(base)["tier"] == "negligible"
    assert rep.classify_tier({**base, "coverage_loss_pp_upper": 4.0})["tier"] == "tolerable"
    assert rep.classify_tier({**base, "coverage_loss_pp_upper": 4.0, "mintmed_coverage": 0.89})["tier"] == "substantive"
    assert rep.classify_tier({**base, "decision_agreement_lower": 0.92})["tier"] == "tolerable"
    assert rep.classify_tier({**base, "decision_agreement_lower": 0.89})["tier"] == "substantive"
    # Sign agreement and bias are not relaxed by the tolerable tier.
    assert rep.classify_tier({**base, "sign_agreement_lower": 0.98})["tier"] == "substantive"
    assert rep.classify_tier({**base, "bias_excess_sd_upper": 0.03})["tier"] == "substantive"
    # Point basis: a perfect rate with a small Wilson bound passes.
    small = {**base, "sign_agreement_lower": 0.97}
    assert rep.classify_tier(small)["tier"] == "substantive"
    assert rep.classify_tier(small, primary_basis="point")["tier"] == "negligible"
    # Not applicable checks never fail.
    point_only = {"bias_excess_sd_upper": 0.001}
    verdict = rep.classify_tier(point_only)
    assert verdict["tier"] == "negligible" and verdict["applicable_checks"] == ["bias_excess_sd"]


def test_reference_with_other_seeds_is_refused(tmp_path: Path, v3) -> None:
    data_seed, analysis_seed = seed_pair(v3.master_seed, 1, 0)
    record = {"TNIE": {"truth": 0.25, "estimate": 0.2, "lower": 0.1, "upper": 0.3}}
    rows = pd.DataFrame([{"cell_id": "cell01_linear_n100", "replicate": 0, "data_seed": str(data_seed),
                          "analysis_seed": str(analysis_seed), "metrics_json": json.dumps(record)}])
    good = tmp_path / "good.csv"
    rows.to_csv(good, index=False)
    reference = rep.load_mintmed_reference([good])
    rep.check_reference_seeds(reference, v3.master_seed)
    bad = tmp_path / "bad.csv"
    rows.assign(analysis_seed="1").to_csv(bad, index=False)
    with pytest.raises(ValueError, match="other seeds"):
        rep.check_reference_seeds(rep.load_mintmed_reference([bad]), v3.master_seed)


# --- frozen Stage 1 charter rules (noise-floor judging) -----------------------------


def _noisy_bootstrap_frame(estimates: np.ndarray, se: float, truth: float, rng: np.random.Generator,
                           jitter: float) -> pd.DataFrame:
    """Percentile-like intervals of one estimator; ``jitter`` mimics the Monte Carlo error of 399 refits."""

    lowers = estimates - 1.96 * se + jitter * rng.standard_normal(len(estimates))
    uppers = estimates + 1.96 * se + jitter * rng.standard_normal(len(estimates))
    return _effect_frame(estimates, lowers, uppers, truth)


def _three_runs(seed: int, *, n: int = 500, truth: float = 0.25, se: float = 0.12, jitter: float = 0.015):
    """Mintmed, a comparator and the comparator's rerun: the same point estimates, independent interval noise."""

    rng = np.random.default_rng(seed)
    estimates = truth + se * rng.standard_normal(n)
    return tuple(_noisy_bootstrap_frame(estimates, se, truth, rng, jitter) for _ in range(3)), estimates


def _charter(mintmed, comparator, rerun, *, null_effect=False, effect="TNIE", cell="cell01_linear_n100"):
    comparison = rep.paired_comparison(
        mintmed, comparator, tool="mediation", cell_id=cell, effect=effect, population_sd=1.2,
        null_effect=null_effect, noise_floor=rep.noise_floor_frame(comparator, rerun),
    )
    return comparison, rep.classify_charter_tier(comparison)


def test_charter_rules_are_the_owner_decision() -> None:
    negligible, tolerable = rep.CHARTER_RULES["negligible"], rep.CHARTER_RULES["tolerable"]
    assert negligible == {
        "decision_excess_pp_upper_max": 5.0, "opposite_significant_pairs_max": 0, "sign_agreement_min": 0.99,
        "coverage_loss_pp_max": 2.5, "coverage_loss_pp_upper_max": 5.0, "false_positive_excess_pp_max": 2.0,
        "power_loss_pp_upper_max": 5.0, "width_ratio_upper_max": 1.10, "bias_excess_sd_upper_max": 0.02,
    }
    assert tolerable == {
        "decision_excess_pp_upper_max": 10.0, "opposite_significant_pairs_max": 0, "sign_agreement_min": 0.99,
        "coverage_loss_pp_upper_max": 5.0, "coverage_abs_min": 0.90, "false_positive_excess_pp_max": 3.0,
        "power_loss_pp_upper_max": 10.0, "width_ratio_upper_max": 1.25, "bias_excess_sd_upper_max": 0.02,
    }
    # The confirmed plan limits are unchanged; only what they are judged on changed.
    assert rep.COMPARISON_RULES["guardrails"]["coverage_loss_pp_max"] == negligible["coverage_loss_pp_max"]
    assert rep.COMPARISON_RULES["guardrails"]["false_positive_excess_pp_max"] == negligible["false_positive_excess_pp_max"]
    assert rep.COMPARISON_RULES["tolerable"]["false_positive_excess_pp_max"] == tolerable["false_positive_excess_pp_max"]


def test_noise_floor_counts_only_disagreements_between_two_available_intervals() -> None:
    a = _effect_frame([0.3, 0.3, 0.3, 0.3], [0.1, -0.1, 0.1, np.nan], [0.5, 0.5, 0.5, np.nan], 0.25)
    b = _effect_frame([0.3, 0.3, 0.3, 0.3], [0.1, 0.1, np.nan, 0.1], [0.5, 0.5, np.nan, 0.5], 0.25)
    floor = rep.noise_floor_frame(a, b)
    assert floor["floor_disagree"].tolist() == [0.0, 1.0, 0.0, 0.0]


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_identical_methods_with_bootstrap_noise_are_negligible(seed: int) -> None:
    (mintmed, comparator, rerun), _ = _three_runs(seed)
    comparison, verdict = _charter(mintmed, comparator, rerun)
    # The noise is real: two runs of one method disagree on a few percent of datasets ...
    assert 1.0 < comparison["noise_floor_pp"] < 10.0 and comparison["decision_disagreement_pp"] > 1.0
    # ... so the absolute T17-S3 rule would not call them negligible, while the excess rule does.
    assert comparison["noise_floor_measured"] and comparison["decision_excess_pairs"] == 500
    assert comparison["opposite_significant_pairs"] == 0
    assert verdict["tier"] == "negligible", (verdict["failed_negligible"], comparison)


def test_identical_methods_on_a_null_effect_are_negligible() -> None:
    (mintmed, comparator, rerun), _ = _three_runs(21, truth=0.0, se=0.05, jitter=0.006)
    comparison, verdict = _charter(mintmed, comparator, rerun, null_effect=True, cell="cell14_b_path_only_n100")
    assert comparison["power_loss_pp"] is None and comparison["false_positive_excess_pp"] is not None
    assert verdict["tier"] == "negligible", (verdict["failed_negligible"], comparison)


def test_a_real_excess_disagreement_is_flagged() -> None:
    (_, comparator, rerun), estimates = _three_runs(31)
    rng = np.random.default_rng(32)
    # Mintmed's intervals carry much more Monte Carlo noise: they flip the decision far more often.
    mintmed = _noisy_bootstrap_frame(estimates, 0.12, 0.25, rng, 0.09)
    comparison, verdict = _charter(mintmed, comparator, rerun)
    assert comparison["decision_excess_pp_upper"] > 10.0
    assert verdict["negligible_checks"]["decision_excess"] is False
    assert verdict["tolerable_checks"]["decision_excess"] is False
    assert verdict["tier"] == "substantive"


def test_a_moderate_excess_disagreement_is_tolerable_not_negligible() -> None:
    base = {"decision_excess_pp": 4.0, "decision_excess_pp_upper": 7.5, "opposite_significant_pairs": 0,
            "sign_agreement": 1.0, "coverage_loss_pp": 0.0, "coverage_loss_pp_upper": 1.5, "mintmed_coverage": 0.95,
            "power_loss_pp_upper": 2.0, "width_ratio_upper": 1.02, "bias_excess_sd_upper": 0.0}
    verdict = rep.classify_charter_tier(base)
    assert verdict["tier"] == "tolerable" and verdict["failed_negligible"] == ["decision_excess"]
    assert rep.classify_charter_tier({**base, "decision_excess_pp_upper": 5.0})["tier"] == "negligible"
    assert rep.classify_charter_tier({**base, "decision_excess_pp_upper": 10.2})["tier"] == "substantive"


def test_a_real_six_point_coverage_loss_is_flagged() -> None:
    (mintmed, comparator, rerun), _ = _three_runs(41, jitter=0.0)
    comparator = mintmed.copy()
    rerun = mintmed.copy()
    mintmed = mintmed.copy()
    # 30 of 500 datasets (6 pp) where both cover: shift Mintmed's interval off the truth but keep its decision.
    covered = mintmed.index[mintmed["coverage"] & (mintmed["lower"] > 0)][:30]
    assert len(covered) == 30
    shift = (0.25 - mintmed.loc[covered, "lower"]) + 0.01
    mintmed.loc[covered, "lower"] += shift
    mintmed.loc[covered, "upper"] += shift
    mintmed.loc[covered, "coverage"] = False
    comparison, verdict = _charter(mintmed, comparator, rerun)
    assert math.isclose(comparison["coverage_loss_pp"], 6.0)
    assert comparison["decision_disagreement_pp"] == 0.0 and comparison["coverage_loss_pp_upper"] > 5.0
    assert verdict["negligible_checks"]["coverage_loss"] is False
    assert verdict["tolerable_checks"]["coverage_loss_upper"] is False
    assert verdict["tier"] == "substantive"


def test_one_opposite_sign_significant_pair_forces_substantive() -> None:
    (mintmed, comparator, rerun), _ = _three_runs(51)
    assert _charter(mintmed, comparator, rerun)[1]["tier"] == "negligible"
    mintmed = mintmed.copy()
    comparator = comparator.copy()
    index = mintmed.index[mintmed["lower"] > 0][0]
    comparator.loc[index, ["estimate", "lower", "upper"]] = [-0.3, -0.5, -0.1]
    comparison, verdict = _charter(mintmed, comparator, rerun)
    assert comparison["opposite_significant_pairs"] == 1
    assert verdict["negligible_checks"]["opposite_significant"] is False
    assert verdict["tolerable_checks"]["opposite_significant"] is False
    assert verdict["tier"] == "substantive"


def test_observed_value_rules_and_limit_edges() -> None:
    base = {"decision_excess_pp_upper": 1.0, "opposite_significant_pairs": 0, "sign_agreement": 1.0,
            "coverage_loss_pp": 0.0, "coverage_loss_pp_upper": 2.0, "mintmed_coverage": 0.94,
            "power_loss_pp_upper": 2.0, "width_ratio_upper": 1.05, "bias_excess_sd_upper": 0.005}
    assert rep.classify_charter_tier(base)["tier"] == "negligible"
    # Coverage: point <= 2.5 and upper <= 5 for negligible; upper <= 5 and coverage >= 0.90 for tolerable.
    assert rep.classify_charter_tier({**base, "coverage_loss_pp": 2.5, "coverage_loss_pp_upper": 4.9})["tier"] == "negligible"
    assert rep.classify_charter_tier({**base, "coverage_loss_pp": 3.0, "coverage_loss_pp_upper": 4.9})["tier"] == "tolerable"
    assert rep.classify_charter_tier({**base, "coverage_loss_pp": 2.0, "coverage_loss_pp_upper": 5.4})["tier"] == "substantive"
    assert rep.classify_charter_tier({**base, "coverage_loss_pp": 3.0, "coverage_loss_pp_upper": 4.9,
                                      "mintmed_coverage": 0.89})["tier"] == "substantive"
    # False positives (null effects): observed excess, exact counts at the limit pass.
    null = {**base, "power_loss_pp_upper": None}
    assert rep.classify_charter_tier({**null, "false_positive_excess_pp": 100 * (10 / 500),
                                      "false_positive_excess_pp_upper": 4.0})["tier"] == "negligible"
    assert rep.classify_charter_tier({**null, "false_positive_excess_pp": 2.2})["tier"] == "tolerable"
    assert rep.classify_charter_tier({**null, "false_positive_excess_pp": 3.2})["tier"] == "substantive"
    # Sign agreement on the observed rate, not relaxed by the tolerable tier.
    assert rep.classify_charter_tier({**base, "sign_agreement": 0.99, "sign_agreement_lower": 0.95})["tier"] == "negligible"
    assert rep.classify_charter_tier({**base, "sign_agreement": 0.985})["tier"] == "substantive"
    # Upper-bound guardrails.
    assert rep.classify_charter_tier({**base, "power_loss_pp_upper": 7.0})["tier"] == "tolerable"
    assert rep.classify_charter_tier({**base, "power_loss_pp_upper": 11.0})["tier"] == "substantive"
    assert rep.classify_charter_tier({**base, "width_ratio_upper": 1.2})["tier"] == "tolerable"
    assert rep.classify_charter_tier({**base, "width_ratio_upper": 1.3})["tier"] == "substantive"
    assert rep.classify_charter_tier({**base, "bias_excess_sd_upper": 0.021})["tier"] == "substantive"
    # Not-applicable checks never fail (point-only Mintmed effects).
    verdict = rep.classify_charter_tier({"bias_excess_sd_upper": 0.001})
    assert verdict["tier"] == "negligible" and verdict["applicable_checks"] == ["bias_excess"]


def test_missing_floor_uses_zero_and_is_stricter() -> None:
    (mintmed, comparator, rerun), _ = _three_runs(61)
    with_floor, _ = _charter(mintmed, comparator, rerun)
    without = rep.paired_comparison(mintmed, comparator, tool="lavaan", cell_id="cell07_serial_three_n200",
                                    effect="TNIE", population_sd=1.4, null_effect=False)
    assert without["noise_floor_measured"] is False and without["noise_floor_pp"] == 0.0
    assert math.isclose(without["decision_excess_pp"], without["decision_disagreement_pp"])
    assert without["decision_excess_pp_upper"] > with_floor["decision_excess_pp_upper"]


def _raw_rows(tool: str, cell: str, frames: pd.DataFrame, config, modes) -> list[dict]:
    rows = []
    truth = cb.effect_truths(cell)
    for replicate in range(len(frames)):
        record = cb.comparator_record(truth["TNIE"], frames["estimate"][replicate], frames["lower"][replicate],
                                      frames["upper"][replicate], status="ok")
        others = {effect: cb.comparator_record(value, value, value - 0.3, value + 0.3, status="ok")
                  for effect, value in truth.items() if effect != "TNIE"}
        records = {mode: {"TNIE": record, **others} for mode in modes}
        rows.append(cb.build_row(config=config, tool=tool, cell_id=cell, replicate=replicate, records=records,
                                 provenance={}))
    return rows


def test_compare_with_mintmed_uses_the_reseed_floor_and_skips_the_rerun(tmp_path: Path) -> None:
    cell = "cell01_linear_n100"
    config = load_config(_small_config(tmp_path, [cell], replicates=500))
    (mintmed, comparator, rerun), _ = _three_runs(71)
    raw = pd.DataFrame(
        _raw_rows("mediation", cell, comparator, config, cb.MODES)
        + _raw_rows("lavaan", cell, comparator, config, cb.MODES)
        + _raw_rows("mediation_reseed", cell, rerun, config, ("primary",)),
        columns=list(cb.RAW_COLUMNS),
    )
    long = rep.expand_records(raw)
    reference_rows = []
    for replicate in range(500):
        data_seed, analysis_seed = seed_pair(config.master_seed, 1, replicate)
        metrics = {"TNIE": {"truth": 0.25, "estimate": float(mintmed["estimate"][replicate]),
                            "lower": float(mintmed["lower"][replicate]), "upper": float(mintmed["upper"][replicate]),
                            "coverage": bool(mintmed["coverage"][replicate]), "width": float(mintmed["width"][replicate]),
                            "zero_exclusion": bool(mintmed["zero_exclusion"][replicate]), "interval_available": True,
                            "bias": float(mintmed["bias"][replicate])}}
        reference_rows.append({"cell_id": cell, "replicate": replicate, "data_seed": str(data_seed),
                               "analysis_seed": str(analysis_seed), "metrics_json": json.dumps(metrics)})
    reference_path = tmp_path / "mintmed.csv"
    pd.DataFrame(reference_rows).to_csv(reference_path, index=False)
    payload = rep.write_report(raw, config, tmp_path / "report", mintmed_raw_paths=[reference_path])
    comparisons = pd.DataFrame(payload["paired_comparisons"])
    tnie = comparisons.loc[comparisons["effect"] == "TNIE"].set_index("tool")
    assert set(tnie.index) == {"mediation", "lavaan"}  # the rerun is a floor, not a comparator
    assert tnie["noise_floor_measured"].all()
    # Both comparators share the cell's mediate-vs-mediate floor.
    assert tnie.loc["mediation", "noise_floor_pp"] == tnie.loc["lavaan", "noise_floor_pp"] > 0
    assert (tnie["tier"] == "negligible").all()
    assert payload["charter_rules"] == rep.CHARTER_RULES
    report = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "noise floor" in report and "**negligible**" in report


# --- Stage 1 run configurations (T17-S7) ----------------------------------------------


def _analysis_settings(config) -> dict:
    canonical = config.canonical_dict
    return {key: canonical[key] for key in ("schema_version", "bootstrap_replicates", "bootstrap_mode",
                                            "integration_draws", "integration_tolerance", "max_seconds",
                                            "memory_budget_mb", "gates")}


def test_mintmed_cells15_16_config_reproduces_the_v3_datasets_and_settings(v3) -> None:
    config = load_config(ROOT / "configs" / "comparator_mintmed_cells15_16.yaml")
    assert config.cell_ids == ("cell15_a_path_only_n250", "cell16_b_path_only_n250")
    assert set(config.cell_ids) <= set(v3.cell_ids)
    assert config.master_seed == v3.master_seed == 20260927 and config.replicates == v3.replicates == 500
    assert _analysis_settings(config) == _analysis_settings(v3)
    assert not config.stress_enabled


def test_pilot_config_uses_the_calibration_seed_not_the_evaluation_seed(v3) -> None:
    config = load_config(ROOT / "configs" / "comparator_pilot.yaml")
    assert config.master_seed == 20260929 != v3.master_seed
    assert _analysis_settings(config) == _analysis_settings(v3)
    assert set(config.cell_ids) <= set(v3.cell_ids)
    supported = {tool: {cell for cell in config.cell_ids if cb.is_supported(tool, cell)} for tool in cb.TOOLS}
    assert supported["mediation"] - supported["lavaan"] and supported["lavaan"] - supported["mediation"]
    assert supported["mediation"] & supported["lavaan"]
