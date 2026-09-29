# Mintmed comparator benchmark (Task 17)

Configuration `mintmed_comparator_runtime_pilot` (hash `e07447b62d195278de3021b6fbcf90a78be8cf7e9ed0983d5dd558dfda621c06`), 90 raw rows keyed by `('tool', 'cell_id', 'replicate')`; complete grid: **True**.

## Operating characteristics

Coverage and zero exclusion use every attempted dataset as the denominator (a missing interval is a miss). Bias is |mean(estimate - truth)|, scaled by the population outcome SD in `abs_bias_sd`.

| Tool | Mode | Cell | Effect | Failures | Bias | MC SE | RMSE | Coverage [Wilson] | Width | Zero excl. | Runtime (s) |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| lavaan | primary | cell02_linear_n250 | PNDE | 0/5 | 0.04764 | 0.04985 | 0.1105 | 1 [0.5655, 1] | 0.5123 | 0.6 | 8.776 |
| lavaan | primary | cell02_linear_n250 | TE | 0/5 | 0.01271 | 0.03534 | 0.07181 | 1 [0.5655, 1] | 0.5621 | 1 | 8.776 |
| lavaan | primary | cell02_linear_n250 | TNIE | 0/5 | -0.03494 | 0.03562 | 0.07934 | 0.6 [0.2307, 0.8824] | 0.2544 | 1 | 8.776 |
| lavaan | primary | cell07_serial_three_n200 | PNDE | 0/5 | -0.05375 | 0.06781 | 0.1459 | 1 [0.5655, 1] | 0.5913 | 0 | 9.199 |
| lavaan | primary | cell07_serial_three_n200 | TE | 0/5 | -0.1109 | 0.04953 | 0.1487 | 1 [0.5655, 1] | 0.7246 | 0.6 | 9.199 |
| lavaan | primary | cell07_serial_three_n200 | TNIE | 0/5 | -0.05715 | 0.06178 | 0.1361 | 0.8 [0.3755, 0.9638] | 0.4719 | 0.8 | 9.199 |
| lavaan | primary | cell09_spline_n250 | PNDE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell09_spline_n250 | TE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell09_spline_n250 | TNIE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell10_moderated_n150 | TNIE_W0 | 0/5 | -0.001444 | 0.04129 | 0.08259 | 1 [0.5655, 1] | 0.3998 | 0.4 | 9.58 |
| lavaan | primary | cell10_moderated_n150 | TNIE_W1 | 0/5 | 0.02674 | 0.06568 | 0.1341 | 1 [0.5655, 1] | 0.6456 | 0.8 | 9.58 |
| lavaan | primary | cell10_moderated_n150 | TNIE_difference | 0/5 | 0.02818 | 0.08721 | 0.1767 | 1 [0.5655, 1] | 0.7816 | 0.6 | 9.58 |
| lavaan | primary | cell11_binary_mediator_n150 | PNDE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell11_binary_mediator_n150 | TE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell11_binary_mediator_n150 | TNIE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell16_b_path_only_n250 | PNDE | 0/5 | 0.08386 | 0.04241 | 0.1193 | 1 [0.5655, 1] | 0.4798 | 0.6 | 6.503 |
| lavaan | primary | cell16_b_path_only_n250 | TE | 0/5 | 0.1079 | 0.04378 | 0.139 | 1 [0.5655, 1] | 0.5386 | 0.6 | 6.503 |
| lavaan | primary | cell16_b_path_only_n250 | TNIE | 0/5 | 0.02403 | 0.01927 | 0.04542 | 1 [0.5655, 1] | 0.227 | 0 | 6.503 |
| lavaan | secondary | cell02_linear_n250 | PNDE | 0/5 | 0.04764 | 0.04985 | 0.1105 | 1 [0.5655, 1] | 0.5225 | 0.6 | 0.0478 |
| lavaan | secondary | cell02_linear_n250 | TE | 0/5 | 0.01271 | 0.03534 | 0.07181 | 1 [0.5655, 1] | 0.5537 | 1 | 0.0478 |
| lavaan | secondary | cell02_linear_n250 | TNIE | 0/5 | -0.03494 | 0.03562 | 0.07934 | 0.6 [0.2307, 0.8824] | 0.2499 | 1 | 0.0478 |
| lavaan | secondary | cell07_serial_three_n200 | PNDE | 0/5 | -0.05375 | 0.06781 | 0.1459 | 1 [0.5655, 1] | 0.5686 | 0.2 | 0.0494 |
| lavaan | secondary | cell07_serial_three_n200 | TE | 0/5 | -0.1109 | 0.04953 | 0.1487 | 1 [0.5655, 1] | 0.6981 | 0.8 | 0.0494 |
| lavaan | secondary | cell07_serial_three_n200 | TNIE | 0/5 | -0.05715 | 0.06178 | 0.1361 | 0.8 [0.3755, 0.9638] | 0.4575 | 0.8 | 0.0494 |
| lavaan | secondary | cell09_spline_n250 | PNDE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell09_spline_n250 | TE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell09_spline_n250 | TNIE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell10_moderated_n150 | TNIE_W0 | 0/5 | -0.001444 | 0.04129 | 0.08259 | 1 [0.5655, 1] | 0.3726 | 0.2 | 0.0484 |
| lavaan | secondary | cell10_moderated_n150 | TNIE_W1 | 0/5 | 0.02674 | 0.06568 | 0.1341 | 1 [0.5655, 1] | 0.6348 | 0.8 | 0.0484 |
| lavaan | secondary | cell10_moderated_n150 | TNIE_difference | 0/5 | 0.02818 | 0.08721 | 0.1767 | 1 [0.5655, 1] | 0.717 | 0.4 | 0.0484 |
| lavaan | secondary | cell11_binary_mediator_n150 | PNDE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell11_binary_mediator_n150 | TE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell11_binary_mediator_n150 | TNIE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell16_b_path_only_n250 | PNDE | 0/5 | 0.08386 | 0.04241 | 0.1193 | 1 [0.5655, 1] | 0.4807 | 0.6 | 0.0376 |
| lavaan | secondary | cell16_b_path_only_n250 | TE | 0/5 | 0.1079 | 0.04378 | 0.139 | 1 [0.5655, 1] | 0.5312 | 0.6 | 0.0376 |
| lavaan | secondary | cell16_b_path_only_n250 | TNIE | 0/5 | 0.02403 | 0.01927 | 0.04542 | 1 [0.5655, 1] | 0.223 | 0 | 0.0376 |
| mediation | primary | cell02_linear_n250 | PNDE | 0/5 | 0.04764 | 0.04985 | 0.1105 | 1 [0.5655, 1] | 0.5013 | 0.6 | 1.661 |
| mediation | primary | cell02_linear_n250 | TE | 0/5 | 0.01271 | 0.03534 | 0.07181 | 1 [0.5655, 1] | 0.5306 | 1 | 1.661 |
| mediation | primary | cell02_linear_n250 | TNIE | 0/5 | -0.03494 | 0.03562 | 0.07934 | 0.6 [0.2307, 0.8824] | 0.2506 | 1 | 1.661 |
| mediation | primary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell09_spline_n250 | PNDE | 0/5 | -0.07036 | 0.03729 | 0.1025 | 1 [0.5655, 1] | 0.4898 | 0 | 4.215 |
| mediation | primary | cell09_spline_n250 | TE | 0/5 | -0.05965 | 0.03877 | 0.09784 | 1 [0.5655, 1] | 0.5258 | 0.4 | 4.215 |
| mediation | primary | cell09_spline_n250 | TNIE | 0/5 | 0.01071 | 0.008203 | 0.01959 | 1 [0.5655, 1] | 0.2398 | 0.8 | 4.215 |
| mediation | primary | cell10_moderated_n150 | TNIE_W0 | 0/5 | -0.001444 | 0.04129 | 0.08259 | 1 [0.5655, 1] | 0.3993 | 0.4 | 5.194 |
| mediation | primary | cell10_moderated_n150 | TNIE_W1 | 0/5 | 0.02674 | 0.06568 | 0.1341 | 1 [0.5655, 1] | 0.6258 | 0.8 | 5.194 |
| mediation | primary | cell10_moderated_n150 | TNIE_difference | 0/5 | 0.02818 | 0.08721 | 0.1767 | 1 [0.5655, 1] | 0.7324 | 0.4 | 5.194 |
| mediation | primary | cell11_binary_mediator_n150 | PNDE | 0/5 | 0.03614 | 0.03075 | 0.07133 | 1 [0.5655, 1] | 0.6286 | 0 | 1.841 |
| mediation | primary | cell11_binary_mediator_n150 | TE | 0/5 | 0.006277 | 0.0322 | 0.06471 | 1 [0.5655, 1] | 0.6505 | 0.8 | 1.841 |
| mediation | primary | cell11_binary_mediator_n150 | TNIE | 0/5 | -0.02986 | 0.03459 | 0.07535 | 1 [0.5655, 1] | 0.2744 | 0.4 | 1.841 |
| mediation | primary | cell16_b_path_only_n250 | PNDE | 0/5 | 0.08386 | 0.04241 | 0.1193 | 1 [0.5655, 1] | 0.4693 | 0.6 | 2.262 |
| mediation | primary | cell16_b_path_only_n250 | TE | 0/5 | 0.1079 | 0.04378 | 0.139 | 1 [0.5655, 1] | 0.5208 | 0.6 | 2.262 |
| mediation | primary | cell16_b_path_only_n250 | TNIE | 0/5 | 0.02403 | 0.01927 | 0.04542 | 1 [0.5655, 1] | 0.2214 | 0 | 2.262 |
| mediation | secondary | cell02_linear_n250 | PNDE | 0/5 | 0.04596 | 0.04908 | 0.1084 | 1 [0.5655, 1] | 0.5276 | 0.6 | 1.781 |
| mediation | secondary | cell02_linear_n250 | TE | 0/5 | 0.01069 | 0.03474 | 0.0703 | 1 [0.5655, 1] | 0.5545 | 1 | 1.781 |
| mediation | secondary | cell02_linear_n250 | TNIE | 0/5 | -0.03527 | 0.03584 | 0.07989 | 0.6 [0.2307, 0.8824] | 0.2527 | 1 | 1.781 |
| mediation | secondary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell09_spline_n250 | PNDE | 0/5 | -0.06729 | 0.03791 | 0.1014 | 1 [0.5655, 1] | 0.4999 | 0 | 6.95 |
| mediation | secondary | cell09_spline_n250 | TE | 0/5 | -0.05291 | 0.04448 | 0.1035 | 1 [0.5655, 1] | 0.5286 | 0.4 | 6.95 |
| mediation | secondary | cell09_spline_n250 | TNIE | 0/5 | 0.01438 | 0.0117 | 0.02747 | 1 [0.5655, 1] | 0.2402 | 0.8 | 6.95 |
| mediation | secondary | cell10_moderated_n150 | TNIE_W0 | 0/5 | 0.0002992 | 0.04179 | 0.08358 | 1 [0.5655, 1] | 0.4148 | 0.2 | 5.468 |
| mediation | secondary | cell10_moderated_n150 | TNIE_W1 | 0/5 | 0.02654 | 0.06642 | 0.1355 | 1 [0.5655, 1] | 0.6285 | 0.8 | 5.468 |
| mediation | secondary | cell10_moderated_n150 | TNIE_difference | 0/5 | 0.02624 | 0.08805 | 0.178 | 1 [0.5655, 1] | 0.7386 | 0.6 | 5.468 |
| mediation | secondary | cell11_binary_mediator_n150 | PNDE | 0/5 | 0.03757 | 0.03195 | 0.07412 | 1 [0.5655, 1] | 0.6201 | 0.2 | 1.493 |
| mediation | secondary | cell11_binary_mediator_n150 | TE | 0/5 | 0.02287 | 0.0372 | 0.07783 | 1 [0.5655, 1] | 0.6562 | 0.8 | 1.493 |
| mediation | secondary | cell11_binary_mediator_n150 | TNIE | 0/5 | -0.0147 | 0.02746 | 0.05684 | 1 [0.5655, 1] | 0.2687 | 0.4 | 1.493 |
| mediation | secondary | cell16_b_path_only_n250 | PNDE | 0/5 | 0.08376 | 0.04324 | 0.1204 | 1 [0.5655, 1] | 0.485 | 0.6 | 2.279 |
| mediation | secondary | cell16_b_path_only_n250 | TE | 0/5 | 0.1073 | 0.0446 | 0.1396 | 1 [0.5655, 1] | 0.535 | 0.4 | 2.279 |
| mediation | secondary | cell16_b_path_only_n250 | TNIE | 0/5 | 0.02355 | 0.01933 | 0.04527 | 1 [0.5655, 1] | 0.2296 | 0 | 2.279 |
| mediation_reseed | primary | cell02_linear_n250 | PNDE | 0/5 | 0.04764 | 0.04985 | 0.1105 | 1 [0.5655, 1] | 0.5159 | 0.6 | 2.393 |
| mediation_reseed | primary | cell02_linear_n250 | TE | 0/5 | 0.01271 | 0.03534 | 0.07181 | 1 [0.5655, 1] | 0.5406 | 1 | 2.393 |
| mediation_reseed | primary | cell02_linear_n250 | TNIE | 0/5 | -0.03494 | 0.03562 | 0.07934 | 0.8 [0.3755, 0.9638] | 0.2505 | 1 | 2.393 |
| mediation_reseed | primary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell09_spline_n250 | PNDE | 0/5 | -0.07036 | 0.03729 | 0.1025 | 1 [0.5655, 1] | 0.4987 | 0 | 3.933 |
| mediation_reseed | primary | cell09_spline_n250 | TE | 0/5 | -0.07466 | 0.05355 | 0.1306 | 1 [0.5655, 1] | 0.5121 | 0.4 | 3.933 |
| mediation_reseed | primary | cell09_spline_n250 | TNIE | 0/5 | -0.004301 | 0.01916 | 0.03855 | 1 [0.5655, 1] | 0.2336 | 0.8 | 3.933 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_W0 | 0/5 | -0.001444 | 0.04129 | 0.08259 | 1 [0.5655, 1] | 0.4044 | 0.4 | 4.683 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_W1 | 0/5 | 0.02674 | 0.06568 | 0.1341 | 1 [0.5655, 1] | 0.6571 | 0.8 | 4.683 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_difference | 0/5 | 0.02818 | 0.08721 | 0.1767 | 1 [0.5655, 1] | 0.7632 | 0.4 | 4.683 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | PNDE | 0/5 | 0.03614 | 0.03075 | 0.07133 | 1 [0.5655, 1] | 0.6253 | 0 | 2.583 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | TE | 0/5 | 0.006991 | 0.03064 | 0.06167 | 1 [0.5655, 1] | 0.6487 | 0.8 | 2.583 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | TNIE | 0/5 | -0.02915 | 0.01006 | 0.03542 | 1 [0.5655, 1] | 0.2676 | 0.4 | 2.583 |
| mediation_reseed | primary | cell16_b_path_only_n250 | PNDE | 0/5 | 0.08386 | 0.04241 | 0.1193 | 1 [0.5655, 1] | 0.4856 | 0.4 | 2.372 |
| mediation_reseed | primary | cell16_b_path_only_n250 | TE | 0/5 | 0.1079 | 0.04378 | 0.139 | 1 [0.5655, 1] | 0.5416 | 0.4 | 2.372 |
| mediation_reseed | primary | cell16_b_path_only_n250 | TNIE | 0/5 | 0.02403 | 0.01927 | 0.04542 | 1 [0.5655, 1] | 0.2226 | 0 | 2.372 |

## Paired comparison with Mintmed (primary modes)

No Mintmed reference rows were supplied, so no paired comparison was made.
