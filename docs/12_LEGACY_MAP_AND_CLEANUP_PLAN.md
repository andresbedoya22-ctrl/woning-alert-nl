# Legacy Map And Cleanup Plan

## Existing useful folders

- `scraper/src/domek_wonen/discovery/`: active discovery and source-master related code worth preserving.
- `scraper/src/domek_wonen/diagnostics/`: useful audit and reporting tools.
- `scraper/src/domek_wonen/harvest/`: reusable card-parsing direction for future parser-family work.
- `scraper/src/domek_wonen/matching/`: existing matching logic that should stay intact during architecture reset.
- `scraper/src/domek_wonen/compliance/`: contains the binding `robots_gate.py`.

## Existing scripts

- `scripts/build_source_master.py`
- `scripts/run_source_coverage_map.py`
- `scripts/run_platform_fingerprint_audit.py`
- `scripts/run_target_area_platform_fingerprint.py`
- `scripts/run_property_discovery_selection_quality_audit.py`
- `scripts/run_discovery_census.py`
- `scripts/run_matching_v1.py`

These are not deleted in this PR. They remain reference points for future conversion work.

## Existing legacy-oriented docs

- `docs/WONING_ALERT_NL_ROADMAP.md`
- `docs/00_README_EJECUTIVO.md`
- `docs/01_CORE_V6_CODEX.md`
- `docs/02_MAKELAAR_DISCOVERY_PLAYBOOK.md`
- `docs/03_CODEX_PROMPTS.md`
- `docs/05_BACKLOG_MVP_14_DIAS.md`
- `docs/08_SOURCE_DISCOVERY_ENGINE_V1.md`
- `docs/10_SOURCE_AND_PROPERTY_DISCOVERY_STRATEGY.md`
- phase reports and alignment notes dated `2026-06-19`

These stay in place and are treated as historical context, not deleted assets.

## Existing modules to keep

- `discovery/`
- `diagnostics/`
- `harvest/`
- `matching/`
- `compliance/`

## Existing modules to adapt later

- `portals/`: legacy or diagnostic only; not the strategic path.
- `properties/`: legacy property-discovery stack to mine for parser-family patterns and normalization ideas.
- `recommendations/` and `woning_scanner/`: future-stage modules that should wait for inventory and matching maturity.

## What is not deleted now

- no functional runtime code;
- no tests;
- no scripts;
- no historical docs;
- no generated artifacts beyond normal git hygiene.

## Cleanup plan by phase

1. Architecture reset: add source-of-truth docs and target structure.
2. Source intelligence conversion: map legacy source artifacts into the new model.
3. Parser-family transition: extract reusable logic from `properties/` into `parsers/` and `inventory/`.
4. Legacy isolation: move portal-first experiments and superseded docs into clearer legacy locations after replacements exist.
5. Final cleanup: remove only code and docs proven obsolete after replacement coverage is validated.

## Legacy Source Intelligence Adapter v1

`scraper/src/domek_wonen/sources/legacy_source_adapter.py` is the temporary bridge between legacy local CSV
artifacts and the new source architecture. It reads source masters, discovery outputs, coverage-style files,
and platform fingerprint CSVs offline, maps variable legacy columns into `SourceIntelligenceRecord`, and then
runs the existing Source Intelligence, Access Policy, and Delivery Fingerprint layers.

It does not scrape, make HTTP requests, validate robots live, use browser automation, modify property-discovery
runtime, or implement parser families. Its purpose is to turn existing artifacts into a real prioritization and
manual-review report before parser-family implementation begins.

## Legacy Adapter Hardening v1

Legacy Adapter Hardening v1 improves the bridge for the real `makelaar_sources_master.csv` shape without adding
network behavior. It supports additional legacy metadata columns including `aanbod_url_type`,
`confidence_score`, `score`, `source_quality_status`, `needs_review`, `review_reason`, `last_seen_at`,
`last_audited_at`, `run_id`, and `is_active`.

The adapter now normalizes `allowed_official_source` to `allowed` and maps missing/manual-review style legacy
states to conservative research or review outcomes before Access Policy sees them. It preserves `run_id`,
score/confidence, timestamps, and review reasons in `notes` or `evidence` so later reporting can explain the
decision trail. This hardening remains offline and does not scrape, make HTTP requests, use Playwright, probe
robots live, or modify property-discovery runtime.

