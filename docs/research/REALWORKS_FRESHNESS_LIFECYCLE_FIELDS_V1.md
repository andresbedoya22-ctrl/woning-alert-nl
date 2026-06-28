# Realworks Freshness & Lifecycle Fields v1

## Objective

Add publication-date, first-seen, observed-at, freshness, and lifecycle fields to the current Realworks readiness and
Excel validation path without creating a real database, matching flow, alerts, email, n8n, or dashboard.

## Strategic context

This phase keeps Realworks family completion ahead of client matching. It extends the in-memory validation pipeline so
advisor review can distinguish source-declared age from system-observed age.

## Scope and constraints

- No matching, client alerts, advisor email, n8n, dashboard, DB, or migrations.
- No `data/raw` modification.
- No Funda or Pararius path.
- No browser automation, Playwright, Selenium, proxies, stealth, CAPTCHA handling, or bypass behavior.
- No raw HTML/JSON persistence.
- No long descriptions, images, or LLM extraction.
- No parser per makelaar and no global eligibility change.

## Field contract

`scraper/src/domek_wonen/inventory/lifecycle.py` defines the family-agnostic contract:

- `ListingLifecycleFields`
- `LifecycleEvent`
- `FreshnessBucket`
- `LifecycleStatus`

Core fields include source publication metadata, first/last/observed timestamps, status and price change timestamps,
removal timestamp, source/system age fields, freshness bucket, and lifecycle events.

## Realworks publication-date candidates

The Realworks extractor checks family-level sources in conservative order:

1. JSON-LD `datePosted` and `datePublished`.
2. JSON-LD `dateModified` as review only.
3. Embedded state fields such as `publishedAt`, `createdAt`, `datePublished`, `datePosted`, and `availableFrom`.
4. Realworks `kenmerkName` / `kenmerkValue` labels such as `aangemeld`, `publicatiedatum`, `datum plaatsing`,
   `beschikbaar sinds`, `plaatsingsdatum`, and `online sinds`.

The extractor does not infer publication date from bouwjaar, status text alone, or URL ids.

## Date parsing rules

Supported formats:

- ISO dates and datetimes such as `2026-06-28` and `2026-06-28T10:30:00Z`.
- Dutch numeric dates such as `28-06-2026`, `28/06/2026`, and `28.06.2026`.
- Dutch textual dates such as `28 juni 2026`.

If multiple strong candidates conflict, the value is marked `review` with `source_published_at_conflict`.

## Lifecycle rules

Initial observations set `first_seen_at`, `last_seen_at`, and `observed_at` to the explicit observation timestamp and
emit `new_listing`. Previous lifecycle records preserve `first_seen_at` and detect `price_changed`, `status_changed`,
`under_offer`, `sold`, and `reappeared`.

Removed detection remains pure/offline through key comparison helpers. No database is created in this phase.

## Freshness buckets

Freshness uses source publication date when usable, otherwise first-seen date. If neither exists, it returns
`unknown_age`.

Buckets are `new_today`, `new_3d`, `new_7d`, `new_14d`, `stale_30d`, `stale_60d`, `stale_90d_plus`, and
`unknown_age`.

## Status/history policy

Readiness keeps the existing Realworks status policy columns: `status_bucket`, `active_inventory_eligible`, and
`db_persistence_action`. Sold and under-contract rows receive lifecycle events but stay out of active inventory.
Non-residential rows receive `non_residential_excluded` and remain `store_excluded_non_residential`.

## Excel additions

The `Realworks Properties` sheet now includes publication, observation, first-seen, price/status change, freshness, and
lifecycle event columns. `Summary` includes source-published counts, freshness bucket counts, and lifecycle event
counts. `Field Gaps` includes `source_published_at`, and `Warnings` can surface publication-date missing/review/conflict
warnings.

## Live Oldenkotte validation

The live bounded Oldenkotte workbook should be regenerated with an explicit UTC `observed_at` and local output path:

```text
tmp/generated/realworks_oldenkotte_excel_validation_v1.xlsx
```

If Oldenkotte does not expose source publication dates, this is acceptable. `first_seen_at` and `observed_at` still
show the system observation date, and no publication date is invented.

## Remaining gaps

- No real persisted lifecycle store exists yet.
- Previous lifecycle records can be injected for tests, but operational history storage is deferred.
- Realworks variants beyond Oldenkotte still need multi-source validation.

## Recommendation

Merge after tests and bounded workbook validation pass, then run Realworks multi-source validation before broader
Noord-Brabant inventory census work.

## Constraints confirmation

This phase adds no matching, client alerts, advisor email, n8n, dashboard, real DB, migrations, Funda/Pararius path,
raw HTML/JSON persistence, long descriptions, images, LLM extraction, parser per makelaar, global eligibility change,
or force-push behavior.
