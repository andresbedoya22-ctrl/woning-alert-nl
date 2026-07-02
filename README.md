# WoningAlert NL

WoningAlert NL is a discovery-first housing intelligence system for the Dutch koopwoning market. The product goal is to identify allowed housing sources, classify their technical delivery patterns, build a safe normalized inventory, compare daily changes, match opportunities against active client searches, and prepare advisor-facing outputs.

## What problem it solves

Advisors should not depend on manual searching across dozens of heterogeneous housing sources. The repo exists to turn scattered public source signals into a controlled inventory pipeline with explicit access policy, reliable change tracking, and matching-ready records.

## What it is not

- It is not a full-market scraper.
- It is not an operational pipeline built on automatic Funda scraping.
- It is not an operational pipeline built on automatic Pararius scraping.
- It is not a parser-per-makelaar strategy.
- It is not a dashboard-first project.
- It is not a stealth automation project.

## Core scaling principle

WoningAlert NL does not scale by creating one parser per makelaar.

WoningAlert NL scales by using source intelligence, delivery modes, parser families, and source configs.

## Target flow

```text
source_registry
-> source_intelligence
-> access_policy
-> delivery_mode_fingerprint
-> parser_family
-> source_config
-> normalized_listing
-> inventory_state
-> client_matching
-> advisor_email
-> n8n_orchestration
```

## High-level architecture

```text
Discovery / Existing Sources
        |
        v
Source Intelligence
        |
        v
Access Policy
        |
        v
Delivery Mode Fingerprint
        |
        v
Parser Family + Source Config
        |
        v
Normalized Listing
        |
        v
QA / Normalization Gates
        |
        v
Inventory State Engine
        |
        v
Client Matching
        |
        v
Advisor Email / Review Pack
        |
        v
n8n Orchestration
```

## Main modules

- `scraper/src/domek_wonen/sources/`: source registry, source intelligence, access policy, delivery fingerprinting.
- `scraper/src/domek_wonen/parsers/`: parser families and domain-level source configs.
- `scraper/src/domek_wonen/pilots/`: small controlled pilots that connect permitted source capture to parser, QA, and inventory layers.
- `scraper/src/domek_wonen/inventory/`: normalized listings, snapshots, diffs, stale-source handling.
- `scraper/src/domek_wonen/qa/`: quality gates, normalization, dedupe, review states.
- `scraper/src/domek_wonen/matching/`: current and future matching logic.
- `scraper/src/domek_wonen/orchestration/`: n8n-facing jobs, schedules, alerts, retries.
- `scraper/src/domek_wonen/portals/`: legacy or diagnostic portal experiments, not the strategic V4 path.
- `scraper/src/domek_wonen/properties/`: legacy property-discovery stack to mine for reusable parser-family ideas.

## Non-negotiable rules

- No automatic scraping of Funda.
- No automatic scraping of Pararius without explicit permission, license, or review.
- No stealth browser automation.
- No CAPTCHA solving.
- No residential proxies.
- No IP rotation to evade controls.
- No human simulation to bypass detection.
- No bypass of login walls, `403`, paywalls, robots, or explicit blocking.
- If a source blocks access, mark it `blocked`, `permission_required`, or `legal_review`.
- Extract only minimum necessary data.
- Do not copy long descriptions.
- Do not download images without explicit permission or license.
- Do not move properties into matching before QA gates pass.
- Do not build dashboard flows before inventory and matching are stable.
- Do not modify `data/raw` unless the user explicitly asks.
- Do not commit generated outputs.

## Working with Codex

- Read [AGENTS.md](/C:/Projects/domek-wonen/AGENTS.md) first.
- Inspect real files before claiming they exist.
- Prefer small, phase-bounded tasks.
- Do not broaden scope from docs to runtime code without need.
- Add or update tests when runtime code changes.
- Run `python -m pytest` after code changes; for docs-only work, run it when practical and report the exact outcome.
- Report changed files, validation status, branch, and residual risks.

Task template for Codex lives in [docs/09_CODEX_WORKFLOW.md](/C:/Projects/domek-wonen/docs/09_CODEX_WORKFLOW.md).

## Install dependencies

```powershell
py -3.12 -m pip install -r requirements.txt
```

## Run tests

```powershell
python -m pytest
```

Pytest is configured to keep its temporary and cache paths under `tmp/` in this repo.

