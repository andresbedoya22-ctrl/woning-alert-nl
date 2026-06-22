# Source Onboarding Skill

Use this skill when moving a source from candidate to production-ready inventory input.

## Required reading

- `AGENTS.md`
- `docs/04_SOURCE_ONBOARDING_PLAYBOOK.md`
- `docs/03_MAKELAAR_DELIVERY_RESEARCH_LOOP.md`

## Goal

Create a controlled path from discovered source to safe extraction.

## Workflow

1. Capture candidate facts.
2. Run access pre-check.
3. Run delivery mode fingerprint.
4. Choose parser family candidate.
5. Define source config or parser work.
6. Define QA expectations.
7. Create test/fixture plan.
8. Decide promotion state.

## Required output

Produce:

```text
source_id:
source_domain:
source_type:
homepage_url:
listing_url:
access_status:
robots_status:
blocking_status:
delivery_mode:
parser_family:
config_path:
qa_expectations:
fixture_plan:
recommended_action:
production_ready: true/false
review_reason:
```

## Promotion rule

Only mark production-ready if:

- access is `allowed` or `limited`;
- delivery mode has evidence;
- parser route exists;
- QA gates are defined;
- tests or fixture plan exist.

## Rejection rule

Reject or hold for review if:

- source is blocked;
- source requires permission;
- source has unclear legal status;
- no parser route exists;
- output would likely pollute koop inventory.
