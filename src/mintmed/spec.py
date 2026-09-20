"""Strict, typed model specifications for the Mintmed mediation pipeline.

The YAML loader in this module is intentionally declarative.  A specification
contains structured terms and graph edges; it never contains an executable
formula string.  Validation happens before a :class:`ModelSpec` is returned so
downstream fitting code can rely on one explicit schema.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, TypeVar

import yaml

from .types import AnalysisStatus, Issue


class Role(str, Enum):
    """Declared role of an observed variable."""

    EXPOSURE = "exposure"
    MEDIATOR = "mediator"
    OUTCOME = "outcome"
    COVARIATE = "covariate"
    MODERATOR = "moderator"
    PARTICIPANT_ID = "participant_id"


class Family(str, Enum):
    """Supported endogenous response families."""

    GAUSSIAN = "gaussian"
    BERNOULLI = "bernoulli"


class TermKind(str, Enum):
    """Supported structured basis terms."""

    LINEAR = "linear"
    QUADRATIC = "quadratic"
    NATURAL_SPLINE = "natural_spline"
    CATEGORICAL = "categorical"


class SpecValidationError(ValueError):
    """Stable validation failure with a machine-readable code and path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")

    @property
    def status(self) -> AnalysisStatus:
        """Map specification rejection into the shared diagnostic vocabulary."""

        return AnalysisStatus.UNSUPPORTED

    def to_issue(self, node: str | None = None) -> Issue:
        """Convert the validation failure to a shared typed diagnostic."""

        return Issue(
            code=self.code,
            message=str(self),
            status=self.status,
            node=node,
        )


class _FrozenDict(dict[str, Any]):
    """Dict-compatible immutable mapping that remains ``dataclasses.asdict`` safe."""

    def __init__(self, value: Mapping[str, Any] | None = None) -> None:
        dict.__init__(self, value or {})

    @staticmethod
    def _read_only(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("mapping is read-only")

    __setitem__ = _read_only
    __delitem__ = _read_only
    clear = _read_only
    pop = _read_only
    popitem = _read_only
    setdefault = _read_only
    update = _read_only
    __ior__ = _read_only

    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenDict:
        return _FrozenDict(deepcopy(dict(self), memo))


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return _FrozenDict(value)


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """One explicitly declared observed variable."""

    name: str
    role: Role
    observed_type: str
    levels: tuple[Any, ...] = ()
    label: str | None = None
    family: Family | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _coerce_enum(self.role, Role, "role"))
        object.__setattr__(self, "levels", tuple(self.levels))
        if self.family is not None:
            object.__setattr__(self, "family", _coerce_enum(self.family, Family, "family"))


@dataclass(frozen=True, slots=True)
class TermSpec:
    """A structured predictor basis attached to one response node."""

    variable: str
    kind: TermKind
    df: int | None = None
    purpose: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _coerce_enum(self.kind, TermKind, "basis"))


@dataclass(frozen=True, slots=True)
class InteractionSpec:
    """A pairwise interaction between two declared main-effect variables."""

    left: str
    right: str


@dataclass(frozen=True, slots=True)
class ScientificModel:
    """Causal edge declarations and the separate factorization order."""

    edges: tuple[tuple[str, str], ...]
    mediator_order: tuple[str, ...]
    arrangement: str = "parallel"
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "edges", tuple(tuple(edge) for edge in self.edges))
        object.__setattr__(self, "mediator_order", tuple(self.mediator_order))


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """One endogenous model node and its explicit design terms."""

    response: str
    family: Family
    intercept: bool
    terms: tuple[TermSpec, ...] = ()
    interactions: tuple[InteractionSpec, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _coerce_enum(self.family, Family, "family"))
        object.__setattr__(self, "terms", tuple(self.terms))
        object.__setattr__(self, "interactions", tuple(self.interactions))


@dataclass(frozen=True, slots=True)
class ContrastSpec:
    """Exposure contrast and moderator regime values for standardization."""

    reference: Any
    comparison: Any
    moderator_values: Mapping[str, Any] = field(default_factory=dict)
    primary_effects: tuple[str, ...] = ("TE", "PNDE", "TNIE")
    interpretation: str = "model_standardized"

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator_values", _freeze_mapping(self.moderator_values))
        object.__setattr__(self, "primary_effects", tuple(self.primary_effects))


