# Parser Family Implementation Skill

Use this skill when implementing or modifying a parser family.

## Purpose

Build reusable parser families that support many sources through config, not one parser per makelaar.

## Required reading

Before editing code, read:

- `AGENTS.md`
- `docs/01_PARSER_FAMILY_ARCHITECTURE.md`
- existing parser files under `scraper/src/domek_wonen/properties/`
- relevant tests under `tests/`

## Rules

- Do not implement a domain-specific parser unless explicitly requested for diagnostics.
- Put domain-specific selectors and mappings in configs or fixtures.
- Return a normalized candidate shape.
- Include confidence and evidence.
- Add tests with synthetic fixtures.
- Do not add network calls in unit tests.
- Do not add stealth, CAPTCHA, proxy, or anti-bot logic.

## Implementation checklist

1. Identify delivery mode.
2. Confirm source access status.
3. Define parser family input and output.
4. Create or update parser config validation.
5. Add fixture HTML/JSON.
6. Implement extraction.
7. Add QA/review reasons.
8. Add tests for success and rejection cases.
9. Run `py -3.12 -m pytest`.

## Output expectations

Report:

- files changed;
- parser family added or modified;
- fixtures added;
- tests run;
- known limitations;
- next recommended source family.
