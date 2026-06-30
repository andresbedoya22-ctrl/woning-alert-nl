# Noord-Brabant Coverage Source Census v1

## Objective

Create an auditable source census for makelaars and source domains that may publish koopwoningen in Noord-Brabant, before applying parser families across the province.

## Strategic context

The next strategic step is source coverage intelligence, not matching or a parser-per-makelaar expansion. Realworks is ready for a later Noord-Brabant Realworks audit, but this census first identifies which domains are Realworks, OGonline, WordPress, custom delivery, blocked/legal-review, no-public-aanbod, inactive, duplicate, or out of scope.

## Scope and constraints

This phase adds `scraper/src/domek_wonen/sources/coverage_census.py` and `scripts/run_noord_brabant_coverage_source_census.py`. It consolidates local evidence, classifies each deduped source terminally, and writes local CSV/XLSX artifacts under `tmp/generated/`.

It does not run matching, create client alerts, send advisor emails, touch n8n, create a dashboard, create a database, add migrations, apply Realworks to all makelaars, parse property inventory, create a new parser family, modify `data/raw`, use Funda or Pararius operationally, persist raw HTML/JSON, copy long descriptions, download images, use browser automation, use proxies or bypass controls, use an LLM in runtime, create a parser per makelaar, or change global eligibility.

## Local evidence inputs

The census reads:

- `data/processed/sources_seed_noord_brabant.csv`
- `data/discovery/reference/property_discovery_source_overrides.csv`
- `data/discovery/processed/sources_seed_with_gemeente.csv`
- `data/discovery/platform_fingerprint/platform_fingerprint_results.csv`
- `data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv`

Generated artifacts are local and must not be committed.

## Coverage definition

Office location is the makelaar office city/gemeente/province when the local evidence provides it.

Coverage location is the city/gemeente/province where the source evidence says the source may publish listings. This is kept separate from office location.

Aanbod location is represented by the accepted official `aanbod_url` and its evidence. Funda and Pararius URLs are rejected as operational aanbod URLs.

Outside-office sources with Noord-Brabant aanbod are allowed in scope when local evidence indicates Noord-Brabant coverage, even if the office province is outside Noord-Brabant.

## Investigation loop

The module defines the bounded pass names:

- `pass_1_local_evidence`
- `pass_2_homepage_links`
- `pass_3_sitemap`
- `pass_4_common_paths`
- `pass_5_family_fingerprint`
- `pass_6_conflict_resolution`
- `pass_7_final_terminal_classification`

The runner defaults to local evidence only. Live HTTP is opt-in with `--allow-live-http`, sequential, capped per domain, standard-library only, and guarded by `robots_gate.can_fetch(domain, path)` before fetch.

## Aanbod URL discovery

Discovery prioritizes explicit local `aanbod_url` values, then homepage links, sitemap URLs, and conservative common official paths when a fetcher is supplied.

The census rejects Funda/Pararius as operational URLs, rejects property detail URLs, rejects non-official domains, and records rejected candidates with reasons.

## Family fingerprinting

Fingerprinting recognizes Realworks, OGonline XHR, WordPress JSON/static, Kolibri, Skarabee, iframe vendor, custom HTML, custom XHR, and custom JS app signals. If exact vendor evidence is not available, the census uses a technical delivery classification rather than leaving an operational unknown.

Evidence previews are capped and sanitized. Raw HTML/JSON and long descriptions are not persisted.

## Terminal classifications

Allowed terminal source statuses are:

- `confirmed_source_ready`
- `confirmed_source_needs_parser_family`
- `confirmed_no_public_aanbod`
- `confirmed_blocked_or_legal_review`
- `confirmed_out_of_scope`
- `confirmed_duplicate`
- `confirmed_inactive_or_no_longer_trading`

The implementation does not leave final `unknown`, `missing`, `tbd`, or `todo` parser-family values for in-scope operational records.

## Quality gates

The hard gates are:

- `operational_unknown_family_count = 0`
- `missing_aanbod_url_without_terminal_reason_count = 0`

The generated local run passed both gates.

## Output artifacts

Generated locally:

- `tmp/generated/noord_brabant_coverage_source_census_v1.xlsx`
- `tmp/generated/noord_brabant_coverage_source_census_v1.csv`
- `tmp/generated/noord_brabant_coverage_source_census_v1_review_queue.csv`

Workbook sheets:

- `Master Sources`
- `Aanbod URL Evidence`
- `Family Fingerprints`
- `Investigation Attempts`
- `Coverage Matrix`
- `Realworks Candidates`
- `OGonline Candidates`
- `Custom Needs Parser`
- `Blocked or Legal Review`
- `Duplicates`
- `Review Queue`

Note: Excel does not permit `/` in worksheet names, so the requested `Custom/Needs Parser` sheet is written as `Custom Needs Parser`.

## Results

Local artifact run:

- total evidence rows: `1812`
- deduped sources: `363`
- in-scope Noord-Brabant coverage sources: `363`
- outside-office sources included because they sell in Noord-Brabant: `0`
- sources with accepted aanbod URL: `222`
- sources without public aanbod: `140`
- blocked/legal-review sources: `5`
- out-of-scope sources: `0`
- duplicate source evidence rows: `1449`
- operational unknown family count: `0`
- missing aanbod URL without terminal reason count: `0`

## Review queue

Review queue count: `5`.

The review queue is intentionally small. Broad custom/needs-parser sources are available in the workbook's `Custom Needs Parser` sheet; the queue focuses on blocked/legal-review or gate-failure records.

## Parser family distribution

- `blocked_or_legal_review`: `5`
- `custom_js_app`: `126`
- `no_public_aanbod`: `140`
- `realworks_public`: `73`
- `wordpress_json`: `18`
- `wordpress_static`: `1`

## Recommended next action

1. Manually review the generated census workbook.
2. Use all confirmed `realworks_public` sources for Noord-Brabant Realworks Audit v1.
3. Treat `custom_js_app`, WordPress, and other custom groups as parser-family/source-config planning inputs, not as parser-per-makelaar work.

## Constraints confirmation

No matching/client alerts/advisor email, no n8n/dashboard, no DB/migrations, no apply-to-all Realworks yet, no property inventory parsing, no `data/raw`, no Funda/Pararius operational source, no raw HTML/JSON, no long descriptions/images, no browser automation/proxies/bypass, no LLM runtime, no parser per makelaar, no global eligibility changes, no force push, and no merge to main.
