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