## Current repo status

As of this architecture reset, the repo already contains:

- discovery and diagnostics code under `scraper/src/domek_wonen/discovery/` and `diagnostics/`;
- legacy portal and property-discovery modules under `portals/` and `properties/`;
- current matching code under `matching/`;
- multiple historical planning docs under `docs/`;
- scripts for source master, coverage, fingerprinting, matching, and audits under `scripts/`.

This PR reframes that codebase under a professional architecture without deleting existing functional modules.

## Controlled Realworks Capture Pilot v1

`scraper/src/domek_wonen/pilots/realworks_capture_pilot.py` adds the first controlled pilot for a small batch of permitted `realworks_public` listing sources. The pilot calls `robots_gate.can_fetch(domain, path)` before any injected fetch function is allowed to run, caps batches at five sources by default, and connects captured HTML through `ParserFamilyRunner`, the parser output QA gate, and `InventorySnapshot` creation.

The pilot does not include a real HTTP fetcher, Playwright, Selenium, stealth automation, proxies, CAPTCHA handling, bypass behavior, persistence, dashboard work, matching, or n8n orchestration. Captured HTML and generated run outputs remain local/generated artifacts and must not be committed.

## Controlled Source Selection for Realworks Pilot v1

`scraper/src/domek_wonen/pilots/source_selection.py` selects up to five `realworks_public` sources from local enriched source-intelligence evidence and converts them into `CapturePilotSource` inputs for the capture pilot.

This selection layer is offline. It does not make network requests, call `robots_gate`, capture HTML, use browser automation, or touch generated capture outputs. It excludes Funda, Pararius, blocked, permission-required, legal-review, manual-review, missing-domain, and missing-URL rows before the capture pilot gets a source list.

## Controlled Realworks Live Fetch v1

`scraper/src/domek_wonen/pilots/live_fetch.py` adds an explicit controlled HTTP fetcher for a small `realworks_public` live pilot. It uses only standard-library HTTP, a clear non-stealth User-Agent, one GET, a required timeout, stable fetch exceptions, and accepts only HTML or text responses.

The fetcher does not call `robots_gate` itself: the capture pilot remains responsible for checking `robots_gate.can_fetch(domain, path)` before invoking any fetch function. The live helper defaults to `max_sources=3`, includes domain dedupe so the first run avoids several variants from the same source domain, and adds no Playwright, Selenium, proxies, stealth behavior, CAPTCHA handling, bypass logic, persistence, or generated outputs.

## Realworks Parser Family Validation v1

Oldenkotte (`oldenkotte.com__tilburg`) was used as the Realworks parser-family validation target. The family-level parser now prefers Realworks listing card containers such as `aanbodEntry`, filters category/archive/service links before parsing, and extracts address, city, price, status, and detail URL fields from the listing card container instead of global navigation anchors.

Validation on the live Oldenkotte listing page improved from `36 total / 0 clean / 36 review / 0 rejected` to `9 total / 9 clean / 0 review / 0 rejected`, with `9` inventory snapshot listings. Backup validation on `olden.nl__heusden` produced `10 total / 10 clean / 0 review / 0 rejected`. This remains a reusable Realworks parser-family improvement, not an Oldenkotte-specific parser, and it does not add matching, email, n8n, dashboard, Excel, eligibility changes, Funda/Pararius work, browser automation, LLM extraction, or raw HTML/JSON persistence.

## Realworks Detail Facts Probe v1

`scraper/src/domek_wonen/pilots/realworks_detail_facts_probe.py` adds a diagnostic probe for permitted Realworks detail pages. It reads in-memory detail HTML and reports compact field availability from reusable Realworks `kenmerkName` / `kenmerkValue` blocks, including areas, rooms, bedrooms, bathrooms, volume, energy label, bouwjaar, heating, insulation, garden, parking, garage, ownership, and description length bucket.

This is not a normalized facts extractor, cache, readiness runner, Excel export, matching input, email flow, n8n job, dashboard, or parser per makelaar. It does not persist raw HTML or JSON, copy long descriptions, download images, call an LLM, touch eligibility, scrape Funda or Pararius, or modify `data/raw`.

## Realworks Property Facts Extractor v1