## Delivery Mode Evidence Enrichment v1

`scraper/src/domek_wonen/sources/evidence_enrichment.py` adds an offline enrichment step that joins the real
source master with local technical evidence CSVs. It can read platform fingerprint, source coverage, target-area,
and delivery-mode evidence artifacts with variable columns, then enrich `SourceIntelligenceRecord` fields before
Access Policy and Delivery Fingerprint run.

This layer does not scrape, make HTTP requests, open websites, use Playwright, validate robots live, modify
property-discovery runtime, or implement parser families. It only reuses local evidence to reduce
`unknown_manual_review` where platform or delivery signals already exist, making it a bridge toward later
parser-family implementation.

## Parser Family Readiness Audit v1

`docs/research/PARSER_FAMILY_READINESS_AUDIT_V1.md` records the offline decision to implement `Realworks Parser
Family Stabilization v1` first. The legacy Realworks parser under `properties/platform_parsers/` should be mined
for fixture-tested parsing logic, while network orchestration and broad WordPress/static config-runner work remain
separate later phases.

## Realworks Parser Family Stabilization v1

`scraper/src/domek_wonen/parsers/realworks_family.py` adds the first V4 parser-family layer for
`realworks_public`. It is offline by construction: callers provide captured listing HTML in `ParserInput`, and the
family emits `ParsedListing` records inside a `ParserFamilyResult`.

This layer does not fetch, scrape live pages, use browser automation, validate robots live, or write inventory. The
legacy `scraper/src/domek_wonen/properties/platform_parsers/realworks_parser.py` remains intact for the existing
property-discovery runtime. Integration with a runner, source configs, inventory state, and QA promotion comes after
this stabilization step.

## Realworks Property Facts Extractor v1

`scraper/src/domek_wonen/facts/realworks_extractor.py` adds a family-level facts extractor for Realworks detail pages.
It accepts already-permitted in-memory detail HTML, reads `kenmerkName` / `kenmerkValue` blocks, and returns the
existing `PropertyFactsRecord` contract with normalized fact values, statuses, capped evidence previews, and warnings.

The validation helper in `scraper/src/domek_wonen/pilots/realworks_property_facts_validation.py` is bounded and checks
`robots_gate.can_fetch` before listing and detail fetches. It does not persist raw HTML or JSON, create cache/readiness
rows, export Excel, touch matching/email/n8n/dashboard/eligibility, use browser automation, or create a parser per
makelaar.

## Realworks Readiness Rows v1

`scraper/src/domek_wonen/pilots/realworks_property_readiness.py` adds the next Realworks pilot layer after parser QA and
property facts extraction. It builds in-memory readiness rows from QA-clean `realworks_public` listings, Realworks
`PropertyFactsRecord` detail facts, the existing `ClientReadyPropertySummary`, and location readiness.

The runner reports readiness row counts, `client_ready` / `advisor_review` / `blocked` status, export readiness, field
completion, missing key fields, review fields, warnings, sample rows, and compact problem rows. Oldenkotte validation
built `9` rows from `9` QA-clean listings and `9` successful detail facts records; all rows are `advisor_review` because
postcode and several facts remain incomplete or review-only.

This remains in-memory only and does not create Excel, cache, matching input, advisor email, n8n flow, dashboard,
generated raw HTML/JSON, images, an LLM extraction path, a parser per makelaar, or inventory eligibility changes.

## Realworks Excel Validation v1

`scraper/src/domek_wonen/pilots/realworks_excel_export.py` adds the local human-validation workbook for Realworks
readiness rows. It consumes already-built rows, writes a caller-provided local/generated `.xlsx` path, exports all rows
including `export_review`, preserves full `canonical_url` text, and creates a clickable `property_link`.

