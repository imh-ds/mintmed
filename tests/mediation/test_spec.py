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


def test_bootstrap_mode_defaults_and_is_canonicalized(tmp_path: Path) -> None:
    value = _valid_mapping()
    spec = load_model_spec(_write_spec(tmp_path, value))

    assert spec.computation.bootstrap_mode == "standard"
    assert '"bootstrap_mode":"standard"' in spec.canonical_json()

    value["computation"]["bootstrap_mode"] = "quick_diagnostic"  # type: ignore[index]
    quick = load_model_spec(_write_spec(tmp_path, value))
    assert quick.computation.bootstrap_mode == "quick_diagnostic"
    assert quick.canonical_json() != spec.canonical_json()


def test_invalid_bootstrap_mode_has_a_typed_error(tmp_path: Path) -> None:
    value = _valid_mapping()
    value["computation"]["bootstrap_mode"] = "fast"  # type: ignore[index]

    caught = _error_for(tmp_path, value)

    assert caught.code == "invalid_computation"
    assert caught.path == "computation.bootstrap_mode"


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


def _template_from(spec: ModelSpec, **changes: object) -> TemplateSpec:
    fields: dict[str, object] = {
        "exposure": spec.exposure,
        "outcome": spec.outcome,
        "mediators": spec.mediators,
        "nodes": spec.nodes,
        "contrast": spec.contrast,
        "computation": spec.computation,
        "baseline": spec.baseline,
        "moderators": spec.moderators,
        "scientific_edges": spec.scientific.edges,
        "mediator_order": spec.scientific.mediator_order,
        "arrangement": spec.scientific.arrangement,
        "missing": spec.missing,
        "interpretation": spec.interpretation,
        "schema_version": spec.schema_version,
        "participant_id": spec.participant_id,
    }
    fields.update(changes)
    return TemplateSpec(**fields)


def _mediator(observed_type: str, family: Family, levels: tuple[object, ...] = ()) -> VariableSpec:
    return VariableSpec("coping", Role.MEDIATOR, observed_type, levels=levels, family=family)


def _set_path(mapping: dict, path: tuple[object, ...], value: object) -> None:
    target = mapping
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


_PARITY_CASES = {
    "ordinal_mediator": (
        [(("mediators", 0, "type"), "ordinal")],
        lambda spec: {"mediators": (_mediator("ordinal", Family.GAUSSIAN), spec.mediators[1])},
        "unsupported_observed_type",
    ),
    "count_mediator": (
        [(("mediators", 0, "type"), "count")],
        lambda spec: {"mediators": (_mediator("count", Family.GAUSSIAN), spec.mediators[1])},
        "unsupported_observed_type",
    ),
    "unknown_mediator_type": (
        [(("mediators", 0, "type"), "banana")],
        lambda spec: {"mediators": (_mediator("banana", Family.GAUSSIAN), spec.mediators[1])},
        "unsupported_observed_type",
    ),
    "bernoulli_on_continuous_mediator": (
        [(("mediators", 0, "family"), "bernoulli")],
        lambda spec: {"mediators": (_mediator("continuous", Family.BERNOULLI), spec.mediators[1])},
        "family_type_mismatch",
    ),
    "bernoulli_mediator_bad_levels": (
        [(("mediators", 0, "family"), "bernoulli"), (("mediators", 0, "type"), "binary"), (("mediators", 0, "levels"), [1, 2])],
        lambda spec: {"mediators": (_mediator("binary", Family.BERNOULLI, (1, 2)), spec.mediators[1])},
        "invalid_binary_levels",
    ),
    "participant_id_not_categorical": (
        [(("participant_id",), {"name": "pid", "type": "continuous"})],
        lambda spec: {"participant_id": VariableSpec("pid", Role.PARTICIPANT_ID, "continuous")},
        "invalid_participant_id",
    ),
    "unsupported_exposure_type": (
        [(("exposure", "type"), "count")],
        lambda spec: {"exposure": VariableSpec("condition", Role.EXPOSURE, "count", levels=(0, 1))},
        "unsupported_exposure_type",
    ),
    "binary_exposure_levels_not_0_1": (
        [(("exposure", "levels"), [1, 2]), (("exposure", "reference"), 1), (("exposure", "comparison"), 2)],
        lambda spec: {"exposure": VariableSpec("condition", Role.EXPOSURE, "binary", levels=(1, 2))},
        "invalid_binary_levels",
    ),
    "continuous_exposure_with_levels": (
        [(("exposure", "type"), "continuous")],
        lambda spec: {"exposure": VariableSpec("condition", Role.EXPOSURE, "continuous", levels=(0, 1))},
        "invalid_exposure_levels",
    ),
    "binary_covariate_without_levels": (
        [(("baseline", 0, "type"), "binary")],
        lambda spec: {"baseline": (VariableSpec("baseline_distress", Role.COVARIATE, "binary"),)},
        "missing_levels",
    ),
}