`scraper/src/domek_wonen/facts/realworks_extractor.py` converts permitted Realworks detail HTML held in memory into the existing `PropertyFactsRecord` contract using reusable `kenmerkName` / `kenmerkValue` blocks.

The extractor is family-level, not Oldenkotte-specific, and does not create a parser per makelaar. It stores normalized facts plus statuses, evidence previews, and warnings, while keeping descriptions to a length bucket only. `scraper/src/domek_wonen/pilots/realworks_property_facts_validation.py` provides a bounded validation helper with robots checks before listing and detail fetches.

This phase does not add cache, readiness rows, Excel, matching, email, n8n, dashboard, eligibility changes, Funda/Pararius work, browser automation, Playwright, Selenium, proxies, stealth behavior, CAPTCHA solving, bypass logic, raw HTML/JSON persistence, long-description storage, image downloads, or LLM extraction.

## Realworks Readiness Rows v1

`scraper/src/domek_wonen/pilots/realworks_property_readiness.py` builds in-memory Realworks readiness rows from
QA-clean parser listings, Realworks `PropertyFactsRecord` detail facts, `ClientReadyPropertySummary`, and location
readiness. It classifies rows as `client_ready`, `advisor_review`, or `blocked`, maps them to export readiness, and
reports field completion, missing key fields, review fields, warnings, sample rows, and compact problem rows before any
Excel phase.

The Oldenkotte validation built `9` readiness rows from `9` QA-clean listings and `9` successful detail facts records.
All rows were `advisor_review` / `export_review`, mainly because postcode is missing for all rows; this is ready for a
human Excel validation phase, not production client-ready promotion.

This phase remains in-memory only. It creates no Excel, cache, matching input, email, n8n flow, dashboard, raw
persistence, Funda/Pararius path, browser automation, LLM extraction, image downloads, parser per makelaar, or
eligibility changes.

## KIN OGonline XHR Paginated Runner v1

`scraper/src/domek_wonen/pilots/ogonline_xhr_paginated_runner.py` adds a controlled paginated runner for `ogonline_xhr` source configs, starting with the KIN fixture. It builds deterministic API URLs with `build_paginated_api_url`, checks `robots_gate.can_fetch(api_domain, api_path)` before each injected `fetch_json` call, then sends caller-provided JSON through `build_parser_input_from_api_json`, `ParserFamilyRunner`, and the parser output QA gate.

This phase does not implement real HTTP, live fetch orchestration, Playwright, Selenium, stealth behavior, proxies, CAPTCHA handling, bypass logic, JSON persistence, property-discovery runtime changes, matching, dashboard work, or n8n orchestration. A real live runner can be added later after this offline config-to-parser path remains stable.

## Controlled OGonline Live Fetch v1

`scraper/src/domek_wonen/pilots/ogonline_xhr_live_fetch.py` adds the controlled standard-library JSON fetch helper for a minimal KIN `ogonline_xhr` live pilot. The fetcher performs one GET with a required timeout and clear non-stealth User-Agent, accepts JSON or text content that parses as JSON, returns the original JSON string, and does not persist responses.

Robots compliance remains upstream in `run_ogonline_xhr_paginated_config`, which checks `robots_gate.can_fetch(api_domain, api_path)` before invoking the fetch function for each API page. The KIN helper caps live execution through `max_pages` and adds no browser automation, retries, parallelism, proxies, stealth behavior, CAPTCHA handling, bypass logic, generated outputs, property-discovery runtime changes, matching, dashboard work, or n8n orchestration.

## Inventory Eligibility Gate v1

`scraper/src/domek_wonen/inventory/eligibility.py` adds an offline eligibility layer after parser output QA. It consumes
`ParserFamilyQAResult`, keeps QA review and rejected listings out of active inventory, and separates QA-clean listings
into active, inactive status, unsupported transaction type, unsupported property type, or review buckets.

The gate does not make HTTP requests, use live fetch, modify matching, relax QA, touch property-discovery runtime, or
change n8n or dashboard flows. Only `koop + beschikbaar + allowed_property_type` listings enter `active_inventory`.
`onder_bod`, `verkocht`, `verhuurd`, `unknown` or empty statuses, unsupported or unknown transaction types, and empty or
unsupported property types stay outside active inventory.

## KIN OGonline Active Inventory Pilot v1