The workbook contains `Realworks Properties`, `Summary`, `Field Gaps`, `Warnings`, and `Problem Rows` worksheets. The
current Oldenkotte sample remains validation-only: `8` rows are `export_review`, the Corellistraat-style `OverigOG`
row is `export_blocked`, and no row is production client-ready. Postcode is exposed as a critical status/source field,
VvE is explicit for apartments, energy labels keep value/status/raw separated, and non-residential rows are blocked or
clearly marked. Postcode now comes from JSON-LD address data or visible Realworks detail headers when present. Status
policy columns keep sold, under-contract, under-offer, and rented rows for later source inventory/history while keeping
them out of active inventory and matching. Generated `.xlsx` files remain uncommitted local artifacts.

This is not matching, advisor email, n8n, dashboard, Funda/Pararius work, raw HTML/JSON persistence, long-description
storage, image download, LLM extraction, eligibility change, or a parser-per-makelaar phase.

## Realworks Freshness & Lifecycle Fields v1

`scraper/src/domek_wonen/inventory/lifecycle.py` adds the offline lifecycle contract used by Realworks readiness rows
and the Excel validation workbook. The contract separates source-declared publication date from system `first_seen_at`
and run-level `observed_at`, computes source/system age, assigns freshness buckets, and records lifecycle events such
as `new_listing`, `price_changed`, `status_changed`, `under_offer`, `sold`, and `non_residential_excluded`.

Realworks-specific extraction remains in `scraper/src/domek_wonen/facts/realworks_extractor.py`, using JSON-LD,
embedded state, and reusable `kenmerkName` / `kenmerkValue` labels. No publication date is invented from bouwjaar,
status text, or URL ids. The existing Realworks status/history policy remains separate through `status_bucket`,
`active_inventory_eligible`, and `db_persistence_action`.

This phase creates no real database, migrations, matching, client alerts, advisor email, n8n, dashboard, Funda/Pararius
path, raw HTML/JSON persistence, long descriptions, images, LLM extraction, parser per makelaar, or global eligibility
change.

## Realworks Multi-source Validation v1

`scraper/src/domek_wonen/pilots/realworks_multi_source_validation.py` adds the controlled Realworks family validation
runner across locally evidenced sources. It selects Oldenkotte as control and Olden as the second makelaar when local
evidence supplies source id, domain, listing URL, Realworks delivery/parser signals, and allowed access status.

The runner reuses the existing Realworks parser, parser QA, bounded detail facts, readiness rows, status/history, and
lifecycle path per source, then writes a local validation workbook and summary CSV under `tmp/generated/`. It does not
create a parser per makelaar, a database, matching, client alerts, advisor email, n8n, dashboard, Funda/Pararius path,
browser automation, raw HTML/JSON persistence, long descriptions, images, LLM extraction, `data/raw` changes, or global
eligibility changes.

## Realworks Broader Bounded Audit v1

`scraper/src/domek_wonen/pilots/realworks_broader_bounded_audit.py` extends the reusable Realworks family validation to
additional locally evidenced Realworks makelaars beyond the Oldenkotte and Olden control sources. The bounded audit
selected `alstedevanmierlomakelaardij.nl__tilburg`, `cvda.nl__tilburg`, and `hansvanberkel.nl__tilburg`, then wrote a
local manual-verification workbook and summary CSV under `tmp/generated/`.

The run produced 29 manual verification rows and the family decision
`realworks_ready_for_noord_brabant_realworks_audit`. Remaining review gaps stay explicit: coordinates,
`source_published_at`, VvE, and heating/hot-water normalization.

This phase does not add matching, client alerts, advisor email, n8n, dashboard, DB, migrations, Noord-Brabant full
census, apply-to-all Realworks execution, raw HTML/JSON persistence, long descriptions, images, browser automation,
proxies, bypass behavior, LLM use, parser-per-makelaar logic, Funda/Pararius work, `data/raw` changes, or global
eligibility changes.

## Parser Family Runner v1

`scraper/src/domek_wonen/parsers/runner.py` adds the first offline connector from
`DeliveryFingerprintResult` to parser families. It operates only on caller-provided
`ParserInput` content and returns `ParserFamilyResult`.

In v1 the runner supports `realworks_public` and `ogonline_xhr`, routing allowed
fingerprints to their offline parser-family implementations. It does not make network
requests, use browser automation, probe robots live, decide Access Policy again,
modify property-discovery runtime, or write inventory. Config runner integration,
inventory state handling, and QA promotion remain later phases.

