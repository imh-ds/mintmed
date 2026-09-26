"""Pickle and copy round trips for immutable result and specification objects."""

from __future__ import annotations

import copy
import pickle
from dataclasses import replace

import numpy as np
import pytest

import mintmed
from mintmed.simulation import sample_fixture
from mintmed.spec import estimate_plan
from mintmed.types import AnalysisStatus, EffectEstimate


def _analysis():
    fixture = sample_fixture("moderated_serial", 120, np.random.default_rng(20260926))
    spec = replace(
        fixture.spec,
        computation=replace(
            fixture.spec.computation,
            bootstrap=2,
            bootstrap_mode="quick_diagnostic",
            integration_tolerance=1.0,
        ),
    )
    return fixture, spec, mintmed.analyze_mediation(fixture.data, spec)


def test_frozen_mapping_survives_pickle_and_copy() -> None:
    effect = EffectEstimate("TE", 1.0, metadata={"nested": {"a": 1}, "values": [1, 2]})

    for clone in (copy.copy(effect.metadata), copy.deepcopy(effect.metadata), pickle.loads(pickle.dumps(effect.metadata))):
        assert clone == effect.metadata
        with pytest.raises(TypeError):
            clone["new"] = 1  # type: ignore[index]
    assert copy.copy(effect.metadata) is effect.metadata


def test_every_result_and_specification_object_round_trips_through_pickle() -> None:
    fixture, spec, result = _analysis()
    plan = estimate_plan(fixture.data, spec)
    assert result.bootstrap is not None

    objects = (
        EffectEstimate("TE", 1.0, status=AnalysisStatus.WARNING, metadata={"k": {"v": 1}}),
        result.effects[0],
        result.bootstrap,
        result,
        spec,
        plan,
        fixture.spec,
    )
    for value in objects:
        restored = pickle.loads(pickle.dumps(value))
        assert type(restored) is type(value)
        assert restored == value
        assert copy.copy(value) is not None
        assert copy.deepcopy(value) is not None


def test_fixture_metadata_is_the_shared_frozen_mapping() -> None:
    from mintmed.simulation import mediation as simulation
    from mintmed import spec as spec_module
    from mintmed import types

    assert simulation._FrozenDict is types._FrozenDict
    assert spec_module._FrozenDict is types._FrozenDict
