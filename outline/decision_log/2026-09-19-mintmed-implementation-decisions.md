# Mintmed Implementation Decision Log

## Purpose

This is the append-only project log for implementation decisions, pivots, revisions, rationale, evidence, and schedule status across Tasks 1–15 in the Mintmed baseline. It complements the task plans; it does not replace them.

Update this document after each task or material decision. Preserve earlier entries and add a dated correction entry when a decision changes.

## Entry format

Each task entry should record:

- **Date:** ISO date.
- **Task:** baseline task number and name.
- **Status:** planned, in progress, completed, blocked, or deferred.
- **Schedule:** on schedule, delayed, or not scheduled; state the reference schedule when no external deadline exists.
- **Decision:** what was chosen.
- **Rationale:** why it satisfies the baseline and repository constraints.
- **Actions:** exact work performed, including pivots and revisions.
- **Evidence:** commands, outputs, hashes, or files that support the decision.
- **Files:** tracked files changed by the task.
- **Verification:** tests/checks run and their results.
- **Follow-up:** next task, unresolved risk, or explicit non-action.

## Decision rules

1. Append rather than rewrite history.
2. Record a pivot when observed repository state differs from the task plan.
3. Record the cost if a ruling is wrong when choosing between valid alternatives.
4. Distinguish environment setup from repository changes.
5. Mark a task “completed on schedule” only after its acceptance checks pass; no external deadline is assumed unless one is recorded.

## Task log

### Task 01 — Restore the supported Python 3.11 development environment

- **Date:** 2026-09-19
- **Task:** Task 1 — Restore a supported Python 3.11 development environment.
- **Status:** Completed.
- **Schedule:** On schedule for the requested task sequence; no external deadline was supplied.
- **Decision:** Use the official Python 3.11 Windows distribution and keep the repository's existing `>=3.11,<3.12` runtime contract unchanged.
- **Rationale:** The preflight found the Windows `py` launcher but no registered Python runtimes and no repository `.venv`. The baseline explicitly requires Python 3.11 and forbids broadening support to another interpreter to bypass a missing runtime.
- **Actions:** Downloaded the official Python 3.11.9 installer and repaired per-user launcher registration after the first silent installation did not make `py -3.11` discover the runtime. The first editable-install attempt exposed that the declared `src/` package directory was absent, so the minimal `src/mintmed/__init__.py` package marker was added as prerequisite scaffolding; Task 2 will extend it with public exports. Created `.venv`, upgraded pip, installed the package in editable mode with `.[test]`, added the README bootstrap section, and created this committed decision log.
- **Evidence:** `py -3.11` resolved to `C:\Users\imhoh\AppData\Local\Programs\Python\Python311\python.exe`. Editable installation completed for `mintmed==0.1.0`. `pip check` reported `No broken requirements found.`
- **Files:** `.gitignore` now keeps the broader `outline/` planning tree ignored while tracking only `outline/decision_log/*.md`; `README.md`; `src/mintmed/__init__.py`; this decision log.
- **Verification:** The inherited aggregation test passed: `4 passed in 0.49s`. Final full suite passed: `4 passed in 0.39s`. Required imports (`mintmed`, Patsy, Statsmodels, NumPy, SciPy, pandas, PyYAML, matplotlib) succeeded. `git diff --check` reported no whitespace errors.
- **Follow-up:** Task 1 is complete on schedule for the requested task sequence. Task 2 may extend `src/mintmed/__init__.py` with public exports while preserving Python `>=3.11,<3.12`.

### Task 02 — Define immutable shared types and result statuses

