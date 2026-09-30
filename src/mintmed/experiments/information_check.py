"""Residual conditional-mutual-information model check (Task 18 Phase 1, information arm).

This is a *status-only* (C2) experimental diagnostic. It asks whether a fitted
node model leaves information about one tested parent in its residuals, after
conditioning on (at most one) continuous covariate. It never changes a fit or an
effect estimate, and it is not part of Mintmed's public API.

Targets
-------
Outcome node (primary), ``information_check(data, "Y ~ A + M + C", "M")``::

    I(r_Y ; M | A, C) = sum_a P(A = a) I(r_Y ; M | C, A = a)

The statistic is ``T = sum_a w_a T_a`` with ``w_a = n_a / n`` over retained
rows, frozen across null resamples, and ``T_a`` the CMIknn estimate of
``I(r ; M | C)`` inside stratum ``A = a``.

Mediator node (secondary), ``information_check(data, "M ~ A + C", "A",
stratify_by=None)``: ``T`` estimates ``I(r_M ; A | C)`` with a binary tested
parent, using the mixed discrete/continuous variant described below. Its
result carries ``settings["role"] == "secondary"`` and
``settings["experimental"] is True``.

Residuals
---------
``residuals="cross_fitted"`` (default): ordinary least squares of the formula
in ``folds`` folds. The fold of each retained row is fixed by ``seed`` (a
seeded permutation of the rows split into ``folds`` near-equal parts), and each
row's residual comes from the fit on the other folds. The patsy design matrix
is built once on all retained rows, so stateful transforms (for example spline
knots) see the covariates of every row; only the outcome is held out.
``residuals="in_sample"`` uses one OLS fit on all rows (sensitivity only).

Estimator (Runge 2018, CMIknn; Frenzel and Pompe 2007)
------------------------------------------------------
Within a stratum of size ``n_a``, each variable is rank-transformed
(``scipy.stats.rankdata``, average ranks for ties, divided by ``n_a``) as in
Runge's CMIknn default. With the maximum norm, for every point ``i``:

* ``eps_i`` is the distance to its ``k``-th nearest neighbour (self excluded)
  in the joint space ``(r, X, Z)``;
* ``n_xz, n_yz, n_z`` count the points (self included) strictly closer than
  ``eps_i`` in the subspaces ``(r, Z)``, ``(X, Z)`` and ``Z``;
* ``T_a = psi(k) - mean(psi(n_xz) + psi(n_yz) - psi(n_z))``.

Ties are handled deterministically without jitter. Average ranks keep tied
values tied. When ``eps_i == 0`` (at least ``k`` exact duplicates of point
``i`` in the joint space), the Gao et al. (2017) / Mesner and Shalizi (2021)
rule applies: ``k`` is replaced by the number of joint duplicates and the
subspace counts use ``<= 0`` (exact duplicates, self included). The number of
tied values per variable and of zero-radius points is reported in ``ties``.
(Runge's reference implementation breaks ties with tiny random noise instead;
the published estimator does not require it, so none is added here.)
Negative estimates are kept; nothing is clipped.

``k_CMI = max(5, round_half_up(k_cmi_fraction * n_a))``.

Binary tested parent (mediator-node check): the binary variable is not ranked;
its coordinate is ``0`` or a separation larger than any rank distance, so a
max-norm ball never crosses levels unless it contains every point. This is the
discrete-metric form of the conditional mixed kNN estimator of Mesner and
Shalizi (2021): the ``k`` joint neighbours are found among rows with the same
level of A, ``n_{A,Z}`` counts same-level rows within ``eps_i`` in C, and
``n_{r,Z}``, ``n_Z`` count all rows.

Null distribution (Runge 2018, local permutation)
-------------------------------------------------
For each stratum, the ``k_perm`` nearest neighbours of every row in the
(ranked) conditioning space are computed once (self included, maximum norm).
In each replicate and each stratum, every row's neighbour list is shuffled,
rows are visited in a random order, and row ``i`` receives the tested-parent
value of the first neighbour on its list that has not been used yet (the last
neighbour if all are used), so draws are without replacement where possible.
Both strata are permuted in every replicate, both ``T_a`` are recomputed and
combined with the frozen weights into one ``T_null``. The p-value is
``(1 + #{T_null >= T_obs}) / (1 + permutations)``. With no conditioning
column, the local permutation is a full random permutation within the stratum.

Status
------
``diagnostic_unavailable`` (with ``statistic`` and ``p_value`` NaN) when a
stratum has fewer than 30 rows, when a stratifier level is absent, when more
than one conditioning column is given, when a column needed is not numeric,
when ``k_CMI`` is not below the stratum size, or when a fold's design is rank
deficient. Small strata are never pooled or jittered.

Calibration is not claimed: Runge's result concerns observed continuous
variables, not estimated residuals. Task 18 S4 measures the empirical null.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import patsy
from scipy.spatial import cKDTree
from scipy.special import digamma
from scipy.stats import rankdata

from ..types import _freeze_mapping

__all__ = [
    "InformationCheckResult",
    "MIN_STRATUM_SIZE",
    "cmi_knn",
    "information_check",
    "k_cmi_for",
    "local_permutation",
]

MIN_STRATUM_SIZE = 30
STATUS_OK = "ok"
STATUS_UNAVAILABLE = "diagnostic_unavailable"
# Coordinate for a discrete level: larger than any rank distance (ranks lie in (0, 1]).
_DISCRETE_SEPARATION = 1.0e6


@dataclass(frozen=True)
class InformationCheckResult:
    """Outcome of one residual CMI check.

    ``stratum_sizes``, ``stratum_estimates``, ``weights``, ``k_cmi`` and
    ``ties`` are keyed by stratum label (``"all"`` without stratification).
    ``null_statistics`` holds the combined ``T`` of each null replicate.
    """

    statistic: float
    p_value: float
    status: str
    reason: str | None
    stratum_sizes: Mapping[str, int]
    stratum_estimates: Mapping[str, float]
    weights: Mapping[str, float]
    k_cmi: Mapping[str, int]
    permutations: int
    runtime_seconds: float
    settings: Mapping[str, Any]
    n: int = 0
    ties: Mapping[str, Any] = field(default_factory=dict)
    null_statistics: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        for name in ("stratum_sizes", "stratum_estimates", "weights", "k_cmi", "settings", "ties"):
            object.__setattr__(self, name, _freeze_mapping(getattr(self, name)))
        object.__setattr__(self, "null_statistics", tuple(float(v) for v in self.null_statistics))


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


def k_cmi_for(n_stratum: int, fraction: float) -> int:
    """``max(5, round(fraction * n))`` with half-up rounding."""

    return max(5, int(math.floor(fraction * n_stratum + 0.5)))


def _rank(values: np.ndarray) -> np.ndarray:
    """Average ranks scaled to (0, 1]; ties stay tied."""

    return rankdata(values, method="average") / values.shape[0]


def _strict_radius(eps: np.ndarray) -> np.ndarray:
    """Largest radius below ``eps`` (``<`` counting); zero stays zero (``<= 0``)."""

    return np.where(eps > 0, np.nextafter(eps, 0.0), 0.0)


def _count_1d(sorted_z: np.ndarray, z: np.ndarray, radius: np.ndarray) -> np.ndarray:
    """Points of ``sorted_z`` within ``radius`` (inclusive) of each ``z``; self included."""

    upper = np.searchsorted(sorted_z, z + radius, side="right")
    lower = np.searchsorted(sorted_z, z - radius, side="left")
    return upper - lower


class _CMIStratum:
    """Precomputed pieces of ``I(x ; y | z)`` for one stratum, where ``y`` is permuted.

    ``x`` (the residual) and ``z`` are fixed across null replicates, so their
    subspace tree is built once; ``y`` enters only through ``estimate(y)``.
    Inputs are already transformed (ranks, or discrete coordinates).
    """

    def __init__(self, x: np.ndarray, z: np.ndarray | None, k: int) -> None:
        self.n = x.shape[0]
        self.k = int(k)
        self.x = x.reshape(-1, 1)
        self.z = None if z is None else z.reshape(-1, 1)
        xz = self.x if self.z is None else np.hstack([self.x, self.z])
        self.tree_xz = cKDTree(xz)
        self.xz = xz
        if self.z is not None:
            self.z_flat = self.z[:, 0]
            self.z_sorted = np.sort(self.z_flat)

    def estimate(self, y: np.ndarray) -> tuple[float, int]:
        """Return the CMI estimate and the number of zero-radius points."""

        y = y.reshape(-1, 1)
        joint = np.hstack([self.xz, y])
        tree = cKDTree(joint)
        dist, _ = tree.query(joint, k=[self.k + 1], p=np.inf)
        eps = dist[:, 0]
        radius = _strict_radius(eps)
        zero = eps == 0
        k_eff = np.full(self.n, float(self.k))
        if zero.any():
            dup = tree.query_ball_point(joint[zero], r=0.0, p=np.inf, return_length=True)
            k_eff[zero] = np.asarray(dup, dtype=float) - 1.0
        n_xz = self.tree_xz.query_ball_point(self.xz, r=radius, p=np.inf, return_length=True)
        if self.z is None:
            yz = y
            n_z = np.full(self.n, float(self.n))
        else:
            yz = np.hstack([y, self.z])
            n_z = _count_1d(self.z_sorted, self.z_flat, radius)
        tree_yz = cKDTree(yz)
        n_yz = tree_yz.query_ball_point(yz, r=radius, p=np.inf, return_length=True)
        value = np.mean(digamma(k_eff) - digamma(n_xz) - digamma(n_yz) + digamma(n_z))
        return float(value), int(zero.sum())


def cmi_knn(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None,
    k: int,
    *,
    transform: str = "ranks",
    discrete_y: bool = False,
) -> float:
    """CMIknn estimate of ``I(x ; y | z)`` (one-dimensional ``x``, ``y``, ``z``).

    ``transform`` is ``"ranks"`` (Runge's default), ``"standardize"`` or
    ``"none"``. With ``discrete_y`` the values of ``y`` are treated as levels
    (discrete metric), see the module docstring.
    """

    x_t = _transform(np.asarray(x, dtype=float), transform)
    z_t = None if z is None else _transform(np.asarray(z, dtype=float), transform)
    y_arr = np.asarray(y, dtype=float)
    y_t = _discrete_coordinate(y_arr) if discrete_y else _transform(y_arr, transform)
    return _CMIStratum(x_t, z_t, k).estimate(y_t)[0]


def _transform(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "ranks":
        return _rank(values)
    if transform == "standardize":
        sd = values.std()
        return (values - values.mean()) / (sd if sd > 0 else 1.0)
    if transform == "none":
        return values.astype(float)
    raise ValueError(f"unknown transform {transform!r}")


def _discrete_coordinate(values: np.ndarray) -> np.ndarray:
    _, codes = np.unique(values, return_inverse=True)
    return codes.astype(float) * _DISCRETE_SEPARATION


# ---------------------------------------------------------------------------
# Local permutation
# ---------------------------------------------------------------------------


def _neighbour_lists(z: np.ndarray | None, n: int, k_perm: int) -> np.ndarray | None:
    """``k_perm`` nearest neighbours of every row in ``z`` (self included)."""

    if z is None:
        return None
    k_here = min(k_perm, n)
    z2 = z.reshape(-1, 1)
    _, idx = cKDTree(z2).query(z2, k=k_here, p=np.inf)
    return np.asarray(idx, dtype=np.int64).reshape(n, k_here)


def local_permutation(neighbours: np.ndarray | None, n: int, rng: np.random.Generator) -> np.ndarray:
    """One Runge (2018) restricted permutation: ``y_null = y[result]``.

    Neighbour lists are shuffled row-wise; rows are visited in random order and
    each takes the first unused neighbour (the last listed one if all are used).
    Without neighbour lists (no conditioning) this is a uniform permutation.
    """

    if neighbours is None:
        return rng.permutation(n)
    k = neighbours.shape[1]
    shuffled = np.take_along_axis(neighbours, rng.random((n, k)).argsort(axis=1), axis=1)
    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    result = np.empty(n, dtype=np.int64)
    rows = shuffled.tolist()
    for i in order.tolist():
        candidates = rows[i]
        choice = candidates[-1]
        for candidate in candidates:
            if not used[candidate]:
                choice = candidate
                break
        result[i] = choice
        used[choice] = True
    return result


# ---------------------------------------------------------------------------
# Residuals
# ---------------------------------------------------------------------------


def _fold_ids(n: int, folds: int, rng: np.random.Generator) -> np.ndarray:
    ids = np.empty(n, dtype=np.int64)
    for fold, rows in enumerate(np.array_split(rng.permutation(n), folds)):
        ids[rows] = fold
    return ids


def _residuals(
    y: np.ndarray, X: np.ndarray, mode: str, folds: int, rng: np.random.Generator
) -> tuple[np.ndarray | None, str | None]:
    p = X.shape[1]
    if mode == "in_sample":
        if np.linalg.matrix_rank(X) < p:
            return None, "design matrix is rank deficient"
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return y - X @ beta, None
    fold_id = _fold_ids(y.shape[0], folds, rng)
    out = np.empty_like(y)
    for fold in range(folds):
        test = fold_id == fold
        train = ~test
        if np.linalg.matrix_rank(X[train]) < p:
            return None, f"training design of fold {fold} is rank deficient"
        beta, *_ = np.linalg.lstsq(X[train], y[train], rcond=None)
        out[test] = y[test] - X[test] @ beta
    return out, None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _tie_count(values: np.ndarray) -> int:
    """Rows whose value is shared with at least one other row."""

    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return int((counts[inverse] > 1).sum())


def _label(level: Any) -> str:
    if isinstance(level, (float, np.floating)) and float(level).is_integer():
        return str(int(level))
    return str(level)


def information_check(
    data: pd.DataFrame,
    formula: str,
    tested_parent: str,
    *,
    conditioning: Sequence[str] = ("C",),
    stratify_by: str | None = "A",
    seed: int,
    permutations: int = 199,
    k_cmi_fraction: float = 0.1,
    k_perm: int = 5,
    folds: int = 5,
    residuals: str = "cross_fitted",
    transform: str = "ranks",
) -> InformationCheckResult:
    """Run the residual CMIknn check on one node model; see the module docstring."""

    started = time.perf_counter()
    conditioning = tuple(conditioning)
    if residuals not in {"cross_fitted", "in_sample"}:
        raise ValueError(f"residuals must be 'cross_fitted' or 'in_sample', got {residuals!r}")
    if transform not in {"ranks", "standardize", "none"}:
        raise ValueError(f"unknown transform {transform!r}")
    if permutations < 1 or k_perm < 1 or folds < 2:
        raise ValueError("permutations >= 1, k_perm >= 1 and folds >= 2 are required")
    if stratify_by is not None and stratify_by in {tested_parent, *conditioning}:
        raise ValueError("stratify_by must differ from the tested parent and the conditioning columns")
    if tested_parent in conditioning:
        raise ValueError("the tested parent cannot also be a conditioning column")

    outcome = formula.split("~", 1)[0].strip()
    node_role = "secondary" if stratify_by is None else "primary"
    settings: dict[str, Any] = {
        "formula": formula,
        "outcome": outcome,
        "tested_parent": tested_parent,
        "conditioning": list(conditioning),
        "stratify_by": stratify_by,
        "seed": int(seed),
        "permutations": int(permutations),
        "k_cmi_fraction": float(k_cmi_fraction),
        "k_perm": int(k_perm),
        "folds": int(folds),
        "residuals": residuals,
        "transform": transform,
        "role": node_role,
        "estimator": "CMIknn (Runge 2018; Frenzel-Pompe), max-norm, zero-radius tie rule (Gao 2017, Mesner-Shalizi 2021)",
        "null": "local C-preserving permutation of the tested parent within every stratum jointly (Runge 2018)",
        "weights_rule": "w_a = n_a / n, frozen across null replicates",
        "min_stratum_size": MIN_STRATUM_SIZE,
    }

    def unavailable(reason: str, **extra: Any) -> InformationCheckResult:
        return InformationCheckResult(
            statistic=math.nan,
            p_value=math.nan,
            status=STATUS_UNAVAILABLE,
            reason=reason,
            stratum_sizes=extra.get("sizes", {}),
            stratum_estimates={},
            weights={},
            k_cmi={},
            permutations=int(permutations),
            runtime_seconds=time.perf_counter() - started,
            settings=settings,
            n=int(extra.get("n", 0)),
        )

    if len(conditioning) > 1:
        return unavailable(f"at most one conditioning column is supported, got {len(conditioning)}")

    needed = [tested_parent, *conditioning] + ([stratify_by] if stratify_by is not None else [])
    missing = [name for name in needed if name not in data.columns]
    if missing:
        raise KeyError(f"columns not in data: {missing}")

    try:
        y_design, x_design = patsy.dmatrices(formula, data, return_type="dataframe", NA_action="drop")
    except patsy.PatsyError as exc:  # pragma: no cover - formula errors are caller bugs
        raise ValueError(f"cannot build the design for {formula!r}: {exc}") from exc
    if y_design.shape[1] != 1:
        return unavailable("the node outcome must be a single numeric column")

    frame = data.loc[y_design.index, needed]
    keep = frame.notna().all(axis=1).to_numpy()
    for name in needed:
        if not pd.api.types.is_numeric_dtype(frame[name]):
            return unavailable(f"column {name!r} is not numeric")
    frame = frame.loc[keep]
    y_vec = y_design.to_numpy(dtype=float)[keep, 0]
    X = x_design.to_numpy(dtype=float)[keep]
    n = int(y_vec.shape[0])

    parent = frame[tested_parent].to_numpy(dtype=float)
    parent_levels = np.unique(parent)
    discrete_parent = stratify_by is None and parent_levels.size <= 2
    settings["tested_parent_kind"] = "binary" if discrete_parent else "continuous"
    if stratify_by is None:
        settings["target"] = (
            f"I(r_{outcome} ; {tested_parent}"
            + (f" | {', '.join(conditioning)})" if conditioning else ")")
        )
    else:
        cond = ", ".join([stratify_by, *conditioning])
        settings["target"] = f"I(r_{outcome} ; {tested_parent} | {cond})"
    settings["experimental"] = bool(node_role == "secondary")
    if discrete_parent:
        settings["estimator"] += "; binary tested parent in discrete metric (Mesner-Shalizi 2021 mixed kNN)"
    if discrete_parent:
        if parent_levels.size != 2 or not np.isin(parent_levels, [0.0, 1.0]).all():
            return unavailable("a binary tested parent must have both levels 0 and 1", n=n)
        level_sizes = {_label(v): int((parent == v).sum()) for v in parent_levels}
        settings["tested_parent_level_sizes"] = level_sizes
        smallest = min(level_sizes.values())
        if smallest < MIN_STRATUM_SIZE or k_cmi_for(n, k_cmi_fraction) >= smallest:
            return unavailable(
                f"a tested-parent level has {smallest} rows; at least {MIN_STRATUM_SIZE} and more than k_CMI are required",
                n=n,
            )

    if stratify_by is None:
        strata_codes = np.zeros(n, dtype=np.int64)
        labels = ["all"]
    else:
        strat = frame[stratify_by].to_numpy(dtype=float)
        levels = np.unique(strat)
        if levels.size != 2 or not np.isin(levels, [0.0, 1.0]).all():
            return unavailable(
                f"stratifier {stratify_by!r} must have both levels 0 and 1 among retained rows",
                n=n,
                sizes={_label(v): int((strat == v).sum()) for v in levels},
            )
        strata_codes = np.searchsorted(levels, strat)
        labels = [_label(v) for v in levels]
    sizes = {label: int((strata_codes == code).sum()) for code, label in enumerate(labels)}
    small = [label for label, size in sizes.items() if size < MIN_STRATUM_SIZE]
    if small:
        return unavailable(
            f"stratum size below {MIN_STRATUM_SIZE} in stratum {', '.join(small)}", n=n, sizes=sizes
        )
    k_values = {label: k_cmi_for(size, k_cmi_fraction) for label, size in sizes.items()}
    too_big = [label for label in labels if k_values[label] >= sizes[label]]
    if too_big:
        return unavailable(f"k_CMI is not below the stratum size in stratum {', '.join(too_big)}", n=n, sizes=sizes)

    seq = np.random.SeedSequence(int(seed))
    fold_rng, perm_rng = (np.random.default_rng(s) for s in seq.spawn(2))
    resid, fail = _residuals(y_vec, X, residuals, folds, fold_rng)
    if resid is None:
        return unavailable(str(fail), n=n, sizes=sizes)
    cond_values = frame[conditioning[0]].to_numpy(dtype=float) if conditioning else None

    weights = {label: sizes[label] / n for label in labels}
    w_vec = np.array([weights[label] for label in labels])
    strata: list[tuple[_CMIStratum, np.ndarray, np.ndarray | None, int]] = []
    ties: dict[str, Any] = {}
    estimates: dict[str, float] = {}
    for code, label in enumerate(labels):
        rows = np.flatnonzero(strata_codes == code)
        r_t = _transform(resid[rows], transform)
        z_t = None if cond_values is None else _transform(cond_values[rows], transform)
        raw_parent = parent[rows]
        y_t = _discrete_coordinate(raw_parent) if discrete_parent else _transform(raw_parent, transform)
        stratum = _CMIStratum(r_t, z_t, k_values[label])
        estimate, zero_radius = stratum.estimate(y_t)
        estimates[label] = estimate
        neighbours = _neighbour_lists(z_t, rows.size, k_perm)
        strata.append((stratum, y_t, neighbours, rows.size))
        ties[label] = {
            "residual_tied_rows": _tie_count(resid[rows]),
            "parent_tied_rows": _tie_count(raw_parent),
            "conditioning_tied_rows": 0 if cond_values is None else _tie_count(cond_values[rows]),
            "zero_radius_points": zero_radius,
        }
    statistic = float(np.dot(w_vec, [estimates[label] for label in labels]))

    null = np.empty(permutations)
    for b in range(permutations):
        values = np.empty(len(strata))
        for s, (stratum, y_t, neighbours, size) in enumerate(strata):
            index = local_permutation(neighbours, size, perm_rng)
            values[s] = stratum.estimate(y_t[index])[0]
        null[b] = float(np.dot(w_vec, values))
    p_value = (1.0 + float(np.sum(null >= statistic))) / (1.0 + permutations)

    return InformationCheckResult(
        statistic=statistic,
        p_value=p_value,
        status=STATUS_OK,
        reason=None,
        stratum_sizes=sizes,
        stratum_estimates=estimates,
        weights=weights,
        k_cmi=k_values,
        permutations=int(permutations),
        runtime_seconds=time.perf_counter() - started,
        settings=settings,
        n=n,
        ties=ties,
        null_statistics=tuple(null.tolist()),
    )
