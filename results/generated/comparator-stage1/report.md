# Mintmed comparator benchmark (Task 17)

Configuration `mintmed_comparator_benchmark` (hash `e6dc06ede1b1332056f41208654c55e2d217f021a82fbaa227e749ada5a4faf3`), 24000 raw rows keyed by `('tool', 'cell_id', 'replicate')`; complete grid: **True**.

## Operating characteristics

Coverage and zero exclusion use every attempted dataset as the denominator (a missing interval is a miss). Bias is |mean(estimate - truth)|, scaled by the population outcome SD in `abs_bias_sd`.

| Tool | Mode | Cell | Effect | Failures | Bias | MC SE | RMSE | Coverage [Wilson] | Width | Zero excl. | Runtime (s) |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| lavaan | primary | cell01_linear_n100 | PNDE | 0/500 | -0.0005542 | 0.009008 | 0.2012 | 0.956 [0.9343, 0.9708] | 0.8215 | 0.162 | 6.824 |
| lavaan | primary | cell01_linear_n100 | TE | 0/500 | 0.0007262 | 0.009627 | 0.2151 | 0.954 [0.9319, 0.9692] | 0.8836 | 0.508 | 6.824 |
| lavaan | primary | cell01_linear_n100 | TNIE | 0/500 | 0.00128 | 0.005017 | 0.1121 | 0.958 [0.9366, 0.9724] | 0.4647 | 0.67 | 6.824 |
| lavaan | primary | cell02_linear_n250 | PNDE | 0/500 | -0.00122 | 0.00573 | 0.128 | 0.948 [0.9249, 0.9643] | 0.5179 | 0.34 | 7.645 |
| lavaan | primary | cell02_linear_n250 | TE | 0/500 | 0.003095 | 0.005882 | 0.1314 | 0.962 [0.9414, 0.9755] | 0.5602 | 0.902 | 7.645 |
| lavaan | primary | cell02_linear_n250 | TNIE | 0/500 | 0.004315 | 0.003423 | 0.07658 | 0.932 [0.9065, 0.9509] | 0.2842 | 0.974 | 7.645 |
| lavaan | primary | cell03_no_a_to_m_n100 | PNDE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.956 [0.9343, 0.9708] | 0.7948 | 0.176 | 5.987 |
| lavaan | primary | cell03_no_a_to_m_n100 | TE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.956 [0.9343, 0.9708] | 0.7948 | 0.176 | 5.987 |
| lavaan | primary | cell03_no_a_to_m_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 5.987 |
| lavaan | primary | cell04_no_m_to_y_n100 | PNDE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.948 [0.9249, 0.9643] | 0.7895 | 0.158 | 5.77 |
| lavaan | primary | cell04_no_m_to_y_n100 | TE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.948 [0.9249, 0.9643] | 0.7895 | 0.158 | 5.77 |
| lavaan | primary | cell04_no_m_to_y_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 5.77 |
| lavaan | primary | cell05_no_mediation_n100 | PNDE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.95 [0.9272, 0.9659] | 0.7936 | 0.166 | 6.009 |
| lavaan | primary | cell05_no_mediation_n100 | TE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.95 [0.9272, 0.9659] | 0.7936 | 0.166 | 6.009 |
| lavaan | primary | cell05_no_mediation_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 6.009 |
| lavaan | primary | cell06_parallel_interaction_n150 | TNIE | not estimable: outcome is nonlinear in the mediators (M1 x M2): natural effects are not path products | | | | | | | |
| lavaan | primary | cell07_serial_three_n200 | PNDE | 0/500 | 0.003583 | 0.006929 | 0.1548 | 0.928 [0.9019, 0.9475] | 0.5896 | 0.286 | 8.349 |
| lavaan | primary | cell07_serial_three_n200 | TE | 0/500 | -0.0028 | 0.007838 | 0.1751 | 0.946 [0.9226, 0.9626] | 0.6824 | 0.872 | 8.349 |
| lavaan | primary | cell07_serial_three_n200 | TNIE | 0/500 | -0.006382 | 0.004889 | 0.1094 | 0.95 [0.9272, 0.9659] | 0.4354 | 0.926 | 8.349 |
| lavaan | primary | cell08_quadratic_n100 | PNDE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | primary | cell08_quadratic_n100 | TE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | primary | cell08_quadratic_n100 | TNIE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | primary | cell09_spline_n250 | PNDE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell09_spline_n250 | TE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell09_spline_n250 | TNIE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | primary | cell10_moderated_n150 | TNIE_W0 | 0/500 | 0.0007396 | 0.003905 | 0.08724 | 0.924 [0.8974, 0.9441] | 0.3506 | 0.154 | 10.14 |
| lavaan | primary | cell10_moderated_n150 | TNIE_W1 | 0/500 | -0.004695 | 0.00732 | 0.1636 | 0.95 [0.9272, 0.9659] | 0.6286 | 0.7 | 10.14 |
| lavaan | primary | cell10_moderated_n150 | TNIE_difference | 0/500 | -0.005434 | 0.008404 | 0.1878 | 0.94 [0.9156, 0.9577] | 0.7229 | 0.332 | 10.14 |
| lavaan | primary | cell11_binary_mediator_n150 | PNDE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell11_binary_mediator_n150 | TE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell11_binary_mediator_n150 | TNIE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell12_mixed_binary_serial_n250 | PNDE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell12_mixed_binary_serial_n250 | TE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell12_mixed_binary_serial_n250 | TNIE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | primary | cell13_a_path_only_n100 | PNDE | 0/500 | 0.007903 | 0.008882 | 0.1986 | 0.944 [0.9203, 0.961] | 0.8206 | 0.15 | 6.4 |
| lavaan | primary | cell13_a_path_only_n100 | TE | 0/500 | 0.005484 | 0.008529 | 0.1906 | 0.944 [0.9203, 0.961] | 0.7913 | 0.154 | 6.4 |
| lavaan | primary | cell13_a_path_only_n100 | TNIE | 0/500 | -0.002419 | 0.002525 | 0.05646 | 0.966 [0.9462, 0.9787] | 0.2455 | 0.034 | 6.4 |
| lavaan | primary | cell14_b_path_only_n100 | PNDE | 0/500 | 0.01279 | 0.009104 | 0.2038 | 0.946 [0.9226, 0.9626] | 0.7989 | 0.186 | 7.313 |
| lavaan | primary | cell14_b_path_only_n100 | TE | 0/500 | 0.01269 | 0.01044 | 0.2336 | 0.94 [0.9156, 0.9577] | 0.8868 | 0.158 | 7.313 |
| lavaan | primary | cell14_b_path_only_n100 | TNIE | 0/500 | -0.0001004 | 0.004627 | 0.1034 | 0.928 [0.9019, 0.9475] | 0.4194 | 0.072 | 7.313 |
| lavaan | primary | cell15_a_path_only_n250 | PNDE | 0/500 | -0.007357 | 0.005881 | 0.1316 | 0.946 [0.9226, 0.9626] | 0.5173 | 0.282 | 7.751 |
| lavaan | primary | cell15_a_path_only_n250 | TE | 0/500 | -0.006952 | 0.005622 | 0.1258 | 0.944 [0.9203, 0.961] | 0.4989 | 0.31 | 7.751 |
| lavaan | primary | cell15_a_path_only_n250 | TNIE | 0/500 | 0.000405 | 0.001484 | 0.03315 | 0.958 [0.9366, 0.9724] | 0.1386 | 0.042 | 7.751 |
| lavaan | primary | cell16_b_path_only_n250 | PNDE | 0/500 | 0.006773 | 0.005788 | 0.1295 | 0.948 [0.9249, 0.9643] | 0.4994 | 0.368 | 7.321 |
| lavaan | primary | cell16_b_path_only_n250 | TE | 0/500 | 0.002684 | 0.006245 | 0.1395 | 0.964 [0.9438, 0.9771] | 0.5582 | 0.298 | 7.321 |
| lavaan | primary | cell16_b_path_only_n250 | TNIE | 0/500 | -0.004089 | 0.002763 | 0.06186 | 0.958 [0.9366, 0.9724] | 0.2544 | 0.042 | 7.321 |
| lavaan | secondary | cell01_linear_n100 | PNDE | 0/500 | -0.0005542 | 0.009008 | 0.2012 | 0.954 [0.9319, 0.9692] | 0.798 | 0.178 | 0.03642 |
| lavaan | secondary | cell01_linear_n100 | TE | 0/500 | 0.0007262 | 0.009627 | 0.2151 | 0.95 [0.9272, 0.9659] | 0.8671 | 0.526 | 0.03642 |
| lavaan | secondary | cell01_linear_n100 | TNIE | 0/500 | 0.00128 | 0.005017 | 0.1121 | 0.952 [0.9296, 0.9675] | 0.4448 | 0.618 | 0.03642 |
| lavaan | secondary | cell02_linear_n250 | PNDE | 0/500 | -0.00122 | 0.00573 | 0.128 | 0.944 [0.9203, 0.961] | 0.5097 | 0.352 | 0.0397 |
| lavaan | secondary | cell02_linear_n250 | TE | 0/500 | 0.003095 | 0.005882 | 0.1314 | 0.962 [0.9414, 0.9755] | 0.5521 | 0.91 | 0.0397 |
| lavaan | secondary | cell02_linear_n250 | TNIE | 0/500 | 0.004315 | 0.003423 | 0.07658 | 0.93 [0.9042, 0.9492] | 0.2788 | 0.972 | 0.0397 |
| lavaan | secondary | cell03_no_a_to_m_n100 | PNDE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.956 [0.9343, 0.9708] | 0.7681 | 0.188 | 0.03416 |
| lavaan | secondary | cell03_no_a_to_m_n100 | TE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.956 [0.9343, 0.9708] | 0.7681 | 0.188 | 0.03416 |
| lavaan | secondary | cell03_no_a_to_m_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 0.03416 |
| lavaan | secondary | cell04_no_m_to_y_n100 | PNDE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.942 [0.9179, 0.9593] | 0.7749 | 0.156 | 0.03617 |
| lavaan | secondary | cell04_no_m_to_y_n100 | TE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.942 [0.9179, 0.9593] | 0.7749 | 0.156 | 0.03617 |
| lavaan | secondary | cell04_no_m_to_y_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 0.03617 |
| lavaan | secondary | cell05_no_mediation_n100 | PNDE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.948 [0.9249, 0.9643] | 0.7773 | 0.162 | 0.03818 |
| lavaan | secondary | cell05_no_mediation_n100 | TE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.948 [0.9249, 0.9643] | 0.7773 | 0.162 | 0.03818 |
| lavaan | secondary | cell05_no_mediation_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 0.03818 |
| lavaan | secondary | cell06_parallel_interaction_n150 | TNIE | not estimable: outcome is nonlinear in the mediators (M1 x M2): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell07_serial_three_n200 | PNDE | 0/500 | 0.003583 | 0.006929 | 0.1548 | 0.934 [0.9088, 0.9526] | 0.5752 | 0.308 | 0.04087 |
| lavaan | secondary | cell07_serial_three_n200 | TE | 0/500 | -0.0028 | 0.007838 | 0.1751 | 0.948 [0.9249, 0.9643] | 0.6716 | 0.892 | 0.04087 |
| lavaan | secondary | cell07_serial_three_n200 | TNIE | 0/500 | -0.006382 | 0.004889 | 0.1094 | 0.954 [0.9319, 0.9692] | 0.4219 | 0.916 | 0.04087 |
| lavaan | secondary | cell08_quadratic_n100 | PNDE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell08_quadratic_n100 | TE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell08_quadratic_n100 | TNIE | not estimable: outcome is nonlinear in M (M^2): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell09_spline_n250 | PNDE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell09_spline_n250 | TE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell09_spline_n250 | TNIE | not estimable: outcome is nonlinear in M (natural spline): natural effects are not path products | | | | | | | |
| lavaan | secondary | cell10_moderated_n150 | TNIE_W0 | 0/500 | 0.0007396 | 0.003905 | 0.08724 | 0.894 [0.8639, 0.918] | 0.3013 | 0.146 | 0.04479 |
| lavaan | secondary | cell10_moderated_n150 | TNIE_W1 | 0/500 | -0.004695 | 0.00732 | 0.1636 | 0.944 [0.9203, 0.961] | 0.6333 | 0.59 | 0.04479 |
| lavaan | secondary | cell10_moderated_n150 | TNIE_difference | 0/500 | -0.005434 | 0.008404 | 0.1878 | 0.934 [0.9088, 0.9526] | 0.6839 | 0.31 | 0.04479 |
| lavaan | secondary | cell11_binary_mediator_n150 | PNDE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell11_binary_mediator_n150 | TE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell11_binary_mediator_n150 | TNIE | not estimable: binary mediator: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell12_mixed_binary_serial_n250 | PNDE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell12_mixed_binary_serial_n250 | TE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell12_mixed_binary_serial_n250 | TNIE | not estimable: binary mediator and outcome: lavaan's probit latent-response effects are a different estimand | | | | | | | |
| lavaan | secondary | cell13_a_path_only_n100 | PNDE | 0/500 | 0.007903 | 0.008882 | 0.1986 | 0.95 [0.9272, 0.9659] | 0.7997 | 0.15 | 0.03447 |
| lavaan | secondary | cell13_a_path_only_n100 | TE | 0/500 | 0.005484 | 0.008529 | 0.1906 | 0.944 [0.9203, 0.961] | 0.7752 | 0.156 | 0.03447 |
| lavaan | secondary | cell13_a_path_only_n100 | TNIE | 0/500 | -0.002419 | 0.002525 | 0.05646 | 0.988 [0.9741, 0.9945] | 0.2155 | 0.012 | 0.03447 |
| lavaan | secondary | cell14_b_path_only_n100 | PNDE | 0/500 | 0.01279 | 0.009104 | 0.2038 | 0.95 [0.9272, 0.9659] | 0.7766 | 0.208 | 0.0385 |
| lavaan | secondary | cell14_b_path_only_n100 | TE | 0/500 | 0.01269 | 0.01044 | 0.2336 | 0.934 [0.9088, 0.9526] | 0.8671 | 0.18 | 0.0385 |
| lavaan | secondary | cell14_b_path_only_n100 | TNIE | 0/500 | -0.0001004 | 0.004627 | 0.1034 | 0.948 [0.9249, 0.9643] | 0.3953 | 0.052 | 0.0385 |
| lavaan | secondary | cell15_a_path_only_n250 | PNDE | 0/500 | -0.007357 | 0.005881 | 0.1316 | 0.948 [0.9249, 0.9643] | 0.5081 | 0.306 | 0.04009 |
| lavaan | secondary | cell15_a_path_only_n250 | TE | 0/500 | -0.006952 | 0.005622 | 0.1258 | 0.94 [0.9156, 0.9577] | 0.4923 | 0.336 | 0.04009 |
| lavaan | secondary | cell15_a_path_only_n250 | TNIE | 0/500 | 0.000405 | 0.001484 | 0.03315 | 0.978 [0.961, 0.9877] | 0.1301 | 0.022 | 0.04009 |
| lavaan | secondary | cell16_b_path_only_n250 | PNDE | 0/500 | 0.006773 | 0.005788 | 0.1295 | 0.946 [0.9226, 0.9626] | 0.4938 | 0.38 | 0.0384 |
| lavaan | secondary | cell16_b_path_only_n250 | TE | 0/500 | 0.002684 | 0.006245 | 0.1395 | 0.958 [0.9366, 0.9724] | 0.552 | 0.302 | 0.0384 |
| lavaan | secondary | cell16_b_path_only_n250 | TNIE | 0/500 | -0.004089 | 0.002763 | 0.06186 | 0.966 [0.9462, 0.9787] | 0.2482 | 0.034 | 0.0384 |
| mediation | primary | cell01_linear_n100 | PNDE | 0/500 | -0.0005542 | 0.009008 | 0.2012 | 0.954 [0.9319, 0.9692] | 0.8048 | 0.17 | 1.837 |
| mediation | primary | cell01_linear_n100 | TE | 0/500 | 0.0007262 | 0.009627 | 0.2151 | 0.952 [0.9296, 0.9675] | 0.8714 | 0.532 | 1.837 |
| mediation | primary | cell01_linear_n100 | TNIE | 0/500 | 0.00128 | 0.005017 | 0.1121 | 0.954 [0.9319, 0.9692] | 0.4545 | 0.696 | 1.837 |
| mediation | primary | cell02_linear_n250 | PNDE | 0/500 | -0.00122 | 0.00573 | 0.128 | 0.944 [0.9203, 0.961] | 0.5065 | 0.338 | 2.095 |
| mediation | primary | cell02_linear_n250 | TE | 0/500 | 0.003095 | 0.005882 | 0.1314 | 0.95 [0.9272, 0.9659] | 0.5485 | 0.912 | 2.095 |
| mediation | primary | cell02_linear_n250 | TNIE | 0/500 | 0.004315 | 0.003423 | 0.07658 | 0.93 [0.9042, 0.9492] | 0.2777 | 0.972 | 2.095 |
| mediation | primary | cell03_no_a_to_m_n100 | PNDE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.952 [0.9296, 0.9675] | 0.7765 | 0.186 | 1.604 |
| mediation | primary | cell03_no_a_to_m_n100 | TE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.952 [0.9296, 0.9675] | 0.7765 | 0.186 | 1.604 |
| mediation | primary | cell03_no_a_to_m_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.604 |
| mediation | primary | cell04_no_m_to_y_n100 | PNDE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.938 [0.9133, 0.956] | 0.7762 | 0.168 | 1.693 |
| mediation | primary | cell04_no_m_to_y_n100 | TE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.938 [0.9133, 0.956] | 0.7762 | 0.168 | 1.693 |
| mediation | primary | cell04_no_m_to_y_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.693 |
| mediation | primary | cell05_no_mediation_n100 | PNDE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.942 [0.9179, 0.9593] | 0.775 | 0.176 | 1.755 |
| mediation | primary | cell05_no_mediation_n100 | TE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.942 [0.9179, 0.9593] | 0.775 | 0.176 | 1.755 |
| mediation | primary | cell05_no_mediation_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.755 |
| mediation | primary | cell06_parallel_interaction_n150 | TNIE | not estimable: joint TNIE of two interacting parallel mediators is outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell08_quadratic_n100 | PNDE | 0/500 | 0.005555 | 0.009445 | 0.2111 | 0.932 [0.9065, 0.9509] | 0.7814 | 0.194 | 2.302 |
| mediation | primary | cell08_quadratic_n100 | TE | 0/500 | 0.003849 | 0.01007 | 0.2249 | 0.952 [0.9296, 0.9675] | 0.8323 | 0.32 | 2.302 |
| mediation | primary | cell08_quadratic_n100 | TNIE | 0/500 | -0.001706 | 0.003205 | 0.07163 | 0.976 [0.9585, 0.9862] | 0.292 | 0.264 | 2.302 |
| mediation | primary | cell09_spline_n250 | PNDE | 0/500 | 0.005079 | 0.005653 | 0.1264 | 0.956 [0.9343, 0.9708] | 0.5094 | 0.354 | 3.533 |
| mediation | primary | cell09_spline_n250 | TE | 0/500 | 0.008438 | 0.00598 | 0.1339 | 0.956 [0.9343, 0.9708] | 0.5242 | 0.642 | 3.533 |
| mediation | primary | cell09_spline_n250 | TNIE | 0/500 | 0.003359 | 0.002483 | 0.05557 | 0.982 [0.9661, 0.9905] | 0.2245 | 0.55 | 3.533 |
| mediation | primary | cell10_moderated_n150 | TNIE_W0 | 0/500 | 0.0007396 | 0.003905 | 0.08724 | 0.912 [0.8839, 0.9338] | 0.3417 | 0.184 | 5.186 |
| mediation | primary | cell10_moderated_n150 | TNIE_W1 | 0/500 | -0.004695 | 0.00732 | 0.1636 | 0.938 [0.9133, 0.956] | 0.6118 | 0.718 | 5.186 |
| mediation | primary | cell10_moderated_n150 | TNIE_difference | 0/500 | -0.005434 | 0.008404 | 0.1878 | 0.936 [0.911, 0.9543] | 0.7054 | 0.342 | 5.186 |
| mediation | primary | cell11_binary_mediator_n150 | PNDE | 0/500 | -0.01201 | 0.007353 | 0.1647 | 0.948 [0.9249, 0.9643] | 0.6443 | 0.214 | 2.27 |
| mediation | primary | cell11_binary_mediator_n150 | TE | 0/500 | -0.009153 | 0.008095 | 0.181 | 0.942 [0.9179, 0.9593] | 0.6701 | 0.432 | 2.27 |
| mediation | primary | cell11_binary_mediator_n150 | TNIE | 0/500 | 0.002861 | 0.00338 | 0.07555 | 0.972 [0.9536, 0.9832] | 0.276 | 0.482 | 2.27 |
| mediation | primary | cell12_mixed_binary_serial_n250 | PNDE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell12_mixed_binary_serial_n250 | TE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell12_mixed_binary_serial_n250 | TNIE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | primary | cell13_a_path_only_n100 | PNDE | 0/500 | 0.007903 | 0.008882 | 0.1986 | 0.942 [0.9179, 0.9593] | 0.8024 | 0.156 | 1.689 |
| mediation | primary | cell13_a_path_only_n100 | TE | 0/500 | 0.005484 | 0.008529 | 0.1906 | 0.944 [0.9203, 0.961] | 0.7754 | 0.154 | 1.689 |
| mediation | primary | cell13_a_path_only_n100 | TNIE | 0/500 | -0.002419 | 0.002525 | 0.05646 | 0.96 [0.939, 0.974] | 0.2386 | 0.04 | 1.689 |
| mediation | primary | cell14_b_path_only_n100 | PNDE | 0/500 | 0.01279 | 0.009104 | 0.2038 | 0.95 [0.9272, 0.9659] | 0.7809 | 0.208 | 1.958 |
| mediation | primary | cell14_b_path_only_n100 | TE | 0/500 | 0.01269 | 0.01044 | 0.2336 | 0.936 [0.911, 0.9543] | 0.8661 | 0.188 | 1.958 |
| mediation | primary | cell14_b_path_only_n100 | TNIE | 0/500 | -0.0001004 | 0.004627 | 0.1034 | 0.918 [0.8906, 0.939] | 0.409 | 0.082 | 1.958 |
| mediation | primary | cell15_a_path_only_n250 | PNDE | 0/500 | -0.007357 | 0.005881 | 0.1316 | 0.93 [0.9042, 0.9492] | 0.506 | 0.314 | 2.087 |
| mediation | primary | cell15_a_path_only_n250 | TE | 0/500 | -0.006952 | 0.005622 | 0.1258 | 0.936 [0.911, 0.9543] | 0.4898 | 0.332 | 2.087 |
| mediation | primary | cell15_a_path_only_n250 | TNIE | 0/500 | 0.000405 | 0.001484 | 0.03315 | 0.946 [0.9226, 0.9626] | 0.1352 | 0.054 | 2.087 |
| mediation | primary | cell16_b_path_only_n250 | PNDE | 0/500 | 0.006773 | 0.005788 | 0.1295 | 0.946 [0.9226, 0.9626] | 0.4908 | 0.394 | 1.926 |
| mediation | primary | cell16_b_path_only_n250 | TE | 0/500 | 0.002684 | 0.006245 | 0.1395 | 0.954 [0.9319, 0.9692] | 0.5488 | 0.31 | 1.926 |
| mediation | primary | cell16_b_path_only_n250 | TNIE | 0/500 | -0.004089 | 0.002763 | 0.06186 | 0.956 [0.9343, 0.9708] | 0.2508 | 0.044 | 1.926 |
| mediation | secondary | cell01_linear_n100 | PNDE | 0/500 | -0.0008652 | 0.009021 | 0.2015 | 0.958 [0.9366, 0.9724] | 0.8096 | 0.158 | 1.676 |
| mediation | secondary | cell01_linear_n100 | TE | 0/500 | 0.000658 | 0.009638 | 0.2153 | 0.956 [0.9343, 0.9708] | 0.884 | 0.51 | 1.676 |
| mediation | secondary | cell01_linear_n100 | TNIE | 0/500 | 0.001523 | 0.005027 | 0.1123 | 0.958 [0.9366, 0.9724] | 0.4574 | 0.69 | 1.676 |
| mediation | secondary | cell02_linear_n250 | PNDE | 0/500 | -0.001573 | 0.005728 | 0.128 | 0.944 [0.9203, 0.961] | 0.5119 | 0.346 | 2.14 |
| mediation | secondary | cell02_linear_n250 | TE | 0/500 | 0.00305 | 0.005889 | 0.1316 | 0.966 [0.9462, 0.9787] | 0.5561 | 0.912 | 2.14 |
| mediation | secondary | cell02_linear_n250 | TNIE | 0/500 | 0.004623 | 0.003423 | 0.07661 | 0.938 [0.9133, 0.956] | 0.2814 | 0.974 | 2.14 |
| mediation | secondary | cell03_no_a_to_m_n100 | PNDE | 0/500 | -0.002556 | 0.008669 | 0.1937 | 0.958 [0.9366, 0.9724] | 0.7864 | 0.18 | 1.545 |
| mediation | secondary | cell03_no_a_to_m_n100 | TE | 0/500 | -0.002556 | 0.008669 | 0.1937 | 0.958 [0.9366, 0.9724] | 0.7864 | 0.18 | 1.545 |
| mediation | secondary | cell03_no_a_to_m_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.545 |
| mediation | secondary | cell04_no_m_to_y_n100 | PNDE | 0/500 | -0.007476 | 0.009101 | 0.2034 | 0.942 [0.9179, 0.9593] | 0.7811 | 0.162 | 1.689 |
| mediation | secondary | cell04_no_m_to_y_n100 | TE | 0/500 | -0.007476 | 0.009101 | 0.2034 | 0.942 [0.9179, 0.9593] | 0.7811 | 0.162 | 1.689 |
| mediation | secondary | cell04_no_m_to_y_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.689 |
| mediation | secondary | cell05_no_mediation_n100 | PNDE | 0/500 | -0.009706 | 0.009136 | 0.2043 | 0.946 [0.9226, 0.9626] | 0.7856 | 0.166 | 1.777 |
| mediation | secondary | cell05_no_mediation_n100 | TE | 0/500 | -0.009706 | 0.009136 | 0.2043 | 0.946 [0.9226, 0.9626] | 0.7856 | 0.166 | 1.777 |
| mediation | secondary | cell05_no_mediation_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.777 |
| mediation | secondary | cell06_parallel_interaction_n150 | TNIE | not estimable: joint TNIE of two interacting parallel mediators is outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell08_quadratic_n100 | PNDE | 0/500 | 0.00528 | 0.009422 | 0.2105 | 0.938 [0.9133, 0.956] | 0.7885 | 0.196 | 3.315 |
| mediation | secondary | cell08_quadratic_n100 | TE | 0/500 | 0.002563 | 0.009686 | 0.2164 | 0.95 [0.9272, 0.9659] | 0.8422 | 0.316 | 3.315 |
| mediation | secondary | cell08_quadratic_n100 | TNIE | 0/500 | -0.002717 | 0.002571 | 0.0575 | 0.976 [0.9585, 0.9862] | 0.2984 | 0.238 | 3.315 |
| mediation | secondary | cell09_spline_n250 | PNDE | 0/500 | 0.005172 | 0.005673 | 0.1268 | 0.956 [0.9343, 0.9708] | 0.5141 | 0.362 | 6.109 |
| mediation | secondary | cell09_spline_n250 | TE | 0/500 | 0.007246 | 0.005858 | 0.1311 | 0.96 [0.939, 0.974] | 0.5317 | 0.64 | 6.109 |
| mediation | secondary | cell09_spline_n250 | TNIE | 0/500 | 0.002074 | 0.002121 | 0.04742 | 0.986 [0.9714, 0.9932] | 0.227 | 0.526 | 6.109 |
| mediation | secondary | cell10_moderated_n150 | TNIE_W0 | 0/500 | 0.0005116 | 0.003899 | 0.08711 | 0.928 [0.9019, 0.9475] | 0.3473 | 0.174 | 5.205 |
| mediation | secondary | cell10_moderated_n150 | TNIE_W1 | 0/500 | -0.00509 | 0.007313 | 0.1634 | 0.946 [0.9226, 0.9626] | 0.6205 | 0.714 | 5.205 |
| mediation | secondary | cell10_moderated_n150 | TNIE_difference | 0/500 | -0.005601 | 0.008397 | 0.1877 | 0.944 [0.9203, 0.961] | 0.7171 | 0.344 | 5.205 |
| mediation | secondary | cell11_binary_mediator_n150 | PNDE | 0/500 | -0.01183 | 0.007361 | 0.1649 | 0.964 [0.9438, 0.9771] | 0.651 | 0.21 | 1.942 |
| mediation | secondary | cell11_binary_mediator_n150 | TE | 0/500 | -0.009899 | 0.007877 | 0.1762 | 0.944 [0.9203, 0.961] | 0.6794 | 0.414 | 1.942 |
| mediation | secondary | cell11_binary_mediator_n150 | TNIE | 0/500 | 0.001928 | 0.002858 | 0.06386 | 0.976 [0.9585, 0.9862] | 0.2734 | 0.454 | 1.942 |
| mediation | secondary | cell12_mixed_binary_serial_n250 | PNDE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell12_mixed_binary_serial_n250 | TE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell12_mixed_binary_serial_n250 | TNIE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation | secondary | cell13_a_path_only_n100 | PNDE | 0/500 | 0.007904 | 0.008878 | 0.1985 | 0.95 [0.9272, 0.9659] | 0.8146 | 0.152 | 1.579 |
| mediation | secondary | cell13_a_path_only_n100 | TE | 0/500 | 0.005516 | 0.008522 | 0.1905 | 0.948 [0.9249, 0.9643] | 0.7923 | 0.15 | 1.579 |
| mediation | secondary | cell13_a_path_only_n100 | TNIE | 0/500 | -0.002388 | 0.002533 | 0.05663 | 0.96 [0.939, 0.974] | 0.241 | 0.04 | 1.579 |
| mediation | secondary | cell14_b_path_only_n100 | PNDE | 0/500 | 0.0127 | 0.009097 | 0.2036 | 0.954 [0.9319, 0.9692] | 0.7906 | 0.194 | 1.87 |
| mediation | secondary | cell14_b_path_only_n100 | TE | 0/500 | 0.01246 | 0.01045 | 0.2337 | 0.938 [0.9133, 0.956] | 0.8875 | 0.16 | 1.87 |
| mediation | secondary | cell14_b_path_only_n100 | TNIE | 0/500 | -0.0002356 | 0.004636 | 0.1036 | 0.926 [0.8997, 0.9458] | 0.4134 | 0.074 | 1.87 |
| mediation | secondary | cell15_a_path_only_n250 | PNDE | 0/500 | -0.007209 | 0.005897 | 0.1319 | 0.94 [0.9156, 0.9577] | 0.5084 | 0.314 | 2.113 |
| mediation | secondary | cell15_a_path_only_n250 | TE | 0/500 | -0.006815 | 0.005637 | 0.1261 | 0.938 [0.9133, 0.956] | 0.4939 | 0.33 | 2.113 |
| mediation | secondary | cell15_a_path_only_n250 | TNIE | 0/500 | 0.0003941 | 0.001489 | 0.03327 | 0.946 [0.9226, 0.9626] | 0.1369 | 0.054 | 2.113 |
| mediation | secondary | cell16_b_path_only_n250 | PNDE | 0/500 | 0.006516 | 0.005788 | 0.1295 | 0.95 [0.9272, 0.9659] | 0.4952 | 0.384 | 1.987 |
| mediation | secondary | cell16_b_path_only_n250 | TE | 0/500 | 0.002464 | 0.006242 | 0.1395 | 0.954 [0.9319, 0.9692] | 0.5545 | 0.3 | 1.987 |
| mediation | secondary | cell16_b_path_only_n250 | TNIE | 0/500 | -0.004052 | 0.002768 | 0.06196 | 0.954 [0.9319, 0.9692] | 0.2526 | 0.046 | 1.987 |
| mediation_reseed | primary | cell01_linear_n100 | PNDE | 0/500 | -0.0005542 | 0.009008 | 0.2012 | 0.95 [0.9272, 0.9659] | 0.8065 | 0.18 | 1.84 |
| mediation_reseed | primary | cell01_linear_n100 | TE | 0/500 | 0.0007262 | 0.009627 | 0.2151 | 0.948 [0.9249, 0.9643] | 0.8695 | 0.524 | 1.84 |
| mediation_reseed | primary | cell01_linear_n100 | TNIE | 0/500 | 0.00128 | 0.005017 | 0.1121 | 0.958 [0.9366, 0.9724] | 0.4543 | 0.682 | 1.84 |
| mediation_reseed | primary | cell02_linear_n250 | PNDE | 0/500 | -0.00122 | 0.00573 | 0.128 | 0.94 [0.9156, 0.9577] | 0.508 | 0.352 | 2.108 |
| mediation_reseed | primary | cell02_linear_n250 | TE | 0/500 | 0.003095 | 0.005882 | 0.1314 | 0.95 [0.9272, 0.9659] | 0.5492 | 0.908 | 2.108 |
| mediation_reseed | primary | cell02_linear_n250 | TNIE | 0/500 | 0.004315 | 0.003423 | 0.07658 | 0.92 [0.8929, 0.9407] | 0.2772 | 0.974 | 2.108 |
| mediation_reseed | primary | cell03_no_a_to_m_n100 | PNDE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.952 [0.9296, 0.9675] | 0.7747 | 0.178 | 1.632 |
| mediation_reseed | primary | cell03_no_a_to_m_n100 | TE | 0/500 | -0.003205 | 0.008665 | 0.1936 | 0.952 [0.9296, 0.9675] | 0.7747 | 0.178 | 1.632 |
| mediation_reseed | primary | cell03_no_a_to_m_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.632 |
| mediation_reseed | primary | cell04_no_m_to_y_n100 | PNDE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.944 [0.9203, 0.961] | 0.7735 | 0.164 | 1.708 |
| mediation_reseed | primary | cell04_no_m_to_y_n100 | TE | 0/500 | -0.007812 | 0.009077 | 0.2029 | 0.944 [0.9203, 0.961] | 0.7735 | 0.164 | 1.708 |
| mediation_reseed | primary | cell04_no_m_to_y_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.708 |
| mediation_reseed | primary | cell05_no_mediation_n100 | PNDE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.936 [0.911, 0.9543] | 0.7766 | 0.178 | 1.759 |
| mediation_reseed | primary | cell05_no_mediation_n100 | TE | 0/500 | -0.009115 | 0.009133 | 0.2042 | 0.936 [0.911, 0.9543] | 0.7766 | 0.178 | 1.759 |
| mediation_reseed | primary | cell05_no_mediation_n100 | TNIE | 0/500 | 0 | 0 | 0 | 1 [0.9924, 1] | 0 | 0 | 1.759 |
| mediation_reseed | primary | cell06_parallel_interaction_n150 | TNIE | not estimable: joint TNIE of two interacting parallel mediators is outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell07_serial_three_n200 | PNDE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell07_serial_three_n200 | TE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell07_serial_three_n200 | TNIE | not estimable: three serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell08_quadratic_n100 | PNDE | 0/500 | 0.005555 | 0.009445 | 0.2111 | 0.932 [0.9065, 0.9509] | 0.781 | 0.196 | 2.35 |
| mediation_reseed | primary | cell08_quadratic_n100 | TE | 0/500 | 0.005945 | 0.009854 | 0.2202 | 0.958 [0.9366, 0.9724] | 0.832 | 0.332 | 2.35 |
| mediation_reseed | primary | cell08_quadratic_n100 | TNIE | 0/500 | 0.0003894 | 0.003274 | 0.07315 | 0.974 [0.956, 0.9847] | 0.2934 | 0.26 | 2.35 |
| mediation_reseed | primary | cell09_spline_n250 | PNDE | 0/500 | 0.005079 | 0.005653 | 0.1264 | 0.954 [0.9319, 0.9692] | 0.5124 | 0.36 | 3.598 |
| mediation_reseed | primary | cell09_spline_n250 | TE | 0/500 | 0.006671 | 0.006069 | 0.1357 | 0.95 [0.9272, 0.9659] | 0.5263 | 0.632 | 3.598 |
| mediation_reseed | primary | cell09_spline_n250 | TNIE | 0/500 | 0.001592 | 0.00244 | 0.05452 | 0.976 [0.9585, 0.9862] | 0.225 | 0.544 | 3.598 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_W0 | 0/500 | 0.0007396 | 0.003905 | 0.08724 | 0.908 [0.8795, 0.9303] | 0.3419 | 0.172 | 4.744 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_W1 | 0/500 | -0.004695 | 0.00732 | 0.1636 | 0.944 [0.9203, 0.961] | 0.6138 | 0.714 | 4.744 |
| mediation_reseed | primary | cell10_moderated_n150 | TNIE_difference | 0/500 | -0.005434 | 0.008404 | 0.1878 | 0.938 [0.9133, 0.956] | 0.7046 | 0.336 | 4.744 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | PNDE | 0/500 | -0.01201 | 0.007353 | 0.1647 | 0.956 [0.9343, 0.9708] | 0.643 | 0.216 | 2.29 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | TE | 0/500 | -0.007396 | 0.007969 | 0.1782 | 0.94 [0.9156, 0.9577] | 0.6698 | 0.442 | 2.29 |
| mediation_reseed | primary | cell11_binary_mediator_n150 | TNIE | 0/500 | 0.004618 | 0.003307 | 0.07402 | 0.974 [0.956, 0.9847] | 0.2752 | 0.468 | 2.29 |
| mediation_reseed | primary | cell12_mixed_binary_serial_n250 | PNDE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell12_mixed_binary_serial_n250 | TE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell12_mixed_binary_serial_n250 | TNIE | not estimable: two serial mediators are outside mediate()'s single-mediator design | | | | | | | |
| mediation_reseed | primary | cell13_a_path_only_n100 | PNDE | 0/500 | 0.007903 | 0.008882 | 0.1986 | 0.938 [0.9133, 0.956] | 0.8038 | 0.146 | 1.807 |
| mediation_reseed | primary | cell13_a_path_only_n100 | TE | 0/500 | 0.005484 | 0.008529 | 0.1906 | 0.936 [0.911, 0.9543] | 0.7749 | 0.156 | 1.807 |
| mediation_reseed | primary | cell13_a_path_only_n100 | TNIE | 0/500 | -0.002419 | 0.002525 | 0.05646 | 0.95 [0.9272, 0.9659] | 0.2389 | 0.05 | 1.807 |
| mediation_reseed | primary | cell14_b_path_only_n100 | PNDE | 0/500 | 0.01279 | 0.009104 | 0.2038 | 0.94 [0.9156, 0.9577] | 0.7845 | 0.198 | 1.97 |
| mediation_reseed | primary | cell14_b_path_only_n100 | TE | 0/500 | 0.01269 | 0.01044 | 0.2336 | 0.932 [0.9065, 0.9509] | 0.8686 | 0.182 | 1.97 |
| mediation_reseed | primary | cell14_b_path_only_n100 | TNIE | 0/500 | -0.0001004 | 0.004627 | 0.1034 | 0.93 [0.9042, 0.9492] | 0.4066 | 0.07 | 1.97 |
| mediation_reseed | primary | cell15_a_path_only_n250 | PNDE | 0/500 | -0.007357 | 0.005881 | 0.1316 | 0.942 [0.9179, 0.9593] | 0.5058 | 0.31 | 2.121 |
| mediation_reseed | primary | cell15_a_path_only_n250 | TE | 0/500 | -0.006952 | 0.005622 | 0.1258 | 0.934 [0.9088, 0.9526] | 0.4885 | 0.31 | 2.121 |
| mediation_reseed | primary | cell15_a_path_only_n250 | TNIE | 0/500 | 0.000405 | 0.001484 | 0.03315 | 0.95 [0.9272, 0.9659] | 0.1352 | 0.05 | 2.121 |
| mediation_reseed | primary | cell16_b_path_only_n250 | PNDE | 0/500 | 0.006773 | 0.005788 | 0.1295 | 0.94 [0.9156, 0.9577] | 0.4919 | 0.378 | 1.923 |
| mediation_reseed | primary | cell16_b_path_only_n250 | TE | 0/500 | 0.002684 | 0.006245 | 0.1395 | 0.946 [0.9226, 0.9626] | 0.5478 | 0.314 | 1.923 |
| mediation_reseed | primary | cell16_b_path_only_n250 | TNIE | 0/500 | -0.004089 | 0.002763 | 0.06186 | 0.952 [0.9296, 0.9675] | 0.2497 | 0.048 | 1.923 |

