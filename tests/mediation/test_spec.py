"""Contract tests for strict mediation specification loading."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from mintmed.spec import (
    ComputationSpec,
    ContrastSpec,
    Family,
    ModelSpec,
    NodeSpec,
    Role,
    ScientificModel,
    SpecValidationError,
    TemplateSpec,
    TermKind,
    TermSpec,
    VariableSpec,
    compile_template,
    load_model_spec,
)


def _valid_mapping() -> dict[str, object]:
    return {
        "schema_version": 1,
        "exposure": {
            "name": "condition",
            "type": "binary",
            "levels": [0, 1],
            "reference": 0,
            "comparison": 1,
        },
        "outcome": {
            "name": "distress",
            "type": "continuous",
            "family": "gaussian",
        },
        "mediators": [
            {"name": "coping", "type": "continuous", "family": "gaussian"},
            {"name": "efficacy", "type": "continuous", "family": "gaussian"},
        ],
        "arrangement": "parallel",
        "mediator_order": ["coping", "efficacy"],
        "baseline": [{"name": "baseline_distress", "type": "continuous"}],
        "scientific_edges": [
            ["condition", "coping"],
            ["condition", "efficacy"],
            ["coping", "distress"],
            ["efficacy", "distress"],
        ],
        "models": {
            "coping": {
                "intercept": True,
                "terms": [
                    {"variable": "condition", "basis": "categorical"},
                    {"variable": "baseline_distress", "basis": "linear"},
                ],
                "interactions": [],
            },
            "efficacy": {
                "intercept": True,
                "terms": [
                    {"variable": "condition", "basis": "categorical"},
                    {"variable": "baseline_distress", "basis": "linear"},
                ],
                "interactions": [],
            },
            "distress": {
                "intercept": True,
                "terms": [
                    {"variable": "condition", "basis": "categorical"},
                    {"variable": "baseline_distress", "basis": "linear"},
                    {"variable": "coping", "basis": "linear"},
                    {"variable": "efficacy", "basis": "natural_spline", "df": 3},
                ],
                "interactions": [],
            },
        },
        "interpretation": "model_standardized",
        "missing": "error",
        "computation": {
            "seed": 20260919,
            "bootstrap": 999,
            "integration_draws": 256,
            "integration_tolerance": 1e-8,
            "max_seconds": 180,
            "memory_budget_mb": 2048,
            "information": False,
        },
    }


def _write_spec(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "model.yml"
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def _error_for(tmp_path: Path, value: object) -> SpecValidationError:
    with pytest.raises(SpecValidationError) as caught:
        load_model_spec(_write_spec(tmp_path, value))
    return caught.value


def test_valid_yaml_loads_to_typed_model_spec(tmp_path: Path) -> None:
    spec = load_model_spec(_write_spec(tmp_path, _valid_mapping()))

    assert isinstance(spec, ModelSpec)
    assert spec.exposure.name == "condition"
    assert spec.exposure.role is Role.EXPOSURE
    assert spec.scientific.mediator_order == ("coping", "efficacy")
    assert spec.contrast.reference == 0
    assert spec.contrast.comparison == 1
    assert spec.nodes[-1].family is Family.GAUSSIAN
    assert spec.nodes[-1].terms[-1].kind is TermKind.NATURAL_SPLINE
    assert spec.nodes[-1].terms[-1].df == 3
    assert spec.computation.seed == 20260919


def test_template_compilation_produces_a_valid_equivalent_shape() -> None:
    template = TemplateSpec(
        exposure=VariableSpec(
            name="condition",
            role=Role.EXPOSURE,
            observed_type="binary",
            levels=(0, 1),
        ),
        outcome=VariableSpec(
            name="distress",
            role=Role.OUTCOME,
            observed_type="continuous",
        ),
        mediators=(
            VariableSpec("coping", Role.MEDIATOR, "continuous"),
            VariableSpec("efficacy", Role.MEDIATOR, "continuous"),
        ),
        baseline=(VariableSpec("baseline_distress", Role.COVARIATE, "continuous"),),
        scientific_edges=(
            ("condition", "coping"),
            ("condition", "efficacy"),
            ("coping", "distress"),
            ("efficacy", "distress"),
        ),
        mediator_order=("coping", "efficacy"),
        nodes=(
            NodeSpec(
                response="coping",
                family=Family.GAUSSIAN,
                intercept=True,
                terms=(
                    TermSpec("condition", TermKind.CATEGORICAL),
                    TermSpec("baseline_distress", TermKind.LINEAR),
                ),
            ),
            NodeSpec(
                response="efficacy",
                family=Family.GAUSSIAN,
                intercept=True,
                terms=(
                    TermSpec("condition", TermKind.CATEGORICAL),
                    TermSpec("baseline_distress", TermKind.LINEAR),
                ),
            ),
            NodeSpec(
                response="distress",
                family=Family.GAUSSIAN,
                intercept=True,
                terms=(
                    TermSpec("condition", TermKind.CATEGORICAL),
                    TermSpec("baseline_distress", TermKind.LINEAR),
                    TermSpec("coping", TermKind.LINEAR),
                    TermSpec("efficacy", TermKind.NATURAL_SPLINE, df=3),
                ),
            ),
        ),
        contrast=ContrastSpec(reference=0, comparison=1),
        computation=ComputationSpec(
            seed=20260919,
            bootstrap=999,
            integration_draws=256,
            integration_tolerance=1e-8,
            max_seconds=180,
            memory_budget_mb=2048,
        ),
    )

    spec = compile_template(template)

    assert spec.exposure == template.exposure
    assert spec.outcome == template.outcome
    assert spec.mediators == template.mediators
    assert spec.nodes == template.nodes
    assert spec.scientific.mediator_order == template.mediator_order
    assert spec.contrast == template.contrast
    assert spec.computation == template.computation


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.update({"unrecognized": True}), "unknown_key"),
        (
            lambda value: value["baseline"].append(
                {"name": "condition", "type": "continuous"}
            ),
            "duplicate_variable",
        ),
        (lambda value: value.pop("exposure"), "missing_exposure"),
        (lambda value: value.pop("outcome"), "missing_outcome"),
        (lambda value: value.update({"mediators": []}), "mediator_count"),
        (
            lambda value: value["mediators"].extend(
                [
                    {"name": "m3", "type": "continuous", "family": "gaussian"},
                    {"name": "m4", "type": "continuous", "family": "gaussian"},
                    {"name": "m5", "type": "continuous", "family": "gaussian"},
                ]
            ),
            "mediator_count",
        ),
        (lambda value: value.pop("mediator_order"), "missing_mediator_order"),
        (
            lambda value: value["models"]["coping"]["terms"].append(
                {"variable": "not_declared", "basis": "linear"}
            ),
            "unknown_predictor",
        ),
        (lambda value: value["models"]["coping"].pop("intercept"), "missing_intercept"),
        (
            lambda value: value["scientific_edges"].extend(
                [["coping", "efficacy"], ["efficacy", "coping"]]
            ),
            "cyclic_graph",
        ),
        (
            lambda value: value["outcome"].update({"family": "poisson"}),
            "invalid_family",
        ),
        (
            lambda value: value["outcome"].update(
                {"family": "bernoulli", "type": "binary", "levels": [1, 2]}
            ),
            "invalid_binary_levels",
        ),
        (
            lambda value: value["models"]["distress"]["terms"][-1].update({"df": 4}),
            "invalid_spline_df",
        ),
        (
            lambda value: value["models"]["coping"]["interactions"].append(
                {"left": "condition", "right": "efficacy"}
            ),
            "interaction_main_effect",
        ),
        (
            lambda value: value["mediators"][0].update({"type": "ordinal"}),
            "unsupported_observed_type",
        ),
        (
            lambda value: value["exposure"].update({"reference": 1, "comparison": 1}),
            "malformed_contrast",
        ),
    ],
)
def test_invalid_specifications_have_stable_codes(
    tmp_path: Path, mutate, code: str
) -> None:
    value = _valid_mapping()
    mutate(value)

    error = _error_for(tmp_path, value)

    assert error.code == code
    assert error.path
    assert str(error).startswith(f"{code} at ")


def test_future_mediator_predictor_is_rejected_without_reordering(tmp_path: Path) -> None:
    value = _valid_mapping()
    value["models"]["coping"]["terms"].append(  # type: ignore[index]
        {"variable": "efficacy", "basis": "linear"}
    )

    error = _error_for(tmp_path, value)

    assert error.code == "invalid_predictor_order"
    assert error.path == "models.coping.terms[2].variable"


def test_formula_like_term_text_is_not_evaluated(tmp_path: Path) -> None:
    value = _valid_mapping()
    value["models"]["coping"]["terms"][0]["basis"] = "condition + efficacy"  # type: ignore[index]

    error = _error_for(tmp_path, value)

    assert error.code == "invalid_term_kind"
    assert "condition + efficacy" in error.message


def test_malformed_yaml_is_wrapped_in_spec_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.yml"
    path.write_text("exposure: [", encoding="utf-8")

    with pytest.raises(SpecValidationError) as caught:
        load_model_spec(path)

    assert caught.value.code == "malformed_yaml"
    assert caught.value.path == "$"


def test_spec_objects_are_immutable_and_asdict_serializable(tmp_path: Path) -> None:
    spec = load_model_spec(_write_spec(tmp_path, _valid_mapping()))

    with pytest.raises((AttributeError, TypeError)):
        spec.exposure.name = "changed"  # type: ignore[misc]

    serialized = asdict(spec)

    assert serialized["exposure"]["name"] == "condition"
    assert serialized["scientific"]["mediator_order"] == ("coping", "efficacy")


def test_continuous_exposure_requires_explicit_values_without_levels(tmp_path: Path) -> None:
    value = _valid_mapping()
    value["exposure"] = {
        "name": "dose",
        "type": "continuous",
        "reference": 0.0,
        "comparison": 1.5,
    }
    value["participant_id"] = {"name": "participant_id", "type": "categorical"}
    value["scientific_edges"] = [
        ["dose", "coping"],
        ["dose", "efficacy"],
        ["coping", "distress"],
        ["efficacy", "distress"],
    ]
    for model in value["models"].values():  # type: ignore[union-attr]
        for term in model["terms"]:  # type: ignore[index]
            if term["variable"] == "condition":
                term["variable"] = "dose"
                term["basis"] = "linear"

    spec = load_model_spec(_write_spec(tmp_path, value))

    assert spec.exposure.observed_type == "continuous"
    assert spec.exposure.levels == ()
    assert spec.contrast.reference == 0.0
    assert spec.participant_id is not None
    assert spec.participant_id.name == "participant_id"
    assert spec.participant_id.role is Role.PARTICIPANT_ID


def test_continuous_exposure_without_contrast_is_rejected(tmp_path: Path) -> None:
    value = _valid_mapping()
    value["exposure"] = {"name": "dose", "type": "continuous", "levels": []}

    error = _error_for(tmp_path, value)

    assert error.code == "missing_key"
    assert error.path in {"exposure.reference", "exposure.comparison"}
