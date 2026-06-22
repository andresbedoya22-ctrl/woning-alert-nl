# Codex Task Planning Skill

Use this skill before asking Codex to implement a non-trivial task.

## Required reading

- `AGENTS.md`
- `docs/02_CODEX_WORKFLOWS.md`
- relevant architecture docs

## Goal

Turn a broad idea into a small, testable Codex task.

## Task prompt structure

Use:

```text
Task:
Context:
Goal:
Constraints:
Acceptance criteria:
Expected files:
Validation:
Out of scope:
```

## Scope rules

A good Codex task changes one module or one workflow.

Avoid tasks that combine:

- parser implementation;
- database schema;
- dashboard;
- n8n workflow;
- matching;
- email generation.

## Acceptance criteria

Every coding task should have:

- exact behavior;
- tests to add or update;
- command to run;
- expected output;
- known out-of-scope items.

## Output

Produce a ready-to-paste Codex task prompt.
