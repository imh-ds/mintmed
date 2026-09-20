"""Contract tests for compiled mediation plans and data preflight."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mintmed.spec import (
    AnalysisPlan,
    AnalysisStatus,
    ComputationSpec,
    CompiledNodePlan,
    ContrastSpec,
    DataValidationError,
    Family,
    NodeSpec,
    Role,
    TemplateSpec,
    TermKind,
    TermSpec,
    UnsupportedAnalysisError,
    VariableSpec,
    compile_template,
    estimate_plan,
)


@pytest.fixture
def valid_spec():
    exposure = VariableSpec("condition", Role.EXPOSURE, "binary", levels=(0, 1))
    outcome = VariableSpec("distress", Role.OUTCOME, "continuous")
    efficacy = VariableSpec("efficacy", Role.MEDIATOR, "continuous")
    coping = VariableSpec("coping", Role.MEDIATOR, "continuous")
    baseline = VariableSpec("baseline_distress", Role.COVARIATE, "continuous")
    participant_id = VariableSpec("participant_id", Role.PARTICIPANT_ID, "categorical")
    node_terms = (
        TermSpec("condition", TermKind.CATEGORICAL),
        TermSpec("baseline_distress", TermKind.LINEAR),
    )
    return compile_template(
        TemplateSpec(
            exposure=exposure,
            outcome=outcome,
            mediators=(efficacy, coping),
            nodes=(
                NodeSpec("coping", Family.GAUSSIAN, True, node_terms + (TermSpec("efficacy", TermKind.LINEAR),)),
                NodeSpec("efficacy", Family.GAUSSIAN, True, node_terms),
                NodeSpec(
                    "distress",
                    Family.GAUSSIAN,
                    True,
                    node_terms + (TermSpec("coping", TermKind.LINEAR), TermSpec("efficacy", TermKind.LINEAR)),
                ),
            ),
            baseline=(baseline,),
            participant_id=participant_id,
            scientific_edges=(
                ("condition", "coping"),
                ("condition", "efficacy"),
                ("coping", "distress"),
                ("efficacy", "distress"),
            ),
            mediator_order=("efficacy", "coping"),
            contrast=ContrastSpec(reference=0, comparison=1),
            computation=ComputationSpec(seed=20260919, bootstrap=0, integration_draws=8),
        )
    )


@pytest.fixture
def valid_frame():
    return pd.DataFrame(
        {
            "participant_id": ["p0", "p1", "p2", "p3", "p4", "p5"],
            "condition": [0, 1, 0, 1, 0, 1],
            "baseline_distress": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
            "efficacy": [0.1, 0.7, 0.2, 0.8, 0.3, 0.9],
            "coping": [0.2, 0.8, 0.3, 0.9, 0.4, 1.0],
            "distress": [1.0, 1.8, 1.1, 1.9, 1.2, 2.0],
        },
        index=[10, 11, 12, 13, 14, 15],
    )


@pytest.fixture
def continuous_spec(valid_spec):
    dose = VariableSpec("dose", Role.EXPOSURE, "continuous")
    nodes = tuple(
        replace(
            node,
            terms=tuple(
                replace(term, variable="dose", kind=TermKind.LINEAR)
                if term.variable == "condition"
                else term
                for term in node.terms
            ),
        )
        for node in valid_spec.nodes
    )
    edges = tuple(
        ("dose" if source == "condition" else source, target)
        for source, target in valid_spec.scientific.edges
    )
    return replace(
        valid_spec,
        exposure=dose,
        nodes=nodes,
        scientific=replace(valid_spec.scientific, edges=edges),
        contrast=ContrastSpec(reference=0.0, comparison=2.5),
    )


@pytest.fixture
def continuous_frame(valid_frame):
    frame = valid_frame.rename(columns={"condition": "dose"}).copy()
    frame["dose"] = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    return frame


def test_task4_public_plan_contract_is_importable() -> None:
    assert AnalysisPlan is not None
    assert CompiledNodePlan is not None
    assert DataValidationError is not None
    assert UnsupportedAnalysisError is not None
    assert estimate_plan is not None


def test_parallel_nuisance_predictor_is_not_a_scientific_parent(valid_frame, valid_spec) -> None:
    plan = estimate_plan(valid_frame, valid_spec)
    coping = next(node for node in plan.nodes if node.response == "coping")

    assert coping.scientific_parents == ("condition",)
    assert coping.factorization_predictors == (
        "condition",
        "baseline_distress",
        "efficacy",
    )
    assert "efficacy" not in coping.scientific_parents
    assert coping.category_levels["condition"] == (0, 1)


def test_explicit_terms_are_not_augmented(valid_frame, valid_spec) -> None:
    plan = estimate_plan(valid_frame, valid_spec)
    outcome = next(node for node in plan.nodes if node.response == "distress")

    assert tuple(term.variable for term in outcome.terms) == (
        "condition",
        "baseline_distress",
        "coping",
        "efficacy",
    )
    assert outcome.factorization_predictors == (
        "condition",
        "baseline_distress",
        "coping",
        "efficacy",
    )


def test_nodes_are_ordered_by_mediator_order_then_outcome(valid_frame, valid_spec) -> None:
    plan = estimate_plan(valid_frame, valid_spec)

    assert tuple(node.response for node in plan.nodes) == (
        "efficacy",
        "coping",
        "distress",
    )


def test_missing_required_column_is_typed(valid_frame, valid_spec) -> None:
    frame = valid_frame.drop(columns=["efficacy"])

    with pytest.raises(DataValidationError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "missing_columns"
    assert caught.value.path == "data.columns"
    assert "efficacy" in caught.value.message


def test_duplicate_dataframe_columns_are_rejected(valid_frame, valid_spec) -> None:
    duplicated = valid_frame.copy()
    duplicated.insert(
        duplicated.columns.get_loc("coping"),
        "coping",
        duplicated["coping"],
        allow_duplicates=True,
    )

    with pytest.raises(DataValidationError) as caught:
        estimate_plan(duplicated, valid_spec)

    assert caught.value.code == "duplicate_columns"


def test_missing_error_reports_counts(valid_frame, valid_spec) -> None:
    frame = valid_frame.copy()
    frame.loc[12, "coping"] = np.nan

    with pytest.raises(DataValidationError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "missing_values"
    assert "coping" in caught.value.message


def test_complete_case_records_original_and_retained_rows(valid_frame, valid_spec) -> None:
    complete_case_spec = replace(valid_spec, missing="complete_case")
    frame = valid_frame.copy()
    frame.loc[12, "coping"] = np.nan
    frame.loc[14, "distress"] = np.nan

    plan = estimate_plan(frame, complete_case_spec)

    assert plan.original_row_count == len(frame)
    assert plan.retained_row_count == len(frame) - 2
    assert plan.retained_row_indices == (10, 11, 13, 15)
    assert plan.excluded_row_indices == (12, 14)
    assert plan.diagnostics["missing"]["excluded_rows"] == 2


@pytest.mark.parametrize("column", ["condition", "baseline_distress", "distress"])
def test_nonfinite_values_are_never_silently_dropped(valid_frame, valid_spec, column) -> None:
    frame = valid_frame.copy()
    frame[column] = frame[column].astype(float)
    frame.loc[12, column] = np.inf

    with pytest.raises(DataValidationError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "nonfinite_values"


def test_nonbinary_values_are_rejected(valid_frame, valid_spec) -> None:
    frame = valid_frame.copy()
    frame.loc[12, "condition"] = 2

    with pytest.raises(DataValidationError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "invalid_binary_values"


def test_tied_continuous_scores_pass(valid_frame, valid_spec) -> None:
    frame = valid_frame.copy()
    frame["baseline_distress"] = [0.0, 0.0, 1.0, 1.0, 2.0, 2.0]

    plan = estimate_plan(frame, valid_spec)

    assert plan.retained_row_count == len(frame)


def test_categorical_exposure_requires_observed_counterfactual_support(valid_frame, valid_spec) -> None:
    frame = valid_frame.copy()
    frame["condition"] = 0

    with pytest.raises(UnsupportedAnalysisError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "unsupported_extrapolation"
    assert caught.value.path == "contrast.comparison"


def test_continuous_exposure_outside_observed_range_is_unsupported(
    continuous_frame, continuous_spec
) -> None:
    out_of_range = replace(
        continuous_spec,
        contrast=replace(continuous_spec.contrast, reference=-1.0),
    )

    with pytest.raises(UnsupportedAnalysisError) as caught:
        estimate_plan(continuous_frame, out_of_range)

    assert caught.value.code == "unsupported_extrapolation"
    assert caught.value.path == "contrast.reference"


def test_fixed_continuous_moderator_requires_observed_range(valid_frame, valid_spec) -> None:
    moderator = VariableSpec("moderator", Role.MODERATOR, "continuous")
    moderated_spec = replace(
        valid_spec,
        moderators=(moderator,),
        contrast=replace(valid_spec.contrast, moderator_values={"moderator": 99.0}),
    )
    frame = valid_frame.copy()
    frame["moderator"] = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]

    with pytest.raises(UnsupportedAnalysisError) as caught:
        estimate_plan(frame, moderated_spec)

    assert caught.value.code == "unsupported_extrapolation"
    assert "moderator" in caught.value.message


def test_repeated_participant_ids_are_not_independent_rows(valid_frame, valid_spec) -> None:
    frame = valid_frame.copy()
    frame.loc[13, "participant_id"] = frame.loc[12, "participant_id"]

    with pytest.raises(UnsupportedAnalysisError) as caught:
        estimate_plan(frame, valid_spec)

    assert caught.value.code == "repeated_rows"
    assert caught.value.path == "participant_id"


def test_sparse_binary_events_are_warnings_not_estimator_switches(valid_frame, valid_spec) -> None:
    binary_outcome = VariableSpec(
        "distress", Role.OUTCOME, "binary", levels=(0, 1), family=Family.BERNOULLI
    )
    binary_nodes = tuple(
        replace(node, family=Family.BERNOULLI)
        if node.response == "distress"
        else node
        for node in valid_spec.nodes
    )
    binary_spec = replace(valid_spec, outcome=binary_outcome, nodes=binary_nodes)
    frame = valid_frame.copy()
    frame["distress"] = [1, 0, 1, 1, 0, 0]

    plan = estimate_plan(frame, binary_spec)

    sparse = [issue for issue in plan.warnings if issue.code == "sparse_binary_events"]
    assert sparse
    assert all(issue.status is AnalysisStatus.WARNING for issue in sparse)
    assert all(node.family is Family.BERNOULLI for node in plan.nodes if node.response == "distress")


def test_hashes_are_deterministic_and_runtime_path_independent(valid_frame, valid_spec) -> None:
    first = estimate_plan(valid_frame, valid_spec)
    second = estimate_plan(valid_frame.copy(deep=True), valid_spec)

    assert first.specification_hash == second.specification_hash
    assert first.analysis_hash == second.analysis_hash


def test_analysis_hash_includes_population_contrast_and_seed(valid_frame, valid_spec) -> None:
    baseline = estimate_plan(valid_frame, valid_spec)
    changed_seed = estimate_plan(
        valid_frame,
        replace(valid_spec, computation=replace(valid_spec.computation, seed=7)),
    )
    changed_contrast = estimate_plan(
        valid_frame,
        replace(valid_spec, contrast=replace(valid_spec.contrast, reference=1, comparison=0)),
    )

    assert baseline.analysis_hash != changed_seed.analysis_hash
    assert baseline.analysis_hash != changed_contrast.analysis_hash


def test_runtime_limits_do_not_change_analysis_hash(valid_frame, valid_spec) -> None:
    short = estimate_plan(
        valid_frame,
        replace(valid_spec, computation=replace(valid_spec.computation, max_seconds=1)),
    )
    long = estimate_plan(
        valid_frame,
        replace(valid_spec, computation=replace(valid_spec.computation, max_seconds=9999)),
    )

    assert short.analysis_hash == long.analysis_hash


def test_plan_summary_contains_population_graph_and_warnings(valid_frame, valid_spec) -> None:
    plan = estimate_plan(valid_frame, valid_spec)
    summary = plan.summary()

    assert "Analysis population:" in summary
    assert "Node order: efficacy -> coping -> distress" in summary
    assert "condition->coping" in summary
    assert "Factorization predictors:" in summary
    assert "Warnings: small_sample" in summary
    assert "p0" not in summary
