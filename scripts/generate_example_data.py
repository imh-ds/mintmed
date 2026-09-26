"""Regenerate the fixed example CSVs under ``examples/`` from seeded generators.

The committed CSVs are the source of truth; this script documents how they
were produced and reproduces them byte for byte. ``parallel`` and
``serial_moderated`` use the Task 7 fixtures ``parallel_correlated`` and
``moderated_serial``. ``single`` declares a binary exposure, which the
``linear`` fixture does not, so it uses the same single-mediator linear
equations with a balanced 0/1 exposure.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from mintmed.simulation import sample_fixture

EXAMPLE_SIZES = {"single": 150, "parallel": 200, "serial_moderated": 160}
EXAMPLE_SEEDS = {"single": 20260919, "parallel": 20260920, "serial_moderated": 20260921}
DECIMALS = 6


def _single(n: int, rng: np.random.Generator) -> pd.DataFrame:
    exposure = np.resize(np.array([0.0, 1.0]), n)
    rng.shuffle(exposure)
    mediator = 0.5 * exposure + rng.standard_normal(n)
    outcome = 0.2 * exposure + 0.5 * mediator + rng.standard_normal(n)
    return pd.DataFrame({"A": exposure.astype(int), "M": mediator, "Y": outcome})


def example_frames() -> dict[str, pd.DataFrame]:
    """Return the three example data frames in their committed column order."""

    frames = {
        "single": _single(EXAMPLE_SIZES["single"], np.random.default_rng(EXAMPLE_SEEDS["single"])),
        "parallel": sample_fixture(
            "parallel_correlated", EXAMPLE_SIZES["parallel"], np.random.default_rng(EXAMPLE_SEEDS["parallel"])
        ).data.loc[:, ["A", "M1", "M2", "Y"]],
        "serial_moderated": sample_fixture(
            "moderated_serial",
            EXAMPLE_SIZES["serial_moderated"],
            np.random.default_rng(EXAMPLE_SEEDS["serial_moderated"]),
        ).data.loc[:, ["A", "W", "C", "M1", "M2", "Y"]],
    }
    rounded = {}
    for name, frame in frames.items():
        frame = frame.copy()
        for column in frame.columns:
            if column in {"A", "W"} and name != "parallel":
                frame[column] = frame[column].astype(int)
            else:
                frame[column] = frame[column].astype(float).round(DECIMALS)
        rounded[name] = frame.reset_index(drop=True)
    return rounded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path("examples"))
    arguments = parser.parse_args()
    for name, frame in example_frames().items():
        path = arguments.examples / name / "data.csv"
        path.write_text(frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8")
        print(f"wrote {path} ({len(frame)} rows)")


if __name__ == "__main__":
    main()
