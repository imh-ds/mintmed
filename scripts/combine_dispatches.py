"""Combine complete dispatches of the same sharded validation design."""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
from pathlib import Path
from types import ModuleType

import pandas as pd


def _load_module(module_path: str) -> tuple[ModuleType, ModuleType]:
    runner = importlib.import_module(module_path)
    reporting = importlib.import_module(f"{module_path}_reporting")
    return runner, reporting


def _assert_same_design(configs: list[object], config_paths: list[Path]) -> None:
    exempt = {"master_seed", "replicates", "source_path"}
    reference = configs[0]
    reference_fields = {
        field.name: getattr(reference, field.name)
        for field in dataclasses.fields(reference)
        if field.name not in exempt
    }
    for config, path in zip(configs[1:], config_paths[1:]):
        for name, value in reference_fields.items():
            other = getattr(config, name)
            if other != value:
                raise SystemExit(
                    f"dispatch configs disagree on field '{name}': "
                    f"{config_paths[0]}={value!r} vs {path}={other!r} -- refusing to combine different designs"
                )


def combine(
    module_path: str,
    config_paths: list[Path],
    artifact_dirs: list[Path],
    output_dir: Path,
) -> pd.DataFrame:
    if len(config_paths) != len(artifact_dirs):
        raise SystemExit(
            f"got {len(config_paths)} config(s) but {len(artifact_dirs)} artifact directorie(s) -- "
            "these must be paired one-to-one"
        )
    if not config_paths:
        raise SystemExit("at least one config/artifact pair is required")

    runner, reporting = _load_module(module_path)
    configs = [runner.load_config(config_path) for config_path in config_paths]
    _assert_same_design(configs, config_paths)

    combination_columns = list(runner.COMBINATION_COLUMNS)
    if "replicate" not in combination_columns:
        raise SystemExit(
            f"{module_path}'s COMBINATION_COLUMNS ({combination_columns}) has no 'replicate' column"
        )

    manifest: list[dict[str, object]] = []
    frames: list[pd.DataFrame] = []
    offset = 0
    for config, config_path, artifact_dir in zip(configs, config_paths, artifact_dirs):
        raw_path = artifact_dir / "raw_metrics.csv"
        if not raw_path.is_file():
            raise SystemExit(f"no raw_metrics.csv found under {artifact_dir}")
        raw = pd.read_csv(raw_path)

        expected_rows = runner.expected_row_count(config)
        if len(raw) != expected_rows:
            raise SystemExit(
                f"dispatch at {artifact_dir} has {len(raw)} rows, expected {expected_rows} "
                "-- combine only complete dispatches"
            )
        combinations = set(raw[combination_columns].itertuples(index=False, name=None))
        if combinations != runner.expected_combinations(config):
            raise SystemExit(f"dispatch at {artifact_dir} does not cover its expected combinations")

        raw = raw.copy()
        raw["replicate"] = raw["replicate"] + offset
        manifest.append(
            {
                "config_path": str(config_path),
                "artifact_dir": str(artifact_dir),
                "master_seed": config.master_seed,
                "local_replicates": config.replicates,
                "global_replicate_start": offset,
                "global_replicate_end": offset + config.replicates,
            }
        )
        frames.append(raw)
        offset += config.replicates

    combined_raw = pd.concat(frames, ignore_index=True)
    combined_config = dataclasses.replace(configs[0], replicates=offset)
    expected_rows = runner.expected_row_count(combined_config)
    if len(combined_raw) != expected_rows:
        raise SystemExit(
            f"combined {len(combined_raw)} rows, expected {expected_rows} for the combined replicate count"
        )

    combinations = set(combined_raw[combination_columns].itertuples(index=False, name=None))
    expected_combinations = runner.expected_combinations(combined_config)
    if combinations != expected_combinations:
        missing = expected_combinations - combinations
        raise SystemExit(f"combined dispatches do not cover every combination -- missing: {missing}")
    duplicate_keys = combined_raw.duplicated(subset=combination_columns)
    if duplicate_keys.any():
        raise SystemExit(
            f"{int(duplicate_keys.sum())} duplicate rows across dispatches (key: {combination_columns})"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    combined_raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    (output_dir / "combined_manifest.json").write_text(
        json.dumps({"module": module_path, "total_replicates": offset, "dispatches": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    reporting.write_report(combined_raw, combined_config, output_dir)
    return combined_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--dispatch-config", required=True, action="append", type=Path)
    parser.add_argument("--dispatch-dir", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    combine(arguments.module, arguments.dispatch_config, arguments.dispatch_dir, arguments.output)


if __name__ == "__main__":
    main()
