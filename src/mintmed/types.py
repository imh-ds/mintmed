"""Immutable shared values used by the Mintmed analysis pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnalysisStatus(str, Enum):
    """Stable status vocabulary for analyses and individual estimates."""

    OK = "ok"
    WARNING = "warning"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"
    FIT_FAILED = "fit_failed"
    INTEGRATION_FAILED = "integration_failed"
    INTERVAL_UNAVAILABLE = "interval_unavailable"
    INCOMPLETE = "incomplete"


class _FrozenDict(dict[str, Any]):
    """Dict-compatible read-only mapping that remains dataclass serializable."""

    def __init__(self, value: Mapping[str, Any] | None = None) -> None:
        dict.__init__(self, value or {})

    @staticmethod
    def _raise_read_only(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("mapping is read-only")

    __setitem__ = _raise_read_only
    __delitem__ = _raise_read_only
    clear = _raise_read_only
    pop = _raise_read_only
    popitem = _raise_read_only
    setdefault = _raise_read_only
    update = _raise_read_only
    __ior__ = _raise_read_only

    def __deepcopy__(self, memo: dict[int, Any]) -> _FrozenDict:
        return _FrozenDict(deepcopy(dict(self), memo))


def _freeze_value(value: Any) -> Any:
    """Recursively freeze result-owned mappings and sequences."""

    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Copy a mapping into a read-only container for frozen result objects."""

    return _FrozenDict({key: _freeze_value(item) for key, item in (value or {}).items()})


def _freeze_records(
    records: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Normalize replicate records to immutable tuples of read-only mappings."""

    return tuple(_freeze_mapping(record) for record in records)


@dataclass(frozen=True, slots=True)
class Issue:
    """A typed warning or failure attached to an analysis component."""

    code: str
    message: str
    status: AnalysisStatus
    node: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class EffectEstimate:
    """One named effect estimate and its explicitly reported interval state."""

    name: str
    estimate: float
    lower: float | None = None
    upper: float | None = None
    status: AnalysisStatus = AnalysisStatus.OK
    reason: str | None = None
    units: str = "outcome_units"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def interval_available(self) -> bool:
        """Whether both interval endpoints are present."""

        return self.lower is not None and self.upper is not None


@dataclass(frozen=True, slots=True)
class RegimeMeans:
    """Standardized outcome means for the primary mediation regimes."""

    mu_00: float
    mu_10: float
    mu_11: float
    mu_01: float | None = None

    @property
    def total_effect(self) -> float:
        return self.mu_11 - self.mu_00

    @property
    def pure_natural_direct_effect(self) -> float:
        return self.mu_10 - self.mu_00

    @property
    def total_natural_indirect_effect(self) -> float:
        return self.mu_11 - self.mu_10


@dataclass(frozen=True, slots=True)
class ContributionResult:
    """Admissibility-gated individual mediator contribution output."""

    available: bool
    contributions: Mapping[str, EffectEstimate] = field(default_factory=dict)
    reason_code: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "contributions", _freeze_mapping(self.contributions))


@dataclass(frozen=True, slots=True)
class PointAnalysis:
    """Point-fit objects consumed by bootstrap and reporting layers."""

    fitted_system: object
    regime_means: RegimeMeans
    effects: tuple[EffectEstimate, ...] | list[EffectEstimate] = ()
    contributions: ContributionResult | None = None
    moderator_contrasts: tuple[object, ...] | list[object] = ()
    draw_budget: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "moderator_contrasts", tuple(self.moderator_contrasts))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Participant-bootstrap records, intervals, and failure accounting."""

    requested: int
    attempted: int
    successful: int
    failed: int
    replicates: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = ()
    intervals: tuple[EffectEstimate, ...] | list[EffectEstimate] = ()
    status: AnalysisStatus = AnalysisStatus.OK
    failure_counts: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "replicates", _freeze_records(self.replicates))
        object.__setattr__(self, "intervals", tuple(self.intervals))
        object.__setattr__(self, "failure_counts", _freeze_mapping(self.failure_counts))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class MediationResult:
    """Complete immutable result returned by the public analysis API."""

    specification_hash: str
    analysis_hash: str
    effects: tuple[EffectEstimate, ...] | list[EffectEstimate] = ()
    contributions: ContributionResult | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    bootstrap: BootstrapResult | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    status: AnalysisStatus = AnalysisStatus.OK

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics))
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))


__all__ = [
    "AnalysisStatus",
    "BootstrapResult",
    "ContributionResult",
    "EffectEstimate",
    "Issue",
    "MediationResult",
    "PointAnalysis",
    "RegimeMeans",
]