@pytest.mark.parametrize("case", sorted(_PARITY_CASES))
def test_yaml_and_template_reject_invalid_variables_with_the_same_code(tmp_path: Path, case: str) -> None:
    yaml_changes, template_changes, code = _PARITY_CASES[case]
    value = _valid_mapping()
    for path, replacement in yaml_changes:
        _set_path(value, path, replacement)
    base = load_model_spec(_write_spec(tmp_path, _valid_mapping()))

    yaml_error = _error_for(tmp_path, value)
    with pytest.raises(SpecValidationError) as caught:
        compile_template(_template_from(base, **template_changes(base)))

    assert yaml_error.code == code
    assert caught.value.code == code
    assert caught.value.path == yaml_error.path


def test_template_round_trip_of_a_valid_yaml_spec_compiles_identically(tmp_path: Path) -> None:
    base = load_model_spec(_write_spec(tmp_path, _valid_mapping()))

    assert compile_template(_template_from(base)) == base


def _moderated_mapping(**contrast: object) -> dict[str, object]:
    value = _valid_mapping()
    value["moderators"] = [{"name": "age", "type": "continuous"}]
    for node in ("coping", "distress"):
        value["models"][node]["terms"].append({"variable": "age", "basis": "linear"})
    value["models"]["coping"]["interactions"] = [{"left": "age", "right": "condition"}]
    value["contrast"] = {"moderator_values": {"age": 40.0}, **contrast}
    return value


def test_moderator_evaluation_values_are_parsed_in_declared_order(tmp_path: Path) -> None:
    spec = load_model_spec(
        _write_spec(tmp_path, _moderated_mapping(moderator_evaluation={"age": [30.0, 40.0, 50.0]}))
    )

    assert spec.contrast.moderator_values == {"age": 40.0}
    assert spec.contrast.moderator_evaluation == {"age": (30.0, 40.0, 50.0)}
    assert compile_template(_template_from(spec)) == spec


def test_absent_moderator_evaluation_keeps_the_canonical_form_unchanged(tmp_path: Path) -> None:
    spec = load_model_spec(_write_spec(tmp_path, _moderated_mapping()))

    assert spec.contrast.moderator_evaluation == {}
    assert "moderator_evaluation" not in spec.to_canonical_dict()["contrast"]


@pytest.mark.parametrize(
    ("evaluation", "code"),
    [
        ({"unknown": [1.0]}, "unknown_moderator"),
        ({"age": []}, "invalid_moderator_evaluation"),
        ({"age": [30.0, 30.0]}, "invalid_moderator_evaluation"),
        ({"age": ["old"]}, "invalid_moderator_evaluation"),
        ({"age": [float("inf")]}, "invalid_moderator_evaluation"),
    ],
)
def test_invalid_moderator_evaluation_is_rejected_by_yaml_and_templates(
    tmp_path: Path, evaluation: dict[str, list[object]], code: str
) -> None:
    from dataclasses import replace

    error = _error_for(tmp_path, _moderated_mapping(moderator_evaluation=evaluation))
    base = load_model_spec(_write_spec(tmp_path, _moderated_mapping()))
    contrast = replace(base.contrast, moderator_evaluation={name: tuple(values) for name, values in evaluation.items()})

    with pytest.raises(SpecValidationError) as caught:
        compile_template(_template_from(base, contrast=contrast))

    assert error.code == code
    assert caught.value.code == code


def test_moderator_evaluation_requires_a_baseline_value(tmp_path: Path) -> None:
    value = _moderated_mapping(moderator_evaluation={"age": [30.0, 50.0]})
    value["contrast"]["moderator_values"] = {}

    assert _error_for(tmp_path, value).code == "missing_moderator_baseline"


def test_categorical_moderator_evaluation_values_must_be_declared_levels(tmp_path: Path) -> None:
    value = _moderated_mapping(moderator_evaluation={"age": [0, 2]})
    value["moderators"] = [{"name": "age", "type": "binary", "levels": [0, 1]}]
    value["contrast"]["moderator_values"] = {"age": 0}

    assert _error_for(tmp_path, value).code == "invalid_moderator_value"


@pytest.mark.parametrize("draws", [8, 128, 1000, 8192])
def test_unsupported_integration_draw_budgets_are_rejected_on_both_paths(tmp_path: Path, draws: int) -> None:
    from dataclasses import replace

    value = _valid_mapping()
    value["computation"]["integration_draws"] = draws
    error = _error_for(tmp_path, value)
    base = load_model_spec(_write_spec(tmp_path, _valid_mapping()))

    with pytest.raises(SpecValidationError) as caught:
        compile_template(
            _template_from(base, computation=replace(base.computation, integration_draws=draws))
        )

    for raised in (error, caught.value):
        assert raised.code == "invalid_computation"
        assert raised.path == "computation.integration_draws"


@pytest.mark.parametrize("draws", [256, 512, 1024, 2048, 4096])
def test_supported_integration_draw_budgets_are_accepted(tmp_path: Path, draws: int) -> None:
    value = _valid_mapping()
    value["computation"]["integration_draws"] = draws

    assert load_model_spec(_write_spec(tmp_path, value)).computation.integration_draws == draws
