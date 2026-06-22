# Test Repair Loop Skill

Use this skill when tests fail or when a coding agent introduced regressions.

## Purpose

Repair failing tests with minimal, focused changes.

## Required reading

- `AGENTS.md`
- the failing test output;
- the changed files;
- the relevant module and test files.

## Rules

- Do not add new features while repairing tests.
- Do not weaken tests unless the test is demonstrably wrong.
- Prefer fixing root cause over patching symptoms.
- Keep changes minimal.
- Preserve Windows PowerShell commands.
- Do not touch generated outputs.

## Workflow

1. Reproduce or inspect failure.
2. Identify failing assertion or exception.
3. Map failure to changed behavior.
4. Decide whether code or test should change.
5. Apply minimal patch.
6. Run targeted tests.
7. Run full test suite.
8. Report root cause and validation result.

## Required final report

- Root cause.
- Files changed.
- Tests run.
- Result.
- Any remaining risk.
