"""Contract and numerical tests for the shared g-formula engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mintmed.models import fit_node
from mintmed.simulation import sample_fixture
from mintmed.spec import Family, estimate_plan
from mintmed.types import AnalysisStatus, RegimeMeans


def _fixture(name: str, n: int = 160):
    fixture = sample_fixture(name, n, np.random.default_rng(20260920))
    return fixture, estimate_plan(fixture.data, fixture.spec)


def test_public_contracts_and_common_draws_are_immutable():
    from mintmed.gformula import CommonDraws, FittedSystem, GFormulaError

    draws = CommonDraws.from_seed(seed=17, draw_count=32, mediator_count=2)
    assert draws.uniforms.shape == (32, 2)
    assert draws.normals.shape == (32, 2)
    assert draws.for_rows(5, 0, Family.BERNOULLI).shape == (5, 32)
    assert draws.for_rows(5, 1, Family.GAUSSIAN).shape == (5, 32)
    assert np.array_equal(
        draws.uniforms,
        CommonDraws.from_seed(seed=17, draw_count=32, mediator_count=2).uniforms,
    )
    assert not draws.uniforms.flags.writeable
    assert not draws.normals.flags.writeable
    with pytest.raises(ValueError):
        CommonDraws.from_seed(seed=17, draw_count=0, mediator_count=2)
    with pytest.raises(ValueError):
        draws.for_rows(5, 2, Family.BERNOULLI)
    assert GFormulaError.__name__ == "GFormulaError"
    assert FittedSystem.__name__ == "FittedSystem"


def test_fitted_system_preserves_retained_rows_and_declared_order():
    from mintmed.gformula import fit_system

    fixture, plan = _fixture("serial_three", 120)
    data = fixture.data.copy()
    data.index = np.arange(1000, 1000 + len(data))
    plan = estimate_plan(data, fixture.spec)
    fitted = fit_system(data, plan)
    assert fitted.status is AnalysisStatus.OK
    assert tuple(node.response for node in fitted.nodes) == tuple(
        node.response for node in plan.nodes
    )
    assert tuple(node.response for node in fitted.mediator_nodes) == tuple(
        node.response for node in plan.nodes[:-1]
    )
    assert fitted.outcome_node.response == plan.nodes[-1].response
    assert plan.retained_row_indices == tuple(data.index)


def test_regime_means_result_contract_is_response_scale():
    assert RegimeMeans(1.0, 2.0, 4.0).total_effect == 3.0
