"""Aggregate complete shard outputs for a validation experiment.

A compatible runner module exposes ``load_config``, ``expected_row_count``,
``expected_combinations``, and ``COMBINATION_COLUMNS``. Its reporting
companion lives at ``<runner_module>_reporting`` and exposes ``write_report``.
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pandas as pd


def _load_module(module_path: str) -> tuple[ModuleType, ModuleType]:
    runner = importlib.import_module(module_path)
    reporting = importlib.import_module(f"{module_path}_reporting")
    return runner, reporting


def aggregate(module_path: str, config_path: Path, shards_dir: Path, output_dir: Path) -> pd.DataFrame:
    runner, reporting = _load_module(module_path)
    config = runner.load_config(config_path)

    shard_paths = sorted(shards_dir.glob("*/raw_metrics.csv"))
    if not shard_paths:
        raise SystemExit(f"no raw_metrics.csv files found under {shards_dir}")

    raw = pd.concat((pd.read_csv(path) for path in shard_paths), ignore_index=True)
    expected_rows = runner.expected_row_count(config)
    if len(raw) != expected_rows:
        raise SystemExit(
            f"aggregated {len(raw)} rows from {len(shard_paths)} shard(s), expected {expected_rows} "
            "-- a shard is missing or duplicated"
        )

    combination_columns = list(runner.COMBINATION_COLUMNS)
    combinations = set(raw[combination_columns].itertuples(index=False, name=None))
    expected_combinations = runner.expected_combinations(config)
    if combinations != expected_combinations:
        missing = expected_combinations - combinations
        raise SystemExit(f"aggregated shards do not cover every combination -- missing: {missing}")

    dedup_columns = combination_columns.copy()
    if "replicate" in raw.columns and "replicate" not in dedup_columns:
        dedup_columns.append("replicate")
    duplicate_keys = raw.duplicated(subset=dedup_columns)
    if duplicate_keys.any():
        raise SystemExit(f"{int(duplicate_keys.sum())} duplicate rows across shards (key: {dedup_columns})")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    _write_provenance(shard_paths, output_dir)
    reporting.write_report(raw, config, output_dir)
    return raw


def _write_provenance(shard_paths: list[Path], output_dir: Path) -> None:
    shard_dirs = sorted({path.parent for path in shard_paths})
    if not shard_dirs:
        return

    reference_config = shard_dirs[0] / "resolved_config.yaml"
    if reference_config.is_file():
        (output_dir / "resolved_config.yaml").write_text(
            reference_config.read_text(encoding="utf-8"), encoding="utf-8"
        )

    metadatas = []
    for shard_dir in shard_dirs:
        metadata_path = shard_dir / "metadata.json"
        if metadata_path.is_file():
            metadatas.append(json.loads(metadata_path.read_text(encoding="utf-8")))
    if not metadatas:
        return

    reference = metadatas[0]
    aggregated_metadata = {
        "charter_sha256": reference.get("charter_sha256"),
        "git_commit": reference.get("git_commit"),
        "python": reference.get("python"),
        "platform": reference.get("platform"),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "total_runtime_seconds": sum(float(metadata.get("runtime_seconds", 0.0)) for metadata in metadatas),
        "shard_count": len(metadatas),
        "note": (
            "Synthesized from per-shard metadata.json files at aggregation time. "
            "total_runtime_seconds sums shard runtimes and is not parallel wall-clock time."
        ),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(aggregated_metadata, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, help="import path of the shardable runner module")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--shards-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    aggregate(arguments.module, arguments.config, arguments.shards_dir, arguments.output)


if __name__ == "__main__":
    main()
