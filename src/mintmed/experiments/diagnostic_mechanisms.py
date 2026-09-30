"""Generating mechanisms and population truths for the Task 18 diagnostic study.

Task 18 Phase 1 calibrates a status-only model-check diagnostic (information
arm versus a conventional lack-of-fit battery) on nine fixed mechanisms.  This
module owns only the data-generating side of that study:

* :data:`MECHANISMS` - the frozen mechanism table (category, generating
  equations, the analyst's *base* model as patsy formulas, and the population
  natural effects under the *true* generating model);
* :func:`generate` - one deterministic dataset with float columns ``A``, ``M``,
  ``Y`` and ``C``;
* :func:`dataset_seed` - the stable per-dataset seed;
* :func:`mintmed_spec` - the Mintmed specification equivalent to the base
  formulas (point estimates only, no bootstrap), used to measure the
  fixed-base-model TNIE bias.

Shared structure (departures are stated per mechanism)::

    A ~ Bernoulli(0.5)            (independent draws, randomized)
    C ~ N(0, 1)
    M = 0.5 A + 0.3 C + e_M       e_M ~ N(0, 1)
    Y = 0.2 A + 0.5 M + 0.3 C + e_Y,  e_Y ~ N(0, 1)

Truths are natural effects for the contrast A = 1 versus A = 0, standardized
over the population distribution of C:
``TE = E[Y(1, M(1))] - E[Y(0, M(0))]``, ``PNDE = E[Y(1, M(0))] - E[Y(0, M(0))]``
and ``TNIE = E[Y(1, M(1))] - E[Y(1, M(0))]``.  All truths are closed form,
except N3 (rounded variables), which is exact up to 64-point Gauss-Hermite
quadrature over C (error far below 1e-8; checked against Monte Carlo in the
tests).

N2 and E3 use a pure quadratic outcome ``Y = 0.2 A + q M^2 + 0.3 C + e_Y``
with mediator intercept 1, because Mintmed's quadratic basis is ``I(M ** 2)``
alone and a node cannot declare both a linear and a quadratic M term; the
declared base formula is ``Y ~ A + I(M ** 2) + C``.

Derivations behind the effect-relevant mechanisms (see
``docs/validation/diagnostic_mechanisms.md``):

* With a Gaussian, homoskedastic mediator whose mean is linear in (A, C) and
  P(A = 1) = 0.5, an omitted ``q M^2`` term gives **no** population TNIE bias
  for the linear fit (the OLS slope on M equals the average derivative,
  Stein's lemma).  E1 therefore uses a skewed mediator error (standardized
  Gamma(4), skewness 1); the TNIE bias of the linear fit is then
  ``q * a1 * skew(e_M) = 0.1``.  The truth does not depend on the skew.
* E2's linear fit converges to slope ``b1 + 0.5 d`` on M, a TNIE bias of
  ``-0.5 d a1 = -0.1``.  E3's single mediator sigma gives a TNIE bias of
  ``-q (s1^2 - s0^2) = -0.1``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from ..spec import (
    ComputationSpec,
    ContrastSpec,
    Family,
    ModelSpec,
    NodeSpec,
    Role,
    TemplateSpec,
    TermKind,
    TermSpec,
    VariableSpec,
    compile_template,
)

SAMPLE_SIZES: tuple[int, ...] = (100, 250, 500)
CATEGORIES: tuple[str, ...] = (
    "effect_correct_null",
    "attribution_null",
    "density_only",
    "effect_relevant",
)
COLUMNS: tuple[str, ...] = ("A", "M", "Y", "C")
CALIBRATION_SEED = 20261001
EVALUATION_SEED = 20261002
# Domain tag in every dataset seed so Task 18 streams never collide with the
# validation matrix (tag 1300 in ``mediation_validation.seed_pair``).
_SEED_DOMAIN = 1800

# Shared base parameters.
A1_PATH = 0.5  # A -> M
G_CM = 0.3  # C -> M
C1_DIRECT = 0.2  # A -> Y
B1_PATH = 0.5  # M -> Y
H_CY = 0.3  # C -> Y

# N3: explicit 7-point rounding.  score = 4 + clip(floor((v - center) / step + 0.5), -3, 3)
N3_M_CENTER, N3_M_STEP = 0.25, 0.75
N3_Y_CENTER, N3_Y_STEP = 0.225, 0.8


@dataclass(frozen=True, slots=True)
class Mechanism:
    """One frozen generating mechanism and the analyst's base model."""

    id: str
    code: int
    category: str
    description: str
    equations: str
    parameters: Mapping[str, float]
    outcome_formula: str
    mediator_formula: str
    truth: dict[str, float]
    truth_method: str
    outcome_sd: float
    outcome_tested_parent: str = "M"
    mediator_tested_parent: str = "A"
    notes: str = ""
    outcome_quadratic_m: bool = field(default=False)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


