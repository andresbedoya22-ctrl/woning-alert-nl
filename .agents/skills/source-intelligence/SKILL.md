# Source Intelligence Skill

Use this skill when converting existing source discovery data into the source-intelligence model.

## Read first

- `AGENTS.md`
- `docs/research/MAKELAAR_SOURCE_INTELLIGENCE_V1.md`
- `docs/03_MAKELAAR_DELIVERY_RESEARCH_LOOP.md`
- `docs/04_SOURCE_ONBOARDING_PLAYBOOK.md`

## Goal

Create a measurable dataset that maps each source domain and aanbod URL to a delivery mode, parser family candidate, quality state, and recommended action.

## Inputs

Use existing repo data first:

- source master CSV;
- discovery outputs;
- coverage reports;
- platform reports;
- test fixtures.

## Required row fields

- `source_id`
- `source_domain`
- `source_name`
- `province`
- `gemeente`
- `homepage_url`
- `aanbod_url`
- `aanbod_url_status`
- `access_status`
- `blocking_status`
- `technology_signals`
- `delivery_mode`
- `delivery_mode_confidence`
- `parser_family_candidate`
- `recommended_action`
- `priority_score`
- `evidence`

## Reports

Generate counts by:

- source status;
- aanbod URL quality;
- province and gemeente;
- detected platform;
- delivery mode;
- parser family candidate;
- recommended action.

Also generate a manual review queue sorted by priority.

## Rules

- Do not use live network checks in the conversion step.
- Do not promote weak evidence.
- Do not confuse membership type with delivery mode.
- Keep blocked, missing, suspect, and review sources separate.

## Output

Report input file, row counts, delivery mode counts, parser family priority, manual review queue, unknowns, blockers, and next implementation step.
