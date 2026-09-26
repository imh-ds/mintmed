"""Fail CI when a shipped example produces a degraded analysis.

Each argument is a CLI output directory containing ``analysis.json``. A run
passes when its overall status is ``complete`` or ``complete_with_warnings``
and at most ``MAX_BOOTSTRAP_FAILURE_RATE`` of attempted bootstrap replicates
failed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ACCEPTED_STATUSES = frozenset({"complete", "complete_with_warnings"})
MAX_BOOTSTRAP_FAILURE_RATE = 0.10


def check_output_dir(output_dir: Path) -> list[str]:
    """Return human-readable problems for one example output directory."""

    path = Path(output_dir) / "analysis.json"
    if not path.is_file():
        return [f"{path}: analysis.json is missing"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    overall = payload.get("overall_status")
    if overall not in ACCEPTED_STATUSES:
        problems.append(f"{path}: overall_status {overall!r} is not one of {sorted(ACCEPTED_STATUSES)}")
    bootstrap = payload.get("bootstrap") or {}
    attempted = int(bootstrap.get("attempted") or 0)
    failed = int(bootstrap.get("failed") or 0)
    if attempted and failed / attempted > MAX_BOOTSTRAP_FAILURE_RATE:
        problems.append(
            f"{path}: {failed} of {attempted} bootstrap replicates failed "
            f"(more than {MAX_BOOTSTRAP_FAILURE_RATE:.0%})"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dirs", nargs="+", type=Path)
    arguments = parser.parse_args(argv)
    problems = [problem for output in arguments.output_dirs for problem in check_output_dir(output)]
    for problem in problems:
        print(problem)
    if not problems:
        print(f"{len(arguments.output_dirs)} example output(s) passed")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
