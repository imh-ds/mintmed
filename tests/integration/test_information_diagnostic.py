"""Tests for the Task 18 information-diagnostic runner (T18-S4)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from mintmed.experiments import diagnostic_mechanisms as dm
from mintmed.experiments import information_diagnostic as idg
from mintmed.experiments import information_diagnostic_reporting as rep
from scripts.aggregate_shards import aggregate

REPO = Path(__file__).resolve().parents[2]


def _tiny_config(tmp_path: Path, **overrides) -> Path:
    raw = yaml.safe_load((REPO / "configs" / "information_diagnostic_calibration.yaml").read_text(encoding="utf-8"))
    raw.update(
        {
            "experiment": "tiny_information_diagnostic",
            "replicates": 2,
            "sample_sizes": [80],
            "mechanisms": ["N1_linear", "E2_omitted_interaction"],
        }
    )
    raw["information"]["permutations"] = 19
    raw.update(overrides)
    path = tmp_path / "tiny.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_shipped_configs_match_the_plan() -> None:
    calibration = idg.load_config(REPO / "configs" / "information_diagnostic_calibration.yaml")
    evaluation = idg.load_config(REPO / "configs" / "information_diagnostic_evaluation.yaml")
    pilot = idg.load_config(REPO / "configs" / "information_diagnostic_pilot.yaml")
    assert calibration.master_seed == dm.CALIBRATION_SEED == 20261001
    assert evaluation.master_seed == dm.EVALUATION_SEED == 20261002
    assert pilot.master_seed not in {dm.CALIBRATION_SEED, dm.EVALUATION_SEED}
    assert calibration.replicates == 200 and evaluation.replicates == 500
    for config in (calibration, evaluation, pilot):
        assert config.sample_sizes == dm.SAMPLE_SIZES
        assert set(config.mechanisms) == set(dm.MECHANISMS)
        assert (config.permutations, config.k_cmi_fraction, config.k_perm, config.folds) == (199, 0.1, 5, 5)
        assert config.sensitivity_k_cmi_fraction == 0.2
    # Evaluation differs from calibration only in its identity, seed and size.
    same = dict(calibration.canonical_dict)
    other = dict(evaluation.canonical_dict)
    for key in ("experiment", "purpose", "master_seed", "replicates"):
        same.pop(key)
        other.pop(key)
    assert same == other
    assert idg.expected_row_count(calibration) == 9 * 3 * 200 * 2


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown"):
        idg.load_config(_tiny_config(tmp_path, thresholds={"information": 0.05}))
    with pytest.raises(ValueError):
        idg.load_config(_tiny_config(tmp_path, mechanisms=["not_a_mechanism"]))


def test_analysis_seed_is_deterministic_and_separate() -> None:
    seed = idg.analysis_seed(20261001, "N1_linear", 100, 3, "outcome")
    assert seed == idg.analysis_seed(20261001, "N1_linear", 100, 3, "outcome")
    others = {
        idg.analysis_seed(20261001, "N1_linear", 100, 3, "mediator"),
        idg.analysis_seed(20261001, "N1_linear", 100, 4, "outcome"),
        idg.analysis_seed(20261001, "N2_curved_declared", 100, 3, "outcome"),
        idg.analysis_seed(20261002, "N1_linear", 100, 3, "outcome"),
    }
    assert seed not in others and len(others) == 4


def test_rows_follow_the_contract(tmp_path: Path) -> None:
    config = idg.load_config(_tiny_config(tmp_path))
    rows = idg.analyse_dataset(config, "E2_omitted_interaction", 80, 1)
    assert [row["node"] for row in rows] == ["outcome", "mediator"]
    outcome, mediator = rows
    assert set(outcome) == set(idg.RAW_COLUMNS)
    assert outcome["formula"] == "Y ~ A + M + C" and mediator["formula"] == "M ~ A + C"
    assert outcome["info_status"] == "ok" and outcome["info_insample_status"] == "ok"
    assert outcome["info_k20_status"] == "ok"
    assert outcome["info_stratum_n0"] + outcome["info_stratum_n1"] == 80
    assert outcome["lof_mean_curvature_M_status"] == "ok" and outcome["lof_mean_curvature_C_p"] is None
    assert mediator["info_insample_p_value"] is None and mediator["info_k20_p_value"] is None
    assert mediator["lof_mean_interaction_AC_status"] == "ok"
    # Reproducible, and the information p-value is a permutation p-value.
    again = idg.analyse_dataset(config, "E2_omitted_interaction", 80, 1)
    for first, second in zip(rows, again, strict=True):
        for key in ("info_statistic", "info_p_value", "lof_min_adjusted_p", "info_k20_statistic", "analysis_seed"):
            assert first[key] == second[key]
    assert round(outcome["info_p_value"] * 20) == pytest.approx(outcome["info_p_value"] * 20)


def test_sensitivities_can_be_switched_off(tmp_path: Path) -> None:
    raw = yaml.safe_load(_tiny_config(tmp_path).read_text(encoding="utf-8"))
    raw["information"]["sensitivities"] = False
    path = tmp_path / "nosens.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = idg.load_config(path)
    outcome = idg.analyse_dataset(config, "N1_linear", 80, 0)[0]
    assert outcome["info_insample_p_value"] is None and outcome["info_k20_p_value"] is None


def test_shards_aggregate_to_a_complete_grid(tmp_path: Path) -> None:
    config_path = _tiny_config(tmp_path)
    config = idg.load_config(config_path)
    shards = tmp_path / "shards"
    for mechanism in config.mechanisms:
        for block in ("0of2", "1of2"):
            code = idg.main(
                ["--config", str(config_path), "--output", str(shards / f"shard-{mechanism}-{block}"),
                 "--mechanism", mechanism, "--replicate-block", block, "--no-report"]
            )
            assert code == 0
    raw = aggregate("mintmed.experiments.information_diagnostic", config_path, shards, tmp_path / "agg")
    assert len(raw) == idg.expected_row_count(config) == 8
    summary = json.loads((tmp_path / "agg" / "summary.json").read_text(encoding="utf-8"))
    assert summary["grid"]["complete"] is True
    cells = pd.read_csv(tmp_path / "agg" / "cell_summary.csv")
    assert len(cells) == 4
    assert (cells["datasets"] == 2).all()
    assert (tmp_path / "agg" / "report.md").is_file()
    assert (tmp_path / "agg" / "runtime_summary.csv").is_file()

    # A missing shard is refused by the aggregator; a missing row by the report.
    missing = tmp_path / "missing"
    missing.mkdir()
    for path in shards.iterdir():
        if path.name != "shard-N1_linear-1of2":
            (missing / path.name).mkdir()
            (missing / path.name / "raw_metrics.csv").write_text(
                (path / "raw_metrics.csv").read_text(encoding="utf-8"), encoding="utf-8"
            )
    with pytest.raises(SystemExit):
        aggregate("mintmed.experiments.information_diagnostic", config_path, missing, tmp_path / "agg2")
    with pytest.raises(ValueError, match="incomplete"):
        rep.write_report(raw.iloc[1:], config, tmp_path / "agg3")


def test_resume_skips_finished_datasets(tmp_path: Path) -> None:
    config_path = _tiny_config(tmp_path)
    config = idg.load_config(config_path)
    out = tmp_path / "out"
    first = idg.run(config, out, mechanisms=["N1_linear"], replicate_stop=1, no_report=True)
    assert len(first) == 2
    second = idg.run(config, out, mechanisms=["N1_linear"], no_report=False)
    assert len(second) == 4
    assert not second.duplicated(subset=["mechanism", "n", "replicate", "node"]).any()


def test_warning_rule_counts_unavailable_as_no_warning() -> None:
    frame = pd.DataFrame(
        {
            "info_p_value": [0.01, 0.05, 0.2, None],
            "info_status": ["ok", "ok", "ok", "diagnostic_unavailable"],
        }
    )
    assert rep.arm_warnings(frame, "information", 0.05).tolist() == [True, True, False, False]
    low, high = rep.wilson(0, 200)
    assert low == pytest.approx(0.0, abs=1e-12) and 0.0 < high < 0.02