## KIN OGonline XHR Parser Spike v1

`scraper/src/domek_wonen/parsers/ogonline_xhr_family.py` adds an offline parser spike
for OGonline XHR JSON responses based on the shape observed for KIN: a top-level
object with `docs`, pagination metadata, and listing fields such as id, address,
postcode, city, price, status, rooms, bedrooms, and photos.

The spike uses synthetic fixtures only and does not store real live JSON or HTML. It
does not make HTTP requests, use Playwright or Selenium, validate robots live, modify
property-discovery runtime, touch matching, persist inventory, or implement the
paginated source-config/live runner. Those integration steps remain later phases.

## OGonline XHR Runner Integration v1

`ParserFamilyRunner` now accepts a permitted `DeliveryFingerprintResult` with
`delivery_mode="ogonline_xhr"` and `parser_family_candidate="ogonline_xhr"` and routes
caller-provided JSON `ParserInput` to `OGonlineXHRParserFamily`.

This integration remains offline: no HTTP requests, Playwright, Selenium, robots live
checks, property-discovery runtime changes, matching changes, generated JSON, source
config runner, or paginated live runner are added in this phase.

## KIN OGonline XHR Source Config v1

`scraper/src/domek_wonen/parsers/source_config.py` adds a small offline source-config
model for KIN as an `ogonline_xhr` source. It captures the OGonline API base URL,
pagination parameters, static query parameters, and `items_path`, then builds
deterministic paginated API URLs and JSON `ParserInput` objects from caller-provided
content.

The KIN fixture is synthetic config only. This phase does not make HTTP requests,
call robots live, use Playwright or Selenium, store real JSON, modify
property-discovery runtime, touch matching, or implement the paginated live runner.

## KIN OGonline XHR Paginated Runner v1

`scraper/src/domek_wonen/pilots/ogonline_xhr_paginated_runner.py` adds the controlled
source-config runner for KIN-style `ogonline_xhr` pages. It accepts only
`ParserSourceConfig` inputs with `parser_family="ogonline_xhr"` and
`delivery_mode="ogonline_xhr"`, builds each page URL with `build_paginated_api_url`,
checks `robots_gate.can_fetch(api_domain, api_path)` before invoking the injected
`fetch_json`, and converts caller-provided JSON into `ParserInput`.

The runner then uses `ParserFamilyRunner` and `qa_parser_family_result` to report
per-page parser, clean, review, and rejected counts plus aggregate totals. This phase
does not add real HTTP, live fetch execution, Playwright, Selenium, proxies, stealth
behavior, CAPTCHA handling, bypass logic, JSON persistence, property-discovery runtime
changes, matching, n8n, dashboard work, or generated outputs. A real live runner remains
a later phase.

## Controlled OGonline Live Fetch v1

`scraper/src/domek_wonen/pilots/ogonline_xhr_live_fetch.py` adds the explicit
standard-library JSON fetch helper for a bounded KIN `ogonline_xhr` live pilot. It makes
one GET with a required timeout and clear non-stealth User-Agent, accepts JSON or text
responses only when the body parses as JSON, returns the original JSON string, and does
not write live JSON or HTML to disk.

Robots compliance remains upstream in `run_ogonline_xhr_paginated_config`, which checks
`robots_gate.can_fetch(api_domain, api_path)` before each injected fetch call. The KIN
helper loads a source config and delegates to the paginated runner with a caller-provided
`max_pages` cap. This phase adds no Playwright, Selenium, proxies, stealth behavior,
CAPTCHA handling, bypass logic, retries, parallelism, property-discovery runtime changes,
matching, n8n, dashboard work, or generated outputs.

## Parser Output QA Gate v1

`scraper/src/domek_wonen/qa/parser_output_gate.py` adds the first offline QA layer for parser-family output. It
validates `ParserFamilyResult` before inventory and separates `ParsedListing` records into clean, review, and
rejected buckets.

This gate does not make network requests, persist inventory, run global dedupe, touch matching, or modify legacy
property-discovery runtime. It creates an initial deterministic `normalized_key` from canonical URL when available,
falling back to postcode plus house number, then raw address plus city.