- **Date:** 2026-09-19
- **Task:** Task 2 — Define immutable shared types and result statuses.
- **Status:** Completed.
- **Schedule:** On schedule for the requested task sequence; no external deadline was supplied.
- **Decision:** Represent shared analysis values with frozen, slotted dataclasses. Normalize ordered collections to tuples and metadata/diagnostic maps to read-only dict-compatible mappings so the objects remain immutable while supporting the planned `dataclasses.asdict`/JSON reporting path.
- **Rationale:** Later specification, fitting, bootstrap, API, and report tasks need one stable result vocabulary. A dict-compatible read-only wrapper preserves mapping semantics and serialization compatibility without exposing mutable result state.
- **Actions:** Added eight focused contract tests and committed the red test contract as `afd8317`. Implemented `AnalysisStatus`, `Issue`, `EffectEstimate`, `RegimeMeans`, `ContributionResult`, `PointAnalysis`, `BootstrapResult`, and `MediationResult` in `src/mintmed/types.py`. The first `MappingProxyType` implementation failed the new `dataclasses.asdict` regression test, so it was replaced with a private `_FrozenDict`; the corrected implementation and tests were committed as `6a525c2`.
- **Evidence:** The initial focused run failed during collection with `ModuleNotFoundError: No module named 'mintmed.types'`. After implementation, the focused suite passed `9 tests`, and the full suite passed `13 tests`.
- **Files:** `src/mintmed/types.py`; `tests/mediation/test_types.py`; this decision log.
- **Verification:** `./.venv/Scripts/python.exe -m pytest tests/mediation/test_types.py -q` → `9 passed in 0.03s`; `./.venv/Scripts/python.exe -m pytest -q` → `13 passed in 0.43s`; `git diff --check` passed.
- **Follow-up:** Task 3 consumes `Issue` and `AnalysisStatus`. It must preserve the lowercase status values and use the existing immutable result vocabulary rather than creating a second error/status hierarchy.

### Task 03 — Parse and validate explicit model specifications

- **Date:** 2026-09-19
- **Task:** Task 3 — Parse and validate explicit model specifications.
- **Status:** Completed.
- **Schedule:** On schedule for the requested task sequence; no external deadline was supplied.
- **Decision:** Implement the YAML boundary as a strict structured-schema compiler. Return frozen dataclasses with enum-valued roles, families, and term kinds; reject unknown nested keys, executable/formula-like term text, unsupported response declarations, invalid graph structures, and incomplete computation/contrast settings with stable `SpecValidationError(code, path, message)` values.
- **Rationale:** Task 4 must consume a validated `ModelSpec` without guessing at scientific intent or silently modifying a user's design. Keeping terms as `{variable, basis, df, purpose}` objects prevents expression evaluation and makes the canonical specification independent of filesystem paths. The existing Task 2 `AnalysisStatus` and `Issue` vocabulary is reused through `SpecValidationError.status` and `SpecValidationError.to_issue()` rather than introducing a second diagnostic status hierarchy.
- **Actions:** Added the red contract suite first and committed it as `eb36fdc`. Implemented `src/mintmed/spec.py` with the frozen specification/template objects, safe YAML loading, role-specific nested-key checks, enum conversion, exact one-exposure/one-outcome and one-to-four-mediator validation, independent mediator factorization order, Kahn acyclic-graph validation, predictor-role/order checks, intercept and node-family checks, natural-spline `df=3` enforcement, interaction main-effect checks, Bernoulli level validation, contrast/moderator validation, deterministic computation settings, and path-free canonical JSON serialization. The roadmap example omits node intercept fields even though the implementation rules require them; the implementation therefore requires an explicit `intercept: true` declaration on every node so the rule is machine-checkable. A stale existing `.venv` also pointed at a non-executable Python 3.11 runtime during the first focused run; the existing per-user Python 3.11 installer repaired that local environment, with no additional tracked environment files changed.
- **Evidence:** The focused test run initially failed during collection with `ModuleNotFoundError: No module named 'mintmed.spec'`, confirming the test contract was red before implementation. After implementation, the focused suite passed `22 tests`. The implementation commit is `e1ca823` (`feat: validate explicit mediation specifications`).
- **Files:** `src/mintmed/spec.py`; `tests/mediation/test_spec.py`; this decision log. The plan-scoped execution ledger is maintained in the ignored `.superpowers/sdd/task-03-specification/` workspace.
- **Verification:** `./.venv/Scripts/python.exe -m pytest tests/mediation/test_spec.py -q` → `22 passed`; `./.venv/Scripts/python.exe -m pytest -q` → `35 passed`; `./.venv/Scripts/python.exe -m compileall -q src tests` passed; `./.venv/Scripts/python.exe -m pip check` → `No broken requirements found`; `git diff --check` passed. The final committed tree was clean after the implementation commit before this documentation update.
- **Follow-up:** Task 3 is completed on schedule. Task 4 may add data-dependent preflight and compilation, but it must accept only validated `ModelSpec` objects, preserve explicit-vs-template provenance, and never silently add, drop, reorder, or downgrade declared model terms/families.

### Task 04 — Compile analysis plans and perform data preflight