`scraper/src/domek_wonen/pilots/kin_ogonline_active_inventory_pilot.py` connects the controlled KIN `ogonline_xhr` live
path to the active inventory gate with `max_pages=2`. It loads the KIN source config, builds deterministic OGonline API
page URLs, checks `robots_gate.can_fetch(api_domain, api_path)`, fetches JSON through the controlled standard-library
helper, runs `ParserFamilyRunner`, applies parser output QA, applies inventory eligibility, and builds an inventory
snapshot from active inventory only.

The pilot does not persist live JSON or HTML, does not touch matching, n8n, dashboard, Funda, Pararius, or `data/raw`,
and does not add retries, parallelism, browser automation, proxies, stealth behavior, CAPTCHA handling, or bypass logic.
Only `active_inventory` listings are passed to the snapshot helper.

## OGonline Detail Property Type Enrichment v1

`scraper/src/domek_wonen/pilots/ogonline_detail_property_type_enrichment.py` adds a bounded enrichment step for the KIN
OGonline active inventory pilot. The OGonline listing API does not expose a useful residential `property_type` for the
current KIN live shape, while the permitted detail page embedded state can expose conservative values such as
`Tussenwoning`, `Vrijstaande woning`, and `Appartement`.

The enrichment is separate from the base `ogonline_xhr` parser family and is disabled by default in
`run_kin_ogonline_active_inventory_pilot`. When explicitly enabled, it checks `robots_gate.can_fetch(domain, path)`
before each detail fetch, caps detail pages through `max_detail_enrichment`, extracts only property-type candidates,
and does not persist HTML or JSON. Eligibility still decides active, inactive, unsupported, or review outcomes after
enrichment. `Open huis` remains a badge/event signal, not a property type or availability status.

## KIN OGonline 5-page Validation Audit v1

`scraper/src/domek_wonen/pilots/kin_ogonline_validation_audit.py` adds a separate validation audit for the KIN
OGonline flow. It measures the listing API, base `ogonline_xhr` parser, parser QA, detail property-type enrichment,
inventory eligibility, and active-only inventory snapshot across at most five API pages.

The audit is separate from the two-page active inventory pilot and does not change its default behavior. It can enrich
QA-clean eligible listings from permitted detail pages, but caps detail enrichment at 120 pages, does not persist live
HTML or JSON, and does not run full KIN. It does not touch matching, n8n, dashboard, Funda, Pararius, or `data/raw`.
The result reports parser, QA, enrichment, eligibility, snapshot, status, decision, property-type, and warning metrics.

## KIN Full OGonline Validation Audit v1

`scraper/src/domek_wonen/pilots/kin_ogonline_full_validation_audit.py` adds a controlled full-source validation audit
for the explicit KIN OGonline source config. It is separate from the two-page active inventory pilot and the five-page
validation audit, and measures the listing API, base `ogonline_xhr` parser, parser QA, detail property-type enrichment,
inventory eligibility, and active-only inventory snapshot across the available KIN API inventory.

Full does not mean unlimited: API pagination is capped at 25 pages and detail enrichment is capped at 300 detail pages.
The audit may use reported `totalPages`, `totalDocs`, or `hasNextPage` metadata to decide how many pages to attempt
within that cap. It does not implement new mappings, change parser or eligibility behavior, persist live HTML or JSON,
touch matching, n8n, dashboard, Funda, Pararius, or `data/raw`, or run a generic crawler. Its output is intended to
decide whether KIN is sufficiently validated before a later OGonline Coverage Audit.

The full audit can also run with explicit runtime budgets for the whole audit and for detail enrichment. If a budget is
exhausted, it returns a partial result with the parser, QA, enrichment, eligibility, and snapshot counts completed so
far, plus stable budget warnings. For KIN full validation, use a runtime budget before treating this as any operational
gate; the audit remains diagnostic and bounded, not an operational crawler.

## OGonline Detail Facts Probe v1

`scraper/src/domek_wonen/pilots/ogonline_detail_facts_probe.py` adds a controlled probe for discovering which property
facts are available on permitted OGonline/KIN detail pages. It is a diagnostic layer for designing later
`OGonline Detail Facts Cache v1` and `Property Facts Extractor v1`, not an operational extractor.