## Inventory Core v1

`scraper/src/domek_wonen/inventory/` adds the first offline inventory core. It consumes only
`ParserFamilyQAResult.clean_listings`, creates source-scoped `InventorySnapshot` objects, and compares snapshots
with `diff_inventory_snapshots`.

The core does not persist to a database, make network requests, use browser automation, touch property-discovery
runtime, or move records into matching. `review_listings` and `rejected_listings` stay outside inventory.

Stale-source behavior is preserved through `safe_to_compare_removals=false`: failed, partial, or stale captures
must not produce removal events, so prior successful inventory can remain the trusted reference until a later
successful capture recovers the source.

## Inventory Eligibility Gate v1

`scraper/src/domek_wonen/inventory/eligibility.py` adds the offline gate between parser QA and active inventory. It
consumes `ParserFamilyQAResult`, keeps QA review and rejected listings out of active inventory, and classifies QA-clean
listings into `active_inventory`, `inactive_status`, `unsupported_transaction_type`, `unsupported_property_type`, or
`review`.

The gate does not make HTTP requests, run live fetch, use browser automation, relax QA, modify matching, touch
property-discovery runtime, or change n8n or dashboard flows. Only `koop + beschikbaar + allowed_property_type` is
eligible for active inventory. `onder_bod`, `verkocht`, `verhuurd`, `unknown` or empty status, unsupported or unknown
transaction type, and empty or unsupported property type stay outside active inventory.

## KIN OGonline Active Inventory Pilot v1

`scraper/src/domek_wonen/pilots/kin_ogonline_active_inventory_pilot.py` adds the controlled live KIN `ogonline_xhr`
pilot for active inventory. It caps execution at `max_pages=2`, builds page URLs from the KIN source config, checks
`robots_gate.can_fetch` for each API URL, fetches JSON through the controlled live helper, runs parser family output
through QA, applies inventory eligibility, and builds an `InventorySnapshot` from active inventory only.

The pilot does not persist live JSON or HTML, does not touch `data/raw`, matching, n8n, dashboard, Funda, or Pararius,
and does not add browser automation, retries, parallelism, proxies, stealth behavior, CAPTCHA handling, or bypass logic.

## OGonline Detail Property Type Enrichment v1

`scraper/src/domek_wonen/pilots/ogonline_detail_property_type_enrichment.py` adds a controlled detail-page enrichment
layer for OGonline-backed KIN listings whose listing API payload has no useful `property_type`. It uses the existing
detail candidate extraction logic to read embedded-state property type signals, maps only conservative known values,
and leaves ambiguous or unknown candidates unchanged.

This enrichment remains separate from the base `ogonline_xhr` parser family. The KIN active inventory pilot can enable
it explicitly with `enrich_detail_property_type=True`, while the default remains disabled. Detail fetches are capped by
`max_detail_enrichment`, each detail URL must pass `robots_gate.can_fetch(domain, path)`, and no HTML or JSON is
persisted. Eligibility remains the downstream authority for active, inactive, unsupported property type, or review
classification. `Open huis` stays a badge/event and is not mapped into property type or status.

## KIN OGonline 5-page Validation Audit v1

`scraper/src/domek_wonen/pilots/kin_ogonline_validation_audit.py` adds a separate audit path for validating whether
the KIN OGonline listing API, base parser, QA gate, detail property-type enrichment, eligibility gate, and active-only
snapshot scale from the two-page pilot to at most five API pages.

This audit does not change the base `ogonline_xhr` parser family or the two-page active inventory pilot. It uses the
detail property-type enrichment layer only as an explicit audit step, caps API pagination at five pages, caps detail
enrichment at 120 pages, does not persist HTML or JSON, and does not run full KIN. Matching, n8n, dashboard,
`data/raw`, Funda, and Pararius remain outside this phase. The audit reports parser, QA, enrichment, eligibility,
snapshot, status, decision, property-type, and warning metrics.

## KIN Full OGonline Validation Audit v1

`scraper/src/domek_wonen/pilots/kin_ogonline_full_validation_audit.py` adds a separate full-source validation audit for
the explicit KIN OGonline source config. It remains separate from the two-page active inventory pilot and the five-page
validation audit while reusing the same base parser, parser QA, detail property-type enrichment, inventory eligibility,
and active-only snapshot path.

