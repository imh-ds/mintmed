from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mintmed.experiments.mediation_validation import (
    cell_definition,
    generate_cell,
    load_config,
    seed_pair,
)
from scripts.export_validation_datasets import export, main, read_dataset

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = "configs/mediation_validation_v2.yaml"


@pytest.fixture(scope="module")
def config():
    return load_config(ROOT / CONFIG_PATH)


def _export(config, tmp_path: Path, cells, start=0, stop=1, name="out"):
    output = tmp_path / name
    manifest = export(
        config,
        output,
        config_path=CONFIG_PATH,
        cell_ids=cells,
        replicate_start=start,
        replicate_stop=stop,
    )
    return output, manifest


def _cell_json(output: Path, cell_id: str) -> dict:
    return json.loads((output / cell_id / "cell.json").read_text(encoding="utf-8"))


def _node(description: dict, response: str) -> dict:
    return next(node for node in description["nodes"] if node["response"] == response)


def _terms(node: dict) -> list[tuple[str, str, int | None]]:
    return [(term["variable"], term["kind"], term["df"]) for term in node["terms"]]


def test_exported_dataset_round_trips_bit_for_bit(config, tmp_path: Path) -> None:
    cells = ["cell01_linear_n100", "cell11_binary_mediator_n150", "cell12_mixed_binary_serial_n250"]
    output, manifest = _export(config, tmp_path, cells, 0, 2)
    for entry in manifest["datasets"]:
        expected = generate_cell(entry["cell_id"], int(entry["data_seed"])).data
        restored = read_dataset(output / entry["path"])
        pd.testing.assert_frame_equal(restored, expected, check_exact=True)
        assert np.array_equal(
            restored.to_numpy().view(np.uint64), expected.to_numpy(dtype=np.float64).view(np.uint64)
        )
        content = (output / entry["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        assert b"\r" not in content
        assert entry["rows"] == len(expected) == cell_definition(entry["cell_id"]).n


def test_manifest_seeds_equal_seed_pair(config, tmp_path: Path) -> None:
    output, manifest = _export(config, tmp_path, ["cell02_linear_n250", "cell14_b_path_only_n100"], 3, 5)
    assert manifest == json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config_hash"] == config.config_hash
    assert manifest["master_seed"] == config.master_seed == 20260927
    assert manifest["config_path"] == CONFIG_PATH
    assert len(manifest["datasets"]) == 4
    for entry in manifest["datasets"]:
        ordinal = cell_definition(entry["cell_id"]).ordinal
        data_seed, analysis_seed = seed_pair(config.master_seed, ordinal, entry["replicate"])
        # Seeds exceed 2**53, so they are stored as exact decimal strings.
        assert entry["data_seed"] == str(data_seed)
        assert entry["analysis_seed"] == str(analysis_seed)
        assert entry["path"] == f"{entry['cell_id']}/rep_{entry['replicate']:04d}.csv"


def test_export_is_byte_identical_on_rerun(config, tmp_path: Path) -> None:
    cells = ["cell08_quadratic_n100", "cell10_moderated_n150"]
    first, _ = _export(config, tmp_path, cells, 0, 2, name="first")
    second, _ = _export(config, tmp_path, cells, 0, 2, name="second")
    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    assert len(first_files) == 1 + 2 * (1 + 2)
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


def test_cell_json_describes_linear_cell(config, tmp_path: Path) -> None:
    output, manifest = _export(config, tmp_path, ["cell01_linear_n100"])
    description = _cell_json(output, "cell01_linear_n100")
    assert manifest["cells"]["cell01_linear_n100"]["sha256"] == hashlib.sha256(
        (output / "cell01_linear_n100" / "cell.json").read_bytes()
    ).hexdigest()
    assert description["columns"] == ["A", "C", "M", "Y"]
    assert description["exposure"]["name"] == "A"
    assert (description["exposure"]["reference"], description["exposure"]["comparison"]) == (0, 1)
    assert description["exposure"]["levels"] == [0, 1]
    assert [item["name"] for item in description["mediators"]] == ["M"]
    assert description["outcome"]["name"] == "Y"
    assert description["outcome"]["family"] == "gaussian"
    assert [item["name"] for item in description["covariates"]] == ["C"]
    assert description["moderators"] == [] and description["moderator_values"] == {}
    assert description["effects"] == ["TE", "PNDE", "TNIE"]
    assert [node["response"] for node in description["nodes"]] == ["M", "Y"]
    mediator, outcome = _node(description, "M"), _node(description, "Y")
    assert mediator["family"] == outcome["family"] == "gaussian"
    assert _terms(mediator) == [("A", "linear", None), ("C", "linear", None)]
    assert _terms(outcome) == [("A", "linear", None), ("C", "linear", None), ("M", "linear", None)]
    assert outcome["interactions"] == [] and outcome["intercept"] is True
    assert outcome["patsy_formula"] == 'Y ~ 1 + Q("A") + Q("C") + Q("M")'


def test_cell_json_describes_quadratic_cell(config, tmp_path: Path) -> None:
    output, _ = _export(config, tmp_path, ["cell08_quadratic_n100"])
    description = _cell_json(output, "cell08_quadratic_n100")
    outcome = _node(description, "Y")
    # The fitted outcome model has M only through its square, no linear M term.
    assert _terms(outcome) == [("A", "linear", None), ("C", "linear", None), ("M", "quadratic", None)]
    assert outcome["patsy_formula"] == 'Y ~ 1 + Q("A") + Q("C") + I(Q("M") ** 2)'
    assert set(description["basis_notes"]) == {"linear", "quadratic"}


def test_cell_json_describes_spline_cell(config, tmp_path: Path) -> None:
    output, _ = _export(config, tmp_path, ["cell09_spline_n250"])
    outcome = _node(_cell_json(output, "cell09_spline_n250"), "Y")
    assert _terms(outcome)[-1] == ("M", "natural_spline", 3)
    assert 'cr(Q("M"), df=3, constraints="center")' in outcome["patsy_formula"]


def test_cell_json_describes_binary_mediator_cell(config, tmp_path: Path) -> None:
    output, _ = _export(config, tmp_path, ["cell11_binary_mediator_n150"])
    description = _cell_json(output, "cell11_binary_mediator_n150")
    (mediator_variable,) = description["mediators"]
    assert mediator_variable["family"] == "bernoulli"
    assert mediator_variable["observed_type"] == "binary"
    assert mediator_variable["levels"] == [0, 1]
    mediator, outcome = _node(description, "M"), _node(description, "Y")
    assert mediator["family"] == "bernoulli"
    assert _terms(mediator) == [("A", "linear", None), ("C", "linear", None)]
    assert outcome["family"] == "gaussian"
    assert _terms(outcome) == [("A", "linear", None), ("M", "linear", None), ("C", "linear", None)]


def test_cell_json_describes_moderated_cell(config, tmp_path: Path) -> None:
    output, _ = _export(config, tmp_path, ["cell10_moderated_n150"])
    description = _cell_json(output, "cell10_moderated_n150")
    assert description["columns"] == ["A", "W", "C", "M", "Y"]
    (moderator,) = description["moderators"]
    assert moderator["name"] == "W" and moderator["levels"] == [0, 1] and moderator["role"] == "moderator"
    assert description["moderator_values"] == {"W": 0.0}
    assert description["effects"] == ["TNIE_W0", "TNIE_W1", "TNIE_difference"]
    mediator, outcome = _node(description, "M"), _node(description, "Y")
    assert _terms(mediator) == [("A", "linear", None), ("W", "linear", None), ("C", "linear", None)]
    assert mediator["interactions"] == [["W", "A"]]
    assert _terms(outcome) == [
        ("A", "linear", None), ("W", "linear", None), ("C", "linear", None), ("M", "linear", None)
    ]
    assert outcome["interactions"] == [["W", "M"]]
    assert outcome["patsy_formula"].endswith('+ (Q("W")):(Q("M"))')


def test_cell_json_describes_serial_order(config, tmp_path: Path) -> None:
    output, _ = _export(config, tmp_path, ["cell07_serial_three_n200"])
    description = _cell_json(output, "cell07_serial_three_n200")
    assert description["mediator_order"] == ["M1", "M2", "M3"]
    assert description["arrangement"] == "sequential"
    assert _terms(_node(description, "M3")) == [("A", "linear", None), ("M2", "linear", None), ("C", "linear", None)]


def _manifest_keys(output: Path) -> list[tuple[str, int]]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    return [(entry["cell_id"], entry["replicate"]) for entry in manifest["datasets"]]


def test_cli_replicate_block_matches_runner_semantics(tmp_path: Path) -> None:
    output = tmp_path / "block"
    # 500 replicates in 200 blocks of ceil(500 / 200) = 3: block 166 is the short last one.
    code = main([
        "--config", str(ROOT / CONFIG_PATH), "--output", str(output),
        "--cell-id", "cell05_no_mediation_n100", "--cell-id", "cell03_no_a_to_m_n100",
        "--replicate-block", "166of200",
    ])
    assert code == 0
    # Registry order, then replicate order, as in the validation runner.
    assert _manifest_keys(output) == [
        ("cell03_no_a_to_m_n100", 498), ("cell03_no_a_to_m_n100", 499),
        ("cell05_no_mediation_n100", 498), ("cell05_no_mediation_n100", 499),
    ]


def test_cli_replicate_range_selection(tmp_path: Path) -> None:
    output = tmp_path / "range"
    code = main([
        "--config", str(ROOT / CONFIG_PATH), "--output", str(output),
        "--cell-id", "cell13_a_path_only_n100", "--replicate-start", "7", "--replicate-stop", "9",
    ])
    assert code == 0
    assert _manifest_keys(output) == [("cell13_a_path_only_n100", 7), ("cell13_a_path_only_n100", 8)]


@pytest.mark.parametrize(
    "extra",
    [
        ["--replicate-block", "0of4", "--replicate-stop", "3"],
        ["--replicate-block", "4of4"],
        ["--replicate-start", "3", "--replicate-stop", "3"],
        ["--replicate-stop", "501"],
        ["--cell-id", "cell99_unknown"],
        ["--cell-id", "cell01_linear_n100", "--cell-id", "cell01_linear_n100"],
    ],
)
def test_cli_rejects_invalid_selection(tmp_path: Path, extra: list[str]) -> None:
    output = tmp_path / "bad"
    code = main(["--config", str(ROOT / CONFIG_PATH), "--output", str(output), *extra])
    assert code == 2
    assert not (output / "manifest.json").exists()
