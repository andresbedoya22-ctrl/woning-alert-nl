# WoningAlert NL Roadmap

## Product objective

WoningAlert NL builds a portal-first national housing inventory that is refreshed regularly, preserves source-level run state, detects new/changed/removed listings safely, matches inventory against client searches, and later produces operational recommendations.

## Portal-first strategy

Start from national or near-national portals first, then add controlled fallback coverage only where portal coverage is insufficient. Avoid makelaar-by-makelaar expansion as the main path until the inventory core, daily sync, and client matching layers are stable.

## Source layers

- Primary candidate: Huislijn
- Benchmark and permission-required: Pararius
- Benchmark-only: Funda
- Fallback only: makelaar parsers
- Operational delivery layer: email alerts
- Future candidates: Huispedia and VastgoedNederland

## Target architecture

Source Adapters -> Inventory Core -> Deduplication -> Inventory State Engine -> Client Matching -> Recommendation Emails -> Woning Scanner

## Phases and Definition of Done

| Phase | Name | Definition of Done |
| --- | --- | --- |
| 0 | GitHub/base limpia | Repo aligned to portal-first scope, modular skeleton present, guardrails documented, validation green. |
| 1 | Portal Inventory Spike | Single portal ingestion spike defined with bounded adapter contract and no production scraper rollout. |
| 2 | Huislijn Adapter v1 | Huislijn adapter contract and normalization flow implemented and validated in isolation. |
| 3 | Inventory Core v1 | Canonical inventory models, dedup rules, and persistence-ready state transitions defined. |
| 4 | Daily Sync v1 | Scheduled sync can process source runs safely without deleting stale inventory on source failure. |
| 5 | Client Matching v1 | Client search inputs match against canonical inventory with deterministic filtering and scoring. |
| 6 | Email Draft Generator v1 | Recommendation email draft generation works from approved match outputs. |
| 7 | Multi-source Strategy v1 | Multiple approved sources run under shared source-state rules and comparison safeguards. |
| 8 | Woning Scanner v1 | Scanner layer operates only on top of stable matching and recommendation foundations. |
| 9 | MVP operativo | End-to-end operational flow is stable, observable, and ready for routine use. |

## Source status values

- `success`
- `partial_success`
- `blocked_captcha`
- `http_403`
- `http_429`
- `timeout`
- `requires_js`
- `parser_broken`
- `permission_required`
- `benchmark_only`
- `disabled`

## Critical failure rule

If a source fails, do not delete inventory from that source and set `safe_to_compare_removals=false`. Keep the last successful inventory snapshot as stale reference data until the source recovers.

## Conceptual model

- `source_runs`
- `raw_listings`
- `canonical_properties`
- `property_sources`
- `inventory_events`
- `client_searches`
- `client_matches`
- `recommendation_emails`

## Anti-drift rules

- No dashboard before Daily Sync v1 and Client Matching v1.
- No scanner before matching.
- No CAPTCHA solving, proxies, or bypass tactics.
- No productive Funda usage without explicit permission.
- Do not chase makelaars one by one as the main strategy.

## Continue from another chat

`Este es el roadmap de WoningAlert NL. Continuar desde Fase X usando este repo.`