## Paired comparison with Mintmed (primary modes)

Tier = the frozen Stage 1 charter rules (docs/validation/comparator_charter.md). Decision agreement is judged on the upper bound of the excess disagreement over the `mediation` vs `mediation_reseed` noise floor (floor 0 where it was not measured, marked `none`); any pair significant in opposite directions is substantive; sign agreement, coverage loss (point and upper) and false-positive excess on observed values; power loss, width ratio and bias excess on the upper bound of a paired bootstrap interval. Cells show point (upper bound) or point [lower, upper]. `n/a` marks a check that does not apply. `S3 tier` is the original T17-S3 judging, descriptive only.

| Tool | Cell | Effect | Pairs | Disagreement pp | Floor pp | Excess pp [lower, upper] | Opposite sig. | Sign agr. (sig. pairs) | Bias excess SD (upper) | Coverage loss pp (upper) | FP excess pp (upper) | Power loss pp (upper) | Width ratio (upper) | Mintmed cov. | Tier | Failed checks | S3 tier |
|---|---|---|---:|---:|---:|---|---:|---|---|---|---|---|---|---:|---|---|---|
| lavaan | cell01_linear_n100 | PNDE | 500 | 3.6 | 3.8 | -0.2 [-2.4, 2] | 0 | 1 (93) | 2.901e-17 (4.811e-17) | 0.6 (2) | n/a (n/a) | -1.2 (0.4) | 0.9774 (0.9832) | 0.95 | **negligible** | - | substantive |
| lavaan | cell01_linear_n100 | TE | 500 | 5.6 | 6 | -0.4 [-2.8, 2] | 0 | 1 (274) | -6.951e-17 (9.056e-17) | 0.6 (2) | n/a (n/a) | -2.4 (-0.4) | 0.9792 (0.9854) | 0.948 | **negligible** | - | substantive |
| lavaan | cell01_linear_n100 | TNIE | 500 | 5.2 | 5 | 0.2 [-2.2, 2.6] | 0 | 1 (353) | -4.227e-17 (5.518e-17) | 0.8 (1.8) | n/a (n/a) | -2 (0) | 0.9772 (0.9834) | 0.95 | **negligible** | - | substantive |
| lavaan | cell02_linear_n250 | PNDE | 500 | 5.8 | 5.4 | 0.4 [-2, 2.8] | 0 | 1 (186) | 7.959e-18 (3.29e-17) | 0.4 (2) | n/a (n/a) | -0.6 (1.6) | 0.9789 (0.9844) | 0.944 | **negligible** | - | substantive |
| lavaan | cell02_linear_n250 | TE | 500 | 2.8 | 1.6 | 1.2 [-0.2, 2.6] | 0 | 1 (461) | -6.12e-17 (8.065e-17) | 0.2 (1.4) | n/a (n/a) | -1.2 (0.4) | 0.9781 (0.9835) | 0.96 | **negligible** | - | negligible |
| lavaan | cell02_linear_n250 | TNIE | 500 | 1.4 | 1.4 | 0 [-1, 1] | 0 | 1 (490) | -4.811e-17 (5.417e-17) | 0.4 (1.6) | n/a (n/a) | 0.2 (1.2) | 0.9755 (0.9817) | 0.928 | **negligible** | - | negligible |
| lavaan | cell03_no_a_to_m_n100 | PNDE | 500 | 3 | 4.8 | -1.8 [-3.6, 0] | 0 | 1 (96) | 2.725e-17 (4.913e-17) | -0.2 (0.4) | n/a (n/a) | -0.2 (1.4) | 0.9815 (0.9872) | 0.958 | **negligible** | - | substantive |
| lavaan | cell03_no_a_to_m_n100 | TE | 500 | 3 | 4.8 | -1.8 [-3.6, 0] | 0 | 1 (96) | 2.725e-17 (4.877e-17) | -0.2 (0.4) | n/a (n/a) | -0.2 (1.4) | 0.9815 (0.9873) | 0.958 | **negligible** | - | substantive |
| lavaan | cell03_no_a_to_m_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| lavaan | cell04_no_m_to_y_n100 | PNDE | 500 | 4 | 3.6 | 0.4 [-1.8, 2.4] | 0 | 1 (89) | 3.473e-17 (5.789e-17) | 0.8 (1.8) | n/a (n/a) | 0 (1.8) | 0.9813 (0.9873) | 0.94 | **negligible** | - | substantive |
| lavaan | cell04_no_m_to_y_n100 | TE | 500 | 4 | 3.6 | 0.4 [-1.6, 2.6] | 0 | 1 (89) | 3.473e-17 (5.954e-17) | 0.8 (1.8) | n/a (n/a) | 0 (1.8) | 0.9813 (0.9873) | 0.94 | **negligible** | - | substantive |
| lavaan | cell04_no_m_to_y_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| lavaan | cell05_no_mediation_n100 | PNDE | 500 | 3 | 3 | 0 [-1.8, 1.8] | 0 | 1 (91) | 3.804e-17 (5.789e-17) | 0.8 (2.2) | n/a (n/a) | -0.2 (1.2) | 0.9799 (0.9865) | 0.942 | **negligible** | - | substantive |
| lavaan | cell05_no_mediation_n100 | TE | 500 | 3 | 3 | 0 [-1.8, 1.8] | 0 | 1 (91) | 3.804e-17 (5.789e-17) | 0.8 (2) | n/a (n/a) | -0.2 (1.4) | 0.9799 (0.9861) | 0.942 | **negligible** | - | substantive |
| lavaan | cell05_no_mediation_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| lavaan | cell07_serial_three_n200 | PNDE | 500 | 5 | none | 5 [3.2, 7] | 0 | 1 (159) | -3.163e-17 (5.098e-17) | 0.6 (2.4) | n/a (n/a) | -1.4 (0.6) | 0.9796 (0.9852) | 0.922 | **tolerable** | decision_excess | substantive |
| lavaan | cell07_serial_three_n200 | TE | 500 | 3.2 | none | 3.2 [1.8, 4.8] | 0 | 1 (448) | 1.099e-16 (1.427e-16) | 0.8 (2) | n/a (n/a) | -1.6 (0) | 0.9755 (0.9808) | 0.938 | **negligible** | - | tolerable |
| lavaan | cell07_serial_three_n200 | TNIE | 500 | 2 | none | 2 [1, 3.4] | 0 | 1 (469) | 7.924e-17 (1.02e-16) | 0.4 (1.4) | n/a (n/a) | -0.4 (0.8) | 0.9807 (0.9868) | 0.946 | **negligible** | - | negligible |
| lavaan | cell10_moderated_n150 | TNIE_W0 | 500 | n/a | none | n/a [n/a, n/a] | n/a | n/a (n/a) | 8.801e-18 (2.605e-17) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a | **negligible** | - | negligible |
| lavaan | cell10_moderated_n150 | TNIE_W1 | 500 | n/a | none | n/a [n/a, n/a] | n/a | n/a (n/a) | -2.183e-17 (4.621e-17) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a | **negligible** | - | negligible |
| lavaan | cell10_moderated_n150 | TNIE_difference | 500 | 5.2 | 6.2 | -1 [-3.6, 1.4] | 0 | 1 (178) | -1.197e-17 (3.469e-17) | 0.4 (1.6) | n/a (n/a) | 0.4 (2.4) | 0.9733 (0.9791) | 0.936 | **negligible** | - | substantive |
| lavaan | cell13_a_path_only_n100 | PNDE | 500 | 4 | 4.6 | -0.6 [-2.6, 1.4] | 0 | 1 (87) | -3.308e-18 (2.035e-17) | 0.6 (1.8) | n/a (n/a) | -0.8 (1) | 0.9801 (0.9857) | 0.938 | **negligible** | - | substantive |
| lavaan | cell13_a_path_only_n100 | TE | 500 | 3.2 | 3 | 0.2 [-1.8, 2] | 0 | 1 (87) | -9.097e-18 (2.327e-17) | 0 (1.2) | n/a (n/a) | -0.8 (0.6) | 0.9782 (0.984) | 0.944 | **negligible** | - | substantive |
| lavaan | cell13_a_path_only_n100 | TNIE | 500 | 2.2 | 1.4 | 0.8 [-0.6, 2.2] | 0 | 1 (25) | 5.375e-18 (1.571e-17) | 1 (2.4) | 1 (2.4) | n/a (n/a) | 0.9738 (0.9816) | 0.956 | **negligible** | - | substantive |
| lavaan | cell14_b_path_only_n100 | PNDE | 500 | 3.8 | 3.4 | 0.4 [-1.4, 2.2] | 0 | 1 (106) | -5.738e-18 (2.582e-17) | 0.8 (1.8) | n/a (n/a) | -1.4 (0.2) | 0.9782 (0.9838) | 0.938 | **negligible** | - | substantive |
| lavaan | cell14_b_path_only_n100 | TE | 500 | 4.4 | 4.2 | 0.2 [-2, 2.4] | 0 | 1 (97) | -1.434e-18 (2.727e-17) | 0.6 (1.605) | n/a (n/a) | -2.8 (-1) | 0.9798 (0.9857) | 0.934 | **negligible** | - | substantive |
| lavaan | cell14_b_path_only_n100 | TNIE | 500 | 1.8 | 2.4 | -0.6 [-2, 0.8] | 0 | 1 (42) | -3.575e-18 (1.004e-17) | 0.6 (1.8) | 0.6 (1.8) | n/a (n/a) | 0.9735 (0.9801) | 0.922 | **negligible** | - | substantive |
| lavaan | cell15_a_path_only_n250 | PNDE | 500 | 5 | 6 | -1 [-3, 1] | 0 | 1 (160) | 1.24e-17 (3.308e-17) | 1 (2.2) | n/a (n/a) | -2.6 (-0.6) | 0.978 (0.9836) | 0.936 | **negligible** | - | substantive |
| lavaan | cell15_a_path_only_n250 | TE | 500 | 5.6 | 5.8 | -0.2 [-2.2, 1.8] | 0 | 1 (173) | 1.654e-17 (3.473e-17) | 0.4 (1.8) | n/a (n/a) | -1.6 (0.4) | 0.9815 (0.9873) | 0.94 | **negligible** | - | substantive |
| lavaan | cell15_a_path_only_n250 | TNIE | 500 | 2.4 | 2.4 | 0 [-1.4, 1.4] | 0 | 1 (28) | -3.515e-18 (9.924e-18) | 0.4 (1.8) | 0.4 (1.8) | n/a (n/a) | 0.9716 (0.9788) | 0.954 | **negligible** | - | substantive |
| lavaan | cell16_b_path_only_n250 | PNDE | 500 | 5.2 | 4.4 | 0.8 [-1.4, 3] | 0 | 1 (204) | 1.291e-17 (3.801e-17) | 0.2 (1.2) | n/a (n/a) | -2.8 (-0.8) | 0.9826 (0.9885) | 0.946 | **negligible** | - | substantive |
| lavaan | cell16_b_path_only_n250 | TE | 500 | 5.4 | 5.6 | -0.2 [-2.6, 2.2] | 0 | 1 (165) | 2.331e-17 (4.734e-17) | 1 (2.4) | n/a (n/a) | -1 (1) | 0.9787 (0.9849) | 0.954 | **negligible** | - | substantive |
| lavaan | cell16_b_path_only_n250 | TNIE | 500 | 1 | 0.8 | 0.2 [-0.6, 1.2] | 0 | 1 (24) | -7.172e-18 (6.726e-18) | 0.2 (1) | 0.2 (1) | n/a (n/a) | 0.9843 (0.9902) | 0.956 | **negligible** | - | substantive |
| mediation | cell01_linear_n100 | PNDE | 500 | 3.6 | 3.8 | -0.2 [-1.8, 1.4] | 0 | 1 (95) | 3.838e-17 (5.872e-17) | 0.4 (1.6) | n/a (n/a) | -0.4 (1.4) | 0.9976 (1.004) | 0.95 | **negligible** | - | substantive |
| mediation | cell01_linear_n100 | TE | 500 | 6.4 | 6 | 0.4 [-1.6, 2.4] | 0 | 1 (282) | -9.993e-17 (1.203e-16) | 0.4 (1.8) | n/a (n/a) | 0 (2.2) | 0.9929 (0.9987) | 0.948 | **negligible** | - | substantive |
| mediation | cell01_linear_n100 | TNIE | 500 | 4.2 | 5 | -0.8 [-2.6, 1] | 0 | 1 (357) | -6.102e-17 (7.535e-17) | 0.4 (1.2) | n/a (n/a) | 0.6 (2.4) | 0.9992 (1.006) | 0.95 | **negligible** | - | substantive |
| mediation | cell02_linear_n250 | PNDE | 500 | 5.6 | 5.4 | 0.2 [-2, 2.2] | 0 | 1 (185) | 4.775e-18 (2.83e-17) | 0 (1.4) | n/a (n/a) | -0.8 (1.4) | 1.001 (1.007) | 0.944 | **negligible** | - | substantive |
| mediation | cell02_linear_n250 | TE | 500 | 1.4 | 1.6 | -0.2 [-1.4, 1] | 0 | 1 (460) | -4.634e-17 (6.369e-17) | -1 (0) | n/a (n/a) | -0.2 (0.8) | 0.9991 (1.005) | 0.96 | **negligible** | - | negligible |
| mediation | cell02_linear_n250 | TNIE | 500 | 0.4 | 1.4 | -1 [-2.2, 0] | 0 | 1 (487) | -3.962e-17 (4.289e-17) | 0.2 (1.4) | n/a (n/a) | 0 (0.6) | 0.9983 (1.004) | 0.928 | **negligible** | - | negligible |
| mediation | cell03_no_a_to_m_n100 | PNDE | 500 | 3.6 | 4.8 | -1.2 [-2.8, 0.4] | 0 | 1 (100) | 4.267e-17 (6.885e-17) | -0.6 (0.4) | n/a (n/a) | 0.8 (2.6) | 1.005 (1.01) | 0.958 | **negligible** | - | substantive |
| mediation | cell03_no_a_to_m_n100 | TE | 500 | 3.6 | 4.8 | -1.2 [-2.8, 0.4] | 0 | 1 (100) | 4.267e-17 (6.814e-17) | -0.6 (0.4) | n/a (n/a) | 0.8 (2.4) | 1.005 (1.011) | 0.958 | **negligible** | - | substantive |
| mediation | cell03_no_a_to_m_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| mediation | cell04_no_m_to_y_n100 | PNDE | 500 | 3.8 | 3.6 | 0.2 [-1.4, 1.8] | 0 | 1 (91) | 5.541e-17 (7.608e-17) | -0.2 (1) | n/a (n/a) | 1 (2.8) | 0.9982 (1.004) | 0.94 | **negligible** | - | substantive |
| mediation | cell04_no_m_to_y_n100 | TE | 500 | 3.8 | 3.6 | 0.2 [-1.4, 1.8] | 0 | 1 (91) | 5.541e-17 (7.609e-17) | -0.2 (1) | n/a (n/a) | 1 (2.8) | 0.9982 (1.004) | 0.94 | **negligible** | - | substantive |
| mediation | cell04_no_m_to_y_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| mediation | cell05_no_mediation_n100 | PNDE | 500 | 3.2 | 3 | 0.2 [-1.6, 2] | 0 | 1 (94) | 5.624e-17 (7.939e-17) | 0 (1.2) | n/a (n/a) | 0.8 (2.4) | 1.003 (1.01) | 0.942 | **negligible** | - | substantive |
| mediation | cell05_no_mediation_n100 | TE | 500 | 3.2 | 3 | 0.2 [-1.6, 2] | 0 | 1 (94) | 5.624e-17 (7.774e-17) | 0 (1.2) | n/a (n/a) | 0.8 (2.4) | 1.003 (1.01) | 0.942 | **negligible** | - | substantive |
| mediation | cell05_no_mediation_n100 | TNIE | 500 | 0 | 0 | 0 [0, 0] | 0 | n/a (0) | 0 (0) | 0 (0) | 0 (0) | n/a (n/a) | n/a (n/a) | 1 | **negligible** | - | negligible |
| mediation | cell08_quadratic_n100 | PNDE | 500 | 4.2 | 4.2 | 0 [-2, 2] | 0 | 1 (109) | -3.07e-17 (5.22e-17) | -0.8 (0.2) | n/a (n/a) | -0.6 (1.2) | 1.001 (1.006) | 0.94 | **negligible** | - | substantive |
| mediation | cell08_quadratic_n100 | TE | 500 | 6.6 | 4.4 | 2.2 [0, 4.4] | 0 | 1 (180) | -0.0006309 (0.002468) | 0.6 (1.8) | n/a (n/a) | -1.4 (0.8) | 0.9836 (0.9894) | 0.946 | **negligible** | - | substantive |
| mediation | cell08_quadratic_n100 | TNIE | 500 | 19.8 | 6.4 | 13.4 [9.595, 17.2] | 0 | 1 (228) | 0.0006309 (0.002499) | 3 (4.6) | n/a (n/a) | -18.6 (-15.2) | 0.8405 (0.8484) | 0.946 | **substantive** | coverage_loss,decision_excess | substantive |
| mediation | cell09_spline_n250 | PNDE | 500 | 6.4 | 6.2 | 0.2 [-1.8, 2.2] | 0 | 1 (195) | -7.779e-17 (2.156e-16) | -0.4 (0.405) | n/a (n/a) | -0.8 (1.4) | 0.9998 (1.006) | 0.96 | **negligible** | - | substantive |
| mediation | cell09_spline_n250 | TE | 500 | 4.8 | 5.4 | -0.6 [-2.8, 1.4] | 0 | 1 (335) | -0.0009892 (0.001358) | -0.2 (0.6) | n/a (n/a) | -0.8 (1.2) | 0.9812 (0.9863) | 0.958 | **negligible** | - | substantive |
| mediation | cell09_spline_n250 | TNIE | 500 | 14 | 8.6 | 5.4 [2.195, 8.6] | 0 | 1 (339) | -0.0009892 (0.00106) | 3.4 (5) | n/a (n/a) | -11.6 (-8.4) | 0.8963 (0.9026) | 0.948 | **tolerable** | coverage_loss,decision_excess | substantive |
| mediation | cell10_moderated_n150 | TNIE_W0 | 500 | n/a | none | n/a [n/a, n/a] | n/a | n/a (n/a) | 2.376e-18 (1.725e-17) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a | **negligible** | - | negligible |
| mediation | cell10_moderated_n150 | TNIE_W1 | 500 | n/a | none | n/a [n/a, n/a] | n/a | n/a (n/a) | -1.971e-17 (4.788e-17) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a (n/a) | n/a | **negligible** | - | negligible |
| mediation | cell10_moderated_n150 | TNIE_difference | 500 | 5.8 | 6.2 | -0.4 [-2.6, 1.6] | 0 | 1 (182) | -1.549e-17 (4.154e-17) | 0 (0.8) | n/a (n/a) | 1.4 (3.6) | 0.9974 (1.004) | 0.936 | **negligible** | - | substantive |
| mediation | cell11_binary_mediator_n150 | PNDE | 500 | 5 | 3.8 | 1.2 [-0.605, 3] | 0 | 1 (119) | -3.758e-17 (4.816e-17) | -0.8 (0.4) | n/a (n/a) | 0.2 (2.2) | 0.9991 (1.005) | 0.956 | **negligible** | - | substantive |
| mediation | cell11_binary_mediator_n150 | TE | 500 | 6 | 5 | 1 [-1, 3] | 0 | 1 (237) | -0.0009542 (0.002079) | 0.4 (1.8) | n/a (n/a) | -2.4 (-0.4) | 0.9792 (0.9849) | 0.938 | **negligible** | - | substantive |
| mediation | cell11_binary_mediator_n150 | TNIE | 500 | 15.6 | 8.2 | 7.4 [4, 11] | 0 | 1 (318) | 0.0009542 (0.003203) | 3.2 (4.8) | n/a (n/a) | -15.2 (-12.2) | 0.8699 (0.8764) | 0.94 | **substantive** | coverage_loss,decision_excess | substantive |
| mediation | cell13_a_path_only_n100 | PNDE | 500 | 4.6 | 4.6 | 0 [-1.6, 1.8] | 0 | 1 (90) | -2.646e-17 (3.847e-17) | 0.4 (1.4) | n/a (n/a) | -0.2 (1.6) | 1.002 (1.008) | 0.938 | **negligible** | - | substantive |
| mediation | cell13_a_path_only_n100 | TE | 500 | 4.4 | 3 | 1.4 [-0.4, 3.2] | 0 | 1 (90) | -3.391e-17 (4.631e-17) | 0 (1) | n/a (n/a) | -0.8 (1) | 0.9982 (1.004) | 0.944 | **negligible** | - | substantive |
| mediation | cell13_a_path_only_n100 | TNIE | 500 | 1.2 | 1.4 | -0.2 [-1.2, 0.8] | 0 | 1 (24) | 5.375e-18 (1.546e-17) | 0.4 (1.4) | 0.4 (1.4) | n/a (n/a) | 1.002 (1.01) | 0.956 | **negligible** | - | substantive |
| mediation | cell14_b_path_only_n100 | PNDE | 500 | 3.2 | 3.4 | -0.2 [-1.8, 1.2] | 0 | 1 (110) | -1.865e-17 (2.242e-17) | 1.2 (2.605) | n/a (n/a) | 0.8 (2.4) | 1.001 (1.007) | 0.938 | **negligible** | - | substantive |
| mediation | cell14_b_path_only_n100 | TE | 500 | 4.6 | 4.2 | 0.4 [-1.2, 2.2] | 0 | 1 (105) | -2.295e-17 (2.799e-17) | 0.2 (1) | n/a (n/a) | 0.2 (2.2) | 1.003 (1.009) | 0.934 | **negligible** | - | substantive |
| mediation | cell14_b_path_only_n100 | TNIE | 500 | 1.6 | 2.4 | -0.8 [-2.2, 0.4] | 0 | 1 (44) | -8.293e-19 (8.607e-18) | -0.4 (0.6) | -0.4 (0.6) | n/a (n/a) | 0.9983 (1.005) | 0.922 | **negligible** | - | substantive |
| mediation | cell15_a_path_only_n250 | PNDE | 500 | 4.2 | 6 | -1.8 [-3.8, 0.2] | 0 | 1 (166) | 3.308e-18 (2.152e-17) | -0.6 (0.8) | n/a (n/a) | 0.6 (2.4) | 0.9997 (1.005) | 0.936 | **negligible** | - | substantive |
| mediation | cell15_a_path_only_n250 | TE | 500 | 5 | 5.8 | -0.8 [-3, 1.2] | 0 | 1 (177) | 4.135e-18 (2.233e-17) | -0.4 (1) | n/a (n/a) | 0.6 (2.6) | 0.9998 (1.006) | 0.94 | **negligible** | - | substantive |
| mediation | cell15_a_path_only_n250 | TNIE | 500 | 1.2 | 2.4 | -1.2 [-2.6, 0] | 0 | 1 (28) | -2.998e-18 (9.097e-18) | -0.8 (0) | -0.8 (0.2) | n/a (n/a) | 0.9959 (1.002) | 0.954 | **negligible** | - | substantive |
| mediation | cell16_b_path_only_n250 | PNDE | 500 | 5 | 4.4 | 0.6 [-1.6, 2.8] | 0 | 1 (210) | 1.865e-17 (4.16e-17) | 0 (1.2) | n/a (n/a) | -0.2 (2) | 0.9998 (1.006) | 0.946 | **negligible** | - | substantive |
| mediation | cell16_b_path_only_n250 | TE | 500 | 5.8 | 5.6 | 0.2 [-1.8, 2.2] | 0 | 1 (169) | 2.618e-17 (4.887e-17) | 0 (1.4) | n/a (n/a) | 0.2 (2.4) | 0.9955 (1.001) | 0.954 | **negligible** | - | substantive |
| mediation | cell16_b_path_only_n250 | TNIE | 500 | 1.2 | 0.8 | 0.4 [-0.4, 1.2] | 0 | 1 (25) | -8.607e-18 (8.251e-18) | 0 (0.805) | 0 (1) | n/a (n/a) | 0.9982 (1.004) | 0.956 | **negligible** | - | substantive |
