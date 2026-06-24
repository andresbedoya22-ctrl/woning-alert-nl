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

## Parser Family Runner v1

`scraper/src/domek_wonen/parsers/runner.py` adds the first offline connector from
`DeliveryFingerprintResult` to parser families. It operates only on caller-provided
`ParserInput` content and returns `ParserFamilyResult`.

In v1 the runner supports only `realworks_public`, routing allowed fingerprints to
`RealworksParserFamily`. It does not make network requests, use browser automation,
probe robots live, decide Access Policy again, modify property-discovery runtime, or
write inventory. Config runner integration, inventory state handling, and QA promotion
remain later phases.

## KIN OGonline XHR Parser Spike v1

`scraper/src/domek_wonen/parsers/ogonline_xhr_family.py` adds an offline parser spike
for OGonline XHR JSON responses based on the shape observed for KIN: a top-level
object with `docs`, pagination metadata, and listing fields such as id, address,
postcode, city, price, status, rooms, bedrooms, and photos.

The spike uses synthetic fixtures only and does not store real live JSON or HTML. It
does not make HTTP requests, use Playwright or Selenium, validate robots live, modify
property-discovery runtime, touch matching, persist inventory, or implement the
paginated source-config/live runner. Those integration steps remain later phases.

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
