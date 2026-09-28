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
    combos = cb.expected_combinations(v3)
    assert cb.expected_row_count(v3) == len(combos) == 2 * 16 * 500
    assert {tool for tool, _, _ in combos} == set(cb.TOOLS)
    assert {cell for _, cell, _ in combos} == set(v3.cell_ids)


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
    assert len(raw) == 2 * 2 * 2
    assert set(raw["status"]) == {"not_estimable"}
    assert not raw["supported"].astype(bool).any()
    for row in raw.itertuples():
        records = json.loads(row.records_json)
        assert set(records) == set(cb.MODES)
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
    assert len(raw) == cb.expected_row_count(config) == 2 * 2 * 2
    summary = json.loads((tmp_path / "agg" / "summary.json").read_text(encoding="utf-8"))
    assert summary["complete_grid"] is True
    assert all(item["estimable"] is False for item in summary["summaries"])
    assert (tmp_path / "agg" / "report.md").read_text(encoding="utf-8").count("not estimable") == 2 * 2 * (1 + 3)


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
