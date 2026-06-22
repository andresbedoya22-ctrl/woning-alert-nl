# AGENTS.md

Primary rules for every human developer and coding agent working in this repository.

This file is the neutral source of truth. Claude-specific, Codex-specific, or local agent files may extend it, but they must not contradict it.

## Product objective

WoningAlert NL exists to detect newly available homes in the Dutch housing market, normalize them into a stable inventory, deduplicate them, compare daily changes, match them with active client profiles, and produce advisor-ready recommendations before manual search becomes necessary.

The active architecture is **parser-family based inventory**, not one scraper per makelaar.

## Strategic architecture

Preferred flow:

```text
source_registry
  -> access_policy
  -> delivery_mode_fingerprint
  -> parser_family
  -> source_config
  -> normalized_property
  -> inventory_state
  -> matching
  -> advisor_email
```

The existing makelaar source discovery and property discovery modules remain useful, but they are not the only path. They should be treated as one layer in a broader inventory system.

## Hard rules

- Execute commands for Windows PowerShell. Do not assume Bash.
- Do not scrape Funda.
- Do not use Pararius unless explicitly requested and legally reviewed for the specific workflow.
- Do not use stealth browser automation.
- Do not implement CAPTCHA solving.
- Do not use rotating residential proxies or IP evasion.
- Do not simulate human browsing behavior to bypass anti-bot systems.
- Do not bypass login, paywalls, 403, robots restrictions, or explicit blocking.
- If a source blocks automation, mark it as `blocked`, `permission_required`, or `legal_review`; do not bypass it.
- Do not read or write `data/raw` unless explicitly requested.
- Do not delete generated pipeline outputs.
- Do not use `git add .`.
- Do not commit directly to `main`.
- Do not make broad refactors unless the task explicitly requires them.

## Access and compliance policy

Every source must have an access decision before production use.

Allowed states:

- `allowed`
- `limited`
- `permission_required`
- `legal_review`
- `blocked`
- `disabled`

A source is not production-ready until the system can explain:

- what URL or feed is being accessed;
- whether robots or source rules allow the intended access;
- whether login, CAPTCHA, 403, or anti-bot blocking appears;
- which fields are extracted;
- why extraction is minimal and necessary;
- which parser family is used;
- how quality is measured.

## Parser-family rules

Do not create one parser per makelaar unless it is a short-lived diagnostic experiment.

Create reusable parser families such as:

- `realworks_public`
- `ogonline_xhr`
- `kolibri_public`
- `wordpress_rest`
- `wordpress_html_cards`
- `json_ld`
- `sitemap_detail`
- `static_html_cards`
- `xhr_json`
- `email_alert`
- `iframe_blocked_handler`

Domain-specific differences should normally live in source config files, not in new parser classes.

A parser family must return normalized candidates with a stable schema and evidence:

- source domain;
- source URL;
- canonical property URL;
- address fields when available;
- city and postcode when available;
- asking price;
- transaction type (`koop`, `huur`, `unknown`);
- status (`beschikbaar`, `onder_bod`, `verkocht`, `verkocht_ov`, `verdwenen`, `unknown`);
- living area, rooms, bedrooms when available;
- energy label when available;
- extraction confidence;
- evidence and review reasons.

## Data minimization

Extract only fields needed for inventory, matching, and change detection.

Avoid storing:

- long descriptions;
- full copied page text;
- downloaded images;
- unnecessary personal data;
- raw HTML in committed files.

If debug snapshots are needed, keep them in ignored generated-output folders.

## Generated artifacts that must not be committed

Do not commit generated outputs from pipeline runs, including:

- `data/property_discovery/`
- `data/property_discovery/latest/`
- `data/property_discovery/runs/`
- `data/discovery/latest/`
- `data/discovery/runs/`
- `data/discovery/platform_fingerprint/`
- `data/discovery/cache/`
- `data/email_previews/`
- `data/matching/`
- `data/diagnostics/`
- `data/source_debug/`
- `data/source_capture_audit/`

If evidence is needed, reference local generated files in the response or create tiny synthetic fixtures under `tests/fixtures/`.

## Validation requirements

When code changes, run at minimum:

```powershell
py -3.12 -m pytest
```

If the task only changes documentation or instructions, state that no runtime tests were required.

Do not claim a coding task is done if tests were not run or did not pass, unless the user explicitly accepts that exception.

## Matching rules

- Matching must use only clean, normalized, available inventory.
- Do not mix rejected, duplicate, invalid, stale, or unavailable records into matching.
- `bedrooms_count` may be a hard filter when the client defines `min_bedrooms`.
- `rooms_count` must not substitute `bedrooms_count` unless the code has a clear signal.
- Location can be a hard filter.
- `m2` and `energy_label` are scoring/warnings unless the client explicitly marks them as mandatory.
- Missing optional fields must not automatically reject a property.

## Agent workflow discipline

For every task:

1. Read this file.
2. Read the relevant architecture doc under `docs/`.
3. Inspect existing code before writing new code.
4. Prefer small, traceable changes.
5. Add or update tests for behavior changes.
6. Avoid adding new dependencies unless necessary.
7. Report changed files, validation commands, and next recommended step.

## Current priority order

1. Repo realignment and agent operating system.
2. Inventory core models and daily state engine.
3. Access policy and source registry v2.
4. Delivery mode fingerprint v2.
5. Parser family config runner.
6. Real parser families: static HTML, WordPress cards, JSON-LD, sitemap/detail, XHR JSON, Realworks/OGonline stabilization.
7. QA gates: BAG/PDOK normalization, price sanity, transaction type, status validation, dedupe.
8. Matching and advisor email generation.
9. n8n orchestration and scheduled jobs.
10. Dashboard only after inventory + matching are stable.
