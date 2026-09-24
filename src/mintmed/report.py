"""Deterministic public reports for :class:`mintmed.types.MediationResult`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from .types import AnalysisStatus, BootstrapResult, ContributionResult, EffectEstimate, MediationResult


_EFFECT_COLUMNS = (
    "name",
    "source",
    "estimate",
    "lower",
    "upper",
    "status",
    "reason",
    "units",
    "interval_available",
    "moderator",
    "moderator_value",
    "baseline_value",
    "metadata",
)
_BOOTSTRAP_COLUMNS = (
    "replicate",
    "status",
    "error_code",
    "error_message",
    "row_seed",
    "integration_seed",
    "runtime_seconds",
    "accepted_draw_budget",
    "integration_draw_count",
    "TE",
    "PNDE",
    "TNIE",
    "contribution_available",
    "contribution_reason_code",
    "contribution_reason",
)
_PRIVATE_REPLICATE_KEYS = {
    "row_positions",
    "row_indices",
    "row_values",
    "participant_id",
    "participant_ids",
    "source_rows",
    "source_row_labels",
    "data",
}


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible copy without exposing unsupported objects."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if is_dataclass(value):
        return _json_safe(asdict(value))
    return value


def _status_value(value: AnalysisStatus | str) -> str:
    return value.value if isinstance(value, AnalysisStatus) else str(value)


def _effect_mapping(effect: EffectEstimate | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(effect, EffectEstimate):
        return asdict(effect)
    if isinstance(effect, Mapping):
        return effect
    raise TypeError(f"effect must be an EffectEstimate or mapping, got {type(effect).__name__}")


def _effect_payload(effect: EffectEstimate | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an effect while retaining its interval state and reason."""

    payload = dict(_json_safe(_effect_mapping(effect)))
    payload["status"] = _status_value(payload.get("status", AnalysisStatus.OK.value))
    payload["interval_available"] = payload.get("lower") is not None and payload.get("upper") is not None
    return payload


def _safe_replicate(record: Mapping[str, Any]) -> dict[str, Any]:
    """Project one bootstrap record without participant-linked row fields."""

    return _json_safe(
        {
            key: value
            for key, value in record.items()
            if key not in _PRIVATE_REPLICATE_KEYS
        }
    )


def _contribution_payload(contributions: ContributionResult | None) -> dict[str, Any] | None:
    if contributions is None:
        return None
    return {
        "available": bool(contributions.available),
        "contributions": {
            str(name): _effect_payload(effect)
            for name, effect in sorted(contributions.contributions.items())
        },
        "reason_code": contributions.reason_code,
        "reason": contributions.reason,
    }


def _bootstrap_payload(bootstrap: BootstrapResult | None) -> dict[str, Any] | None:
    if bootstrap is None:
        return None
    return {
        "requested": int(bootstrap.requested),
        "attempted": int(bootstrap.attempted),
        "successful": int(bootstrap.successful),
        "failed": int(bootstrap.failed),
        "status": _status_value(bootstrap.status),
        "failure_counts": _json_safe(bootstrap.failure_counts),
        "metadata": _json_safe(bootstrap.metadata),
        "intervals": [_effect_payload(effect) for effect in bootstrap.intervals],
        "replicates": [_safe_replicate(record) for record in bootstrap.replicates],
    }


def result_to_dict(result: MediationResult) -> dict[str, Any]:
    """Convert one immutable analysis result to the versioned public schema."""

    if not isinstance(result, MediationResult):
        raise TypeError("result must be a MediationResult")

    # Use the dataclass conversion as the structural boundary, then replace
    # sensitive/nested sections with their explicit public projections.
    raw = asdict(result)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": _status_value(result.status),
        "overall_status": _json_safe(result.diagnostics.get("overall_status")),
        "specification_hash": str(result.specification_hash),
        "analysis_hash": str(result.analysis_hash),
        "effects": [_effect_payload(effect) for effect in result.effects],
        "contributions": _contribution_payload(result.contributions),
        "bootstrap": _bootstrap_payload(result.bootstrap),
        "diagnostics": _json_safe(raw["diagnostics"]),
        "provenance": _json_safe(raw["provenance"]),
    }
    json.dumps(payload, sort_keys=True, allow_nan=False)
    return payload


