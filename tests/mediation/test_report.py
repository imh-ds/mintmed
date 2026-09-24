from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from mintmed.report import (
    bootstrap_rows,
    effects_rows,
    render_markdown,
    result_to_dict,
    write_reports,
)
from mintmed.types import (
    AnalysisStatus,
    BootstrapResult,
    ContributionResult,
    EffectEstimate,
    MediationResult,
)


def _effect_record(
    name: str,
    estimate: float,
    *,
    lower: float | None = None,
    upper: float | None = None,
    status: AnalysisStatus = AnalysisStatus.OK,
    reason: str | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "estimate": estimate,
        "lower": lower,
        "upper": upper,
        "status": status.value,
        "reason": reason,
        "units": "outcome_units",
        "interval_available": lower is not None and upper is not None,
        "metadata": {"source": "test"},
    }


def _result(*, bootstrap: bool = True) -> MediationResult:
    effects = (
        EffectEstimate(
            "TE",
            0.5,
            lower=0.1,
            upper=0.9,
            metadata={"vector": np.array([1, 2]), "estimand": "total"},
        ),
        EffectEstimate(
            "PNDE",
            -0.4,
            status=AnalysisStatus.INTERVAL_UNAVAILABLE,
            reason="bootstrap_failure_threshold",
        ),
        EffectEstimate("TNIE", 0.9, units="outcome_units"),
    )
    diagnostics = {
        "overall_status": "complete_with_warnings",
        "rows": {"original": 10, "retained": 10, "excluded": 0},
        "scientific": {
            "contrast": {"reference": 0, "comparison": 1, "moderator_values": {"W": 0}},
            "interpretation": "model_standardized",
            "units": "outcome_units",
            "arrangement": "parallel",
            "factorization_order": ["M"],
        },
        "moderation": {
            "requested": True,
            "status": "ok",
            "contrasts": [
                {
                    "moderator": "W",
                    "value": 1,
                    "baseline_value": 0,
                    "status": "ok",
                    "reason": None,
                    "effects": [_effect_record("TNIE", 0.7, lower=0.2, upper=1.1)],
                    "differences": [_effect_record("TNIE", 0.2, lower=-0.1, upper=0.5)],
                }
            ],
        },
        "assumptions": ["rows are independent"],
        "exclusions": ["no raw participant rows are reported"],
        "warnings": [{"code": "small_sample", "message": "small sample", "status": "warning"}],
        "bootstrap": {"status": "ok"},
        "nodes": [],
        "integration": {"status": "ok"},
    }
    bootstrap_result = None
    if bootstrap:
        bootstrap_result = BootstrapResult(
            requested=2,
            attempted=2,
            successful=1,
            failed=1,
            replicates=(
                {
                    "replicate": 0,
                    "row_seed": np.int64(4),
                    "integration_seed": np.int64(5),
                    "row_positions": (0, 1),
                    "row_indices": ("participant-a", "participant-b"),
                    "status": "ok",
                    "TE": np.float64(0.4),
                },
                {
                    "replicate": 1,
                    "status": "fit_failed",
                    "error_code": "rank_deficient",
                    "error_message": "rank deficient",
                    "row_positions": (1, 0),
                    "row_indices": ("participant-b", "participant-a"),
                },
            ),
            intervals=(
                EffectEstimate("TE", 0.5, lower=0.1, upper=0.9),
                EffectEstimate(
                    "PNDE",
                    -0.4,
                    status=AnalysisStatus.INTERVAL_UNAVAILABLE,
                    reason="bootstrap_failure_threshold",
                ),
            ),
            status=AnalysisStatus.INTERVAL_UNAVAILABLE,
            failure_counts={"rank_deficient": 1},
            metadata={"bootstrap_mode": "standard", "nonfinite": float("nan")},
        )
    return MediationResult(
        specification_hash="spec-hash",
        analysis_hash="analysis-hash",
        effects=effects,
        contributions=ContributionResult(
            available=False,
            reason_code="contribution_nonparallel",
            reason="individual contribution is unavailable for this outcome model",
        ),
        diagnostics=diagnostics,
        bootstrap=bootstrap_result,
        provenance={"seed": np.int64(12), "mintmed_version": "0.1.0"},
        status=AnalysisStatus.WARNING,
    )


def test_result_to_dict_preserves_statuses_hashes_and_safe_bootstrap_records() -> None:
    payload = result_to_dict(_result())

    assert set(payload) == {
        "schema_version",
        "status",
        "overall_status",
        "specification_hash",
        "analysis_hash",
        "effects",
        "contributions",
        "bootstrap",
        "diagnostics",
        "provenance",
    }
    assert payload["status"] == "warning"
    assert payload["overall_status"] == "complete_with_warnings"
    assert payload["specification_hash"] == "spec-hash"
    assert payload["effects"][1]["estimate"] == -0.4
    assert payload["effects"][1]["lower"] is None
    assert payload["effects"][1]["status"] == "interval_unavailable"
    assert payload["bootstrap"]["replicates"][0]["row_seed"] == 4
    assert "row_positions" not in payload["bootstrap"]["replicates"][0]
    assert "row_indices" not in payload["bootstrap"]["replicates"][0]
    assert payload["bootstrap"]["metadata"]["nonfinite"] is None
    json.dumps(payload, allow_nan=False)


def test_effect_and_bootstrap_rows_preserve_negative_values_and_empty_bounds() -> None:
    result = _result()

    rows = effects_rows(result)
    pnde = next(row for row in rows if row["source"] == "primary" and row["name"] == "PNDE")
    moderator_difference = next(row for row in rows if row["source"] == "moderator_difference")
    assert pnde["estimate"] == -0.4
    assert pnde["lower"] is None
    assert pnde["upper"] is None
    assert pnde["status"] == "interval_unavailable"
    assert moderator_difference["moderator"] == "W"
    assert moderator_difference["moderator_value"] == 1

    replicate_rows = bootstrap_rows(result)
    assert replicate_rows[0]["TE"] == 0.4
    assert "row_positions" not in replicate_rows[0]
    assert "row_indices" not in replicate_rows[0]
    assert replicate_rows[1]["TE"] is None


def test_render_markdown_starts_with_answer_and_avoids_significance_language() -> None:
    report = render_markdown(_result())

    assert report.startswith("# Mintmed mediation analysis\n\n## Contrast and answer")
    assert report.index("## Contrast and answer") < report.index("## Uncertainty")
    assert report.index("## Uncertainty") < report.index("## Model")
    assert "PNDE" in report
    assert "Moderator contrasts:" in report
    assert "Arrangement: `parallel`" in report
    assert "not available" in report
    assert "causal interpretation requires the declared assumptions" in report.lower()
    assert "p-value" not in report.lower()
    assert "significance star" not in report.lower()
    assert "proportion mediated" not in report.lower()


def test_write_reports_creates_four_utf8_artifacts_with_header_only_no_bootstrap(tmp_path: Path) -> None:
    paths = write_reports(_result(bootstrap=False), tmp_path)

    assert tuple(path.name for path in paths) == (
        "analysis.json",
        "effects.csv",
        "bootstrap.csv",
        "report.md",
    )
    assert all(path.exists() for path in paths)
    payload = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert payload["bootstrap"] is None
    with (tmp_path / "bootstrap.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 1
    assert rows[0][0] == "replicate"
