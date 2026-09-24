"""Contract tests for named mediation effects and Task 9 outputs."""

from __future__ import annotations

import numpy as np
import pytest

from mintmed.effects import ModeratorContrast, natural_effects
from mintmed.types import AnalysisStatus, RegimeMeans


def test_effect_module_exports_task9_contracts():
    means = RegimeMeans(mu_00=1.0, mu_10=1.2, mu_11=1.5)
    effects = natural_effects(
        means,
        exposure_reference=0,
        exposure_comparison=1,
        units="outcome_units",
    )
    assert tuple(effect.name for effect in effects) == ("TE", "PNDE", "TNIE")
    assert tuple(effect.estimate for effect in effects) == pytest.approx((0.5, 0.2, 0.3))
    assert ModeratorContrast.__name__ == "ModeratorContrast"


def test_natural_effects_preserves_cancellation_and_metadata():
    effects = natural_effects(
        RegimeMeans(mu_00=1.0, mu_10=0.0, mu_11=1.0),
        units="probability_difference",
        interpretation="model_standardized",
    )
    assert effects[0].estimate == pytest.approx(0.0)
    assert effects[0].units == "probability_difference"
    assert effects[0].metadata["standardization_population"] == "retained_analysis_rows"
    assert effects[1].estimate == pytest.approx(-1.0)
    assert effects[2].estimate == pytest.approx(1.0)


def test_nonfinite_means_are_explicit_failures_not_silent_zeroes():
    effects = natural_effects(RegimeMeans(np.nan, 0.0, 1.0))
    assert all(effect.status is AnalysisStatus.INTEGRATION_FAILED for effect in effects)
    assert all(effect.reason == "nonfinite_regime_mean" for effect in effects)
