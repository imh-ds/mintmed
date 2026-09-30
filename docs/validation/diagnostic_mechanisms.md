# Task 18 diagnostic mechanisms (T18-S1)

This page records the nine generating mechanisms for the Task 18 Phase 1 diagnostic calibration, their population truths, and the TNIE point bias of the fixed base model measured with Mintmed.

- Code: `src/mintmed/experiments/diagnostic_mechanisms.py`
- Tests: `tests/integration/test_diagnostic_mechanisms.py`
- Bias measurement: `scripts/measure_mechanism_bias.py`

## Shared contract

- **Data.** Each dataset is a `pandas.DataFrame` with float columns `A`, `M`, `Y` and `C`:
  - `A` is binary 0/1, drawn independently with P(A = 1) = 0.5;
  - `C` is standard normal;
  - `M` and `Y` are continuous. Under N3 they are 7-point scores.
- **Generator.** `generate(mechanism_id, n, seed)` is deterministic in `seed`, which is an int or a `numpy.random.SeedSequence`. Draws are made in a fixed order: A, C, the mediator error, then the outcome error.
- **Seeds.** `dataset_seed(master, mechanism_id, n, replicate)` returns `SeedSequence([master, 1800, code, n, replicate])`. Each mechanism has a fixed integer `code` from 1 to 9, in table order. Python `hash()` is not used.
  - Calibration seed: 20261001.
  - Evaluation seed: 20261002.
