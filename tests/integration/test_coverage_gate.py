"""Coverage-gate rules: the run-1 Wilson rule and the Option B exact binomial rule."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from scipy.stats import binom

from mintmed.experiments.mediation_validation import (
    RAW_COLUMNS,
    coverage_rule,
    load_config,
    metric_record,
)
from mintmed.experiments.mediation_validation_reporting import (
    coverage_critical_count,
    evaluate_gates,
    expand_metrics,
    summarize_metrics,
    write_report,
)

ROOT = Path(__file__).parents[2]
SMOKE = ROOT / "configs" / "mediation_validation_smoke.yaml"
FULL = ROOT / "configs" / "mediation_validation.yaml"
RUN1_CONFIG_HASH = "176be1124d5b0525107af4a5b5cc265c805fdb82b9caeef63ee2716aaa968f94"
TRUTHS = {"TE": 0.45, "PNDE": 0.2, "TNIE": 0.25}


def _write_config(tmp_path: Path, *, exact: bool, replicates: int = 20, **gate_overrides: float) -> Path:
    raw = yaml.safe_load(SMOKE.read_text(encoding="utf-8"))
    raw["replicates"] = replicates
    raw["cell_ids"] = ["cell01_linear_n100"]
    if exact:
        del raw["gates"]["coverage_wilson_lower"]
        raw["gates"]["coverage_family_alpha"] = 0.05
        raw["gates"]["coverage_nominal"] = 0.95
    raw["gates"].update(gate_overrides)
    path = tmp_path / ("exact.yaml" if exact else "wilson.yaml")
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def _raw_rows(config, covered: dict[str, int]) -> pd.DataFrame:
    """Rows for cell 01 where metric ``m`` covers the truth in ``covered[m]`` replicates.

    Misses place the whole interval below the truth, so the truth is above it.
    """

    rows = []
    for replicate in range(config.replicates):
        metrics = {}
        for name, truth in TRUTHS.items():
            if replicate < covered[name]:
                metrics[name] = metric_record(truth, truth, truth - 0.1, truth + 0.1, status="complete")
            else:
                metrics[name] = metric_record(truth, truth - 0.3, truth - 0.4, truth - 0.2, status="complete")
        first = metrics["TE"]
        row = {
            "cell_id": "cell01_linear_n100",
            "replicate": replicate,
            "data_seed": 1,
            "analysis_seed": 2,
            "config_hash": config.config_hash,
            "truth_method": "closed_form",
            "outcome_kind": "continuous",
            "estimand": "TE",
            "truth": first["truth"],
            "estimate": first["estimate"],
            "bias": first["bias"],
            "lower": first["lower"],
            "upper": first["upper"],
            "coverage": first["coverage"],
            "width": first["width"],
            "zero_exclusion": first["zero_exclusion"],
            "interval_available": first["interval_available"],
            "status": first["status"],
            "failure_code": None,
            "failure_message": None,
            "runtime_seconds": 0.1,
            "fit_count": 2,
            "draw_budget": 256,
            "metrics_json": json.dumps(metrics),
            "provenance_json": json.dumps({"config_hash": config.config_hash}),
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=list(RAW_COLUMNS))


def _gates(config, covered: dict[str, int]) -> dict:
    raw = _raw_rows(config, covered)
    summary = summarize_metrics(expand_metrics(raw, config), raw, config)
    return evaluate_gates(summary, raw, config)


@pytest.mark.parametrize(
    ("trials", "gated_effects", "expected"),
    [(500, 38, 458), (500, 32, 459), (200, 32, 179), (20, 3, 16)],
)
def test_critical_count_matches_the_frozen_plan(trials: int, gated_effects: int, expected: int) -> None:
    count = coverage_critical_count(trials, gated_effects, 0.95, 0.05)

    assert count == expected
    per_effect_alpha = 0.05 / gated_effects
    assert binom.cdf(count, trials, 0.95) <= per_effect_alpha
    assert binom.cdf(count + 1, trials, 0.95) > per_effect_alpha


def test_critical_count_rejects_empty_denominators() -> None:
    with pytest.raises(ValueError, match="positive"):
        coverage_critical_count(0, 32, 0.95, 0.05)
    with pytest.raises(ValueError, match="positive"):
        coverage_critical_count(500, 0, 0.95, 0.05)


def test_run1_config_keeps_its_hash_and_wilson_rule() -> None:
    config = load_config(FULL)

    assert config.config_hash == RUN1_CONFIG_HASH
    assert coverage_rule(dict(config.gates)) == "wilson_lower"


def test_exact_rule_config_loads_with_a_distinct_hash(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, exact=True))

    assert coverage_rule(dict(config.gates)) == "exact_binomial_bonferroni"
    assert dict(config.gates)["coverage_family_alpha"] == pytest.approx(0.05)
    assert config.config_hash != load_config(_write_config(tmp_path, exact=False)).config_hash


@pytest.mark.parametrize(
    "edit",
    [
        {"coverage_family_alpha": 0.05, "coverage_nominal": 0.95},  # both rules declared
        {"coverage_family_alpha": 0.05},  # Wilson plus a partial exact rule
    ],
)
def test_config_rejects_ambiguous_coverage_rules(tmp_path: Path, edit: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="exactly one complete coverage rule"):
        load_config(_write_config(tmp_path, exact=False, **edit))


def test_config_rejects_missing_or_partial_coverage_rules(tmp_path: Path) -> None:
    raw = yaml.safe_load(SMOKE.read_text(encoding="utf-8"))
    del raw["gates"]["coverage_wilson_lower"]
    path = tmp_path / "none.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one complete coverage rule"):
        load_config(path)

    raw["gates"]["coverage_nominal"] = 0.95
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one complete coverage rule"):
        load_config(path)


@pytest.mark.parametrize("key", ["coverage_family_alpha", "coverage_nominal"])
@pytest.mark.parametrize("value", [0.0, 1.0])
def test_config_rejects_degenerate_exact_rule_probabilities(tmp_path: Path, key: str, value: float) -> None:
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        load_config(_write_config(tmp_path, exact=True, **{key: value}))


def test_exact_rule_fails_only_effects_at_or_below_the_critical_count(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, exact=True))
    # k = 3 gated effects and n = 20, so the critical count is 16.
    result = _gates(config, {"TE": 17, "PNDE": 16, "TNIE": 20})
    gate = result["gates"]["coverage_exact_binomial_bonferroni"]

    assert "coverage_wilson_lower" not in result["gates"]
    assert gate["gated_effects"] == 3
    assert gate["threshold"] == pytest.approx(0.05 / 3)
    assert gate["failing_effects"] == ["cell01_linear_n100:PNDE"]
    assert gate["passed"] is False
    assert result["overall_pass"] is False
    effects = {effect["metric"]: effect for effect in gate["effects"]}
    assert {effect["critical_count"] for effect in effects.values()} == {16}
    assert effects["PNDE"]["p_value"] == pytest.approx(binom.cdf(16, 20, 0.95))
    assert effects["TE"]["passed"] is True
    assert effects["PNDE"]["truth_above_interval_rows"] == 4
    assert effects["PNDE"]["truth_below_interval_rows"] == 0
    assert gate["observed"] == pytest.approx(effects["PNDE"]["p_value"])


def test_exact_rule_passes_when_every_effect_clears_the_critical_count(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, exact=True))
    gate = _gates(config, {"TE": 17, "PNDE": 17, "TNIE": 19})["gates"]["coverage_exact_binomial_bonferroni"]

    assert gate["failing_effects"] == []
    assert gate["passed"] is True


def test_wilson_rule_still_fails_low_coverage(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, exact=False))
    result = _gates(config, {"TE": 17, "PNDE": 17, "TNIE": 19})

    assert "coverage_exact_binomial_bonferroni" not in result["gates"]
    wilson_gate = result["gates"]["coverage_wilson_lower"]
    # 17/20 has a Wilson lower bound near 0.64, far below the 0.90 threshold.
    assert wilson_gate["observed"] < 0.90
    assert wilson_gate["passed"] is False


def test_report_lists_every_effect_under_the_exact_rule(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, exact=True))
    raw = _raw_rows(config, {"TE": 17, "PNDE": 16, "TNIE": 20})
    output = tmp_path / "report"

    write_report(raw, config, output)

    report = (output / "report.md").read_text(encoding="utf-8")
    assert "### Coverage: exact binomial with Bonferroni adjustment" in report
    assert "| cell01_linear_n100 | PNDE | 16 | 20 | 16 |" in report
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["gates"]["gates"]["coverage_exact_binomial_bonferroni"]["failing_effects"] == [
        "cell01_linear_n100:PNDE"
    ]
    cells = pd.read_csv(output / "cell_summary.csv")
    assert {"truth_above_interval_rows", "truth_below_interval_rows"} <= set(cells.columns)
