"""Run the R comparator runners on real exported datasets (skipped without R).

Covers 2 replicates of cells 01, 08, 10 and 11 with reduced draw counts (the
point estimates do not depend on them), checks the estimand mapping against
OLS path products, determinism, the seed rule and the Python runner's
end-to-end path. Cell 09 checks that R's ns(M, df = 3) spans the same
function space as patsy's cr(M, df = 3, constraints = "center").
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import pytest

from mintmed.experiments import comparator_benchmark as cb
from mintmed.experiments.mediation_validation import load_config
from scripts.export_validation_datasets import export, read_dataset

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "mediation_validation_v3.yaml"
CELLS = ["cell01_linear_n100", "cell08_quadratic_n100", "cell10_moderated_n150", "cell11_binary_mediator_n150"]
BOOT, QB = 49, 100
RSCRIPT = cb.find_rscript()
R_READY = cb.r_packages_available(RSCRIPT)
if not R_READY and os.environ.get(cb.REQUIRE_R_ENV) == "1":
    pytest.fail(f"{cb.REQUIRE_R_ENV}=1 but Rscript with mediation, lavaan and jsonlite is not available", pytrace=False)

pytestmark = pytest.mark.skipif(not R_READY, reason="Rscript with mediation, lavaan and jsonlite is not available")


@pytest.fixture(scope="module")
def exported(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("comparator-datasets")
    export(load_config(CONFIG), root, config_path="configs/mediation_validation_v3.yaml",
           cell_ids=[*CELLS, "cell09_spline_n250"], replicate_start=0, replicate_stop=2)
    return root


def _run(tool: str, exported: Path, output: Path) -> pd.DataFrame:
    long, failure = cb.run_r_tool(RSCRIPT, tool, exported / "manifest.json", output, boot_sims=BOOT, qb_sims=QB)
    assert failure is None, failure
    return long.loc[long["cell_id"].isin(CELLS)].reset_index(drop=True)


@pytest.fixture(scope="module")
def outputs(exported: Path, tmp_path_factory) -> dict[str, pd.DataFrame]:
    out = tmp_path_factory.mktemp("comparator-out")
    return {tool: _run(tool, exported, out / f"{tool}.csv") for tool in cb.TOOLS}


def _estimate(long: pd.DataFrame, mode: str, cell: str, replicate: int, effect: str) -> float:
    row = long.loc[(long["mode"] == mode) & (long["cell_id"] == cell) & (long["replicate"] == str(replicate))
                   & (long["effect"] == effect)]
    assert len(row) == 1
    return float(row["estimate"].iloc[0])


def _ols(y: np.ndarray, columns: list[np.ndarray]) -> np.ndarray:
    design = np.column_stack([np.ones_like(y), *columns])
    return np.linalg.lstsq(design, y, rcond=None)[0]


def test_every_dataset_mode_and_effect_has_a_row(outputs) -> None:
    for tool, long in outputs.items():
        for cell in CELLS:
            effects = cb.effect_truths(cell)
            subset = long.loc[long["cell_id"] == cell]
            assert len(subset) == 2 * len(cb.MODES) * len(effects)
            statuses = set(subset["status"])
            if cb.is_supported(tool, cell):
                assert statuses <= {"ok", "ok_warnings"}, subset[["mode", "effect", "status", "message"]]
                assert subset["estimate"].map(float).notna().all()
            else:
                assert statuses == {"not_estimable"}
                assert (subset["estimate"] == "").all()


def test_seed_rule_matches_python(outputs) -> None:
    for long in outputs.values():
        for row in long.itertuples():
            assert int(row.r_seed) == cb.r_seed(row.analysis_seed)


def test_linear_cell_estimates_are_ols_path_products(outputs, exported: Path) -> None:
    for replicate in (0, 1):
        data = read_dataset(exported / "cell01_linear_n100" / f"rep_{replicate:04d}.csv")
        a = _ols(data["M"].to_numpy(), [data["A"].to_numpy(), data["C"].to_numpy()])[1]
        outcome = _ols(data["Y"].to_numpy(), [data["A"].to_numpy(), data["C"].to_numpy(), data["M"].to_numpy()])
        direct, b = outcome[1], outcome[3]
        expected = {"TNIE": a * b, "PNDE": direct, "TE": direct + a * b}
        for effect, value in expected.items():
            for mode in cb.MODES:
                assert _estimate(outputs["lavaan"], mode, "cell01_linear_n100", replicate, effect) == pytest.approx(value, abs=1e-10)
            # mediate's bootstrap-mode point estimate is exact when Y is linear in M.
            assert _estimate(outputs["mediation"], "primary", "cell01_linear_n100", replicate, effect) == pytest.approx(value, abs=1e-10)


def test_moderated_cell_conditional_effects(outputs, exported: Path) -> None:
    for replicate in (0, 1):
        data = read_dataset(exported / "cell10_moderated_n150" / f"rep_{replicate:04d}.csv")
        A, W, C, M, Y = (data[name].to_numpy() for name in ("A", "W", "C", "M", "Y"))
        m_coef = _ols(M, [A, W, C, W * A])
        y_coef = _ols(Y, [A, W, C, M, W * M])
        low = m_coef[1] * y_coef[4]
        high = (m_coef[1] + m_coef[4]) * (y_coef[4] + y_coef[5])
        expected = {"TNIE_W0": low, "TNIE_W1": high, "TNIE_difference": high - low}
        for effect, value in expected.items():
            assert _estimate(outputs["lavaan"], "primary", "cell10_moderated_n150", replicate, effect) == pytest.approx(value, abs=1e-10)
            assert _estimate(outputs["mediation"], "primary", "cell10_moderated_n150", replicate, effect) == pytest.approx(value, abs=1e-10)


def test_runners_are_deterministic(exported: Path, outputs, tmp_path: Path) -> None:
    ignore = ["runtime_seconds"]
    for tool in cb.TOOLS:
        again = _run(tool, exported, tmp_path / f"{tool}-again.csv")
        pd.testing.assert_frame_equal(outputs[tool].drop(columns=ignore), again.drop(columns=ignore))


def test_r_natural_spline_spans_patsy_cr_basis(exported: Path, tmp_path: Path) -> None:
    path = (exported / "cell09_spline_n250" / "rep_0000.csv").as_posix()
    data = read_dataset(exported / "cell09_spline_n250" / "rep_0000.csv")
    probe = np.array([data["M"].min() - 1.0, data["M"].median(), data["M"].max() + 1.5])
    output = tmp_path / "spline.csv"
    script = (
        "suppressPackageStartupMessages(library(splines));"
        f"d <- read.csv('{path}', colClasses = 'numeric');"
        "fit <- lm(Y ~ A + C + ns(M, df = 3), data = d);"
        f"new <- data.frame(A = 1, C = 0, M = c({', '.join(repr(float(x)) for x in probe)}));"
        f"write.csv(data.frame(value = sprintf('%.17g', c(fitted(fit), predict(fit, new)))), '{output.as_posix()}', row.names = FALSE)"
    )
    completed = subprocess.run([RSCRIPT, "-e", script], capture_output=True, text=True, timeout=120, check=False)
    assert completed.returncode == 0, completed.stderr
    r_values = pd.read_csv(output, dtype=str)["value"].map(float).to_numpy()
    design = patsy.dmatrix('1 + A + C + cr(M, df=3, constraints="center")', data)
    coef = np.linalg.lstsq(np.asarray(design), data["Y"].to_numpy(), rcond=None)[0]
    new = pd.DataFrame({"A": 1.0, "C": 0.0, "M": probe})
    predicted = np.asarray(patsy.build_design_matrices([design.design_info], new)[0]) @ coef
    python_values = np.concatenate([np.asarray(design) @ coef, predicted])
    np.testing.assert_allclose(r_values, python_values, rtol=0, atol=1e-9)


def test_python_runner_end_to_end(tmp_path: Path) -> None:
    config = load_config(CONFIG)
    raw = cb.run(config, tmp_path / "out", config_path=CONFIG, cell_ids=["cell11_binary_mediator_n150"], replicate=0,
                 rscript=RSCRIPT, boot_sims=29, qb_sims=50)
    status = dict(zip(raw["tool"], raw["status"], strict=True))
    assert status["lavaan"] == "not_estimable"
    assert status["mediation"] in {"ok", "ok_warnings"}
    summary = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "bootstrap refits 29" in summary  # non-frozen settings are flagged