The audit is bounded, not a generic crawler: API pagination is capped at 25 pages and detail enrichment is capped at
300 detail pages. It can use OGonline pagination metadata such as `totalPages`, `totalDocs`, and `hasNextPage` to decide
how many KIN pages to attempt within those limits. This phase does not implement new mappings, relax QA, change
eligibility, persist live HTML or JSON, touch matching, n8n, dashboard, `data/raw`, Funda, or Pararius. Its purpose is
to decide whether KIN is sufficiently validated before moving to a later OGonline Coverage Audit.

Runtime hardening keeps the full audit useful when detail enrichment is slow. The audit can accept a whole-run budget
and a detail-enrichment budget; when either budget is exhausted, it stops cleanly and returns partial metrics instead
of relying on an external timeout. These partial results preserve completed API, parser, QA, enrichment, eligibility,
and snapshot counts. The full audit remains diagnostic and bounded, and KIN should be run with an explicit runtime
budget before it is considered as any later gate.

## OGonline Detail Facts Probe v1

`scraper/src/domek_wonen/pilots/ogonline_detail_facts_probe.py` adds a bounded diagnostic probe for OGonline/KIN detail
pages. It records which property-fact sources appear to be available, including property type, price, areas, rooms,
energy label, ownership, VvE, heating, outdoor space, parking, availability, Open huis/event hints, and whether a short
description source exists.

This layer is not an extractor, cache, matching input, dashboard feed, or n8n job. It checks `robots_gate.can_fetch`
before each API and detail fetch, uses the existing controlled fetch helpers, caps samples, keeps HTML/JSON only in
memory, and reports compact field previews rather than raw documents. Long descriptions are not copied; the probe only
records availability, a length bucket, and at most a 120-character preview. Its purpose is to inform later
`OGonline Detail Facts Cache v1` and `Property Facts Extractor v1` design without changing the base OGonline parser or
eligibility behavior.

## OGonline Property Facts Contract + Cache v1

`scraper/src/domek_wonen/facts/` adds the reusable, offline contract for normalized property facts plus a configurable
local JSONL cache. The layer defines allowed fact fields, fact-level confidence/status/source metadata, stable record
serialization, pure normalization helpers, and an explicit bridge from `OGonlineDetailFactsProbeSample` into
`PropertyFactsRecord` for tests and diagnostics.

This phase is not an operational HTML extractor and does not add live fetch, browser automation, raw HTML persistence,
raw web JSON persistence, image downloads, long-description storage, LLM summaries, matching, n8n, dashboard work,
parser changes, eligibility changes, Funda, Pararius, or `data/raw` changes. Cache files are generated/local artifacts
only and are written only when a caller provides an explicit cache path.

## OGonline Normalized Facts Extractor v1

`scraper/src/domek_wonen/facts/ogonline_extractor.py` converts permitted OGonline detail HTML held in memory into
`PropertyFactsRecord` values using the existing facts contract and JSONL cache. The pure extractor handles normalized
signals for property type, asking price, areas, room counts, energy label, ownership, VvE, heating, outdoor space,
parking, availability, Open huis/event, and description length bucket without copying long descriptions.

The controlled KIN batch path uses the OGonline listing API, parser-family QA-clean listings, `robots_gate.can_fetch`
before API/detail fetches, and `PropertyFactsCache` for explicit-path cache hit, stale, and `force_refresh` behavior.
It remains sequential and bounded by API page, detail, and runtime caps. This phase does not persist raw HTML or raw web
JSON, download images, call an LLM, change the base `ogonline_xhr` parser, relax QA, change eligibility, touch matching,
n8n, dashboard, Funda, Pararius, or `data/raw`. It prepares a later `Client-ready Property Summary v1`.

Quality hardening remains inside the facts layer: normalized-equivalent candidates dedupe without conflict, high-priority
structured facts can beat weak HTML candidates, real conflicts require two strong normalized sources, and ambiguous or
implausible count candidates stay review-only. This does not promote the facts layer to client-ready summaries.

## Client-ready Property Summary v1

