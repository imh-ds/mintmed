"""Contract tests for the public mediation analysis API."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect

import numpy as np
import pytest

import mintmed
from mintmed.simulation import sample_fixture


def _fixture(name: str = "linear", *, n: int = 80, bootstrap: int = 0):
    fixture = sample_fixture(name, n, np.random.default_rng(20261111 + n))
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            bootstrap=bootstrap,
            integration_tolerance=1.0,
        ),
    )
    return fixture.data, spec


def test_public_package_exports_analysis_entry_points() -> None:
    assert callable(mintmed.analyze_mediation)
    assert callable(mintmed.compile_template)
    assert callable(mintmed.estimate_plan)
    assert callable(mintmed.load_model_spec)
    assert mintmed.MediationResult.__name__ == "MediationResult"
    assert list(inspect.signature(mintmed.analyze_mediation).parameters) == ["data", "spec"]


def test_linear_analysis_returns_named_immutable_point_result() -> None:
    data, spec = _fixture()

    result = mintmed.analyze_mediation(data, spec)

    assert isinstance(result, mintmed.MediationResult)
    assert tuple(effect.name for effect in result.effects) == ("TE", "PNDE", "TNIE")
    assert all(effect.units == "outcome_units" for effect in result.effects)
    assert result.bootstrap is None
    assert result.diagnostics["overall_status"] == "point_only"
    with pytest.raises(TypeError):
        result.diagnostics["overall_status"] = "complete"
    with pytest.raises(FrozenInstanceError):
        result.effects += (result.effects[0],)


def test_linear_result_contains_auditable_hashes_and_provenance() -> None:
    data, spec = _fixture()

    first = mintmed.analyze_mediation(data, spec)
    second = mintmed.analyze_mediation(data, spec)

    assert first.specification_hash == second.specification_hash
    assert first.analysis_hash == second.analysis_hash
    assert first.provenance == second.provenance
    assert first.provenance["mintmed_version"] == mintmed.__version__
    assert first.provenance["specification_hash"] == first.specification_hash
    assert first.provenance["analysis_hash"] == first.analysis_hash
    serialized = repr(first.diagnostics) + repr(first.provenance)
    assert "C:\\Users\\" not in serialized
    assert "row_values" not in serialized


def test_wrong_public_input_types_are_programmer_errors() -> None:
    data, spec = _fixture()

    with pytest.raises(TypeError, match="data must be a pandas DataFrame"):
        mintmed.analyze_mediation(data.to_dict(), spec)
    with pytest.raises(TypeError, match="spec must be a ModelSpec"):
        mintmed.analyze_mediation(data, spec.to_canonical_dict())