The probe checks `robots_gate.can_fetch(domain, path)` before API and detail fetches, caps KIN API sampling at five
pages and detail samples at twenty, and keeps live responses in memory only. It does not cache, persist HTML or JSON,
copy long descriptions, download images, modify the base `ogonline_xhr` parser, relax QA, touch matching, n8n,
dashboard, Funda, Pararius, or `data/raw`. Description handling is limited to source availability, a length bucket,
and an optional preview capped at 120 characters.

## OGonline Property Facts Contract + Cache v1

`scraper/src/domek_wonen/facts/` defines the offline, normalized property-facts contract that a later
`OGonline Normalized Facts Extractor v1` can populate. The contract stores allowlisted fact fields with normalized
values, confidence, status, source, compact evidence previews, schema version, source identity, canonical URL,
fetch timestamps, expiry, and stable warnings.

This is not a live extractor and does not make HTTP requests, run Playwright or Selenium, use proxies, call an LLM,
modify matching, n8n, dashboard, the base OGonline parser, eligibility, Funda, Pararius, or `data/raw`. The cache is
a local/generated JSONL artifact that writes only when callers pass an explicit path. It stores normalized facts and
minimum evidence previews only; it must not store raw HTML, raw web JSON, images, or long descriptions.

## OGonline Normalized Facts Extractor v1

`scraper/src/domek_wonen/facts/ogonline_extractor.py` adds the controlled extractor for permitted OGonline detail
pages. It converts in-memory detail HTML plus listing metadata into the existing `PropertyFactsRecord` contract,
normalizing property type, price, areas, rooms, bedrooms, bathrooms, energy label, ownership, VvE, heating, outdoor,
parking, availability, Open huis/event, and description length bucket signals.

The extractor uses `PropertyFactsCache` only when callers pass an explicit cache path. Fresh cache hits skip repeated
detail fetches; stale records or `force_refresh=True` cause a new permitted detail fetch. Cache files remain
local/generated artifacts and store only normalized facts, compact evidence previews, timestamps, and warnings. The
extractor does not persist raw HTML, raw web JSON, images, or long descriptions, does not create LLM summaries, and does
not touch matching, n8n, dashboard, Funda, Pararius, the base OGonline parser, eligibility, or `data/raw`. This prepares
a later `Client-ready Property Summary v1` without implementing that summary yet.

Quality hardening keeps the extractor conservative: equivalent normalized values no longer create false conflicts,
structured sources outrank weak text signals, count fields reject implausible values, and ambiguous candidates are
reported only when the final field remains in review. Live warnings still need to be reviewed before using these facts
for client-ready summaries.

## Client-ready Property Summary v1

`scraper/src/domek_wonen/facts/summary.py` adds an offline compact property card for advisor and client review. It
converts an existing `PropertyFactsRecord` into a deterministic `ClientReadyPropertySummary` with headline,
facts, financial, outdoor, energy, attention, missing-key-field, and warning sections.

The summary uses only normalized facts that are already marked `usable`. Facts marked `review` become attention points,
and missing key fields are reported explicitly instead of being invented. This layer does not call an LLM, perform live
fetches, write cache files, store raw HTML or raw web JSON, copy long descriptions, download images, touch matching,
n8n, dashboard, Funda, Pararius, `data/raw`, the base OGonline parser, or inventory eligibility.

## KIN Full Facts + Location Readiness v1

`scraper/src/domek_wonen/pilots/kin_full_property_readiness.py` adds a controlled full-source readiness runner for KIN
as the OGonline laboratory. It combines KIN listing API capture, parser QA-clean listings, normalized detail facts, the
facts cache, `ClientReadyPropertySummary`, and location readiness into in-memory rows that are ready for a later Excel
export phase.

This phase does not create Excel files, send email, run matching, touch n8n, build a dashboard, modify `data/raw`,
scrape Funda or Pararius, call an LLM, persist raw HTML or raw web JSON, download images, change the base OGonline
parser, or change inventory eligibility. Location is explicit because future client matching needs at least a usable or
reviewable address/city/postcode signal before a row can be exported safely.

## KIN Full Coverage Completion + Field Gap Audit v1

`scraper/src/domek_wonen/pilots/kin_full_coverage_audit.py` adds a completion/audit layer on top of the KIN full
property readiness runner. It requires an explicit facts `cache_path`, reuses cache hits between bounded runs, and
raises the effective detail limit enough that cached rows do not prevent later uncached QA-clean listings from being
attempted. The audit reports total QA-clean coverage, partial/completed state, cache and detail-fetch counters, export
readiness counts, quality status counts, field gaps, top blockers, and compact problem-row samples.

