"""Export the exact validation-matrix datasets, with seeds and fitted models, for R.

For each selected (cell, replicate) of a validation config this writes the
dataset Mintmed analysed, ``generate_cell(cell_id, data_seed).data``, so that
external comparators (R ``mediation::mediate()`` and lavaan, Task 17) can fit
the same data. Layout under ``--output``::

    manifest.json                 config, seeds and SHA-256 of every CSV
    <cell_id>/cell.json           variable roles and fitted node specifications
    <cell_id>/rep_<RRRR>.csv      one dataset per replicate

CSVs are written with ``float_format='%.17g'``, which is lossless for float64:
each file is read back after writing and compared bitwise with the generated
frame. Read them with a correctly rounded parser (R ``read.csv``, or pandas
with ``float_precision='round_trip'``). Files are written with ``\\n`` line
endings and sorted JSON, so rerunning an export gives byte-identical output.

Seeds are unsigned 64-bit integers, above the 2**53 limit of JSON readers
that parse numbers as doubles (R ``jsonlite``), so the manifest stores
``master_seed`` as a number but ``data_seed`` and ``analysis_seed`` as decimal
strings.

``cell.json`` is derived from the fixture's compiled ``ModelSpec``, never
hand-written. Each node also carries the exact patsy formula Mintmed fits.

Usage::

    python scripts/export_validation_datasets.py --config configs/mediation_validation_v2.yaml \\
        --output OUT [--cell-id ID ...] [--replicate-block 0of4 | --replicate-start S --replicate-stop E]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mintmed.design import _build_formula
from mintmed.experiments.mediation_validation import (
    ValidationConfig,
    cell_definition,
    generate_cell,
    load_config,
    replicate_block_range,
    seed_pair,
    selected_combinations,
)
from mintmed.spec import ModelSpec, NodeSpec, TermKind, VariableSpec, estimate_plan

FLOAT_FORMAT = "%.17g"
MANIFEST_SCHEMA_VERSION = 1
CELL_SCHEMA_VERSION = 1

# How each basis kind enters the linear predictor (mirrors mintmed.design).
_BASIS_NOTES = {
    TermKind.LINEAR.value: "x",
    TermKind.QUADRATIC.value: "I(x^2) only; no linear x term is added unless declared separately",
    TermKind.NATURAL_SPLINE.value: (
        "patsy cr(x, df, constraints='center'): natural cubic regression spline with "
        "patsy's default knots (quantiles of x in the analysed data) and a centring "
        "(sum-to-zero) constraint"
    ),
    TermKind.CATEGORICAL.value: "treatment-coded indicators against the first declared level",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _variable_dict(variable: VariableSpec) -> dict[str, Any]:
    return {
        "name": variable.name,
        "role": variable.role.value,
        "observed_type": variable.observed_type,
        "family": None if variable.family is None else variable.family.value,
        "levels": _json_value(list(variable.levels)),
    }


def _node_dict(node: NodeSpec, formula: str) -> dict[str, Any]:
    return {
        "response": node.response,
        "family": node.family.value,
        "intercept": bool(node.intercept),
        "terms": [
            {"variable": term.variable, "kind": TermKind(term.kind).value, "df": term.df}
            for term in node.terms
        ],
        "interactions": [[item.left, item.right] for item in node.interactions],
        "patsy_formula": f"{node.response} ~ {formula}",
    }


def cell_description(cell_id: str, spec: ModelSpec, data: pd.DataFrame) -> dict[str, Any]:
    """Describe the fitted model of one cell from its compiled spec.

    ``data`` is one of the cell's datasets; it is only used to compile the
    analysis plan whose node formulas are recorded (they do not depend on data).
    """

    cell = cell_definition(cell_id)
    plan = estimate_plan(data, spec)
    formulas = {node.response: _build_formula(node)[0] for node in plan.nodes}
    contrast = spec.contrast
    kinds_used = sorted({TermKind(term.kind).value for node in spec.nodes for term in node.terms})
    return {
        "schema_version": CELL_SCHEMA_VERSION,
        "cell_id": cell.cell_id,
        "cell_ordinal": cell.ordinal,
        "n": cell.n,
        "generator": cell.generator_name,
        "outcome_kind": cell.outcome_kind,
        "effects": list(cell.metric_names),
        "columns": [str(column) for column in data.columns],
        "exposure": {
            **_variable_dict(spec.exposure),
            "reference": _json_value(contrast.reference),
            "comparison": _json_value(contrast.comparison),
        },
        "mediators": [_variable_dict(item) for item in spec.mediators],
        "mediator_order": list(spec.scientific.mediator_order),
        "arrangement": spec.scientific.arrangement,
        "outcome": _variable_dict(spec.outcome),
        "covariates": [_variable_dict(item) for item in spec.baseline],
        "moderators": [_variable_dict(item) for item in spec.moderators],
        "moderator_values": {
            str(name): _json_value(value) for name, value in dict(contrast.moderator_values).items()
        },
        "moderator_evaluation": {
            str(name): _json_value(list(values))
            for name, values in dict(contrast.moderator_evaluation).items()
        },
        "contrast": {
            "primary_effects": list(contrast.primary_effects),
            "interpretation": contrast.interpretation,
        },
        "scientific_edges": [[left, right] for left, right in spec.scientific.edges],
        "nodes": [_node_dict(node, formulas[node.response]) for node in spec.nodes],
        "basis_notes": {kind: _BASIS_NOTES[kind] for kind in kinds_used},
    }


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def csv_bytes(data: pd.DataFrame) -> bytes:
    return data.to_csv(index=False, float_format=FLOAT_FORMAT, lineterminator="\n").encode("utf-8")


def read_dataset(path: Path) -> pd.DataFrame:
    """Read an exported CSV losslessly as float64 columns."""

    return pd.read_csv(path, dtype=np.float64, float_precision="round_trip")


def _check_round_trip(path: Path, data: pd.DataFrame) -> None:
    restored = read_dataset(path)
    if list(restored.columns) != list(data.columns):
        raise ValueError(f"{path}: column names did not round-trip")
    expected = data.to_numpy(dtype=np.float64)
    observed = restored.to_numpy(dtype=np.float64)
    if expected.shape != observed.shape or not np.array_equal(
        expected.view(np.uint64), observed.view(np.uint64)
    ):
        raise ValueError(f"{path}: values did not round-trip bit for bit")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def export(
    config: ValidationConfig,
    output_dir: Path,
    *,
    config_path: str,
    cell_ids: Sequence[str] | None = None,
    replicate_start: int = 0,
    replicate_stop: int | None = None,
    verify: bool = True,
) -> dict[str, Any]:
    """Write the selected datasets, per-cell model descriptions and the manifest."""

    output = Path(output_dir)
    selected = selected_combinations(
        config,
        cell_ids=cell_ids,
        replicate_start=replicate_start,
        replicate_stop=replicate_stop,
    )
    datasets: list[dict[str, Any]] = []
    cells: dict[str, dict[str, Any]] = {}
    specs: dict[str, ModelSpec] = {}
    for cell_id, replicate in selected:
        cell = cell_definition(cell_id)
        data_seed, analysis_seed = seed_pair(config.master_seed, cell.ordinal, replicate)
        fixture = generate_cell(cell_id, data_seed)
        data = fixture.data
        if cell_id not in specs:
            specs[cell_id] = fixture.spec
            description = cell_description(cell_id, fixture.spec, data)
            content = _json_bytes(description)
            _write_bytes(output / cell_id / "cell.json", content)
            cells[cell_id] = {"path": f"{cell_id}/cell.json", "sha256": hashlib.sha256(content).hexdigest()}
        elif fixture.spec != specs[cell_id]:
            raise ValueError(f"{cell_id}: fitted spec differs between replicates")
        relative = f"{cell_id}/rep_{replicate:04d}.csv"
        content = csv_bytes(data)
        path = output / relative
        _write_bytes(path, content)
        if verify:
            _check_round_trip(path, data)
        datasets.append(
            {
                "cell_id": cell_id,
                "cell_ordinal": cell.ordinal,
                "replicate": int(replicate),
                "data_seed": str(int(data_seed)),
                "analysis_seed": str(int(analysis_seed)),
                "rows": int(len(data)),
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "config_path": Path(config_path).as_posix(),
        "config_hash": config.config_hash,
        "experiment": config.experiment,
        "master_seed": int(config.master_seed),
        "config": config.canonical_dict,
        "float_format": FLOAT_FORMAT,
        "cells": cells,
        "datasets": datasets,
    }
    _write_bytes(output / "manifest.json", _json_bytes(manifest))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell-id", action="append", dest="cell_ids")
    parser.add_argument("--replicate-start", type=int, default=0)
    parser.add_argument("--replicate-stop", type=int)
    parser.add_argument("--replicate-block", help="block INDEX:COUNT (or INDEXofCOUNT) of the replicates")
    parser.add_argument("--no-verify", action="store_true", help="skip the per-file round-trip check")
    arguments = parser.parse_args(argv)
    try:
        config = load_config(arguments.config)
        start, stop = arguments.replicate_start, arguments.replicate_stop
        if arguments.replicate_block is not None:
            if start != 0 or stop is not None:
                raise ValueError("--replicate-block cannot be combined with explicit bounds")
            start, stop = replicate_block_range(config.replicates, arguments.replicate_block)
        manifest = export(
            config,
            arguments.output,
            config_path=str(arguments.config),
            cell_ids=arguments.cell_ids,
            replicate_start=start,
            replicate_stop=stop,
            verify=not arguments.no_verify,
        )
    except (OSError, ValueError) as exc:
        parser.print_usage()
        print(f"error: {exc}")
        return 2
    print(f"exported {len(manifest['datasets'])} dataset(s) to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
