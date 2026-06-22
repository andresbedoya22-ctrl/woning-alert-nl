# Advisor Email Generation Skill

Use this skill when generating advisor-ready emails or property recommendation summaries.

## Required reading

- `AGENTS.md`
- matching report or match result rows
- client language/preferences fixture

## Goal

Generate clear, reviewable advisor drafts from clean matched inventory.

## Rules

- Use only clean inventory and match output.
- Do not invent property facts.
- Keep missing fields as warnings, not claims.
- Write in the client's configured language.
- Keep tone professional and useful for a mortgage/housing advisor.
- Include why the property matches.
- Include risks or missing data.
- Do not send automatically without explicit approval.

## Output

Produce:

- short advisor summary;
- client-facing email draft;
- bullet list of matching reasons;
- warnings/missing data;
- recommended next action.
