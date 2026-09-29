"""T17-S5 harness validation: the R comparators reproduce Mintmed within pre-declared tolerances.

Skipped without Rscript (mediation, lavaan, jsonlite); with ``MINTMED_REQUIRE_R=1``
(the CI job) a missing R fails instead. Mintmed is re-run here, point estimates
only, on the same exported datasets, so the test needs no stored results.

* All-linear cells, replicates 0-4: lavaan (both modes) and ``mediate()``'s
  bootstrap-mode points equal Mintmed's within ``EXACT_POINT_TOLERANCE``;
  ``mediate()``'s quasi-Bayesian points are within their Monte Carlo tolerance.
* Nonlinear or binary-mediator cells 08, 09, 11 (replicate 0): a HARNESS CHECK,
  not a verdict. The average of ``mediate()``'s bootstrap-mode point over
  ``MONTE_CARLO_AVERAGE_SEEDS`` seeds agrees with Mintmed's exact value within
  its own Monte Carlo error; PNDE (no Monte Carlo error there) is exact.
* Optionally (``MINTMED_RUN2_RAW`` = path to run 2's raw_metrics.csv), the fresh
  Mintmed points are also checked against the stored run-2 rows.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from mintmed.api import analyze_mediation
from mintmed.experiments import comparator_benchmark as cb
from mintmed.experiments.mediation_validation import (
    _prepare_spec,
    cell_definition,
    extract_metrics,
    generate_cell,
    load_config,
)
from mintmed.report import result_to_dict
from scripts.export_validation_datasets import export, read_dataset

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = "configs/mediation_validation_v3.yaml"
CONFIG = load_config(ROOT / CONFIG_PATH)
REPLICATES = range(5)
_LINEAR_IN_M = ["cell01_linear_n100", "cell02_linear_n250", "cell03_no_a_to_m_n100", "cell04_no_m_to_y_n100",
                "cell05_no_mediation_n100", "cell10_moderated_n150", "cell13_a_path_only_n100",
                "cell14_b_path_only_n100", "cell15_a_path_only_n250", "cell16_b_path_only_n250"]
LINEAR_CELLS = {
    "mediation": _LINEAR_IN_M,
    "lavaan": [*_LINEAR_IN_M[:5], "cell07_serial_three_n200", *_LINEAR_IN_M[5:]],
}
NONLINEAR_CELLS = ["cell08_quadratic_n100", "cell09_spline_n250", "cell11_binary_mediator_n150"]
BOOT = 19  # point estimates do not depend on the refit count; intervals are not checked here
RUN2_ENV = "MINTMED_RUN2_RAW"

RSCRIPT = cb.find_rscript()
R_READY = cb.r_packages_available(RSCRIPT)
if not R_READY and os.environ.get(cb.REQUIRE_R_ENV) == "1":
    pytest.fail(f"{cb.REQUIRE_R_ENV}=1 but Rscript with mediation, lavaan and jsonlite is not available", pytrace=False)

pytestmark = pytest.mark.skipif(not R_READY, reason="Rscript with mediation, lavaan and jsonlite is not available")


def test_tolerance_constants_are_the_declared_values() -> None:
    assert cb.EXACT_POINT_TOLERANCE == 1e-8
    assert cb.QUASI_BAYES_TOLERANCE_MULTIPLIER == 5.0
    assert cb.MONTE_CARLO_AVERAGE_SEEDS == 200
    assert cb.MONTE_CARLO_AVERAGE_TOLERANCE_MULTIPLIER == 4.0
    # 95% interval of width 3.92 -> draw SD 1; 5 SD / sqrt(100) = 0.5.
    assert cb.quasi_bayes_tolerance(-1.959963984540054, 1.959963984540054, 100) == pytest.approx(0.5)
    assert cb.quasi_bayes_tolerance(0.0, 0.0, 1000) == cb.EXACT_POINT_TOLERANCE
    assert cb.monte_carlo_average_tolerance([0.0, 2.0] * 50) == pytest.approx(4.0 * math.sqrt(100 / 99) / 10)


def mintmed_points(dataset: Path, cell_id: str, data_seed: int, analysis_seed: int) -> dict[str, float]:
    """Mintmed's point estimates on an exported dataset (no bootstrap: points do not depend on it)."""

    fixture = generate_cell(cell_id, data_seed)
    spec = _prepare_spec(fixture, CONFIG, analysis_seed)
    spec = replace(spec, computation=replace(spec.computation, bootstrap=0))
    payload = result_to_dict(analyze_mediation(read_dataset(dataset), spec))
    return {effect: float(record["estimate"]) for effect, record in extract_metrics(payload, cell_id).items()}


