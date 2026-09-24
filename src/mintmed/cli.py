"""CSV/YAML command-line boundary for Mintmed analyses."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import NoReturn

import pandas as pd

from . import __version__
from .api import analyze_mediation
from .diagnostics import PlanValidationError
from .report import write_reports
from .spec import SpecValidationError, load_model_spec


_SUCCESS_STATES = {"complete", "complete_with_warnings", "point_only"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mintmed",
        description="Run a declared Mintmed mediation analysis from CSV data and YAML.",
    )
    parser.add_argument("--data", type=Path, required=False, help="input CSV file")
    parser.add_argument("--spec", type=Path, required=False, help="strict YAML model specification")
    parser.add_argument("--output", type=Path, required=False, help="output directory")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _fail(message: str) -> NoReturn:
    print(f"mintmed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _required_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    missing = [name for name in ("data", "spec", "output") if getattr(args, name) is None]
    if missing:
        _fail("missing required option(s): " + ", ".join(f"--{name}" for name in missing))
    return args.data, args.spec, args.output


def _format_spec_error(error: SpecValidationError) -> str:
    return f"{error.code} at {error.path}: {error.message}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run one analysis and return a stable process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    data_path, spec_path, output_dir = _required_paths(args)

    try:
        data = pd.read_csv(data_path)
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        _fail(f"could not read data CSV {data_path}: {error}")

    try:
        spec = load_model_spec(spec_path)
    except SpecValidationError as error:
        _fail(_format_spec_error(error))
    except (OSError, UnicodeError, ValueError) as error:
        _fail(f"could not read model specification {spec_path}: {error}")

    try:
        result = analyze_mediation(data, spec)
    except PlanValidationError as error:
        _fail(str(error))

    try:
        write_reports(result, output_dir)
    except (OSError, TypeError, ValueError) as error:
        _fail(f"could not write reports to {output_dir}: {error}")

    overall_status = str(result.diagnostics.get("overall_status", "incomplete"))
    if overall_status in _SUCCESS_STATES:
        return 0
    print(f"mintmed: analysis status {overall_status}; see analysis.json for diagnostics", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
