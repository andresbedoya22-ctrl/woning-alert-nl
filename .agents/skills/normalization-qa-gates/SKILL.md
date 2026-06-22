# Normalization QA Gates Skill

Use this skill when improving normalized inventory quality.

## Required reading

- `AGENTS.md`
- `docs/01_PARSER_FAMILY_ARCHITECTURE.md`
- existing files under `scraper/src/domek_wonen/properties/`

## Goal

Prevent weak, duplicate, rental, stale, or malformed listings from reaching matching.

## QA gates

Check:

- source access status;
- canonical URL;
- transaction type;
- listing status;
- price sanity;
- address quality;
- city/postcode normalization;
- duplicate key;
- parser confidence;
- review reason.

## Required separation

Keep these concepts separate:

- `transaction_type`: `koop`, `huur`, `unknown`;
- `status`: `beschikbaar`, `onder_bod`, `verkocht`, `verkocht_ov`, `verdwenen`, `unknown`;
- `quality_state`: `clean`, `needs_review`, `rejected`.

## Tests

Add tests for:

- `te huur` not entering koop matching;
- invalid prices rejected;
- missing optional fields becoming warnings;
- address recovered from slug when possible;
- duplicate keys stable across source URLs.

## Output

Report changed gates, rejection reasons, tests, and remaining risk.