The audit computes gaps before any Excel phase. It checks usable, review, and missing counts for key property facts
plus location fields, including latitude and longitude as known completeness gaps rather than hard blockers when
address, postcode, and city are usable. It does not create Excel, send email, run matching, touch n8n, build a
dashboard, persist raw HTML or raw web JSON, call an LLM, download images, scrape Funda or Pararius, modify
`data/raw`, change the base OGonline parser, or change inventory eligibility.

## KIN Key Matching Fields Hardening v1

The OGonline facts extractor now applies conservative family-level hardening for key future matching fields:
`bedrooms`, `living_area_m2`, `property_type`, and `energy_label`. Bedrooms are accepted only from structured fields or
strong slaapkamer labels, living area is accepted from specific woonoppervlakte/gebruiksoppervlakte wonen signals,
property type prefers structured OGonline detail state over weak text, and energy-label spacing/casing variants are
normalized before conflict handling.

This phase does not infer bedrooms from rooms, does not use an LLM, does not persist raw HTML or raw web JSON, and does
not create Excel, send email, run matching, touch n8n, build a dashboard, modify `data/raw`, scrape Funda or Pararius,
change inventory eligibility, or add a parser per makelaar.

## KIN Excel Export v1

`scraper/src/domek_wonen/pilots/kin_excel_export.py` exports existing in-memory KIN readiness rows to a local `.xlsx`
validation artifact. It consumes rows produced by `run_kin_full_property_readiness`, writes all available rows rather
than only client-ready samples, and includes canonical URL text plus a clickable `property_link`.

The workbook includes facts, client-ready summary lines, location readiness, `export_readiness`, `quality_status`,
`missing_key_fields`, warnings, summary counts, field gaps, warning aggregation, and compact problem rows. Output paths
are caller-provided local/generated paths such as `tmp/generated/kin_excel_export_v1.xlsx`; generated `.xlsx` files and
cache files must not be committed.

This phase does not send email, run matching, touch n8n, build a dashboard, modify `data/raw`, persist raw HTML or raw
web JSON, call an LLM, download images, scrape Funda or Pararius, change inventory eligibility, or create a parser per
makelaar.

## Realworks Excel Validation v1

`scraper/src/domek_wonen/pilots/realworks_excel_export.py` exports existing Realworks readiness rows to a local
caller-provided `.xlsx` validation artifact. It writes all rows, including the current Oldenkotte `export_review` rows,
preserves full `canonical_url` text, and creates a clickable `property_link`.

The workbook contains `Realworks Properties`, `Summary`, `Field Gaps`, `Warnings`, and `Problem Rows` worksheets. The
current Oldenkotte sample remains human-review only: `8` rows are `export_review` and the Corellistraat-style
`OverigOG` row is `export_blocked`, not production client-ready output. The export makes postcode critical, VvE
explicit for apartments, energy labels visible as value/status/raw, and non-residential classifications visible.
Postcode is extracted from JSON-LD or visible Realworks detail headers when present, and status policy columns keep
sold/under-contract rows for source history while excluding them from active inventory/matching.
Generated `.xlsx` files such as `tmp/generated/realworks_oldenkotte_excel_validation_v1.xlsx` must not be committed.

This phase does not send email, run matching, touch n8n, build a dashboard, modify `data/raw`, persist raw HTML or raw
web JSON, call an LLM, download images, copy long descriptions, scrape Funda or Pararius, change inventory eligibility,
or create a parser per makelaar.

## Realworks Freshness & Lifecycle Fields v1

`scraper/src/domek_wonen/inventory/lifecycle.py` adds a family-agnostic offline contract for source publication dates,
first-seen/last-seen/observed timestamps, freshness buckets, and lifecycle events. Realworks readiness rows and the
Excel validation workbook now expose these fields while keeping `source_published_at`, `first_seen_at`, and
`observed_at` separate.

The Realworks extractor reads explicit publication-date candidates from JSON-LD, embedded state, and reusable
`kenmerkName` / `kenmerkValue` labels. It does not invent publication dates from bouwjaar, status text, or URL ids.
`dateModified` is review-only when it is the only candidate. This phase creates no real DB, migrations, matching,
client alerts, advisor email, n8n, dashboard, raw HTML/JSON persistence, long-description export, images, LLM path,
Funda/Pararius path, parser per makelaar, or global eligibility change.

