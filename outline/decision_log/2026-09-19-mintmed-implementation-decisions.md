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