def _interval_index(result: MediationResult) -> dict[str, Mapping[str, Any]]:
    if result.bootstrap is None:
        return {}
    return {
        effect.name: _effect_payload(effect)
        for effect in result.bootstrap.intervals
    }


def _canonical_value(value: object) -> str:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".15g")
    return str(value)


def _moderator_interval_key(moderator: object, value: object, effect: object) -> str:
    return (
        f"moderator_difference__{moderator}__"
        f"{_canonical_value(value)}__{effect}"
    )


def _compact_metadata(metadata: Any) -> str:
    return json.dumps(_json_safe(metadata or {}), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _effect_row(
    effect: EffectEstimate | Mapping[str, Any],
    *,
    source: str,
    interval: Mapping[str, Any] | None = None,
    moderator: object | None = None,
    moderator_value: object | None = None,
    baseline_value: object | None = None,
) -> dict[str, Any]:
    point = _effect_payload(effect)
    selected = dict(interval or point)
    lower = selected.get("lower")
    upper = selected.get("upper")
    status = _status_value(selected.get("status", point["status"]))
    reason = selected.get("reason", point.get("reason"))
    if interval is None and source == "moderator_effect" and lower is None and upper is None:
        reason = reason or "bootstrap_interval_not_reported_for_moderator_effect"
    return {
        "name": point.get("name"),
        "source": source,
        "estimate": point.get("estimate"),
        "lower": lower,
        "upper": upper,
        "status": status,
        "reason": reason,
        "units": point.get("units"),
        "interval_available": lower is not None and upper is not None,
        "moderator": moderator,
        "moderator_value": moderator_value,
        "baseline_value": baseline_value,
        "metadata": _compact_metadata(point.get("metadata")),
    }


def effects_rows(result: MediationResult) -> tuple[dict[str, Any], ...]:
    """Flatten every public point effect into one deterministic CSV row."""

    if not isinstance(result, MediationResult):
        raise TypeError("result must be a MediationResult")
    intervals = _interval_index(result)
    rows: list[dict[str, Any]] = []
    for effect in result.effects:
        rows.append(_effect_row(effect, source="primary", interval=intervals.get(effect.name)))
    if result.contributions is not None:
        for name, effect in sorted(result.contributions.contributions.items()):
            rows.append(_effect_row(effect, source="contribution", interval=intervals.get(name)))
    moderation = result.diagnostics.get("moderation", {})
    if isinstance(moderation, Mapping):
        for contrast in moderation.get("contrasts", ()):
            if not isinstance(contrast, Mapping):
                continue
            moderator = contrast.get("moderator")
            value = contrast.get("value")
            baseline_value = contrast.get("baseline_value")
            for effect in contrast.get("effects", ()):
                if isinstance(effect, Mapping):
                    rows.append(
                        _effect_row(
                            effect,
                            source="moderator_effect",
                            moderator=moderator,
                            moderator_value=value,
                            baseline_value=baseline_value,
                        )
                    )
            for effect in contrast.get("differences", ()):
                if isinstance(effect, Mapping):
                    key = _moderator_interval_key(moderator, value, effect.get("name"))
                    rows.append(
                        _effect_row(
                            effect,
                            source="moderator_difference",
                            interval=intervals.get(key),
                            moderator=moderator,
                            moderator_value=value,
                            baseline_value=baseline_value,
                        )
                    )
    return tuple(rows)


def bootstrap_rows(result: MediationResult) -> tuple[dict[str, Any], ...]:
    """Return safe, rectangular bootstrap rows for CSV output."""

    if not isinstance(result, MediationResult):
        raise TypeError("result must be a MediationResult")
    if result.bootstrap is None:
        return ()
    safe_rows = [_safe_replicate(record) for record in result.bootstrap.replicates]
    dynamic = sorted(
        {
            key
            for row in safe_rows
            for key in row
            if key not in _BOOTSTRAP_COLUMNS and key not in _PRIVATE_REPLICATE_KEYS
        }
    )
    columns = (*_BOOTSTRAP_COLUMNS, *dynamic)
    return tuple(
        {column: _json_safe(row.get(column)) for column in columns}
        for row in safe_rows
    )


def _display(value: Any) -> str:
    value = _json_safe(value)
    if value is None:
        return "not available"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".8g")
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _markdown_cell(value: Any) -> str:
    return _display(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(_markdown_cell(value) for value in row) + " |" for row in rows)
    return output


