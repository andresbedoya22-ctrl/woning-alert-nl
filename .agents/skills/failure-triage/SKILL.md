# Failure Triage Skill

Use this skill when a source, parser, daily job, or test run fails.

## Required reading

- `AGENTS.md`
- relevant run report or test output
- relevant parser/source files

## Goal

Classify failure causes and propose safe next actions.

## Failure categories

- access changed;
- robots or policy changed;
- source timeout;
- source returned empty page;
- layout changed;
- parser config mismatch;
- detail page missing signals;
- transaction type pollution;
- price parsing issue;
- address parsing issue;
- duplicate explosion;
- source volume collapse;
- test regression;
- unknown manual review.

## Workflow

1. Read failure artifact.
2. Identify affected source or module.
3. Classify root cause.
4. Decide whether this is code, config, source, access, or data quality.
5. Recommend one next action.
6. Avoid broad changes.

## Output

```text
failure_category:
affected_source_or_module:
root_cause:
evidence:
recommended_action:
files_to_inspect:
tests_to_run:
risk:
```
