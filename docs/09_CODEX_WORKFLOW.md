# Codex Workflow

## Working style

- Keep tasks small.
- Read `AGENTS.md` first.
- Review real files before touching them.
- Avoid broad changes unless the task requires them.
- Add tests when runtime behavior changes.
- Run `py -3.12 -m pytest` and report the real result.
- Report changed files and exact scope.
- Never invent repo state or outcomes.
- Never say a file exists if you did not verify it.

## Task template

```text
Task:
Context:
Files to read:
Goal:
Constraints:
Expected files:
Acceptance criteria:
Validation:
Out of scope:
Final response:
```

## Good task-shaping examples

- isolate architecture docs from runtime code;
- isolate parser-family work from matching work;
- isolate one delivery-mode family at a time;
- isolate access-policy changes from inventory changes.

## Common failure modes

- touching multiple phases in one PR;
- modifying runtime code while claiming docs-only scope;
- assuming a source is allowed because it is technically reachable;
- inferring repo state without reading the files.