- **Date:** 2026-09-19
- **Task:** Task 4 — Compile analysis plans and perform data preflight.
- **Status:** Completed.
- **Schedule:** On schedule for the requested task sequence; no external deadline was supplied.
- **Decision:** Keep `estimate_plan(data, spec)` in `src/mintmed/spec.py`, add immutable `CompiledNodePlan` and `AnalysisPlan` contracts there, and place typed fatal preflight exceptions in `src/mintmed/diagnostics.py` with re-exports at the specification boundary. Compile nodes in declared scientific mediator order followed by the outcome, preserve explicit terms exactly, and separate scientific parents from factorization predictors.
- **Rationale:** Task 5 needs one auditable contract containing frozen category meaning, the retained analysis population, and explicit node metadata without reparsing YAML or retaining a mutable frame. Data-dependent checks belong after specification validation: missingness, finite/type support, observed counterfactual support, and participant independence cannot be decided from YAML alone. Task 2's `Issue` and `AnalysisStatus` vocabulary remains the only warning/status system.
- **Actions:** Added the red Task 4 contract tests and committed them as `7b07fbc`. Extended Task 3's schema narrowly to support continuous exposures with explicit reference/comparison values and optional categorical participant IDs. Added `PlanValidationError`, `DataValidationError`, and `UnsupportedAnalysisError`. Implemented immutable compiled-node and analysis-plan dataclasses, declared-column selection, complete-case/error missingness handling, nonfinite and binary/category checks, tied-continuous acceptance, categorical/continuous exposure and moderator support checks, repeated-participant rejection, sparse binary and small-sample warnings, structured diagnostics, readable summaries, and SHA-256 specification/data hashes. The implementation was committed as `54245e4`. Final review found mediator validation was still using tuple declaration order and that `computation.information` was absent from `analysis_hash`; failing regression tests were added, the fixes were implemented, and committed as `5535ff3`.
- **Evidence:** The initial Task 4 focused run failed during collection with `ImportError: cannot import name 'AnalysisPlan' from 'mintmed.spec'`. The focused Task 4 suite passed `24 tests` after implementation. The final review regression tests both failed before their fixes and both passed afterward. Implementation commits: `7b07fbc`, `54245e4`, and `5535ff3`.
- **Files:** `src/mintmed/spec.py`; `src/mintmed/diagnostics.py`; `tests/mediation/test_plan.py`; `tests/mediation/test_spec.py`; this decision log. The ignored plan-scoped ledger is `.superpowers/sdd/task-04-compiled-plan/progress.md`.
- **Verification:** `./.venv/Scripts/python.exe -m pytest tests/mediation/test_plan.py -q` → `24 passed`; `./.venv/Scripts/python.exe -m pytest -q` → `61 passed`; `./.venv/Scripts/python.exe -m compileall -q src tests` passed; `./.venv/Scripts/python.exe -m pip check` → `No broken requirements found`; `git diff --check` passed. Final review was a self-review because no subagent tool is available; no Critical or Important findings remain and no Minor findings were deferred.
- **Follow-up:** Task 4 is completed on schedule. Task 5 must consume only `AnalysisPlan`/`CompiledNodePlan`, use frozen declared category levels and structured terms for Patsy design construction, preserve retained row indices, and raise typed rank/design errors instead of repairing a deficient declared model.

### Task 05 — Build and freeze declared design matrices