- **Sample sizes.** `SAMPLE_SIZES = (100, 250, 500)`.
- **Mechanism fields.** Each `Mechanism` carries:
  - `id`, `code`, `category`, `description` and `equations`;
  - `parameters`, `outcome_formula` and `mediator_formula` (the analyst's base model, as patsy formulas);
  - `outcome_tested_parent = "M"` and `mediator_tested_parent = "A"`;
  - `truth` (TE, PNDE, TNIE), `truth_method` and `outcome_sd` (the marginal population SD of Y).
- **Truths.** Truths are natural effects for A = 1 versus A = 0, standardized over the population distribution of C, under the *true* generating model:
  - `TE = E[Y(1,M(1))] - E[Y(0,M(0))]`;
  - `PNDE = E[Y(1,M(0))] - E[Y(0,M(0))]`;
  - `TNIE = E[Y(1,M(1))] - E[Y(1,M(0))]`.

## Base structure

```
M = a0 + 0.5 A + g C + e_M,        g = 0.3, a0 = 0 unless stated
Y = 0.2 A + 0.5 M + 0.3 C + e_Y,   e_M, e_Y ~ N(0, 1) unless stated
```

## Mechanisms

| ID | Category | Generating equations (departure from base) | Base model (outcome; mediator) | TE | PNDE | TNIE | SD(Y) |
|---|---|---|---|---:|---:|---:|---:|
| N1_linear | effect_correct_null | base | `Y ~ A + M + C`; `M ~ A + C` | 0.4500 | 0.2000 | 0.2500 | 1.226 |
| N2_curved_declared | effect_correct_null | `M = 1 + 0.5A + 0.3C + e_M`; `Y = 0.2A + 0.25 M^2 + 0.3C + e_Y` | `Y ~ A + I(M ** 2) + C`; `M ~ A + C` | 0.5125 | 0.2000 | 0.3125 | 1.364 |
| N3_ties | effect_correct_null | `M = score7(M*; 0.25, 0.75)` with M* the base mediator; `Y = score7(0.2A + 0.5(0.25 + 0.75(M - 4)) + 0.3C + e_Y; 0.225, 0.8)` | `Y ~ A + M + C`; `M ~ A + C` | 0.5307 | 0.2392 | 0.2914 | 1.496 |
| N4_heavy_tail | effect_correct_null | base with `e_M, e_Y ~ t(4)/sqrt(2)` (unit variance, constant) | `Y ~ A + M + C`; `M ~ A + C` | 0.4500 | 0.2000 | 0.2500 | 1.225 |
| A1_c_only | attribution_null | g = 0.6; `Y = base + 0.4 C^2` | `Y ~ A + M + C`; `M ~ A + C` | 0.4500 | 0.2000 | 0.2500 | 1.408 |
| V1_outcome_variance | density_only | `e_Y ~ N(0, s_A^2)`, s_0 = 0.7, s_1 = 1.3 | `Y ~ A + M + C`; `M ~ A + C` | 0.4500 | 0.2000 | 0.2500 | 1.262 |
| E1_omitted_quadratic | effect_relevant | `e_M = (G - 4)/2`, G ~ Gamma(4, 1) (mean 0, variance 1, skewness 1); `Y = base + 0.2 M^2` | `Y ~ A + M + C`; `M ~ A + C` | 0.5000 | 0.2000 | 0.3000 | 1.435 |
| E2_omitted_interaction | effect_relevant | `Y = base + 0.4 A M` | `Y ~ A + M + C`; `M ~ A + C` | 0.6500 | 0.2000 | 0.4500 | 1.378 |
| E3_mediator_variance | effect_relevant | `M = 1 + 0.5A + 0.3C + s_A e_M`, s_0 = 0.8, s_1 = 1.2; `Y = 0.2A + 0.125 M^2 + 0.3C + e_Y` | `Y ~ A + I(M ** 2) + C`; `M ~ A + C` | 0.4563 | 0.2000 | 0.2563 | 1.172 |

The N3 truths to full precision are TE = 0.530691, PNDE = 0.239243 and TNIE = 0.291448. The E3 truths are TE = 0.45625 and TNIE = 0.25625.

`score7(v; c, s) = 4 + clip(floor((v - c)/s + 0.5), -3, 3)`. It maps a value to the integers 1 to 7. The end scores 1 and 7 each hold about 4% of M values and 5% of Y values.

### Truth accuracy

- **Closed form.** All mechanisms except N3 have closed-form truths. With `E[M(a) | C] = a0 + 0.5a + gC` and a quadratic outcome `b1 M + q M^2`:
  - TNIE = `0.5 b1 + q (0.25 + a0 + Var M(1) - Var M(0))`.
  - PNDE = `c1`, because no mechanism has an A x M term acting at M(0). E2 is the exception, where PNDE = `c1 + d E[M(0)] = c1` because E[M(0)] = 0.
- **N3.** N3 is computed exactly over the score probabilities of M and the expected Y score, and integrated over C by 64-point Gauss-Hermite quadrature. The 32-point and 64-point results agree to 1e-10. The truth is for the observed (rounded) scores: Y depends on M only through its observed score, so the 7-point M is itself the mediator.
- **Monte Carlo check.** `monte_carlo_truth` simulates the counterfactuals from the same structural equations. With 2,000,000 draws (one shared seed) it matches every truth within 2.5 MC SE, where every MC SE is at most 0.0004. For the N3 TNIE the gap is 0.0005 with SE 0.0003. The tests repeat the check with 400,000 draws for N2, N3, E1, E2 and E3.
- **Outcome SDs.** SD(Y) is the sample SD of `generate(id, 10**7, 0)`, with MC error below 1e-3.

### Design notes

1. **N2 and E3 use a pure quadratic outcome.** Mintmed's `TermKind.QUADRATIC` basis is `I(M ** 2)` alone, and a node cannot declare both a linear and a quadratic term for M (`duplicate_term`). N2 and E3 therefore use `Y = 0.2A + q M^2 + 0.3C + e_Y` with mediator intercept a0 = 1, so the curve has a linear component over the data. The declared base formula is `Y ~ A + I(M ** 2) + C`.
2. **E1 needs a skewed mediator error.** Take a Gaussian homoskedastic mediator whose mean is linear in (A, C), with P(A = 1) = 0.5. If `q M^2` is omitted from Y, the linear fit has **no** population TNIE bias.
   - Why: the OLS slope on M is `b1 + 2q E[M]`, and `0.5 (b1 + 2q E[M])` equals the true TNIE (Stein's lemma).
   - Consequence: the TNIE bias of an omitted quadratic comes only from non-Gaussian mediator shape, and equals `q a1 skew(e_M)`.
   - E1 therefore uses a standardized Gamma(4) error with skewness 1, which gives a population bias of 0.2 x 0.5 x 1 = +0.10.
   - The truth does not depend on the skew, and the mediator node's mean and variance remain correct. Only its density shape differs.
3. **E2.** The pooled slope on M converges to `b1 + 0.5 d`. The linear fit's TNIE limit is therefore `0.5 (0.5 + 0.2) = 0.35`, a bias of -0.10.
4. **E3.** The fitted single sigma is about `(s_0^2 + s_1^2)/2`. The g-formula TNIE therefore converges to `q (a1^2 + 2 a1 a0) = 0.15625`, a bias of `-q (s_1^2 - s_0^2) = -0.10`.
5. **A1.** The omitted `0.4 C^2` is a function of C only. The residual of M on (1, A, C) is `e_M`, which is independent of C^2, so the M slope and the TNIE stay consistent. Only the C coefficient and the intercept absorb the misfit.
6. **V1 and N4.** The mean model is correct, so OLS and the TNIE are unbiased. Only the error density is wrong.

### Mapping the base formulas to Mintmed

`mintmed_spec(mechanism_id)` builds the equivalent Mintmed specification: a Gaussian node `M` with linear terms A and C, and a Gaussian node `Y` with linear terms A and C plus M.

- **M term in Y.** The M term is `TermKind.LINEAR` for `Y ~ A + M + C` and `TermKind.QUADRATIC` for `Y ~ A + I(M ** 2) + C`.
- **Point estimates only.** The spec sets `bootstrap = 0`, so no bootstrap is run and `overall_status` is `point_only`.
- **Integration.** Integration is Gauss-Hermite, which Mintmed selects automatically for a single Gaussian mediator.
- **Check.** A test confirms that Mintmed's fitted Y coefficients equal statsmodels OLS on the patsy base formula for N1 and N2.

## Fixed-base-model bias, measured with Mintmed

Setup:

- **Datasets.** 200 datasets per mechanism and N, from `dataset_seed(20261001, id, n, r)` with r = 0 to 199 (calibration seed only).
- **Estimates.** Point estimates from `analyze_mediation` with the spec above.
- **Bias.** Bias is the mean of (estimate - truth). SE is the Monte Carlo SE (SD / sqrt(200)). "/ SD(Y)" divides the bias by the population outcome SD.
- **Failures.** No fit failed.
- **Environment.** Python 3.11.9, numpy 2.4.6, scipy 1.17.1, statsmodels 0.14.6, pandas 3.0.6, run locally on Windows. The run took 302 s for all 5,400 fits.

Command: `python scripts/measure_mechanism_bias.py --replicates 200`

| Mechanism | Category | N | TNIE bias (SE) | TNIE bias / SD(Y) | PNDE bias (SE) | TE bias (SE) |
|---|---|---:|---:|---:|---:|---:|
| N1_linear | effect_correct_null | 100 | -0.0001 (0.0087) | -0.000 | -0.0177 (0.0158) | -0.0178 (0.0175) |
| N1_linear | effect_correct_null | 250 | +0.0007 (0.0053) | +0.001 | +0.0053 (0.0091) | +0.0060 (0.0098) |
| N1_linear | effect_correct_null | 500 | +0.0018 (0.0034) | +0.001 | +0.0075 (0.0063) | +0.0093 (0.0066) |
| N2_curved_declared | effect_correct_null | 100 | +0.0014 (0.0096) | +0.001 | -0.0119 (0.0128) | -0.0106 (0.0160) |
| N2_curved_declared | effect_correct_null | 250 | -0.0069 (0.0055) | -0.005 | +0.0080 (0.0093) | +0.0011 (0.0101) |
| N2_curved_declared | effect_correct_null | 500 | +0.0091 (0.0044) | +0.007 | -0.0016 (0.0060) | +0.0075 (0.0069) |
| N3_ties | effect_correct_null | 100 | +0.0069 (0.0098) | +0.005 | -0.0184 (0.0190) | -0.0114 (0.0189) |
| N3_ties | effect_correct_null | 250 | +0.0011 (0.0057) | +0.001 | +0.0104 (0.0116) | +0.0115 (0.0122) |
| N3_ties | effect_correct_null | 500 | +0.0018 (0.0043) | +0.001 | -0.0095 (0.0081) | -0.0077 (0.0082) |
| N4_heavy_tail | effect_correct_null | 100 | -0.0018 (0.0093) | -0.001 | -0.0117 (0.0158) | -0.0136 (0.0160) |
| N4_heavy_tail | effect_correct_null | 250 | -0.0021 (0.0056) | -0.002 | -0.0025 (0.0090) | -0.0047 (0.0103) |
| N4_heavy_tail | effect_correct_null | 500 | +0.0073 (0.0035) | +0.006 | +0.0014 (0.0070) | +0.0086 (0.0077) |
| A1_c_only | attribution_null | 100 | +0.0090 (0.0090) | +0.006 | +0.0180 (0.0186) | +0.0270 (0.0192) |
| A1_c_only | attribution_null | 250 | +0.0002 (0.0057) | +0.000 | +0.0073 (0.0100) | +0.0075 (0.0106) |
| A1_c_only | attribution_null | 500 | -0.0006 (0.0038) | -0.000 | +0.0052 (0.0075) | +0.0046 (0.0082) |
| V1_outcome_variance | density_only | 100 | +0.0015 (0.0088) | +0.001 | +0.0208 (0.0139) | +0.0223 (0.0160) |
| V1_outcome_variance | density_only | 250 | +0.0031 (0.0050) | +0.002 | +0.0165 (0.0087) | +0.0196 (0.0097) |
| V1_outcome_variance | density_only | 500 | +0.0042 (0.0037) | +0.003 | -0.0099 (0.0067) | -0.0056 (0.0070) |
| E1_omitted_quadratic | effect_relevant | 100 | +0.0767 (0.0124) | +0.053 | -0.0829 (0.0156) | -0.0062 (0.0195) |
| E1_omitted_quadratic | effect_relevant | 250 | +0.1056 (0.0098) | +0.074 | -0.0843 (0.0100) | +0.0214 (0.0129) |
| E1_omitted_quadratic | effect_relevant | 500 | +0.1044 (0.0060) | +0.073 | -0.0971 (0.0070) | +0.0073 (0.0086) |
| E2_omitted_interaction | effect_relevant | 100 | -0.0961 (0.0108) | -0.070 | +0.0891 (0.0145) | -0.0070 (0.0183) |
| E2_omitted_interaction | effect_relevant | 250 | -0.1036 (0.0070) | -0.075 | +0.0878 (0.0097) | -0.0158 (0.0118) |
| E2_omitted_interaction | effect_relevant | 500 | -0.1025 (0.0048) | -0.074 | +0.0941 (0.0063) | -0.0084 (0.0080) |
| E3_mediator_variance | effect_relevant | 100 | -0.0898 (0.0062) | -0.077 | -0.0408 (0.0151) | -0.1306 (0.0152) |
| E3_mediator_variance | effect_relevant | 250 | -0.0938 (0.0038) | -0.080 | +0.0047 (0.0091) | -0.0891 (0.0094) |
| E3_mediator_variance | effect_relevant | 500 | -0.0957 (0.0023) | -0.082 | +0.0086 (0.0065) | -0.0872 (0.0067) |

**Reading.**

- **Effect-relevant mechanisms.** All three have TNIE bias of about 0.07-0.08 outcome SD (about 0.10 on the raw scale) at every N, and each is more than 6 MC SE from zero. This matches the population limits derived above.
  - A single N = 200,000 fit gives TNIE bias of +0.105 (E1), -0.097 (E2) and -0.098 (E3).
  - E1 is weaker at N = 100 (+0.077).
- **Effect-correct nulls, attribution null and density-only mechanism.** All TNIE biases are within ±0.01 raw (≤ 0.007 SD).
  - The only value above 2 SE is N2 at N = 500 (+0.0091, 2.1 SE), which is consistent with chance across 18 null cells.
  - At N = 200,000 the N2 bias is +0.0035, which is within the MC error of that single fit.
- **Scope.** This page reports point bias only. Coverage of the fixed base model is not measured here, because it needs the bootstrap. The plan's `effect_bias_reported` coverage item remains for a later run.