## Realworks Multi-source Validation v1

`scraper/src/domek_wonen/pilots/realworks_multi_source_validation.py` validates the reusable Realworks family across
locally evidenced sources instead of treating Oldenkotte as the only proof point. The selector keeps Oldenkotte as
control, includes Olden when local evidence is available, excludes Funda/Pararius and blocked/legal-review/permission
rows, then runs the existing parser, QA, bounded detail facts, readiness, status/history, and lifecycle path per source.

The bounded live validation selected `oldenkotte.com__tilburg` and `olden.nl__heusden`. Both passed with explicit
review gaps, so the family decision is `realworks_family_usable_for_broader_audit`. Generated artifacts such as
`tmp/generated/realworks_multi_source_validation_v1.xlsx` and the summary CSV remain local and must not be committed.

This phase does not add matching, client alerts, advisor email, n8n, dashboard, DB, migrations, Noord-Brabant full
census, raw HTML/JSON persistence, long descriptions, images, browser automation, proxies, bypass behavior, LLM use,
parser-per-makelaar logic, Funda/Pararius work, `data/raw` changes, or global eligibility changes.

## Realworks Broader Bounded Audit v1

`scraper/src/domek_wonen/pilots/realworks_broader_bounded_audit.py` validates the reusable Realworks family on
additional locally evidenced Realworks makelaars beyond Oldenkotte and Olden. It writes a local manual-verification
workbook and summary CSV under `tmp/generated/`, excluding generated artifacts from git.

The bounded audit selected `alstedevanmierlomakelaardij.nl__tilburg`, `cvda.nl__tilburg`, and
`hansvanberkel.nl__tilburg`, producing 29 manual verification rows. The family decision is
`realworks_ready_for_noord_brabant_realworks_audit`, with review gaps still explicit.

This phase does not add matching, client alerts, advisor email, n8n, dashboard, DB, migrations, Noord-Brabant full
census, raw HTML/JSON persistence, long descriptions, images, browser automation, proxies, bypass behavior, LLM use,
parser-per-makelaar logic, Funda/Pararius work, `data/raw` changes, apply-to-all Realworks execution, or global
eligibility changes.

## Noord-Brabant Coverage Source Census Hardened v1

`scraper/src/domek_wonen/sources/coverage_census.py` consolidates local source evidence into a terminally classified
Noord-Brabant source census before broader parser-family application. It separates office location, coverage location,
and accepted aanbod URL evidence, dedupes by normalized domain, rejects Funda/Pararius and property-detail URLs as
operational aanbod URLs, and classifies every in-scope source as a reusable family, technical delivery mode,
no-public-aanbod, blocked/legal-review, inactive, duplicate, or out of scope.

`scripts/run_noord_brabant_coverage_source_census.py` writes local generated artifacts under `tmp/generated/`, including
the hardened master CSV, review queue CSV, workbook, and optional live-run log. Live HTTP is opt-in only, sequential,
capped, standard-library based, and guarded by `robots_gate.can_fetch(domain, path)`. The hardened census writes
`accepted_aanbod_url` instead of an ambiguous operational `aanbod_url`, moves missing-domain evidence into a dedicated
queue, verifies Realworks with strong structural evidence, resolves KIN to `ogonline_xhr`, and re-fingerprints
`custom_js_app` rows before finalization. The phase does not create matching, client alerts, advisor email, n8n,
dashboard, DB/migrations, property inventory parsing, raw HTML/JSON persistence, images, LLM runtime, a parser per
makelaar, or global eligibility changes.

## Noord-Brabant Source Completion & Scope Verification v1

The coverage census runner now has an explicit completion mode:

```powershell
python scripts/run_noord_brabant_coverage_source_census.py --allow-live-http --completion-scope-verification --max-passes 8 --max-requests-per-domain 10 --timeout-seconds 15
```

This mode keeps the same source-intelligence scope, but adds final verification tables for missing-domain rows,
`no_public_aanbod` decisions, accepted aanbod URL scope, Realworks audit readiness, and office location evidence. Live
HTTP remains opt-in, sequential, capped, standard-library based, and guarded by `robots_gate.can_fetch(domain, path)`.