# ---------------------------------------------------------------------------
# Rounding (N3)


def score7(values: np.ndarray, center: float, step: float) -> np.ndarray:
    """Map a continuous value to the 7-point score 1..7 (half-up rounding)."""

    level = np.floor((np.asarray(values, dtype=float) - center) / step + 0.5)
    return 4.0 + np.clip(level, -3.0, 3.0)


def _score_thresholds(center: float, step: float) -> np.ndarray:
    """Cut points t_1..t_6: score = 1 + #{j : v >= t_j}."""

    return center + step * (np.arange(1, 7) - 3.5)


def _expected_score(mean: np.ndarray, center: float, step: float) -> np.ndarray:
    """E[score7(V)] for V ~ N(mean, 1)."""

    cuts = _score_thresholds(center, step)
    mean = np.asarray(mean, dtype=float)
    return 1.0 + norm.sf(cuts[None, :] - mean[..., None]).sum(axis=-1)


def _score_probabilities(mean: np.ndarray, center: float, step: float) -> np.ndarray:
    """P(score7(V) = s), s = 1..7, for V ~ N(mean, 1); shape (..., 7)."""

    cuts = _score_thresholds(center, step)
    mean = np.asarray(mean, dtype=float)
    cdf = norm.cdf(cuts[None, :] - mean[..., None])
    lower = np.concatenate([np.zeros(cdf.shape[:-1] + (1,)), cdf], axis=-1)
    upper = np.concatenate([cdf, np.ones(cdf.shape[:-1] + (1,))], axis=-1)
    return upper - lower


def _hermite(order: int = 64) -> tuple[np.ndarray, np.ndarray]:
    nodes, weights = np.polynomial.hermite.hermgauss(order)
    return np.sqrt(2.0) * nodes, weights / np.sqrt(np.pi)


def _n3_regime_mean(a_outcome: float, a_mediator: float, order: int = 64) -> float:
    """E[Y(a, M(a'))] for N3, integrated exactly over M and by quadrature over C."""

    c_values, c_weights = _hermite(order)
    m_star_mean = A1_PATH * a_mediator + G_CM * c_values
    probs = _score_probabilities(m_star_mean, N3_M_CENTER, N3_M_STEP)  # (nC, 7)
    scores = np.arange(1.0, 8.0)
    m_tilde = N3_M_CENTER + N3_M_STEP * (scores - 4.0)
    y_mean = (
        C1_DIRECT * a_outcome
        + B1_PATH * m_tilde[None, :]
        + H_CY * c_values[:, None]
    )  # (nC, 7)
    ey = _expected_score(y_mean, N3_Y_CENTER, N3_Y_STEP)
    return float(np.dot(c_weights, (probs * ey).sum(axis=1)))


@lru_cache(maxsize=None)
def _n3_truth(order: int = 64) -> tuple[float, float, float]:
    base = _n3_regime_mean(0.0, 0.0, order)
    direct = _n3_regime_mean(1.0, 0.0, order)
    total = _n3_regime_mean(1.0, 1.0, order)
    return total - base, direct - base, total - direct


def _truth(te: float, pnde: float, tnie: float) -> dict[str, float]:
    return {"TE": float(te), "PNDE": float(pnde), "TNIE": float(tnie)}


_LINEAR_TRUTH = (C1_DIRECT + A1_PATH * B1_PATH, C1_DIRECT, A1_PATH * B1_PATH)

# Mechanism-specific departures.
# N2 and E3 use a pure quadratic outcome, Y = 0.2 A + q M^2 + 0.3 C + e_Y, with
# a mediator intercept of 1 so the curve has a linear component over the data.
# Mintmed's quadratic basis is I(M ** 2) alone and a node cannot declare both a
# linear and a quadratic M term, so this is the curved model it can represent.
QUAD_M_INTERCEPT = 1.0
N2_Q = 0.25
A1_G = 0.6
A1_K = 0.4
V1_SD = (0.7, 1.3)
E1_Q = 0.2
E1_GAMMA_SHAPE = 4.0  # standardized Gamma(4, 1): mean 0, variance 1, skewness 1
E2_D = 0.4
E3_Q = 0.125
E3_SD = (0.8, 1.2)

