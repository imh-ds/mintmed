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
import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
import pandas as pd
import yaml

from . import __version__
from .diagnostics import (
    DataValidationError,
    PlanValidationError,
    UnsupportedAnalysisError,
)
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
    participant_id: VariableSpec | None = None

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
    participant_id: VariableSpec | None = None

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


@dataclass(frozen=True, slots=True)
class CompiledNodePlan:
    """Immutable node contract produced after data-dependent preflight."""

    response: str
    family: Family
    terms: tuple[TermSpec, ...]
    interactions: tuple[InteractionSpec, ...]
    scientific_parents: tuple[str, ...]
    factorization_predictors: tuple[str, ...]
    intercept: bool
    category_levels: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _coerce_enum(self.family, Family, "family"))
        object.__setattr__(self, "terms", tuple(self.terms))
        object.__setattr__(self, "interactions", tuple(self.interactions))
        object.__setattr__(self, "scientific_parents", tuple(self.scientific_parents))
        object.__setattr__(self, "factorization_predictors", tuple(self.factorization_predictors))
        object.__setattr__(
            self,
            "category_levels",
            _freeze_mapping({name: tuple(levels) for name, levels in self.category_levels.items()}),
        )


@dataclass(frozen=True, slots=True)
class AnalysisPlan:
    """Immutable compiled analysis population and node contracts."""

    nodes: tuple[CompiledNodePlan, ...]
    retained_row_indices: tuple[Any, ...]
    excluded_row_indices: tuple[Any, ...]
    analysis_columns: tuple[str, ...]
    original_row_count: int
    retained_row_count: int
    participant_id: str | None
    contrast: ContrastSpec
    computation: ComputationSpec
    missing: str
    issues: tuple[Issue, ...]
    specification_hash: str
    analysis_hash: str
    diagnostics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "retained_row_indices", tuple(self.retained_row_indices))
        object.__setattr__(self, "excluded_row_indices", tuple(self.excluded_row_indices))
        object.__setattr__(self, "analysis_columns", tuple(self.analysis_columns))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "diagnostics", _freeze_recursive(self.diagnostics))

    @property
    def warnings(self) -> tuple[Issue, ...]:
        """Return nonfatal warnings without exposing mutable plan state."""

        return tuple(issue for issue in self.issues if issue.status is AnalysisStatus.WARNING)

    def summary(self) -> str:
        """Render a deterministic human-readable plan summary."""

        return _render_plan_summary(self)


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
            participant_id=template.participant_id,
        )
        _validate_model(spec)
        return spec
    except SpecValidationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise SpecValidationError("malformed_template", "$", str(exc)) from exc


