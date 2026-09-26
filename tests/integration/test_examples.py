"""Contracts that keep the shipped examples realistic and CI-checked."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from mintmed.cli import main as cli_main
from mintmed.spec import ComputationSpec

ROOT = Path(__file__).parents[2]
EXAMPLES = ("single", "parallel", "serial_moderated")
DEFAULT_TOLERANCE = ComputationSpec(seed=1, bootstrap=0, integration_draws=256).integration_tolerance


@pytest.mark.parametrize("example", EXAMPLES)
def test_examples_use_the_default_tolerance_and_a_real_quick_diagnostic_bootstrap(example: str) -> None:
    spec = yaml.safe_load((ROOT / "examples" / example / "analysis.yaml").read_text(encoding="utf-8"))
    computation = spec["computation"]

    assert computation["integration_tolerance"] == DEFAULT_TOLERANCE
    assert computation["bootstrap"] >= 50
    assert computation["bootstrap_mode"] == "quick_diagnostic"
    assert len(pd.read_csv(ROOT / "examples" / example / "data.csv")) >= 100


def test_validation_smoke_config_uses_the_default_tolerance() -> None:
    config = yaml.safe_load((ROOT / "configs" / "mediation_validation_smoke.yaml").read_text(encoding="utf-8"))

    assert config["integration_tolerance"] == DEFAULT_TOLERANCE


def test_example_data_are_reproduced_by_the_generator_script() -> None:
    from scripts.generate_example_data import example_frames

    for example, frame in example_frames().items():
        committed = (ROOT / "examples" / example / "data.csv").read_text(encoding="utf-8")
        assert frame.to_csv(index=False, lineterminator="\n") == committed


def _write_analysis(path: Path, *, overall: str, attempted: int, failed: int) -> Path:
    path.mkdir(parents=True)
    payload = {
        "overall_status": overall,
        "bootstrap": {"requested": attempted, "attempted": attempted, "successful": attempted - failed, "failed": failed},
    }
    (path / "analysis.json").write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_output_checker_accepts_healthy_runs_and_rejects_degraded_ones(tmp_path: Path) -> None:
    from scripts.check_example_outputs import check_output_dir

    assert check_output_dir(_write_analysis(tmp_path / "ok", overall="complete_with_warnings", attempted=50, failed=5)) == []
    assert check_output_dir(_write_analysis(tmp_path / "point", overall="point_only", attempted=50, failed=0))
    assert check_output_dir(_write_analysis(tmp_path / "fails", overall="complete", attempted=50, failed=6))
    assert check_output_dir(tmp_path / "missing")


@pytest.mark.parametrize("example", ("single", "parallel"))
def test_example_runs_pass_the_ci_output_check(tmp_path: Path, example: str) -> None:
    from scripts.check_example_outputs import check_output_dir

    output = tmp_path / example
    exit_code = cli_main(
        [
            "--data",
            str(ROOT / "examples" / example / "data.csv"),
            "--spec",
            str(ROOT / "examples" / example / "analysis.yaml"),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert check_output_dir(output) == []
