from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts.aggregate_shards import aggregate
from scripts.combine_dispatches import combine


def _write_dummy_experiment(module_dir: Path) -> str:
    package = module_dir / "dummy_evidence"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "runner.py").write_text(
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n"
        "import yaml\n\n"
        "@dataclass(frozen=True)\n"
        "class Config:\n"
        "    conditions: tuple[str, ...]\n"
        "    replicates: int\n"
        "    master_seed: int\n"
        "    source_path: Path | None = None\n\n"
        "COMBINATION_COLUMNS = (\"condition\", \"replicate\")\n\n"
        "def load_config(path):\n"
        "    values = yaml.safe_load(Path(path).read_text(encoding=\"utf-8\"))\n"
        "    return Config(tuple(values[\"conditions\"]), int(values[\"replicates\"]), "
        "int(values[\"master_seed\"]), Path(path).resolve())\n\n"
        "def expected_combinations(config):\n"
        "    return {(condition, replicate) for condition in config.conditions "
        "for replicate in range(config.replicates)}\n\n"
        "def expected_row_count(config):\n"
        "    return len(expected_combinations(config))\n",
        encoding="utf-8",
    )
    (package / "runner_reporting.py").write_text(
        "def write_report(raw, config, output_dir):\n"
        "    (output_dir / \"report.txt\").write_text(f\"rows={len(raw)}\\n\", encoding=\"utf-8\")\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(module_dir))
    return "dummy_evidence.runner"


def _write_config(path: Path, *, master_seed: int, replicates: int = 2) -> None:
    path.write_text(
        yaml.safe_dump(
            {"conditions": ["linear", "nonlinear"], "replicates": replicates, "master_seed": master_seed}
        ),
        encoding="utf-8",
    )


def _write_rows(path: Path, rows: list[dict[str, object]], *, runtime: float = 1.0) -> None:
    path.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(path / "raw_metrics.csv", index=False)
    (path / "resolved_config.yaml").write_text("locked: true\n", encoding="utf-8")
    (path / "metadata.json").write_text(
        json.dumps(
            {
                "charter_sha256": "abc123",
                "git_commit": "deadbeef",
                "python": "3.11",
                "platform": "test",
                "runtime_seconds": runtime,
            }
        ),
        encoding="utf-8",
    )


def test_aggregate_combines_complete_shards_and_preserves_provenance(tmp_path: Path) -> None:
    module_path = _write_dummy_experiment(tmp_path / "modules")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, master_seed=101)
    shards = tmp_path / "shards"
    _write_rows(
        shards / "a",
        [
            {"condition": "linear", "replicate": 0, "estimate": 0.1},
            {"condition": "nonlinear", "replicate": 0, "estimate": 0.2},
        ],
        runtime=1.25,
    )
    _write_rows(
        shards / "b",
        [
            {"condition": "linear", "replicate": 1, "estimate": 0.3},
            {"condition": "nonlinear", "replicate": 1, "estimate": 0.4},
        ],
        runtime=2.75,
    )

    output = tmp_path / "aggregated"
    raw = aggregate(module_path, config_path, shards, output)

    assert len(raw) == 4
    assert (output / "raw_metrics.csv").is_file()
    assert (output / "resolved_config.yaml").read_text(encoding="utf-8") == "locked: true\n"
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["shard_count"] == 2
    assert metadata["total_runtime_seconds"] == 4.0
    assert (output / "report.txt").read_text(encoding="utf-8") == "rows=4\n"


def test_aggregate_rejects_incomplete_grid(tmp_path: Path) -> None:
    module_path = _write_dummy_experiment(tmp_path / "modules")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, master_seed=202)
    shards = tmp_path / "shards"
    _write_rows(
        shards / "only",
        [{"condition": "linear", "replicate": 0, "estimate": 0.1}],
    )

    with pytest.raises(SystemExit, match="expected 4"):
        aggregate(module_path, config_path, shards, tmp_path / "aggregated")


def test_combine_remaps_dispatch_replicates_and_writes_manifest(tmp_path: Path) -> None:
    module_path = _write_dummy_experiment(tmp_path / "modules")
    config_a = tmp_path / "a.yaml"
    config_b = tmp_path / "b.yaml"
    _write_config(config_a, master_seed=301)
    _write_config(config_b, master_seed=302)

    dispatch_a = tmp_path / "dispatch_a"
    dispatch_b = tmp_path / "dispatch_b"
    rows = [
        {"condition": condition, "replicate": replicate, "estimate": float(replicate)}
        for condition in ("linear", "nonlinear")
        for replicate in (0, 1)
    ]
    _write_rows(dispatch_a, rows)
    _write_rows(dispatch_b, rows)

    output = tmp_path / "combined"
    combined = combine(module_path, [config_a, config_b], [dispatch_a, dispatch_b], output)

    assert set(combined["replicate"]) == {0, 1, 2, 3}
    manifest = json.loads((output / "combined_manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_replicates"] == 4
    assert manifest["dispatches"][1]["global_replicate_start"] == 2
    assert (output / "report.txt").read_text(encoding="utf-8") == "rows=8\n"


def test_combine_rejects_different_dispatch_designs(tmp_path: Path) -> None:
    module_path = _write_dummy_experiment(tmp_path / "modules")
    config_a = tmp_path / "a.yaml"
    config_b = tmp_path / "b.yaml"
    _write_config(config_a, master_seed=401)
    config_b.write_text(
        yaml.safe_dump({"conditions": ["linear"], "replicates": 2, "master_seed": 402}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="disagree on field 'conditions'"):
        combine(module_path, [config_a, config_b], [tmp_path / "a", tmp_path / "b"], tmp_path / "out")
