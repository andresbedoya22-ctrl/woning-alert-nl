# Parser Config Authoring Skill

Use this skill when an existing parser family can support a new source through configuration.

## Required reading

- `AGENTS.md`
- `docs/01_PARSER_FAMILY_ARCHITECTURE.md`
- `docs/03_MAKELAAR_DELIVERY_RESEARCH_LOOP.md`
- `scraper/src/domek_wonen/properties/source_parser_config.py`

## Goal

Create or revise source configs instead of writing a new parser class.

## Workflow

1. Confirm access state.
2. Confirm delivery mode.
3. Select parser family.
4. Identify listing URL.
5. Identify card selector.
6. Identify detail URL selector.
7. Identify field selectors.
8. Define status mapping.
9. Define price patterns.
10. Define QA expectations.
11. Create fixture and test plan.

## Fields to define

- `source_domain`
- `parser_family`
- `listing_url`
- `card_selector`
- `detail_url_selector`
- `address_selector`
- `city_selector`
- `price_selector`
- `status_selector`
- `living_area_selector`
- `rooms_selector`
- `image_selector`
- `pagination_strategy`
- `detail_enrichment_required`
- `known_noise_selectors`
- `status_mapping`
- `price_patterns`
- `qa_expectations`

## QA expectations

At minimum, define expected card count, whether address is required, and whether price is required.

## Output

Report:

- proposed config path;
- parser family;
- selectors chosen;
- QA expectations;
- fixture plan;
- tests to add;
- known limitations.
