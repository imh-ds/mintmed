from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from mintmed.cli import main


def _spec_mapping() -> dict[str, object]:
    return {
        "schema_version": 1,
        "exposure": {"name": "A", "type": "binary", "levels": [0, 1], "reference": 0, "comparison": 1},
        "outcome": {"name": "Y", "type": "continuous", "family": "gaussian"},
        "mediators": [{"name": "M", "type": "continuous", "family": "gaussian"}],
        "arrangement": "parallel",
        "mediator_order": ["M"],
        "baseline": [],
        "moderators": [],
        "scientific_edges": [["A", "M"], ["A", "Y"], ["M", "Y"]],
        "models": {
            "M": {"intercept": True, "terms": [{"variable": "A", "basis": "categorical"}], "interactions": []},
            "Y": {
                "intercept": True,
                "terms": [
                    {"variable": "A", "basis": "categorical"},
                    {"variable": "M", "basis": "linear"},
                ],
                "interactions": [],
            },
        },
        "interpretation": "model_standardized",
        "missing": "error",
        "computation": {
            "seed": 20260919,
            "bootstrap": 0,
            "bootstrap_mode": "standard",
            "integration_draws": 256,
            "integration_tolerance": 1.0,
            "max_seconds": 30,
            "memory_budget_mb": 256,
            "information": False,
        },
    }


def _write_inputs(tmp_path: Path, *, missing_outcome: bool = False) -> tuple[Path, Path]:
    data_path = tmp_path / "data.csv"
    data = pd.DataFrame(
        {
            "A": [0, 0, 0, 0, 1, 1, 1, 1],
            "M": [0.1, 0.2, 0.0, 0.3, 0.9, 1.0, 1.1, 0.8],
            "Y": [0.2, 0.3, 0.1, 0.4, 1.0, 1.1, 1.2, 0.9],
        }
    )
    if missing_outcome:
        data = data.drop(columns=["Y"])
    data.to_csv(data_path, index=False)
    spec_path = tmp_path / "analysis.yaml"
    spec_path.write_text(yaml.safe_dump(_spec_mapping(), sort_keys=False), encoding="utf-8")
    return data_path, spec_path


def test_cli_writes_four_artifacts_for_a_structured_analysis(tmp_path: Path, capsys) -> None:
    data_path, spec_path = _write_inputs(tmp_path)
    output = tmp_path / "output"

    exit_code = main(["--data", str(data_path), "--spec", str(spec_path), "--output", str(output)])

    assert exit_code == 0
    assert {path.name for path in output.iterdir()} == {
        "analysis.json",
        "effects.csv",
        "bootstrap.csv",
        "report.md",
    }
    payload = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    assert payload["specification_hash"]
    assert payload["analysis_hash"]
    assert "## Contrast and answer" in (output / "report.md").read_text(encoding="utf-8")
    assert capsys.readouterr().err == ""


def test_cli_writes_structured_invalid_data_and_returns_one(tmp_path: Path) -> None:
    data_path, spec_path = _write_inputs(tmp_path, missing_outcome=True)
    output = tmp_path / "invalid-output"

    exit_code = main(["--data", str(data_path), "--spec", str(spec_path), "--output", str(output)])

    assert exit_code == 1
    payload = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    assert payload["overall_status"] == "invalid_data"
    assert payload["diagnostics"]["error"]["code"] == "missing_columns"


def test_cli_reports_typed_spec_error_without_traceback(tmp_path: Path, capsys) -> None:
    data_path, _ = _write_inputs(tmp_path)
    spec_path = tmp_path / "bad.yaml"
    spec_path.write_text("schema_version: 1\n", encoding="utf-8")

    exit_code = main(["--data", str(data_path), "--spec", str(spec_path), "--output", str(tmp_path / "bad-output")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "missing_exposure" in captured.err
    assert "Traceback" not in captured.err
