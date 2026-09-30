"""Conventional lack-of-fit battery for the Task 18 Phase 1 comparator arm.

The battery is the *conventional* C2 diagnostic that the information-theoretic
residual check is compared against (``outline/06``, follow-up answer 1). It
must be a fair comparator, so it tests the same candidate mean terms that the
later model revision (C1) would offer for the tested parent, plus a variance
test, and combines them with a fixed Holm procedure into one warning.

Components
----------
Outcome node (e.g. ``"Y ~ A + M + C"``), tested parent ``M``:

``mean_curvature_M``
    Nested partial F test of the base design ``X0`` against
    ``X1 = [X0, B]`` where ``B`` is the patsy natural cubic regression spline
    basis ``cr(M, df=spline_df + 1) - 1``. With the default ``spline_df=3``
    this is a natural cubic spline carrying 3 df for M *excluding the
    intercept* (the R ``ns(M, df=3)`` convention): 4 knots at the M quantiles
    (0, 1/3, 2/3, 1), a basis spanning {1, M, two nonlinear directions}. The
    basis contains the constant and the linear M already in ``X0``, so the
    numerator df is not the column count but the rank increase
    ``rank(X1) - rank(X0)`` (2 for a linear base model). If the base model
    already declares curvature in M (e.g. ``I(M ** 2)``), the test is of the
    spline additions beyond the declared terms: the rank increase is then
    computed the same way and the F test is for whatever the spline adds that
    ``X0`` cannot already represent.
``mean_interaction_AM``
    Nested partial F test adding the product ``A * M``. When the base design
    already spans it (e.g. the formula contains ``A:M``), the rank increase is
    zero and the component is recorded as ``not_applicable`` and left out of
    the Holm family.
``variance_BP``
    Studentized (Koenker 1981) Breusch-Pagan test: regress the squared
    in-sample OLS residuals on ``[1, A, M, C]``; ``LM = n * R^2`` compared with
    chi-square on ``rank([1, A, M, C]) - 1`` df.

Mediator node (e.g. ``"M ~ A + C"``), tested parent ``A``:

``mean_curvature_C``
    As ``mean_curvature_M`` but for the spline in C. ``A`` is binary, so a
    curvature term in A does not exist and none is tested.
``variance_BP``
    As above, on ``[1, A, C]``.

With ``conditioning=()`` the C terms are simply absent (``mean_curvature_C``
is ``not_applicable``). More than one conditioning column returns
``diagnostic_unavailable`` to match the information arm's scope.

All tests use the in-sample residuals of the base OLS fit: F and
Breusch-Pagan tests are exact/asymptotic under in-sample fitting, so the
information arm's cross-fit splits are not shared here (not valid for these
tests). There is no randomness anywhere in the battery.
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
from scipy import stats
from statsmodels.formula.api import ols

__all__ = [
    "LackOfFitComponent",
    "LackOfFitResult",
    "holm_adjust",
    "lack_of_fit_battery",
    "nested_f_test",
]

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "diagnostic_unavailable"
COMPONENT_OK = "ok"
COMPONENT_NOT_APPLICABLE = "not_applicable"
_RANK_RTOL = 1e-10


@dataclass(frozen=True)
class LackOfFitComponent:
    """One test of the battery; ``status`` is ``ok`` or ``not_applicable``."""

    name: str
    statistic: float
    df: tuple[int, ...]
    p_value: float
    adjusted_p_value: float
    status: str = COMPONENT_OK
    reason: str = ""


@dataclass(frozen=True)
class LackOfFitResult:
    warning: bool
    min_adjusted_p: float
    components: tuple[LackOfFitComponent, ...]
    status: str
    reason: str
    runtime_seconds: float
    settings: Mapping[str, Any] = field(default_factory=dict)


def _rank(matrix: np.ndarray) -> int:
    """Numerical rank after scaling columns to unit norm (scale invariant)."""

    if matrix.size == 0:
        return 0
    norms = np.linalg.norm(matrix, axis=0)
    keep = norms > 0
    if not np.any(keep):
        return 0
    scaled = matrix[:, keep] / norms[keep]
    singular = np.linalg.svd(scaled, compute_uv=False)
    return int(np.sum(singular > _RANK_RTOL * singular[0] * max(scaled.shape)))


def _rss(design: np.ndarray, response: np.ndarray) -> float:
    coef, *_ = np.linalg.lstsq(design, response, rcond=None)
    resid = response - design @ coef
    return float(resid @ resid)


def nested_f_test(
    base: np.ndarray, added: np.ndarray, response: np.ndarray
) -> tuple[float, int, int, float]:
    """Partial F test of ``[base, added]`` against ``base``.

    The numerator df is the rank increase and the denominator df is
    ``n - rank([base, added])``, so redundant or collinear added columns do not
    inflate the df. Returns ``(F, df_num, df_den, p)``; ``df_num == 0`` means
    the added columns are already spanned (F and p are NaN).
    """

    base = np.asarray(base, dtype=float)
    full = np.column_stack([base, np.asarray(added, dtype=float)])
    response = np.asarray(response, dtype=float)
    rank0 = _rank(base)
    rank1 = _rank(full)
    df_num = rank1 - rank0
    df_den = response.shape[0] - rank1
    if df_num <= 0 or df_den <= 0:
        return math.nan, df_num, df_den, math.nan
    rss0 = _rss(base, response)
    rss1 = _rss(full, response)
    if rss1 <= 0:
        return math.inf, df_num, df_den, 0.0
    f_stat = ((rss0 - rss1) / df_num) / (rss1 / df_den)
    f_stat = max(f_stat, 0.0)
    return float(f_stat), df_num, df_den, float(stats.f.sf(f_stat, df_num, df_den))


def breusch_pagan_koenker(
    residuals: np.ndarray, regressors: np.ndarray
) -> tuple[float, int, float]:
    """Studentized Breusch-Pagan: ``n * R^2`` of ``e^2`` on ``[1, regressors]``."""

    residuals = np.asarray(residuals, dtype=float)
    n = residuals.shape[0]
    design = np.column_stack([np.ones(n), np.asarray(regressors, dtype=float)])
    df = _rank(design) - 1
    squared = residuals**2
    centered = squared - squared.mean()
    tss = float(centered @ centered)
    if df <= 0 or tss <= 0:
        return math.nan, df, math.nan
    r_squared = 1.0 - _rss(design, squared) / tss
    lm = float(n * max(r_squared, 0.0))
    return lm, df, float(stats.chi2.sf(lm, df))


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values (monotone, capped at 1)."""

    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for step, index in enumerate(order):
        running = max(running, min(1.0, (m - step) * p_values[index]))
        adjusted[index] = running
    return adjusted


