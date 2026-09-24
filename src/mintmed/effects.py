"""Named mediation effects and attribution helpers.

This module contains estimand-level calculations only.  It deliberately does
not own fitting, uncertainty, or the package-level analysis API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .types import AnalysisStatus, EffectEstimate, RegimeMeans, _freeze_mapping


@dataclass(frozen=True, slots=True)
class ModeratorContrast:
    """Effects and paired effect differences for one moderator value."""

    moderator: str
    value: object
    baseline_value: object
    effects: tuple[EffectEstimate, ...]
    differences: tuple[EffectEstimate, ...]
    status: AnalysisStatus = AnalysisStatus.OK
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "differences", tuple(self.differences))
        object.__setattr__(self, "status", AnalysisStatus(self.status))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


def _validate_tolerance(value: float) -> float:
    tolerance = float(value)
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("numerical_tolerance must be finite and nonnegative")
    return tolerance


def natural_effects(
    means: RegimeMeans,
    *,
    exposure_reference: object = 0,
    exposure_comparison: object = 1,
    units: str = "outcome_units",
    interpretation: str = "model_standardized",
    standardization_population: str = "retained_analysis_rows",
    numerical_tolerance: float = 1e-10,
) -> tuple[EffectEstimate, EffectEstimate, EffectEstimate]:
    """Return TE, PNDE, and TNIE using the primary mediation convention."""

    tolerance = _validate_tolerance(numerical_tolerance)
    te = float(means.mu_11 - means.mu_00)
    pnde = float(means.mu_10 - means.mu_00)
    tnie = float(means.mu_11 - means.mu_10)
    values = (te, pnde, tnie)
    finite = all(np.isfinite(value) for value in (means.mu_00, means.mu_10, means.mu_11))
    identity_residual = te - pnde - tnie
    identity_ok = np.isfinite(identity_residual) and abs(identity_residual) <= tolerance

    if not finite:
        status = AnalysisStatus.INTEGRATION_FAILED
        reason = "nonfinite_regime_mean"
    elif not identity_ok:
        status = AnalysisStatus.INTEGRATION_FAILED
        reason = "effect_decomposition_identity_failed"
    else:
        status = AnalysisStatus.OK
        reason = None

    metadata = {
        "exposure_reference": exposure_reference,
        "exposure_comparison": exposure_comparison,
        "interpretation": interpretation,
        "standardization_population": standardization_population,
        "decomposition": "TE = PNDE + TNIE",
        "identity_residual": identity_residual,
        "numerical_tolerance": tolerance,
    }
    return tuple(
        EffectEstimate(
            name=name,
            estimate=value,
            status=status,
            reason=reason,
            units=units,
            metadata=metadata,
        )
        for name, value in zip(("TE", "PNDE", "TNIE"), values, strict=True)
    )  # type: ignore[return-value]


__all__ = [
    "ModeratorContrast",
    "natural_effects",
]