@dataclass(frozen=True, slots=True)
class ComputationSpec:
    """Deterministic computation and resource settings."""

    seed: int
    bootstrap: int
    integration_draws: int
    integration_tolerance: float = 1e-8
    max_seconds: int | None = None
    memory_budget_mb: int | None = None
    information: bool = False


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Complete validated explicit mediation model specification."""

    schema_version: int
    exposure: VariableSpec
    outcome: VariableSpec
    mediators: tuple[VariableSpec, ...]
    baseline: tuple[VariableSpec, ...]
    moderators: tuple[VariableSpec, ...]
    scientific: ScientificModel
    nodes: tuple[NodeSpec, ...]
    contrast: ContrastSpec
    missing: str
    interpretation: str
    computation: ComputationSpec

    def __post_init__(self) -> None:
        object.__setattr__(self, "mediators", tuple(self.mediators))
        object.__setattr__(self, "baseline", tuple(self.baseline))
        object.__setattr__(self, "moderators", tuple(self.moderators))
        object.__setattr__(self, "nodes", tuple(self.nodes))

    @property
    def node_by_response(self) -> Mapping[str, NodeSpec]:
        """Return a fresh read-only response-to-node index."""

        return _freeze_mapping({node.response: node for node in self.nodes})

    def to_canonical_dict(self) -> dict[str, Any]:
        """Serialize without paths in a stable, JSON-compatible structure."""

        return _canonicalize(asdict(self))

    def canonical_json(self) -> str:
        """Return canonical sorted JSON suitable as input to a specification hash."""

        return json.dumps(
            self.to_canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    """Typed template input accepted by :func:`compile_template`."""

    exposure: VariableSpec
    outcome: VariableSpec
    mediators: tuple[VariableSpec, ...]
    nodes: tuple[NodeSpec, ...]
    contrast: ContrastSpec
    computation: ComputationSpec
    baseline: tuple[VariableSpec, ...] = ()
    moderators: tuple[VariableSpec, ...] = ()
    scientific_edges: tuple[tuple[str, str], ...] = ()
    mediator_order: tuple[str, ...] = ()
    arrangement: str = "parallel"
    missing: str = "error"
    interpretation: str = "model_standardized"
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "mediators", tuple(self.mediators))
        object.__setattr__(self, "baseline", tuple(self.baseline))
        object.__setattr__(self, "moderators", tuple(self.moderators))
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(
            self,
            "scientific_edges",
            tuple(tuple(edge) for edge in self.scientific_edges),
        )
        object.__setattr__(self, "mediator_order", tuple(self.mediator_order))


_T = TypeVar("_T", bound=Enum)
_MISSING = object()
_SUPPORTED_TYPES = {"continuous", "binary", "categorical", "ordinal", "count"}
_ENDOGENOUS_UNSUPPORTED_TYPES = {"ordinal", "count"}
_INTERPRETATIONS = {"assumption_based_causal", "model_standardized"}
_MISSING_POLICIES = {"error", "complete_case"}
_ARRANGEMENTS = {"parallel", "sequential"}
_PRIMARY_EFFECTS = {"TE", "PNDE", "TNIE", "TNDE", "TNIE", "PDE"}


def load_model_spec(path: Path) -> ModelSpec:
    """Load and strictly validate a YAML model specification from ``path``."""

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SpecValidationError("file_error", str(path), str(exc)) from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecValidationError("malformed_yaml", "$", str(exc)) from exc

    try:
        template = _parse_template_mapping(raw)
        return compile_template(template)
    except SpecValidationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise SpecValidationError("malformed_spec", "$", str(exc)) from exc


def compile_template(template: TemplateSpec) -> ModelSpec:
    """Compile typed template inputs into the same validated shape as YAML."""

    if not isinstance(template, TemplateSpec):
        raise SpecValidationError(
            "invalid_template", "$", "compile_template expects a TemplateSpec"
        )

    try:
        spec = ModelSpec(
            schema_version=template.schema_version,
            exposure=template.exposure,
            outcome=template.outcome,
            mediators=template.mediators,
            baseline=template.baseline,
            moderators=template.moderators,
            scientific=ScientificModel(
                edges=template.scientific_edges,
                mediator_order=template.mediator_order,
                arrangement=template.arrangement,
            ),
            nodes=template.nodes,
            contrast=template.contrast,
            missing=template.missing,
            interpretation=template.interpretation,
            computation=template.computation,
        )
        _validate_model(spec)
        return spec
    except SpecValidationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise SpecValidationError("malformed_template", "$", str(exc)) from exc


def _parse_template_mapping(raw: Any) -> TemplateSpec:
    root = _mapping(raw, "$", "specification root")
    if "exposure" not in root:
        _fail("missing_exposure", "exposure", "exposure declaration is required")
    if "outcome" not in root:
        _fail("missing_outcome", "outcome", "outcome declaration is required")
    if "mediator_order" not in root:
        _fail("missing_mediator_order", "mediator_order", "mediator_order is required")
    _keys(
        root,
        {
            "schema_version",
            "exposure",
            "outcome",
            "mediators",
            "arrangement",
            "mediator_order",
            "baseline",
            "moderators",
            "scientific_edges",
            "models",
            "contrast",
            "interpretation",
            "missing",
            "computation",
        },
        "$",
        required={
            "schema_version",
            "mediators",
            "arrangement",
            "scientific_edges",
            "models",
            "missing",
            "computation",
        },
    )

    schema_version = _int(root["schema_version"], "schema_version", minimum=1)
    if schema_version != 1:
        _fail("unsupported_schema_version", "schema_version", "only schema_version 1 is supported")

    exposure, exposure_reference, exposure_comparison = _parse_exposure(
        root["exposure"], "exposure"
    )
    outcome = _parse_endogenous_variable(root["outcome"], Role.OUTCOME, "outcome")
    mediators = tuple(
        _parse_endogenous_variable(item, Role.MEDIATOR, f"mediators[{index}]")
        for index, item in enumerate(_sequence(root["mediators"], "mediators"))
    )
    if not 1 <= len(mediators) <= 4:
        _fail("mediator_count", "mediators", "declare between one and four mediators")

    baseline = tuple(
        _parse_variable(item, Role.COVARIATE, f"baseline[{index}]")
        for index, item in enumerate(
            _sequence(root.get("baseline", ()), "baseline")
        )
    )
    moderators = tuple(
        _parse_variable(item, Role.MODERATOR, f"moderators[{index}]")
        for index, item in enumerate(
            _sequence(root.get("moderators", ()), "moderators")
        )
    )
    _validate_unique_variables((exposure, outcome, *mediators, *baseline, *moderators))

    mediator_order = tuple(
        _string(item, f"mediator_order[{index}]")
        for index, item in enumerate(
            _sequence(root["mediator_order"], "mediator_order")
        )
    )
    arrangement = _string(root["arrangement"], "arrangement")
    if arrangement not in _ARRANGEMENTS:
        _fail("invalid_arrangement", "arrangement", f"unsupported arrangement {arrangement!r}")

    edges = _parse_edges(root["scientific_edges"])
    nodes = _parse_nodes(
        root["models"], exposure, outcome, mediators, baseline, moderators
    )
    contrast = _parse_contrast(
        root.get("contrast"),
        exposure,
        moderators,
        root.get("interpretation", "model_standardized"),
        exposure_reference,
        exposure_comparison,
    )
    interpretation = _string(
        root.get("interpretation", contrast.interpretation), "interpretation"
    )
    if interpretation not in _INTERPRETATIONS:
        _fail("invalid_interpretation", "interpretation", f"unsupported mode {interpretation!r}")
    missing = _string(root["missing"], "missing")
    if missing not in _MISSING_POLICIES:
        _fail("invalid_missing_policy", "missing", f"unsupported policy {missing!r}")
    computation = _parse_computation(root["computation"])

    return TemplateSpec(
        exposure=exposure,
        outcome=outcome,
        mediators=mediators,
        baseline=baseline,
        moderators=moderators,
        scientific_edges=edges,
        mediator_order=mediator_order,
        arrangement=arrangement,
        nodes=nodes,
        contrast=contrast,
        missing=missing,
        interpretation=interpretation,
        computation=computation,
        schema_version=schema_version,
    )


def _parse_exposure(value: Any, path: str) -> tuple[VariableSpec, Any, Any]:
    mapping = _mapping(value, path, "exposure")
    _keys(
        mapping,
        {"name", "type", "levels", "reference", "comparison", "label"},
        path,
        required={"name", "type", "levels", "reference", "comparison"},
    )
    variable = _parse_variable(
        {key: mapping[key] for key in ("name", "type", "levels", "label") if key in mapping},
        Role.EXPOSURE,
        path,
    )
    if variable.observed_type not in {"binary", "categorical", "continuous"}:
        _fail("unsupported_exposure_type", f"{path}.type", "exposure type is not supported")
    if not variable.levels:
        _fail("missing_levels", f"{path}.levels", "exposure levels must be explicit")
    if variable.observed_type == "binary" and tuple(variable.levels) != (0, 1):
        _fail("invalid_binary_levels", f"{path}.levels", "binary levels must be exactly [0, 1]")
    return variable, mapping["reference"], mapping["comparison"]


def _parse_endogenous_variable(value: Any, role: Role, path: str) -> VariableSpec:
    mapping = _mapping(value, path, role.value)
    _keys(mapping, {"name", "type", "family", "levels", "label"}, path, required={"name", "family"})
    family = _family(mapping["family"], f"{path}.family")
    observed_type = mapping.get("type", "binary" if family is Family.BERNOULLI else "continuous")
    variable = _parse_variable(
        {
            key: mapping[key]
            for key in ("name", "levels", "label")
            if key in mapping
        }
        | {"type": observed_type},
        role,
        path,
    )
    variable = VariableSpec(
        variable.name,
        variable.role,
        variable.observed_type,
        levels=variable.levels,
        label=variable.label,
        family=family,
    )
    if observed_type in _ENDOGENOUS_UNSUPPORTED_TYPES:
        _fail(
            "unsupported_observed_type",
            f"{path}.type",
            "ordinal and count endogenous responses are not supported",
        )
    if family is Family.BERNOULLI:
        if observed_type != "binary":
            _fail("family_type_mismatch", f"{path}.type", "Bernoulli responses must be binary")
        if variable.levels and tuple(variable.levels) != (0, 1):
            _fail(
                "invalid_binary_levels",
                f"{path}.levels",
                "Bernoulli response levels must be exactly [0, 1]",
            )
        if not variable.levels:
            variable = VariableSpec(
                variable.name,
                variable.role,
                variable.observed_type,
                levels=(0, 1),
                label=variable.label,
                family=family,
            )
    return variable


def _parse_variable(value: Any, role: Role, path: str) -> VariableSpec:
    mapping = _mapping(value, path, role.value)
    _keys(mapping, {"name", "type", "levels", "label"}, path, required={"name", "type"})
    name = _string(mapping["name"], f"{path}.name")
    if not name:
        _fail("invalid_variable_name", f"{path}.name", "variable names cannot be empty")
    observed_type = _string(mapping["type"], f"{path}.type")
    if observed_type not in _SUPPORTED_TYPES:
        _fail("unsupported_observed_type", f"{path}.type", f"unsupported observed type {observed_type!r}")
    levels = _levels(mapping.get("levels", ()), f"{path}.levels")
    if observed_type in {"binary", "categorical"} and not levels:
        _fail("missing_levels", f"{path}.levels", "categorical levels must be explicit")
    label = mapping.get("label")
    if label is not None:
        label = _string(label, f"{path}.label")
    if role is Role.PARTICIPANT_ID and observed_type != "categorical":
        _fail("invalid_participant_id", f"{path}.type", "participant_id must be categorical")
    return VariableSpec(name=name, role=role, observed_type=observed_type, levels=levels, label=label)


def _parse_edges(value: Any) -> tuple[tuple[str, str], ...]:
    edges: list[tuple[str, str]] = []
    for index, item in enumerate(_sequence(value, "scientific_edges")):
        pair = _sequence(item, f"scientific_edges[{index}]")
        if len(pair) != 2:
            _fail("malformed_edge", f"scientific_edges[{index}]", "each edge must contain [source, target]")
        edges.append(
            (
                _string(pair[0], f"scientific_edges[{index}][0]"),
                _string(pair[1], f"scientific_edges[{index}][1]"),
            )
        )
    return tuple(edges)


def _parse_nodes(
    value: Any,
    exposure: VariableSpec,
    outcome: VariableSpec,
    mediators: tuple[VariableSpec, ...],
    baseline: tuple[VariableSpec, ...],
    moderators: tuple[VariableSpec, ...],
) -> tuple[NodeSpec, ...]:
    mapping = _mapping(value, "models", "models")
    expected = {item.name for item in (*mediators, outcome)}
    for key in mapping:
        if not isinstance(key, str):
            _fail("unknown_model_node", "models", "model node names must be strings")
        if key not in expected:
            _fail("unknown_model_node", f"models.{key}", "no such endogenous model node")
    for name in expected:
        if name not in mapping:
            _fail("missing_model_node", f"models.{name}", "every endogenous variable needs a model")

    variables = {
        item.name: item
        for item in (*mediators, outcome, exposure, *baseline, *moderators)
    }
    mediator_index = {item.name: index for index, item in enumerate(mediators)}
    nodes = []
    for response in (*[item.name for item in mediators], outcome.name):
        path = f"models.{response}"
        node_mapping = _mapping(mapping[response], path, "model node")
        if "intercept" not in node_mapping:
            _fail("missing_intercept", f"{path}.intercept", "every node must declare intercept: true")
        if "terms" not in node_mapping:
            _fail("missing_terms", f"{path}.terms", "every node must declare a terms sequence")
        _keys(node_mapping, {"intercept", "terms", "interactions", "family"}, path, required={"intercept", "terms"})
        intercept = node_mapping["intercept"]
        if not isinstance(intercept, bool):
            _fail("invalid_intercept", f"{path}.intercept", "intercept must be boolean true")
        if not intercept:
            _fail("invalid_intercept", f"{path}.intercept", "every node must declare intercept: true")
        response_variable = outcome if response == outcome.name else next(
            item for item in mediators if item.name == response
        )
        expected_family = response_variable.family or Family.GAUSSIAN
        declared_family = node_mapping.get("family")
        if declared_family is not None and _family(declared_family, f"{path}.family") is not expected_family:
            _fail("family_mismatch", f"{path}.family", "node family does not match its response declaration")
        terms = tuple(
            _parse_term(item, f"{path}.terms[{index}]")
            for index, item in enumerate(_sequence(node_mapping["terms"], f"{path}.terms"))
        )
        interactions = tuple(
            _parse_interaction(item, f"{path}.interactions[{index}]")
            for index, item in enumerate(
                _sequence(node_mapping.get("interactions", ()), f"{path}.interactions")
            )
        )
        nodes.append(NodeSpec(response, expected_family, True, terms, interactions))

        term_names = [term.variable for term in terms]
        if len(term_names) != len(set(term_names)):
            _fail("duplicate_term", f"{path}.terms", "each predictor may have one declared main term")
        for index, term in enumerate(terms):
            _validate_term(term, term_names, variables, exposure, mediators, outcome, response, mediator_index, path, index)
        for index, interaction in enumerate(interactions):
            if interaction.left == interaction.right:
                _fail("malformed_interaction", f"{path}.interactions[{index}]", "interaction members must differ")
            if interaction.left not in term_names or interaction.right not in term_names:
                _fail(
                    "interaction_main_effect",
                    f"{path}.interactions[{index}]",
                    "both interaction members must have declared main terms on this node",
                )
    return tuple(nodes)


def _parse_term(value: Any, path: str) -> TermSpec:
    mapping = _mapping(value, path, "term")
    _keys(mapping, {"variable", "basis", "df", "purpose"}, path, required={"variable", "basis"})
    variable = _string(mapping["variable"], f"{path}.variable")
    basis = _enum(mapping["basis"], TermKind, f"{path}.basis", "invalid_term_kind")
    df = mapping.get("df")
    if df is not None:
        df = _int(df, f"{path}.df", minimum=1)
    purpose = mapping.get("purpose")
    if purpose is not None:
        purpose = _string(purpose, f"{path}.purpose")
    return TermSpec(variable, basis, df=df, purpose=purpose)


def _parse_interaction(value: Any, path: str) -> InteractionSpec:
    mapping = _mapping(value, path, "interaction")
    _keys(mapping, {"left", "right"}, path, required={"left", "right"})
    return InteractionSpec(
        left=_string(mapping["left"], f"{path}.left"),
        right=_string(mapping["right"], f"{path}.right"),
    )


def _parse_contrast(
    value: Any,
    exposure: VariableSpec,
    moderators: tuple[VariableSpec, ...],
    default_interpretation: Any,
    exposure_reference: Any,
    exposure_comparison: Any,
) -> ContrastSpec:
    path = "contrast"
    mapping = {} if value is None else _mapping(value, path, "contrast")
    _keys(mapping, {"reference", "comparison", "moderator_values", "primary_effects", "interpretation"}, path)
    reference = mapping.get("reference", exposure_reference)
    comparison = mapping.get("comparison", exposure_comparison)
    if reference == comparison:
        _fail("malformed_contrast", path, "reference and comparison must differ")
    if exposure.observed_type in {"binary", "categorical"}:
        if reference not in exposure.levels:
            _fail("malformed_contrast", f"{path}.reference", "reference is not a declared exposure level")
        if comparison not in exposure.levels:
            _fail("malformed_contrast", f"{path}.comparison", "comparison is not a declared exposure level")
    moderator_values = mapping.get("moderator_values", {})
    moderator_mapping = _mapping(moderator_values, f"{path}.moderator_values", "moderator values")
    known_moderators = {moderator.name: moderator for moderator in moderators}
    for name, regime_value in moderator_mapping.items():
        if name not in known_moderators:
            _fail("unknown_moderator", f"{path}.moderator_values.{name}", "moderator is not declared")
        moderator = known_moderators[name]
        if moderator.levels and regime_value not in moderator.levels:
            _fail("invalid_moderator_value", f"{path}.moderator_values.{name}", "value is not a declared level")
    primary_effects = mapping.get("primary_effects", ("TE", "PNDE", "TNIE"))
    primary_effects = tuple(
        _string(item, f"{path}.primary_effects[{index}]")
        for index, item in enumerate(_sequence(primary_effects, f"{path}.primary_effects"))
    )
    invalid_effects = set(primary_effects) - _PRIMARY_EFFECTS
    if invalid_effects:
        _fail("malformed_contrast", f"{path}.primary_effects", "unknown primary effect name")
    interpretation = _string(mapping.get("interpretation", default_interpretation), f"{path}.interpretation")
    if interpretation not in _INTERPRETATIONS:
        _fail("invalid_interpretation", f"{path}.interpretation", f"unsupported mode {interpretation!r}")
    return ContrastSpec(reference, comparison, moderator_mapping, primary_effects, interpretation)


def _parse_computation(value: Any) -> ComputationSpec:
    path = "computation"
    mapping = _mapping(value, path, "computation")
    _keys(
        mapping,
        {"seed", "bootstrap", "integration_draws", "integration_tolerance", "max_seconds", "memory_budget_mb", "information"},
        path,
        required={"seed", "bootstrap", "integration_draws"},
    )
    seed = _int(mapping["seed"], f"{path}.seed", minimum=0)
    bootstrap = _int(mapping["bootstrap"], f"{path}.bootstrap", minimum=0)
    integration_draws = _int(mapping["integration_draws"], f"{path}.integration_draws", minimum=1)
    tolerance = mapping.get("integration_tolerance", 1e-8)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance <= 0:
        _fail("invalid_computation", f"{path}.integration_tolerance", "tolerance must be positive")
    max_seconds = mapping.get("max_seconds")
    if max_seconds is not None:
        max_seconds = _int(max_seconds, f"{path}.max_seconds", minimum=1)
    memory_budget = mapping.get("memory_budget_mb")
    if memory_budget is not None:
        memory_budget = _int(memory_budget, f"{path}.memory_budget_mb", minimum=1)
    information = mapping.get("information", False)
    if not isinstance(information, bool):
        _fail("invalid_computation", f"{path}.information", "information must be boolean")
    return ComputationSpec(seed, bootstrap, integration_draws, float(tolerance), max_seconds, memory_budget, information)


def _validate_model(spec: ModelSpec) -> None:
    if spec.schema_version != 1:
        _fail("unsupported_schema_version", "schema_version", "only schema_version 1 is supported")
    if spec.exposure.role is not Role.EXPOSURE:
        _fail("invalid_role", "exposure.role", "exposure must have role exposure")
    if spec.outcome.role is not Role.OUTCOME:
        _fail("invalid_role", "outcome.role", "outcome must have role outcome")
    if not 1 <= len(spec.mediators) <= 4:
        _fail("mediator_count", "mediators", "declare between one and four mediators")
    _validate_unique_variables((spec.exposure, spec.outcome, *spec.mediators, *spec.baseline, *spec.moderators))
    _validate_mediator_order(spec.scientific.mediator_order, spec.mediators)
    if spec.scientific.arrangement not in _ARRANGEMENTS:
        _fail("invalid_arrangement", "arrangement", f"unsupported arrangement {spec.scientific.arrangement!r}")
    all_variables = (spec.exposure, spec.outcome, *spec.mediators, *spec.baseline, *spec.moderators)
    _validate_graph(spec.scientific.edges, all_variables)
    if len(spec.nodes) != len(spec.mediators) + 1:
        _fail("invalid_model_nodes", "models", "models must contain exactly all mediators and the outcome")
    node_names = tuple(node.response for node in spec.nodes)
    expected_names = tuple(item.name for item in (*spec.mediators, spec.outcome))
    if set(node_names) != set(expected_names):
        _fail("invalid_model_nodes", "models", "models must contain exactly all mediators and the outcome")
    variables = {item.name: item for item in all_variables}
    mediator_index = {item.name: index for index, item in enumerate(spec.mediators)}
    for node in spec.nodes:
        response_variable = variables.get(node.response)
        if response_variable is None:
            _fail("unknown_model_node", f"models.{node.response}", "response is not declared")
        expected_family = response_variable.family or (
            Family.BERNOULLI
            if response_variable.observed_type == "binary"
            and response_variable.role is Role.OUTCOME
            else Family.GAUSSIAN
        )
        if node.family is not expected_family:
            _fail("family_mismatch", f"models.{node.response}.family", "node family does not match its response declaration")
        if node.intercept is not True:
            _fail("invalid_intercept", f"models.{node.response}.intercept", "every node must declare intercept: true")
        term_names = [term.variable for term in node.terms]
        if len(term_names) != len(set(term_names)):
            _fail("duplicate_term", f"models.{node.response}.terms", "each predictor may have one declared main term")
        for index, term in enumerate(node.terms):
            _validate_term(
                term,
                term_names,
                variables,
                spec.exposure,
                spec.mediators,
                spec.outcome,
                node.response,
                mediator_index,
                f"models.{node.response}",
                index,
            )
        for index, interaction in enumerate(node.interactions):
            if interaction.left == interaction.right:
                _fail("malformed_interaction", f"models.{node.response}.interactions[{index}]", "interaction members must differ")
            if interaction.left not in term_names or interaction.right not in term_names:
                _fail("interaction_main_effect", f"models.{node.response}.interactions[{index}]", "both interaction members must have declared main terms on this node")
    if spec.missing not in _MISSING_POLICIES:
        _fail("invalid_missing_policy", "missing", f"unsupported policy {spec.missing!r}")
    if spec.interpretation not in _INTERPRETATIONS:
        _fail("invalid_interpretation", "interpretation", f"unsupported mode {spec.interpretation!r}")
    _validate_contrast(spec.contrast, spec.exposure, spec.moderators)
    _validate_computation(spec.computation)


def _validate_term(
    term: TermSpec,
    term_names: list[str],
    variables: Mapping[str, VariableSpec],
    exposure: VariableSpec,
    mediators: tuple[VariableSpec, ...],
    outcome: VariableSpec,
    response: str,
    mediator_index: Mapping[str, int],
    path: str,
    index: int,
) -> None:
    term_path = f"{path}.terms[{index}]"
    predictor = variables.get(term.variable)
    if predictor is None:
        _fail("unknown_predictor", f"{term_path}.variable", "predictor is not declared")
    allowed = {exposure.name, *(item.name for item in mediators if item.name != response)}
    allowed.update(item.name for item in variables.values() if item.role in {Role.COVARIATE, Role.MODERATOR})
    if response in mediator_index:
        allowed = {
            exposure.name,
            *(item.name for item in mediators[: mediator_index[response]]),
            *(item.name for item in variables.values() if item.role in {Role.COVARIATE, Role.MODERATOR}),
        }
    if term.variable not in allowed:
        code = "invalid_predictor_order" if predictor.role is Role.MEDIATOR else "invalid_predictor_role"
        _fail(code, f"{term_path}.variable", "predictor is not permitted for this node")
    if term.kind is TermKind.NATURAL_SPLINE:
        if term.df != 3:
            _fail("invalid_spline_df", f"{term_path}.df", "natural spline terms require df=3")
        if predictor.observed_type != "continuous":
            _fail("invalid_term_semantics", term_path, "natural splines require continuous predictors")
    elif term.kind is TermKind.QUADRATIC:
        if predictor.observed_type != "continuous":
            _fail("invalid_term_semantics", term_path, "quadratic terms require continuous predictors")
        if term.df is not None:
            _fail("unexpected_df", f"{term_path}.df", "only natural splines accept df")
    elif term.kind is TermKind.CATEGORICAL:
        if not predictor.levels:
            _fail("missing_levels", f"{term_path}.variable", "categorical terms require declared levels")
        if term.df is not None:
            _fail("unexpected_df", f"{term_path}.df", "only natural splines accept df")
    elif term.df is not None:
        _fail("unexpected_df", f"{term_path}.df", "only natural splines accept df")


def _validate_unique_variables(variables: Sequence[VariableSpec]) -> None:
    seen: dict[str, VariableSpec] = {}
    for variable in variables:
        if variable.name in seen:
            _fail("duplicate_variable", f"variables.{variable.name}", "variable names must be unique across roles")
        seen[variable.name] = variable


def _validate_mediator_order(order: Sequence[str], mediators: Sequence[VariableSpec]) -> None:
    names = tuple(item.name for item in mediators)
    if not order:
        _fail("missing_mediator_order", "mediator_order", "mediator_order must list every mediator")
    if len(order) != len(names) or set(order) != set(names) or len(set(order)) != len(order):
        _fail("invalid_mediator_order", "mediator_order", "mediator_order must contain each mediator exactly once")


def _validate_graph(edges: Sequence[tuple[str, str]], variables: Sequence[VariableSpec]) -> None:
    names = {variable.name for variable in variables}
    roles = {variable.name: variable.role for variable in variables}
    adjacency = {name: set() for name in names}
    indegree = {name: 0 for name in names}
    for index, (source, target) in enumerate(edges):
        path = f"scientific_edges[{index}]"
        if source not in names or target not in names:
            _fail("unknown_edge_variable", path, "scientific edge endpoint is not declared")
        if source == target:
            _fail("cyclic_graph", path, "self edges are not allowed")
        if roles[target] in {Role.EXPOSURE, Role.COVARIATE, Role.MODERATOR, Role.PARTICIPANT_ID}:
            _fail("invalid_edge_direction", path, "pre-exposure variables cannot have incoming edges")
        if roles[source] is Role.OUTCOME:
            _fail("invalid_edge_direction", path, "outcome cannot be a scientific parent")
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
    queue = [name for name, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop(0)
        visited += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(names):
        _fail("cyclic_graph", "scientific_edges", "scientific graph must be acyclic")


def _validate_contrast(contrast: ContrastSpec, exposure: VariableSpec, moderators: Sequence[VariableSpec]) -> None:
    if contrast.reference == contrast.comparison:
        _fail("malformed_contrast", "contrast", "reference and comparison must differ")
    if exposure.observed_type in {"binary", "categorical"}:
        if contrast.reference not in exposure.levels or contrast.comparison not in exposure.levels:
            _fail("malformed_contrast", "contrast", "contrast values must be declared exposure levels")
    known = {moderator.name: moderator for moderator in moderators}
    for name, value in contrast.moderator_values.items():
        if name not in known:
            _fail("unknown_moderator", f"contrast.moderator_values.{name}", "moderator is not declared")
        if known[name].levels and value not in known[name].levels:
            _fail("invalid_moderator_value", f"contrast.moderator_values.{name}", "value is not a declared level")
    if set(contrast.primary_effects) - _PRIMARY_EFFECTS:
        _fail("malformed_contrast", "contrast.primary_effects", "unknown primary effect name")
    if contrast.interpretation not in _INTERPRETATIONS:
        _fail("invalid_interpretation", "contrast.interpretation", "unsupported interpretation mode")


def _validate_computation(computation: ComputationSpec) -> None:
    if isinstance(computation.seed, bool) or computation.seed < 0:
        _fail("invalid_computation", "computation.seed", "seed must be a non-negative integer")
    if isinstance(computation.bootstrap, bool) or computation.bootstrap < 0:
        _fail("invalid_computation", "computation.bootstrap", "bootstrap must be non-negative")
    if isinstance(computation.integration_draws, bool) or computation.integration_draws < 1:
        _fail("invalid_computation", "computation.integration_draws", "integration_draws must be positive")
    if computation.integration_tolerance <= 0:
        _fail("invalid_computation", "computation.integration_tolerance", "tolerance must be positive")


def _coerce_enum(value: Any, enum_type: type[_T], field_name: str) -> _T:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field_name}: {value!r}") from exc


def _enum(value: Any, enum_type: type[_T], path: str, code: str) -> _T:
    try:
        return _coerce_enum(value, enum_type, path)
    except ValueError:
        _fail(code, path, f"unsupported value {value!r}")
    raise AssertionError("unreachable")


def _family(value: Any, path: str) -> Family:
    return _enum(value, Family, path, "invalid_family")


def _mapping(value: Any, path: str, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid_mapping", path, f"{description} must be a mapping")
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("invalid_sequence", path, "value must be a sequence")
    return value


def _keys(
    mapping: Mapping[str, Any],
    allowed: set[str],
    path: str,
    required: set[str] | None = None,
) -> None:
    for key in mapping:
        if not isinstance(key, str) or key not in allowed:
            _fail("unknown_key", f"{path}.{key}", "key is not part of the specification schema")
    for key in required or set():
        if key not in mapping:
            _fail("missing_key", f"{path}.{key}", "required key is missing")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail("invalid_string", path, "value must be a string")
    return value


def _int(value: Any, path: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("invalid_integer", path, "value must be an integer")
    if minimum is not None and value < minimum:
        _fail("invalid_integer", path, f"value must be at least {minimum}")
    return value


def _levels(value: Any, path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("invalid_levels", path, "levels must be a sequence")
    levels = tuple(value)
    try:
        if len(levels) != len(set(levels)):
            _fail("invalid_levels", path, "levels must be unique")
    except TypeError:
        _fail("invalid_levels", path, "levels must contain scalar values")
    return levels


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fail(code: str, path: str, message: str) -> None:
    raise SpecValidationError(code, path, message)


__all__ = [
    "ComputationSpec",
    "ContrastSpec",
    "Family",
    "InteractionSpec",
    "ModelSpec",
    "NodeSpec",
    "Role",
    "ScientificModel",
    "SpecValidationError",
    "TemplateSpec",
    "TermKind",
    "TermSpec",
    "VariableSpec",
    "compile_template",
    "load_model_spec",
]