def _spline_basis(values: pd.Series, spline_df: int) -> np.ndarray:
    frame = pd.DataFrame({"x": np.asarray(values, dtype=float)})
    return np.asarray(patsy.dmatrix(f"cr(x, df={spline_df + 1}) - 1", frame))


def _unavailable(reason: str, start: float, settings: dict[str, Any]) -> LackOfFitResult:
    return LackOfFitResult(
        warning=False,
        min_adjusted_p=math.nan,
        components=(),
        status=STATUS_UNAVAILABLE,
        reason=reason,
        runtime_seconds=time.perf_counter() - start,
        settings=settings,
    )


def _f_component(name: str, base, added, response) -> dict[str, Any]:
    f_stat, df_num, df_den, p = nested_f_test(base, added, response)
    if df_num <= 0:
        return {
            "name": name,
            "statistic": math.nan,
            "df": (df_num, df_den),
            "p_value": math.nan,
            "status": COMPONENT_NOT_APPLICABLE,
            "reason": "candidate terms already spanned by the base model",
        }
    return {
        "name": name,
        "statistic": f_stat,
        "df": (df_num, df_den),
        "p_value": p,
        "status": COMPONENT_OK,
        "reason": "",
    }


def lack_of_fit_battery(
    data: pd.DataFrame,
    formula: str,
    tested_parent: str,
    *,
    conditioning: Sequence[str] = ("C",),
    alpha: float = 0.05,
    spline_df: int = 3,
) -> LackOfFitResult:
    """Run the conventional lack-of-fit battery for one Gaussian node.

    ``tested_parent="M"`` checks an outcome node ``Y | A, M, C``;
    ``tested_parent="A"`` checks a mediator node ``M | A, C``. See the module
    docstring for the exact components.
    """

    start = time.perf_counter()
    conditioning = tuple(conditioning)
    settings: dict[str, Any] = {
        "formula": formula,
        "tested_parent": tested_parent,
        "conditioning": conditioning,
        "alpha": alpha,
        "spline_df": spline_df,
        "spline_basis": f"cr(x, df={spline_df + 1}) - 1",
        "variance_test": "Breusch-Pagan, studentized (Koenker)",
        "residuals": "in-sample OLS",
        "combination": "Holm",
    }
    if tested_parent not in {"A", "M"}:
        raise ValueError("tested_parent must be 'M' (outcome node) or 'A' (mediator node)")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1)")
    if len(conditioning) > 1:
        return _unavailable(
            "more than one conditioning covariate is outside the Phase 1 scope", start, settings
        )

    fit = ols(formula, data=data).fit()
    rows = data.loc[fit.model.data.row_labels]
    base = np.asarray(fit.model.exog, dtype=float)
    response = np.asarray(fit.model.endog, dtype=float)
    residuals = np.asarray(fit.resid, dtype=float)
    settings["n"] = int(response.shape[0])

    a = rows["A"].to_numpy(dtype=float)
    covariates = [rows[name].to_numpy(dtype=float) for name in conditioning]

    raw: list[dict[str, Any]] = []
    if tested_parent == "M":
        m = rows["M"].to_numpy(dtype=float)
        raw.append(
            _f_component("mean_curvature_M", base, _spline_basis(m, spline_df), response)
        )
        raw.append(_f_component("mean_interaction_AM", base, (a * m)[:, None], response))
        het = np.column_stack([a, m, *covariates])
    else:
        if covariates:
            raw.append(
                _f_component(
                    "mean_curvature_C",
                    base,
                    _spline_basis(pd.Series(covariates[0]), spline_df),
                    response,
                )
            )
        else:
            raw.append(
                {
                    "name": "mean_curvature_C",
                    "statistic": math.nan,
                    "df": (0, 0),
                    "p_value": math.nan,
                    "status": COMPONENT_NOT_APPLICABLE,
                    "reason": "no conditioning covariate",
                }
            )
        het = np.column_stack([a, *covariates])
    lm, df_bp, p_bp = breusch_pagan_koenker(residuals, het)
    raw.append(
        {
            "name": "variance_BP",
            "statistic": lm,
            "df": (df_bp,),
            "p_value": p_bp,
            "status": COMPONENT_OK if df_bp > 0 and not math.isnan(p_bp) else COMPONENT_NOT_APPLICABLE,
            "reason": "" if df_bp > 0 and not math.isnan(p_bp) else "degenerate residual variance",
        }
    )

    applicable = [item for item in raw if item["status"] == COMPONENT_OK]
    adjusted = holm_adjust([item["p_value"] for item in applicable])
    for item, adj in zip(applicable, adjusted):
        item["adjusted_p_value"] = adj
    components = tuple(
        LackOfFitComponent(
            name=item["name"],
            statistic=item["statistic"],
            df=tuple(int(v) for v in item["df"]),
            p_value=item["p_value"],
            adjusted_p_value=item.get("adjusted_p_value", math.nan),
            status=item["status"],
            reason=item["reason"],
        )
        for item in raw
    )
    if not applicable:
        return LackOfFitResult(
            warning=False,
            min_adjusted_p=math.nan,
            components=components,
            status=STATUS_UNAVAILABLE,
            reason="no applicable component",
            runtime_seconds=time.perf_counter() - start,
            settings=settings,
        )
    min_adjusted = float(min(adjusted))
    return LackOfFitResult(
        warning=bool(min_adjusted < alpha),
        min_adjusted_p=min_adjusted,
        components=components,
        status=STATUS_OK,
        reason="",
        runtime_seconds=time.perf_counter() - start,
        settings=settings,
    )