_PURE_QUADRATIC = {"N2_curved_declared": N2_Q, "E3_mediator_variance": E3_Q}


def _quadratic_tnie(q: float, a0: float, b1: float, var_m1_minus_var_m0: float = 0.0) -> float:
    """TNIE for Y = ... + b1 M + q M^2 with E[M(a) | C] = a0 + a1 a + g C, E C = 0.

    E[M(1)^2] - E[M(0)^2] = a1^2 + 2 a1 a0 + Var(M(1)) - Var(M(0)).
    """

    return A1_PATH * b1 + q * (A1_PATH**2 + 2.0 * A1_PATH * a0 + var_m1_minus_var_m0)


_LINEAR_FORMULAS = ("Y ~ A + M + C", "M ~ A + C")
_QUADRATIC_FORMULAS = ("Y ~ A + I(M ** 2) + C", "M ~ A + C")


def _mechanism_table() -> dict[str, Mechanism]:
    n3 = _n3_truth()
    n2_tnie = _quadratic_tnie(N2_Q, QUAD_M_INTERCEPT, 0.0)
    e1_tnie = _quadratic_tnie(E1_Q, 0.0, B1_PATH)
    e3_tnie = _quadratic_tnie(E3_Q, QUAD_M_INTERCEPT, 0.0, E3_SD[1] ** 2 - E3_SD[0] ** 2)
    e2_tnie = A1_PATH * (B1_PATH + E2_D)
    rows = [
        Mechanism(
            id="N1_linear",
            code=1,
            category="effect_correct_null",
            description="linear M and Y, correct linear model",
            equations="M = 0.5A + 0.3C + e_M; Y = 0.2A + 0.5M + 0.3C + e_Y; e ~ N(0,1)",
            parameters={"a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(*_LINEAR_TRUTH),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["N1_linear"],
        ),
        Mechanism(
            id="N2_curved_declared",
            code=2,
            category="effect_correct_null",
            description="quadratic M -> Y, quadratic term declared",
            equations="M = 1 + 0.5A + 0.3C + e_M; Y = 0.2A + 0.25M^2 + 0.3C + e_Y; e ~ N(0,1)",
            parameters={"a0": QUAD_M_INTERCEPT, "a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT,
                        "h": H_CY, "q": N2_Q},
            outcome_formula=_QUADRATIC_FORMULAS[0],
            mediator_formula=_QUADRATIC_FORMULAS[1],
            truth=_truth(C1_DIRECT + n2_tnie, C1_DIRECT, n2_tnie),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["N2_curved_declared"],
            outcome_quadratic_m=True,
        ),
        Mechanism(
            id="N3_ties",
            code=3,
            category="effect_correct_null",
            description="N1 with Y and M rounded to a 7-point scale score",
            equations=(
                "M* = 0.5A + 0.3C + e_M; M = score7(M*; 0.25, 0.75); "
                "Y* = 0.2A + 0.5*(0.25 + 0.75(M - 4)) + 0.3C + e_Y; Y = score7(Y*; 0.225, 0.8); "
                "score7(v; c, s) = 4 + clip(floor((v - c)/s + 0.5), -3, 3)"
            ),
            parameters={
                "a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY,
                "m_center": N3_M_CENTER, "m_step": N3_M_STEP,
                "y_center": N3_Y_CENTER, "y_step": N3_Y_STEP,
            },
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(*n3),
            truth_method="exact_score_probabilities_gauss_hermite64_over_C",
            outcome_sd=_OUTCOME_SD["N3_ties"],
            notes=(
                "Truth is of the observed (rounded) scores: Y depends on M only through the "
                "observed score, so the mediator is the 7-point M itself."
            ),
        ),
        Mechanism(
            id="N4_heavy_tail",
            code=4,
            category="effect_correct_null",
            description="N1 with t(4) errors, constant variance",
            equations="as N1 with e_M, e_Y ~ t(4)/sqrt(2) (unit variance)",
            parameters={"a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY, "t_df": 4.0},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(*_LINEAR_TRUTH),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["N4_heavy_tail"],
            notes="Negative control: wrong Gaussian density, correct mean and constant variance.",
        ),
        Mechanism(
            id="A1_c_only",
            code=5,
            category="attribution_null",
            description="omitted C^2 in Y, C correlated with M",
            equations="M = 0.5A + 0.6C + e_M; Y = 0.2A + 0.5M + 0.3C + 0.4C^2 + e_Y; e ~ N(0,1)",
            parameters={"a1": A1_PATH, "g": A1_G, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY, "k": A1_K},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(*_LINEAR_TRUTH),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["A1_c_only"],
            notes="The omitted term is a function of C only; TNIE of the linear fit is consistent.",
        ),
        Mechanism(
            id="V1_outcome_variance",
            code=6,
            category="density_only",
            description="Var(Y | A, M, C) depends on A",
            equations="as N1 with e_Y ~ N(0, s_A^2), s_0 = 0.7, s_1 = 1.3",
            parameters={"a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY,
                        "sd_y_a0": V1_SD[0], "sd_y_a1": V1_SD[1]},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(*_LINEAR_TRUTH),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["V1_outcome_variance"],
        ),
        Mechanism(
            id="E1_omitted_quadratic",
            code=7,
            category="effect_relevant",
            description="quadratic M -> Y, analyst fits linear",
            equations=(
                "M = 0.5A + 0.3C + e_M, e_M = (G - 4)/2, G ~ Gamma(4, 1) (skewness 1); "
                "Y = 0.2A + 0.5M + 0.2M^2 + 0.3C + e_Y, e_Y ~ N(0,1)"
            ),
            parameters={"a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY,
                        "q": E1_Q, "gamma_shape": E1_GAMMA_SHAPE},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            truth=_truth(C1_DIRECT + e1_tnie, C1_DIRECT, e1_tnie),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["E1_omitted_quadratic"],
            notes=(
                "The mediator error is skewed because with a Gaussian mediator an omitted "
                "quadratic gives no population TNIE bias (Stein's lemma). Linear-fit TNIE "
                "limit = truth + q*a1*skew = truth + 0.1."
            ),
        ),
        Mechanism(
            id="E2_omitted_interaction",
            code=8,
            category="effect_relevant",
            description="A x M in Y, analyst omits it",
            equations="M = 0.5A + 0.3C + e_M; Y = 0.2A + 0.5M + 0.4A*M + 0.3C + e_Y; e ~ N(0,1)",
            parameters={"a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT, "b1": B1_PATH, "h": H_CY, "d": E2_D},
            outcome_formula=_LINEAR_FORMULAS[0],
            mediator_formula=_LINEAR_FORMULAS[1],
            # PNDE = c1 + d * E[M(0)] = c1 (E[M(0)] = 0).
            truth=_truth(C1_DIRECT + e2_tnie, C1_DIRECT, e2_tnie),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["E2_omitted_interaction"],
            notes="Linear-fit TNIE limit = a1*(b1 + 0.5d) = truth - 0.1.",
        ),
        Mechanism(
            id="E3_mediator_variance",
            code=9,
            category="effect_relevant",
            description=(
                "Var(M | A) depends on A with a quadratic M -> Y declared; "
                "the Gaussian family cannot represent it"
            ),
            equations=(
                "M = 1 + 0.5A + 0.3C + s_A e_M, s_0 = 0.8, s_1 = 1.2, e_M ~ N(0,1); "
                "Y = 0.2A + 0.125M^2 + 0.3C + e_Y, e_Y ~ N(0,1)"
            ),
            parameters={"a0": QUAD_M_INTERCEPT, "a1": A1_PATH, "g": G_CM, "c1": C1_DIRECT,
                        "h": H_CY, "q": E3_Q, "sd_m_a0": E3_SD[0], "sd_m_a1": E3_SD[1]},
            outcome_formula=_QUADRATIC_FORMULAS[0],
            mediator_formula=_QUADRATIC_FORMULAS[1],
            truth=_truth(C1_DIRECT + e3_tnie, C1_DIRECT, e3_tnie),
            truth_method="closed_form",
            outcome_sd=_OUTCOME_SD["E3_mediator_variance"],
            outcome_quadratic_m=True,
            notes=(
                "The fitted single sigma gives a TNIE limit of q*(a1^2 + 2*a1*a0) = truth - "
                "q*(s_1^2 - s_0^2) = truth - 0.1. The tested parent of the mediator node is A."
            ),
        ),
    ]
    return {row.id: row for row in rows}


# Marginal population SD of Y per mechanism: sample SD of ``generate(id, 10**7, 0)``
# (Monte Carlo error < 1e-3; regenerate with
# ``python scripts/measure_mechanism_bias.py --outcome-sd``).
_OUTCOME_SD: dict[str, float] = {
    "N1_linear": 1.2263,
    "N2_curved_declared": 1.3642,
    "N3_ties": 1.4963,
    "N4_heavy_tail": 1.2252,
    "A1_c_only": 1.4077,
    "V1_outcome_variance": 1.2624,
    "E1_omitted_quadratic": 1.4353,
    "E2_omitted_interaction": 1.3783,
    "E3_mediator_variance": 1.1723,
}

MECHANISMS: Mapping[str, Mechanism] = MappingProxyType(_mechanism_table())
MECHANISM_IDS: tuple[str, ...] = tuple(MECHANISMS)


def mechanism(mechanism_id: str) -> Mechanism:
    try:
        return MECHANISMS[mechanism_id]
    except KeyError as exc:
        raise ValueError(f"unknown mechanism {mechanism_id!r}") from exc


# ---------------------------------------------------------------------------
# Seeds and generation


def dataset_seed(master: int, mechanism_id: str, n: int, replicate: int) -> np.random.SeedSequence:
    """Return the stable seed for one dataset (no Python ``hash``)."""

    code = mechanism(mechanism_id).code
    if int(n) <= 0 or int(replicate) < 0:
        raise ValueError("n must be positive and replicate nonnegative")
    return np.random.SeedSequence([int(master), _SEED_DOMAIN, code, int(n), int(replicate)])


def _unit_t4(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.standard_t(4.0, size=n) / np.sqrt(2.0)


def _draw_errors(mid: str, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Standardized mediator and outcome errors (mean 0, variance 1), in that order."""

    if mid == "N4_heavy_tail":
        e_m = _unit_t4(rng, n)
    elif mid == "E1_omitted_quadratic":
        e_m = (rng.gamma(E1_GAMMA_SHAPE, 1.0, size=n) - E1_GAMMA_SHAPE) / np.sqrt(E1_GAMMA_SHAPE)
    else:
        e_m = rng.standard_normal(n)
    e_y = _unit_t4(rng, n) if mid == "N4_heavy_tail" else rng.standard_normal(n)
    return e_m, e_y


def _mediator(mid: str, a: np.ndarray | float, c: np.ndarray, e_m: np.ndarray) -> np.ndarray:
    """Structural equation for M given A, C and the standardized error."""

    a = np.asarray(a, dtype=float)
    intercept = QUAD_M_INTERCEPT if mid in _PURE_QUADRATIC else 0.0
    g = A1_G if mid == "A1_c_only" else G_CM
    scale = np.where(a == 1.0, E3_SD[1], E3_SD[0]) if mid == "E3_mediator_variance" else 1.0
    m = intercept + A1_PATH * a + g * c + scale * e_m
    if mid == "N3_ties":
        m = score7(m, N3_M_CENTER, N3_M_STEP)
    return m


def _outcome(mid: str, a: np.ndarray | float, m: np.ndarray, c: np.ndarray, e_y: np.ndarray) -> np.ndarray:
    """Structural equation for Y given A, M, C and the standardized error."""

    a = np.asarray(a, dtype=float)
    scale = np.where(a == 1.0, V1_SD[1], V1_SD[0]) if mid == "V1_outcome_variance" else 1.0
    base = C1_DIRECT * a + H_CY * c + scale * e_y
    if mid == "N3_ties":
        m_tilde = N3_M_CENTER + N3_M_STEP * (m - 4.0)
        return score7(base + B1_PATH * m_tilde, N3_Y_CENTER, N3_Y_STEP)
    if mid in _PURE_QUADRATIC:
        return base + _PURE_QUADRATIC[mid] * m**2
    if mid == "E1_omitted_quadratic":
        return base + B1_PATH * m + E1_Q * m**2
    if mid == "A1_c_only":
        return base + B1_PATH * m + A1_K * c**2
    if mid == "E2_omitted_interaction":
        return base + B1_PATH * m + E2_D * a * m
    return base + B1_PATH * m


def generate(mechanism_id: str, n: int, seed: int | np.random.SeedSequence) -> pd.DataFrame:
    """Generate one dataset with float columns A, M, Y, C (deterministic in ``seed``).

    Draw order is fixed: A, C, the mediator error, the outcome error.
    """

    mid = mechanism(mechanism_id).id
    n = int(n)
    if n <= 0:
        raise ValueError("n must be positive")
    if not isinstance(seed, (int, np.integer, np.random.SeedSequence)) or isinstance(seed, bool):
        raise TypeError("seed must be an int or numpy.random.SeedSequence")
    rng = np.random.default_rng(seed)
    a = (rng.random(n) < 0.5).astype(float)
    c = rng.standard_normal(n)
    e_m, e_y = _draw_errors(mid, rng, n)
    m = _mediator(mid, a, c, e_m)
    y = _outcome(mid, a, m, c, e_y)
    return pd.DataFrame(
        {"A": a, "M": np.asarray(m, dtype=float), "Y": np.asarray(y, dtype=float), "C": c},
        columns=list(COLUMNS),
    )


def monte_carlo_truth(mechanism_id: str, draws: int, seed: int = 0) -> dict[str, Any]:
    """Estimate TE/PNDE/TNIE by simulating counterfactuals from the true model.

    Uses the same structural equations as :func:`generate`; returns the
    estimates and their Monte Carlo standard errors.  Used to check the
    closed-form and quadrature truths.
    """

    mid = mechanism(mechanism_id).id
    n = int(draws)
    rng = np.random.default_rng(seed)
    c = rng.standard_normal(n)
    e_m, e_y = _draw_errors(mid, rng, n)
    m0, m1 = _mediator(mid, 0.0, c, e_m), _mediator(mid, 1.0, c, e_m)
    y00 = _outcome(mid, 0.0, m0, c, e_y)
    y10 = _outcome(mid, 1.0, m0, c, e_y)
    y11 = _outcome(mid, 1.0, m1, c, e_y)
    out: dict[str, Any] = {}
    for name, diff in (("TE", y11 - y00), ("PNDE", y10 - y00), ("TNIE", y11 - y10)):
        out[name] = float(diff.mean())
        out[f"{name}_se"] = float(diff.std(ddof=1) / np.sqrt(n))
    return out


# ---------------------------------------------------------------------------
# Mintmed base-model specification


def mintmed_spec(mechanism_id: str, *, seed: int = 0) -> ModelSpec:
    """Return the Mintmed spec equal to the mechanism's base formulas.

    ``Y ~ A + M + C`` maps to linear terms A, C, M; ``Y ~ A + I(M ** 2) + C``
    maps to linear A, C and a ``TermKind.QUADRATIC`` term on M (Mintmed's
    quadratic basis is ``I(M ** 2)`` alone).  ``M ~ A + C`` is a Gaussian node with linear A, C.
    ``bootstrap=0`` requests point estimates only.
    """

    spec = mechanism(mechanism_id)
    linear = TermKind.LINEAR
    m_kind = TermKind.QUADRATIC if spec.outcome_quadratic_m else linear
    outcome_terms = (TermSpec("A", linear), TermSpec("C", linear), TermSpec("M", m_kind))
    template = TemplateSpec(
        exposure=VariableSpec("A", Role.EXPOSURE, "binary", levels=(0, 1)),
        outcome=VariableSpec("Y", Role.OUTCOME, "continuous", family=Family.GAUSSIAN),
        mediators=(VariableSpec("M", Role.MEDIATOR, "continuous", family=Family.GAUSSIAN),),
        baseline=(VariableSpec("C", Role.COVARIATE, "continuous"),),
        nodes=(
            NodeSpec(
                response="M",
                family=Family.GAUSSIAN,
                intercept=True,
                terms=(TermSpec("A", linear), TermSpec("C", linear)),
            ),
            NodeSpec(
                response="Y",
                family=Family.GAUSSIAN,
                intercept=True,
                terms=outcome_terms,
            ),
        ),
        contrast=ContrastSpec(reference=0, comparison=1),
        computation=ComputationSpec(
            seed=int(seed),
            bootstrap=0,
            integration_draws=256,
            integration_tolerance=1e-3,
            max_seconds=600,
            memory_budget_mb=1024,
        ),
        scientific_edges=(("A", "M"), ("A", "Y"), ("M", "Y")),
        mediator_order=("M",),
        missing="error",
    )
    return compile_template(template)


__all__ = [
    "CALIBRATION_SEED",
    "CATEGORIES",
    "COLUMNS",
    "EVALUATION_SEED",
    "MECHANISMS",
    "MECHANISM_IDS",
    "Mechanism",
    "SAMPLE_SIZES",
    "dataset_seed",
    "generate",
    "mechanism",
    "mintmed_spec",
    "monte_carlo_truth",
    "score7",
]