Generated local artifacts:

- `tmp/generated/noord_brabant_source_completion_scope_verification_v1.xlsx`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v1.csv`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v1_review_queue.csv`
- `tmp/generated/noord_brabant_realworks_audit_input_v1.csv`

The Realworks audit input CSV contains only verified `realworks_public` records with accepted official aanbod URLs and
scope status ready for the later Noord-Brabant Realworks audit. KIN remains classified as `ogonline_xhr` and is excluded
from Realworks audit input.

## Missing Domain External Resolution v1

The coverage census runner also supports:

```powershell
python scripts/run_noord_brabant_coverage_source_census.py --allow-live-http --completion-scope-verification --missing-domain-external-resolution --max-passes 8 --max-requests-per-domain 10 --timeout-seconds 15
```

This controlled follow-up attempts every Missing Domain Queue row. It first resolves duplicates or existing sources by
local name/alias/raw-id evidence, then checks at most eight conservative official-domain candidates per row. Funda,
Pararius, search/social/maps pages, directories, comparison sites, and third-party portals are rejected as operational
official domains. Verified new domains are deduped before becoming source candidates, and accepted aanbod URLs still
reject property-detail, off-domain, Funda/Pararius, and third-party-only URLs.

Live checks remain opt-in, sequential, capped, standard-library based, and guarded by `robots_gate.can_fetch`. The mode
writes local generated resolution artifacts plus Source Completion v2 CSV/XLSX files under `tmp/generated/`; these are
not committed. It does not run matching, alerts, advisor email, n8n, dashboard, DB/migrations, full inventory, browser
automation, proxies, bypass behavior, LLM runtime, parser-per-makelaar logic, or `data/raw` changes.

## Noord-Brabant Realworks Audit v1

`scraper/src/domek_wonen/pilots/noord_brabant_realworks_audit.py` audits only the ready
`tmp/generated/noord_brabant_realworks_audit_input_v1.csv` handoff set. The runner validates the 65-source input
strictly, rejects KIN, unclear scope, missing accepted URL, Funda/Pararius, property-detail, blocked/legal/manual-review,
and non-Realworks rows, then reuses the existing Realworks readiness path for sequential bounded listing/detail checks.

The CLI writes local generated artifacts under `tmp/generated/`:

- `tmp/generated/noord_brabant_realworks_audit_v1.xlsx`
- `tmp/generated/noord_brabant_realworks_audit_v1_summary.csv`
- `tmp/generated/noord_brabant_realworks_audit_v1_problem_sources.csv`

The handoff was repaired after an initial audit attempt correctly refused an invalid CSV missing `coverage_province`
and `parser_family_candidate`. The source-completion producer now emits canonical audit-input columns plus
`tmp/generated/noord_brabant_realworks_audit_input_reconciliation_v1.csv`. The regenerated reconciled run authorizes
`65` ready Realworks sources and excludes `26` verified Realworks rows pending manual scope check; KIN remains excluded.

This phase remains audit-only: no matching, alerts, advisor email, n8n, dashboard, DB, migrations, full inventory,
`data/raw`, Funda/Pararius operational sourcing, raw HTML/JSON persistence, browser automation, LLM runtime, parser per
makelaar, or global eligibility changes.

Realworks Audit Resolution v1 regenerated a stale local handoff artifact from the repaired source-completion producer,
then reran the provincial audit on the canonical `65` ready Realworks sources. The regenerated run produced `5` passed,
`34` passed with review gaps, `24` no-current-listings monitor sources, and `2` isolated fetch failures, with `0`
hardening candidates. Property-level QA reviewed `304` readiness rows and found no duplicate, readiness-label, status,
source-attribution, raw-persistence, or long-description hard-gate failures. The final decision is
`realworks_partially_ready_with_exclusions`: merge is appropriate after manual review, while no-current-listing and
fetch-failed sources remain excluded or monitored.

## Recommended next PRs

- `PR 2: Source Intelligence Conversion v1`
- `PR 3: Access Policy v1`
- `PR 4: Delivery Mode Fingerprint v2`
- `PR 5: Inventory Core v1`
- `PR 6: Parser Config Runner v1`

For the detailed staged plan, see [docs/11_ROADMAP.md](/C:/Projects/domek-wonen/docs/11_ROADMAP.md).