def estimate_plan(data: pd.DataFrame, spec: ModelSpec) -> AnalysisPlan:
    """Compile a validated model specification against an observed data frame."""

    if not isinstance(spec, ModelSpec):
        raise PlanValidationError(
            "invalid_plan_spec", "spec", "estimate_plan expects a validated ModelSpec"
        )
    try:
        _validate_model(spec)
    except SpecValidationError as exc:
        raise PlanValidationError("invalid_plan_spec", exc.path, exc.message) from exc

    selected, retained, excluded, analysis_columns, missing_counts = _select_analysis_rows(
        data, spec
    )
    variables = _spec_variables(spec)
    _validate_observed_values(retained, variables)
    _validate_participant_independence(retained, spec.participant_id)
    support = _support_summaries(retained, variables)
    _validate_counterfactual_support(retained, spec, variables)
    nodes = _compile_nodes(spec, variables)
    issues, binary_counts = _build_issues(retained, spec, variables)

    specification_hash = hashlib.sha256(spec.canonical_json().encode("utf-8")).hexdigest()
    data_fingerprint = _data_fingerprint(selected, analysis_columns)
    analysis_specification = spec.to_canonical_dict()
    analysis_specification["computation"].pop("max_seconds", None)
    analysis_specification["computation"].pop("memory_budget_mb", None)
    analysis_specification_hash = hashlib.sha256(
        json.dumps(
            analysis_specification,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    analysis_payload = {
        "scientific_specification_hash": analysis_specification_hash,
        "data_fingerprint": data_fingerprint,
        "analysis_columns": list(analysis_columns),
        "missing": spec.missing,
        "retained_row_indices": [_json_safe(value) for value in retained.index.tolist()],
        "excluded_row_indices": [_json_safe(value) for value in excluded],
        "contrast": asdict(spec.contrast),
        "seed": spec.computation.seed,
        "bootstrap": spec.computation.bootstrap,
        "integration_draws": spec.computation.integration_draws,
        "integration_tolerance": spec.computation.integration_tolerance,
        "software_versions": {"mintmed": __version__, "pandas": pd.__version__},
    }
    analysis_hash = hashlib.sha256(
        json.dumps(
            _canonicalize(analysis_payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    diagnostics = {
        "rows": {
            "original": len(selected),
            "retained": len(retained),
            "excluded": len(excluded),
        },
        "missing": {
            "policy": spec.missing,
            "excluded_rows": len(excluded),
            "counts": missing_counts,
        },
        "participant_id": {
            "column": spec.participant_id.name if spec.participant_id else None,
            "unique": True,
        },
        "support": support,
        "binary_counts": binary_counts,
        "scientific_edges": [list(edge) for edge in spec.scientific.edges],
        "factorization_order": list(spec.scientific.mediator_order),
        "nodes": [
            {
                "response": node.response,
                "family": node.family.value,
                "terms": [term.variable for term in node.terms],
                "interactions": [
                    [interaction.left, interaction.right]
                    for interaction in node.interactions
                ],
            }
            for node in nodes
        ],
        "warnings": [issue.code for issue in issues],
    }
    return AnalysisPlan(
        nodes=nodes,
        retained_row_indices=tuple(retained.index.tolist()),
        excluded_row_indices=excluded,
        analysis_columns=analysis_columns,
        original_row_count=len(selected),
        retained_row_count=len(retained),
        participant_id=spec.participant_id.name if spec.participant_id else None,
        contrast=spec.contrast,
        computation=spec.computation,
        missing=spec.missing,
        issues=issues,
        specification_hash=specification_hash,
        analysis_hash=analysis_hash,
        diagnostics=diagnostics,
    )


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
            "participant_id",
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
    participant_id = None
    if root.get("participant_id") is not None:
        participant_id = _parse_variable(
            root["participant_id"], Role.PARTICIPANT_ID, "participant_id"
        )
        if participant_id.observed_type != "categorical":
            _fail(
                "invalid_participant_id",
                "participant_id.type",
                "participant_id must be categorical",
            )
    _validate_unique_variables(
        (
            exposure,
            outcome,
            *mediators,
            *baseline,
            *moderators,
            *((participant_id,) if participant_id is not None else ()),
        )
    )

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
        root["models"],
        exposure,
        outcome,
        mediators,
        baseline,
        moderators,
        participant_id,
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
        participant_id=participant_id,
    )


def _parse_exposure(value: Any, path: str) -> tuple[VariableSpec, Any, Any]:
    mapping = _mapping(value, path, "exposure")
    _keys(
        mapping,
        {"name", "type", "levels", "reference", "comparison", "label"},
        path,
        required={"name", "type", "reference", "comparison"},
    )
    variable = _parse_variable(
        {key: mapping[key] for key in ("name", "type", "levels", "label") if key in mapping},
        Role.EXPOSURE,
        path,
    )
    if variable.observed_type not in {"binary", "categorical", "continuous"}:
        _fail("unsupported_exposure_type", f"{path}.type", "exposure type is not supported")
    if variable.observed_type in {"binary", "categorical"} and not variable.levels:
        _fail("missing_levels", f"{path}.levels", "exposure levels must be explicit")
    if variable.observed_type == "continuous" and variable.levels:
        _fail(
            "invalid_exposure_levels",
            f"{path}.levels",
            "continuous exposures cannot declare categorical levels",
        )
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
    if (
        observed_type in {"binary", "categorical"}
        and not levels
        and role is not Role.PARTICIPANT_ID
    ):
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
    participant_id: VariableSpec | None,
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
        for item in (
            *mediators,
            outcome,
            exposure,
            *baseline,
            *moderators,
            *((participant_id,) if participant_id is not None else ()),
        )
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
    _validate_unique_variables(
        (
            spec.exposure,
            spec.outcome,
            *spec.mediators,
            *spec.baseline,
            *spec.moderators,
            *((spec.participant_id,) if spec.participant_id is not None else ()),
        )
    )
    _validate_mediator_order(spec.scientific.mediator_order, spec.mediators)
    if spec.scientific.arrangement not in _ARRANGEMENTS:
        _fail("invalid_arrangement", "arrangement", f"unsupported arrangement {spec.scientific.arrangement!r}")
    all_variables = (
        spec.exposure,
        spec.outcome,
        *spec.mediators,
        *spec.baseline,
        *spec.moderators,
        *((spec.participant_id,) if spec.participant_id is not None else ()),
    )
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


def _spec_variables(spec: ModelSpec) -> dict[str, VariableSpec]:
    """Return declared variables in the analysis-column order."""

    by_name = {
        variable.name: variable
        for variable in (
            spec.exposure,
            *spec.mediators,
            spec.outcome,
            *spec.baseline,
            *spec.moderators,
            *((spec.participant_id,) if spec.participant_id is not None else ()),
        )
    }
    ordered_names = [spec.exposure.name]
    ordered_names.extend(spec.scientific.mediator_order)
    ordered_names.append(spec.outcome.name)
    ordered_names.extend(variable.name for variable in spec.baseline)
    ordered_names.extend(variable.name for variable in spec.moderators)
    if spec.participant_id is not None:
        ordered_names.append(spec.participant_id.name)
    return {name: by_name[name] for name in ordered_names}


def _select_analysis_rows(
    data: pd.DataFrame,
    spec: ModelSpec,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[Any, ...], tuple[str, ...], Mapping[str, int]]:
    if not isinstance(data, pd.DataFrame):
        raise DataValidationError("invalid_data", "data", "data must be a pandas DataFrame")
    if data.columns.has_duplicates:
        raise DataValidationError(
            "duplicate_columns", "data.columns", "data columns must be unique"
        )
    variables = _spec_variables(spec)
    analysis_columns = tuple(variables)
    missing_columns = [column for column in analysis_columns if column not in data.columns]
    if missing_columns:
        raise DataValidationError(
            "missing_columns",
            "data.columns",
            f"required analysis columns are missing: {missing_columns}",
        )
    selected = data.loc[:, list(analysis_columns)].copy(deep=True)
    for variable in variables.values():
        if variable.observed_type not in {"continuous", "binary"}:
            continue
        series = selected[variable.name]
        if not pd.api.types.is_numeric_dtype(series):
            raise DataValidationError(
                "invalid_data_type",
                f"data.{variable.name}",
                f"{variable.observed_type} variable must use a numeric dtype",
            )
        values = series.astype(float).to_numpy()
        missing = series.isna().to_numpy()
        if ((~missing) & ~np.isfinite(values)).any():
            raise DataValidationError(
                "nonfinite_values",
                f"data.{variable.name}",
                "numeric analysis values must be finite",
            )
    missing_mask = selected.isna().any(axis=1)
    missing_counts = {
        name: int(count)
        for name, count in selected.loc[missing_mask].isna().sum().items()
        if count
    }
    if missing_mask.any() and spec.missing == "error":
        raise DataValidationError(
            "missing_values",
            "data",
            f"missing values by column: {missing_counts}",
        )
    retained = selected.loc[~missing_mask].copy(deep=True)
    excluded = tuple(selected.index[missing_mask].tolist())
    if retained.empty:
        raise DataValidationError(
            "missing_values",
            "data",
            "no complete analysis rows remain after missingness handling",
        )
    return selected, retained, excluded, analysis_columns, missing_counts


def _validate_observed_values(
    data: pd.DataFrame,
    variables: Mapping[str, VariableSpec],
) -> None:
    for variable in variables.values():
        series = data[variable.name]
        if variable.observed_type == "binary":
            invalid = ~series.isin((0, 1))
            if invalid.any():
                raise DataValidationError(
                    "invalid_binary_values",
                    f"data.{variable.name}",
                    "binary values must be coded as 0 or 1",
                )
        elif variable.observed_type == "categorical" and variable.role is not Role.PARTICIPANT_ID:
            invalid = ~series.isin(variable.levels)
            if invalid.any():
                raise DataValidationError(
                    "invalid_category_values",
                    f"data.{variable.name}",
                    "observed categorical values must be declared levels",
                )


def _validate_participant_independence(
    data: pd.DataFrame,
    participant_id: VariableSpec | None,
) -> None:
    if participant_id is None:
        return
    duplicated = data[participant_id.name].duplicated(keep=False)
    if duplicated.any():
        raise UnsupportedAnalysisError(
            "repeated_rows",
            "participant_id",
            f"{int(duplicated.sum())} retained rows share a participant identifier",
        )


def _support_summaries(
    data: pd.DataFrame,
    variables: Mapping[str, VariableSpec],
) -> dict[str, Mapping[str, Any]]:
    summaries: dict[str, Mapping[str, Any]] = {}
    for variable in variables.values():
        series = data[variable.name]
        if variable.role is Role.PARTICIPANT_ID:
            summaries[variable.name] = {
                "observed_count": int(series.nunique(dropna=True)),
                "unique": True,
            }
        elif variable.observed_type == "continuous":
            summaries[variable.name] = {
                "observed_min": float(series.min()),
                "observed_max": float(series.max()),
            }
        else:
            observed = [_json_safe(value) for value in pd.unique(series)]
            summaries[variable.name] = {
                "observed_levels": observed,
                "declared_levels": [_json_safe(value) for value in variable.levels],
            }
    return summaries


def _validate_counterfactual_support(
    data: pd.DataFrame,
    spec: ModelSpec,
    variables: Mapping[str, VariableSpec],
) -> None:
    _validate_supported_value(
        data[spec.exposure.name],
        variables[spec.exposure.name],
        spec.contrast.reference,
        "contrast.reference",
    )
    _validate_supported_value(
        data[spec.exposure.name],
        variables[spec.exposure.name],
        spec.contrast.comparison,
        "contrast.comparison",
    )
    for name, value in spec.contrast.moderator_values.items():
        _validate_supported_value(
            data[name], variables[name], value, f"contrast.moderator_values.{name}"
        )


def _validate_supported_value(
    series: pd.Series,
    variable: VariableSpec,
    value: Any,
    path: str,
) -> None:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        raise UnsupportedAnalysisError(
            "unsupported_extrapolation", path, "counterfactual value must be finite"
        )
    if variable.observed_type == "continuous":
        observed_min = float(series.min())
        observed_max = float(series.max())
        try:
            supported = observed_min <= float(value) <= observed_max
        except (TypeError, ValueError):
            supported = False
    else:
        supported = bool(series.eq(value).any())
    if not supported:
        raise UnsupportedAnalysisError(
            "unsupported_extrapolation",
            path,
            f"{variable.name} counterfactual is outside retained observed support",
        )


def _compile_nodes(
    spec: ModelSpec,
    variables: Mapping[str, VariableSpec],
) -> tuple[CompiledNodePlan, ...]:
    node_by_response = {node.response: node for node in spec.nodes}
    seen_edges: set[tuple[str, str]] = set()
    for edge in spec.scientific.edges:
        if edge in seen_edges:
            raise PlanValidationError(
                "invalid_plan_spec",
                "scientific_edges",
                f"duplicate scientific edge {edge!r}",
            )
        seen_edges.add(edge)
    ordered_responses = (*spec.scientific.mediator_order, spec.outcome.name)
    compiled: list[CompiledNodePlan] = []
    for response in ordered_responses:
        node = node_by_response[response]
        parents = tuple(
            source for source, target in spec.scientific.edges if target == response
        )
        predictors = tuple(dict.fromkeys(term.variable for term in node.terms))
        category_levels: dict[str, tuple[Any, ...]] = {}
        response_variable = variables[response]
        if response_variable.levels:
            category_levels[response] = tuple(response_variable.levels)
        for predictor in predictors:
            predictor_variable = variables[predictor]
            if predictor_variable.levels:
                category_levels[predictor] = tuple(predictor_variable.levels)
        compiled.append(
            CompiledNodePlan(
                response=response,
                family=node.family,
                terms=node.terms,
                interactions=node.interactions,
                scientific_parents=parents,
                factorization_predictors=predictors,
                intercept=node.intercept,
                category_levels=category_levels,
            )
        )
    return tuple(compiled)


def _build_issues(
    data: pd.DataFrame,
    spec: ModelSpec,
    variables: Mapping[str, VariableSpec],
) -> tuple[tuple[Issue, ...], dict[str, Mapping[str, int]]]:
    issues: list[Issue] = []
    binary_counts: dict[str, Mapping[str, int]] = {}
    for response in (*spec.scientific.mediator_order, spec.outcome.name):
        variable = variables[response]
        if variable.observed_type != "binary":
            continue
        series = data[response]
        events = int((series == 1).sum())
        non_events = int((series == 0).sum())
        binary_counts[response] = {"events": events, "non_events": non_events}
        if events < 5 or non_events < 5:
            issues.append(
                Issue(
                    code="sparse_binary_events",
                    message=(
                        f"{response} has {events} events and {non_events} non-events; "
                        "both counts should be at least 5 for this warning gate"
                    ),
                    status=AnalysisStatus.WARNING,
                    node=response,
                )
            )
    if len(data) < 100:
        issues.append(
            Issue(
                code="small_sample",
                message=f"analysis population has {len(data)} retained rows, below 100",
                status=AnalysisStatus.WARNING,
            )
        )
    return tuple(issues), binary_counts


def _data_fingerprint(frame: pd.DataFrame, columns: tuple[str, ...]) -> str:
    selected = frame.loc[:, list(columns)]
    metadata = {
        "columns": list(columns),
        "dtypes": [str(selected[column].dtype) for column in columns],
        "row_count": len(selected),
    }
    digest = hashlib.sha256()
    digest.update(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    digest.update(
        pd.util.hash_pandas_object(selected, index=True)
        .to_numpy(dtype="uint64")
        .tobytes()
    )
    return digest.hexdigest()


def _render_plan_summary(plan: AnalysisPlan) -> str:
    edges = ", ".join(f"{source}->{target}" for source, target in plan.diagnostics["scientific_edges"])
    lines = [
        (
            "Analysis population: "
            f"retained={plan.retained_row_count}, "
            f"excluded={len(plan.excluded_row_indices)}, "
            f"original={plan.original_row_count}"
        ),
        f"Node order: {' -> '.join(node.response for node in plan.nodes)}",
        f"Scientific edges: {edges or 'none'}",
        "Factorization predictors:",
    ]
    lines.extend(
        f"  {node.response}: {', '.join(node.factorization_predictors) or 'none'}"
        for node in plan.nodes
    )
    lines.extend(
        [
            f"Exposure contrast: {plan.contrast.reference} -> {plan.contrast.comparison}",
            f"Interpretation: {plan.contrast.interpretation}",
            "Warnings: "
            + (
                ", ".join(
                    issue.code
                    + (f"({issue.node})" if issue.node is not None else "")
                    for issue in plan.warnings
                )
                or "none"
            ),
        ]
    )
    return "\n".join(lines)


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _freeze_recursive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze_recursive(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_recursive(item) for item in value)
    return value


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
    "AnalysisPlan",
    "ComputationSpec",
    "CompiledNodePlan",
    "ContrastSpec",
    "DataValidationError",
    "Family",
    "InteractionSpec",
    "ModelSpec",
    "NodeSpec",
    "PlanValidationError",
    "Role",
    "ScientificModel",
    "SpecValidationError",
    "TemplateSpec",
    "TermKind",
    "TermSpec",
    "UnsupportedAnalysisError",
    "VariableSpec",
    "compile_template",
    "estimate_plan",
    "load_model_spec",
]