`scraper/src/domek_wonen/facts/summary.py` adds the first offline client-ready summary layer on top of
`PropertyFactsRecord`. It creates a compact card with headline, fact, financial, outdoor, energy, attention,
missing-key-field, and warning sections for advisor/client review.

Only normalized facts with `status="usable"` are rendered as confirmed values. Facts with `status="review"` become
attention points, and missing key fields remain explicit instead of being inferred. This layer does not make HTTP
requests, run live fetch, write cache files, call an LLM, store raw HTML or raw web JSON, copy long descriptions,
download images, modify matching, email, n8n, dashboard, Funda, Pararius, `data/raw`, the base OGonline parser, or
inventory eligibility.

## KIN Full Facts + Location Readiness v1

`scraper/src/domek_wonen/pilots/kin_full_property_readiness.py` adds the KIN-specific full-source readiness layer for
the OGonline laboratory. It reuses the listing API, parser-family runner, parser QA gate, normalized facts extractor,
explicit facts cache, and client-ready summary builder, then adds location readiness so each in-memory row can later be
written to Excel without inventing missing location fields.

This remains a pilot/audit layer, not an operational app surface. It does not create Excel, send email, run matching,
touch n8n, build a dashboard, persist raw HTML or raw web JSON, call an LLM, download images, touch `data/raw`, scrape
Funda or Pararius, modify the base `ogonline_xhr` parser, or change inventory eligibility. Location readiness is kept
separate because future client matching depends on explicit address, postcode, and city quality before sending rows
downstream.

## KIN Full Coverage Completion + Field Gap Audit v1

`scraper/src/domek_wonen/pilots/kin_full_coverage_audit.py` adds the next KIN audit layer without creating Excel. It
wraps the full property readiness runner, requires an explicit generated/local facts cache path, preserves partial
runtime-budget behavior, and supports progressive reruns by counting cached records while continuing toward uncached
QA-clean listings.

The result reports coverage rate as `rows_built / qa_clean_count`, completed versus partial state, cache and detail
fetch counters, location completeness, export readiness, quality status buckets, field completion counts, missing key
fields, attention points, warning counts, field gaps, top blockers, and compact problem-row samples. Field gaps cover
key property facts and location fields before the later Excel phase; missing latitude/longitude remains visible as a
known gap but does not override usable address/postcode/city readiness.

This audit does not send email, run matching, touch n8n, build a dashboard, modify `data/raw`, persist raw HTML or raw
web JSON, call an LLM, download images, scrape Funda or Pararius, change the base OGonline parser, or change inventory
eligibility.

## KIN Key Matching Fields Hardening v1

The OGonline facts layer now hardens future matching fields without changing matching itself. It accepts bedrooms only
from structured state or strong slaapkamer labels, accepts living area only from specific woonoppervlakte or
gebruiksoppervlakte wonen evidence, keeps property type structured-first while ignoring weak event/badge signals such
as Open huis, and normalizes energy-label spacing/casing variants before conflict detection.

This remains a parser-family improvement, not a KIN-specific parser or parser-per-makelaar path. It does not infer
bedrooms from rooms, use an LLM, persist raw HTML or raw web JSON, create Excel, send email, run matching, touch n8n,
build a dashboard, modify `data/raw`, scrape Funda or Pararius, or change inventory eligibility.

## KIN Excel Export v1

`scraper/src/domek_wonen/pilots/kin_excel_export.py` adds the human-validation artifact for the KIN full readiness
rows. It writes a caller-provided local/generated `.xlsx` path, exports all available rows, preserves
`canonical_url` as full text, and creates a clickable `property_link` for valid listing URLs.

The workbook contains `KIN Properties`, `Summary`, `Field Gaps`, `Warnings`, and compact `Problem Rows` worksheets.
Rows include normalized facts, summary lines, location fields, export readiness, quality status, missing key fields,
and warnings without copying raw HTML, raw web JSON, images, long descriptions, or evidence dumps.

This is not email, matching, n8n, dashboard, source crawling, Funda/Pararius work, LLM work, an eligibility change, or a
parser-per-makelaar phase. Generated `.xlsx` files and cache files remain uncommitted local artifacts.

## Controlled Realworks Capture Pilot v1