@pytest.fixture(scope="module")
def exported(tmp_path_factory) -> tuple[Path, dict]:
    root = tmp_path_factory.mktemp("harness-datasets")
    cells = sorted({*LINEAR_CELLS["lavaan"], *NONLINEAR_CELLS}, key=lambda cell: cell_definition(cell).ordinal)
    manifest = export(CONFIG, root, config_path=CONFIG_PATH, cell_ids=cells,
                      replicate_start=min(REPLICATES), replicate_stop=max(REPLICATES) + 1)
    return root, manifest


@pytest.fixture(scope="module")
def mintmed(exported) -> dict[tuple[str, int], dict[str, float]]:
    root, manifest = exported
    return {
        (entry["cell_id"], entry["replicate"]): mintmed_points(
            root / entry["path"], entry["cell_id"], int(entry["data_seed"]), int(entry["analysis_seed"]))
        for entry in manifest["datasets"]
        if entry["cell_id"] in LINEAR_CELLS["lavaan"] or entry["replicate"] == 0
    }


def _subset_manifest(root: Path, manifest: dict, cells: list[str], name: str) -> Path:
    entries = [entry for entry in manifest["datasets"] if entry["cell_id"] in cells]
    path = root / name
    path.write_text(json.dumps({**manifest, "datasets": entries}, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def linear_outputs(exported, tmp_path_factory) -> dict[str, pd.DataFrame]:
    root, manifest = exported
    out = tmp_path_factory.mktemp("harness-out")
    outputs = {}
    for tool, cells in LINEAR_CELLS.items():
        long, failure = cb.run_r_tool(
            RSCRIPT, tool, _subset_manifest(root, manifest, cells, f"manifest_linear_{tool}.json"),
            out / f"{tool}.csv", boot_sims=BOOT, qb_sims=cb.QUASI_BAYES_SIMS,
        )
        assert failure is None, failure
        outputs[tool] = long
    return outputs


def _rows(long: pd.DataFrame, mode: str):
    subset = long.loc[long["mode"] == mode]
    assert not subset.empty
    for row in subset.itertuples(index=False):
        assert row.status in cb.ESTIMATED_STATUSES, (row.cell_id, row.replicate, row.effect, row.message)
        yield row


def _check_exact(long: pd.DataFrame, mode: str, mintmed, expected_cells: list[str]) -> float:
    seen = set()
    worst = 0.0
    for row in _rows(long, mode):
        reference = mintmed[(row.cell_id, int(row.replicate))][row.effect]
        difference = abs(float(row.estimate) - reference)
        worst = max(worst, difference)
        assert difference <= cb.EXACT_POINT_TOLERANCE, (row.tool, mode, row.cell_id, row.replicate, row.effect, difference)
        seen.add((row.cell_id, int(row.replicate), row.effect))
    expected = {(cell, rep, effect) for cell in expected_cells for rep in REPLICATES for effect in cb.effect_truths(cell)}
    assert seen == expected
    return worst


@pytest.mark.parametrize("mode", cb.MODES)
def test_lavaan_points_equal_mintmed(linear_outputs, mintmed, mode: str) -> None:
    worst = _check_exact(linear_outputs["lavaan"], mode, mintmed, LINEAR_CELLS["lavaan"])
    print(f"lavaan {mode}: max |diff| {worst:.3g}")


def test_mediate_bootstrap_points_equal_mintmed_in_linear_in_m_cells(linear_outputs, mintmed) -> None:
    worst = _check_exact(linear_outputs["mediation"], "primary", mintmed, LINEAR_CELLS["mediation"])
    print(f"mediate primary: max |diff| {worst:.3g}")


def test_mediate_quasi_bayes_points_within_monte_carlo_tolerance(linear_outputs, mintmed) -> None:
    seen = set()
    worst_ratio = 0.0
    for row in _rows(linear_outputs["mediation"], "secondary"):
        sims = int(float(row.sims_successful))
        assert sims >= 0.99 * cb.QUASI_BAYES_SIMS
        tolerance = cb.quasi_bayes_tolerance(float(row.lower), float(row.upper), sims)
        assert tolerance < 0.05  # a vacuous tolerance would hide a mapping error
        difference = abs(float(row.estimate) - mintmed[(row.cell_id, int(row.replicate))][row.effect])
        worst_ratio = max(worst_ratio, difference / tolerance)
        assert difference <= tolerance, (row.cell_id, row.replicate, row.effect, difference, tolerance)
        seen.add((row.cell_id, int(row.replicate), row.effect))
    assert len(seen) == sum(len(cb.effect_truths(cell)) for cell in LINEAR_CELLS["mediation"]) * len(REPLICATES)
    print(f"mediate quasi-Bayesian: max |diff| / tolerance {worst_ratio:.3f}")


def test_nonlinear_mediate_seed_average_agrees_with_mintmed(exported, mintmed, tmp_path: Path) -> None:
    """Harness check on replicate 0 of cells 08, 09 and 11; not a verdict on either method."""

    root, manifest = exported
    entries = []
    for entry in manifest["datasets"]:
        if entry["cell_id"] in NONLINEAR_CELLS and entry["replicate"] == 0:
            base = int(entry["analysis_seed"])
            entries += [{**entry, "replicate": seed, "analysis_seed": str(base + seed)}
                        for seed in range(cb.MONTE_CARLO_AVERAGE_SEEDS)]
    path = root / "manifest_seed_average.json"
    path.write_text(json.dumps({**manifest, "datasets": entries}, indent=2, sort_keys=True), encoding="utf-8")
    long, failure = cb.run_r_tool(RSCRIPT, "mediation", path, tmp_path / "seeds.csv", boot_sims=2,
                                  qb_sims=cb.QUASI_BAYES_SIMS, modes=("primary",))
    assert failure is None, failure
    assert set(long["status"]) <= cb.ESTIMATED_STATUSES, long.loc[~long["status"].isin(cb.ESTIMATED_STATUSES)]
    assert len(set(long["r_seed"])) == len(entries)  # distinct seeds, one per entry
    for cell in NONLINEAR_CELLS:
        reference = mintmed[(cell, 0)]
        for effect, value in reference.items():
            estimates = long.loc[(long["cell_id"] == cell) & (long["effect"] == effect), "estimate"].map(float).tolist()
            assert len(estimates) == cb.MONTE_CARLO_AVERAGE_SEEDS
            mean = math.fsum(estimates) / len(estimates)
            if effect == "PNDE":  # z0 carries no Monte Carlo error: no A x M term
                assert max(abs(item - value) for item in estimates) <= cb.EXACT_POINT_TOLERANCE, (cell, effect)
                continue
            tolerance = cb.monte_carlo_average_tolerance(estimates)
            print(f"{cell} {effect}: mediate seed mean {mean:.5f}, Mintmed {value:.5f}, tolerance {tolerance:.5f}")
            assert abs(mean - value) <= tolerance, (cell, effect, mean, value, tolerance)


@pytest.mark.skipif(not os.environ.get(RUN2_ENV), reason=f"{RUN2_ENV} (run-2 raw_metrics.csv) not set")
def test_fresh_mintmed_points_equal_run2_rows(mintmed) -> None:
    raw = pd.read_csv(os.environ[RUN2_ENV], dtype={"data_seed": str, "analysis_seed": str})
    checked = 0
    for (cell, replicate), points in mintmed.items():
        match = raw.loc[(raw["cell_id"] == cell) & (raw["replicate"] == replicate)]
        if match.empty:  # cells 15 and 16 are not in run 2
            continue
        stored = json.loads(match["metrics_json"].iloc[0])
        for effect, value in points.items():
            assert abs(float(stored[effect]["estimate"]) - value) <= cb.EXACT_POINT_TOLERANCE, (cell, replicate, effect)
            checked += 1
    assert checked > 0
