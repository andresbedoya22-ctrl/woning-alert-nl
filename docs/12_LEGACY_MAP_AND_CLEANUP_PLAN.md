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