def render_markdown(result: MediationResult) -> str:
    """Render an assumption-aware readable report from one result."""

    payload = result_to_dict(result)
    diagnostics = payload["diagnostics"]
    scientific = diagnostics.get("scientific", {})
    contrast = scientific.get("contrast", {})
    rows = payload["effects"]
    lines = [
        "# Mintmed mediation analysis",
        "",
        "## Contrast and answer",
        "",
        f"- Overall status: `{_display(payload['overall_status'])}` (result status `{_display(payload['status'])}`).",
        f"- Exposure contrast: `{_display(contrast.get('reference'))}` → `{_display(contrast.get('comparison'))}`.",
        f"- Interpretation: `{_display(scientific.get('interpretation'))}`.",
        "",
        "| Estimand | Estimate | 95% interval | Units | Status | Reason |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for effect in rows:
        interval = (
            f"[{_display(effect.get('lower'))}, {_display(effect.get('upper'))}]"
            if effect.get("interval_available")
            else "not available"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    _display(effect.get("name")),
                    _display(effect.get("estimate")),
                    interval,
                    _display(effect.get("units")),
                    _display(effect.get("status")),
                    _display(effect.get("reason")),
                )
            )
            + " |"
        )
    contributions = payload.get("contributions")
    if contributions is not None and not contributions.get("available", False):
        lines.extend(
            [
                "",
                f"Individual mediator contributions: unavailable (`{_display(contributions.get('reason_code'))}`; {_display(contributions.get('reason'))}).",
            ]
        )
    moderator_rows = [row for row in effects_rows(result) if row["source"] in {"moderator_effect", "moderator_difference"}]
    if moderator_rows:
        lines.extend(
            [
                "",
                "Moderator contrasts:",
                "",
                "| Estimand | Source | Moderator | Value | Baseline | Estimate | 95% interval | Status | Reason |",
                "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
            ]
        )
        for effect in moderator_rows:
            interval = (
                f"[{_display(effect.get('lower'))}, {_display(effect.get('upper'))}]"
                if effect.get("interval_available")
                else "not available"
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        _display(effect.get("name")),
                        _display(effect.get("source")),
                        _display(effect.get("moderator")),
                        _display(effect.get("moderator_value")),
                        _display(effect.get("baseline_value")),
                        _display(effect.get("estimate")),
                        interval,
                        _display(effect.get("status")),
                        _display(effect.get("reason")),
                    )
                )
                + " |"
            )

    lines.extend(["", "## Uncertainty", ""])
    bootstrap = payload.get("bootstrap")
    if bootstrap is None:
        lines.append("No participant bootstrap was requested; the displayed effects are point estimates without interval estimates.")
    else:
        lines.extend(
            [
                f"- Bootstrap mode: `{_display(payload.get('provenance', {}).get('bootstrap_mode', 'standard'))}`.",
                f"- Replicates: requested {_display(bootstrap.get('requested'))}, attempted {_display(bootstrap.get('attempted'))}, successful {_display(bootstrap.get('successful'))}, failed {_display(bootstrap.get('failed'))}.",
                f"- Bootstrap status: `{_display(bootstrap.get('status'))}`; interval policy: percentile 2.5/97.5 over successful finite values.",
            ]
        )
        if bootstrap.get("metadata", {}).get("provisional") or bootstrap.get("metadata", {}).get("reason") == "quick_diagnostic_provisional":
            lines.append("- These intervals are provisional quick-diagnostic intervals and are not release evidence.")
        if bootstrap.get("failure_counts"):
            lines.append(f"- Failure counts: `{_display(bootstrap.get('failure_counts'))}`.")

    lines.extend(["", "## Model", ""])
    rows_info = diagnostics.get("rows", {})
    lines.extend(
        [
            f"- Analysis population: {_display(rows_info.get('retained'))} retained of {_display(rows_info.get('original'))} rows; {_display(rows_info.get('excluded'))} excluded.",
            f"- Outcome units: `{_display(scientific.get('units'))}`; outcome family: `{_display(scientific.get('outcome_family'))}`.",
            f"- Arrangement: `{_display(scientific.get('arrangement'))}`; factorization order: `{_display(scientific.get('factorization_order'))}`.",
            f"- Scientific edges: `{_display(scientific.get('scientific_edges'))}`; factorization predictors are recorded separately.",
            f"- Integration: `{_display(diagnostics.get('integration', {}).get('method'))}` with accepted draw budget `{_display(diagnostics.get('integration', {}).get('accepted_draw_budget'))}`.",
        ]
    )

    lines.extend(["", "## Assumptions and exclusions", ""])
    assumptions = diagnostics.get("assumptions", []) or ["No assumption summary was recorded."]
    exclusions = diagnostics.get("exclusions", []) or ["No exclusions were recorded."]
    lines.extend(f"- {_markdown_cell(item)}" for item in assumptions)
    lines.extend(f"- {_markdown_cell(item)}" for item in exclusions)

    lines.extend(["", "## Diagnostics", ""])
    lines.extend(
        _markdown_table(
            ("Category", "Value"),
            (
                ("Missingness", diagnostics.get("missing")),
                ("Support", diagnostics.get("support")),
                ("Binary counts", diagnostics.get("binary_counts")),
                ("Warnings", diagnostics.get("warnings")),
                ("Integration", diagnostics.get("integration")),
            ),
        )
    )
    if diagnostics.get("error"):
        lines.extend(["", f"Error: `{_display(diagnostics['error'])}`."])

    lines.extend(["", "## Provenance", ""])
    for key in ("specification_hash", "analysis_hash", "mintmed_version", "python_version", "seed", "bootstrap_requested", "bootstrap_mode"):
        if key in payload["provenance"]:
            lines.append(f"- {key}: `{_display(payload['provenance'][key])}`")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Causal interpretation requires the declared assumptions; otherwise these are model-standardized contrasts.",
            "- An unavailable interval is not a zero effect and is not evidence of a null finding.",
            "- This report does not apply a significance cascade or supply a default proportion-mediated quantity.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def write_reports(result: MediationResult, output_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Write JSON, effects CSV, bootstrap CSV, and Markdown atomically by file."""

    if not isinstance(result, MediationResult):
        raise TypeError("result must be a MediationResult")
    output_dir = Path(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(str(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = result_to_dict(result)
    effect_data = effects_rows(result)
    bootstrap_data = bootstrap_rows(result)
    bootstrap_dynamic = sorted(
        {key for row in bootstrap_data for key in row if key not in _BOOTSTRAP_COLUMNS}
    )
    targets = (
        output_dir / "analysis.json",
        output_dir / "effects.csv",
        output_dir / "bootstrap.csv",
        output_dir / "report.md",
    )
    with tempfile.TemporaryDirectory(prefix=".mintmed-report-", dir=output_dir) as staging_name:
        staging = Path(staging_name)
        (staging / "analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        _write_csv(staging / "effects.csv", _EFFECT_COLUMNS, effect_data)
        _write_csv(staging / "bootstrap.csv", (*_BOOTSTRAP_COLUMNS, *bootstrap_dynamic), bootstrap_data)
        (staging / "report.md").write_text(render_markdown(result), encoding="utf-8")
        json.loads((staging / "analysis.json").read_text(encoding="utf-8"))
        for name, target in zip((path.name for path in targets), targets, strict=True):
            os.replace(staging / name, target)
    return targets


__all__ = [
    "bootstrap_rows",
    "effects_rows",
    "render_markdown",
    "result_to_dict",
    "write_reports",
]