`scraper/src/domek_wonen/pilots/realworks_capture_pilot.py` adds a small, auditable pilot for permitted
`realworks_public` listing pages. It checks `robots_gate.can_fetch(domain, path)` before invoking an injected
`fetch_html` callable, runs at most five sources by default, and sends captured HTML through `ParserInput`,
`ParserFamilyRunner`, the parser output QA gate, and inventory snapshot creation to report parser, QA, and
inventory counts.

The pilot does not add a real HTTP fetcher, Playwright, Selenium, stealth behavior, proxies, CAPTCHA handling,
bypass behavior, matching, n8n, dashboard work, DB persistence, property-discovery runtime changes, captured HTML,
or generated outputs. Failed or blocked captures remain `safe_to_compare_removals=false`.

## Controlled Source Selection for Realworks Pilot v1

`scraper/src/domek_wonen/pilots/source_selection.py` adds the offline source-selection layer before the controlled
capture pilot. It reads local enriched source-intelligence evidence, prefers `production_parser_ready_sources`, and
selects up to five `realworks_public` rows with allowed or limited access, a source domain, and an explicit listing
URL.

The selector does not make network requests, call `robots_gate`, fetch HTML, use Playwright or Selenium, modify
property-discovery runtime, touch matching, or create generated outputs. It keeps Funda, Pararius, blocked,
permission-required, legal-review, manual-review, missing-domain, and missing-URL sources out of the pilot input.

## Controlled Realworks Live Fetch v1

`scraper/src/domek_wonen/pilots/live_fetch.py` adds the first explicit HTTP fetch helper for a controlled
`realworks_public` live pilot. The fetch function uses the standard library only, performs one GET with a required
timeout and a clear non-stealth User-Agent, accepts only HTML or text content, and raises stable fetch exceptions for
HTTP status or content-type failures.

Robots compliance remains upstream in the capture pilot: `run_realworks_capture_pilot_for_source` must call
`robots_gate.can_fetch(domain, path)` successfully before this fetcher is invoked. The live pilot helper defaults to
`max_sources=3` and provides domain dedupe for the first run so multiple selected city variants from the same domain
are not fetched together. This phase adds no Playwright, Selenium, proxies, stealth behavior, CAPTCHA handling,
bypass logic, DB persistence, property-discovery runtime changes, matching, dashboard work, or generated outputs.

## Realworks Parser Family Validation v1

`scraper/src/domek_wonen/parsers/realworks_family.py` now hardens the reusable Realworks parser family against
navigation and filter overcapture. The parser prefers Realworks listing containers such as `aanbodEntry`, requires
detail-like Realworks URL shapes, rejects category/archive/open-house/service paths, and parses card-level address,
city, price, status, and property signals before QA.

Oldenkotte (`oldenkotte.com__tilburg`) was the validation lab. Baseline live parser output was `36 total / 0 clean /
36 review / 0 rejected`, with category URLs such as `/aanbod/woningaanbod/koop` and
`/aanbod/woningaanbod/koop/garage`. After hardening, Oldenkotte produced `9 total / 9 clean / 0 review / 0 rejected`
and `9` inventory snapshot listings. Backup validation on `olden.nl__heusden` produced `10 total / 10 clean / 0
review / 0 rejected`.

This remains parser-family work only. No parser per makelaar, matching, advisor email, n8n, dashboard, Excel,
eligibility change, Funda/Pararius extraction, browser automation, LLM extraction, or raw HTML/JSON persistence was
added.

## Realworks Detail Facts Probe v1

`scraper/src/domek_wonen/pilots/realworks_detail_facts_probe.py` adds a bounded diagnostic layer for Realworks detail
pages after QA-clean listing capture. It extracts compact field availability from in-memory detail HTML using
family-level Realworks `kenmerkName` / `kenmerkValue` structures and reports explicit available, review, and missing
states for candidate property facts.

This probe is research-only. It does not create a facts cache, normalized extractor, readiness runner, Excel export,
matching input, advisor email, n8n flow, dashboard, eligibility change, parser per makelaar, Funda/Pararius path,
browser automation, raw HTML/JSON persistence, image download, long-description storage, or `data/raw` change.