- **Date:** 2026-09-20
- **Task:** Task 5 — Build and freeze declared design matrices.
- **Status:** Completed.
- **Schedule:** On schedule for the requested task sequence; no external deadline was supplied.
- **Decision:** Implement a dedicated `mintmed.design` boundary that consumes only `CompiledNodePlan` objects, generates safe structured Patsy expressions, freezes the exact fit-time `DesignInfo`, stores a read-only numeric matrix, and rebuilds every counterfactual matrix through `patsy.build_design_matrices`. Add `NodeFitError` to the existing diagnostics hierarchy and expose it from the design module as the canonical node-level failure type.
- **Rationale:** Later node-fitting and effect-estimation tasks need one authoritative design contract. Rebuilding formulas would refit spline state and category handling; manually rebuilding terms would risk inconsistent interactions and quadratic columns. A read-only NumPy matrix is convenient for model fitting, while retained Patsy metadata preserves the transform state needed for counterfactual predictions. Typed rank, missing-column, unseen-category, nonfinite, formula, and transform errors make declared-identifiability failures explicit instead of silently changing the scientific model.
- **Actions:** Wrote the Task 5 contract tests first and committed the red contract as `ff05f92` (`test: define frozen design contracts`). The planned `.venv` interpreter was stale and pointed to a missing Python 3.11 installation, so the prescribed command could not start. A local temporary Python 3.12 test environment was used after the repository-local environment was unavailable; Patsy was installed only into that temporary environment after the sandbox blocked the first network attempt. The red focused run then failed at collection with `ModuleNotFoundError: No module named 'mintmed.design'`. Implemented `NodeFitError`, `DesignTerm`, `FrozenDesign`, structured linear/quadratic/natural-spline/categorical expression generation, explicit safe variable quoting, declared-level rendering, deterministic interactions, finite checks, full-rank checks, frozen-category checks, exact column checks, and `DesignInfo` transforms. Added regression tests for spline columns, design-info reuse, exposure and moderator interactions, quadratic replacement, formula-safe names, categorical levels, missing categories, rank deficiency, nonfinite transforms, missing columns, immutability, and empty frames. Committed the implementation as `169bb7b` (`feat: build structured frozen design matrices`).
- **Evidence:** The Task 5 focused suite initially failed for the expected missing-module reason. After implementation it passed `20 tests`. The first corrected full-suite attempt reached the tests but could not create pytest's default temp directories because of the runtime ACL; the suite was rerun with an explicit repository-local basetemp and passed `81 tests`. The implementation commit contains only `src/mintmed/design.py`, `src/mintmed/diagnostics.py`, and `tests/mediation/test_design.py`. The task-scoped execution ledger is maintained in the ignored `.superpowers/sdd/task-05-frozen-designs/progress.md` workspace.
- **Files:** `src/mintmed/design.py`; `src/mintmed/diagnostics.py`; `tests/mediation/test_design.py`; this decision log.
- **Verification:** Focused Task 5 run using the temporary environment and `PYTHONPATH=src` → `20 passed in 2.22s`; full suite using `PYTHONPATH=src;.` and explicit basetemp → `81 passed in 1.20s`; `python -m compileall -q src tests` passed; `pip check` → `No broken requirements found`; targeted Ruff on all changed source/test files → `All checks passed`; `git diff --check` passed. Repository-wide Ruff reported two pre-existing unused imports in `tests/mediation/test_spec.py` and no findings in the changed files. Final review was a self-review because no subagent tool is available; no Critical or Important findings remain and no Minor findings were deferred.
- **Follow-up:** Task 5 is completed on schedule. Task 6 may consume `FrozenDesign.matrix`, `.columns`, `.rank`, `.response`, `.family`, and `.design_info` through `fit_design`/`transform_design`; it must not rebuild formulas, infer categories, recompute spline state, or bypass the frozen transform boundary. A pytest temporary directory created for verification could not be deleted because it was owned by the sandbox runtime; it is untracked and contains only generated test artifacts, not implementation files.

#### Task 05 correction — preserve offending-variable context in transform failures

- **Date:** 2026-09-20
- **Task:** Task 5 — review correction.
- **Status:** Completed.
- **Schedule:** On schedule; correction completed in the same implementation window.
- **Decision:** Populate `NodeFitError.variable` for generic Patsy transformation failures whenever the exception names a required variable or the frozen design has exactly one required variable.
- **Rationale:** The Task 5 failure contract requires transform errors to identify the node and, when possible, the offending variable. The first implementation preserved the node but left the variable unset for generic Patsy errors. The narrow fix improves diagnostics without parsing arbitrary YAML or changing transform behavior.
- **Actions:** Added `test_transform_patsy_failure_includes_variable_context`, observed the expected failure (`variable is None`), added `_error_variable(...)`, and committed the fix as `50b63e6` (`fix: include variable context in transform errors`).
- **Evidence:** Focused Task 5 suite changed from `20 passed` to `21 passed`; the failing regression test passed after the fix. The final post-correction full suite passed `82 tests`.
- **Files:** `src/mintmed/design.py`; `tests/mediation/test_design.py`; this decision log.
- **Verification:** The regression test was red before implementation and green afterward. The final full suite using the temporary Python environment and explicit repository-local basetemp reported `82 passed in 1.11s`; targeted Ruff reported `All checks passed`, compileall passed, pip check reported `No broken requirements found`, and `git diff --check` passed.
- **Follow-up:** No further Task 5 behavior change is planned; Task 6 should use `NodeFitError.variable` when presenting node transform failures.

## Reusable entry template

### Task NN — Name

- **Date:** YYYY-MM-DD
- **Task:** Task NN — Name.
- **Status:** planned | in progress | completed | blocked | deferred.
- **Schedule:** on schedule | delayed | not scheduled; explain the reference.
- **Decision:**
- **Rationale:**
- **Actions:**
- **Evidence:**
- **Files:**
- **Verification:**
- **Follow-up:**
