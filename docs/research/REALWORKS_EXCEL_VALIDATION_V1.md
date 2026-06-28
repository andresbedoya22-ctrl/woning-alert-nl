# Realworks Excel Validation v1

## Objective

Create a local `.xlsx` validation artifact for human review of Realworks Oldenkotte readiness rows.

## Scope and constraints

This phase exports already-built Realworks readiness rows. It does not send email, run matching, touch n8n, create a
dashboard, modify `data/raw`, scrape Funda or Pararius, use browser automation, persist raw HTML/JSON, copy long
descriptions, download images, use an LLM, create a parser per makelaar, change eligibility, or promote rows to
client-ready automatically.

## Workbook design

`scraper/src/domek_wonen/pilots/realworks_excel_export.py` writes five worksheets:

- `Realworks Properties`
- `Summary`
- `Field Gaps`
- `Warnings`
- `Problem Rows`

`canonical_url` is stored as full text and `property_link` is a clickable hyperlink when the URL is valid.

## Live validation input

- `source_id`: `oldenkotte.com__tilburg`
- `listing_url`: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- `max_listing_fetches`: `1`
- `max_detail_fetches`: `9`
- `timeout_seconds`: `15`

## Export result

The workbook is generated at:

```text
tmp/generated/realworks_oldenkotte_excel_validation_v1.xlsx
```

Generated `.xlsx` files are local validation artifacts and must not be committed.

## Sheet summary

`Realworks Properties` exports all readiness rows, including `export_review` rows. It includes source identity, URL,
clickable link, address/city, available facts, missing key fields, review fields, warnings, readiness statuses, and
client summary lines. It now also exposes `residential_classification`, postcode status/source/review reason,
source status, status bucket, active-inventory eligibility, DB persistence action, VvE active/monthly/status/review/
missing fields, and energy label value/status/raw/review reason.

`Summary` includes parser/detail/readiness counters, Excel row count, quality status counts, export readiness counts,
`generated_at`, and explicit statements that this is an Excel validation artifact only and not client-ready production
output.

`Field Gaps` reports usable, review, and missing counts for Realworks property facts plus postcode and coordinates.

`Warnings` aggregates warnings and includes sample canonical URLs.

`Problem Rows` ranks rows by missing/review/warning severity without hardcoding a specific address.

## Quality status counts

Current Oldenkotte readiness after hardening:

```text
advisor_review=8
client_ready=0
blocked=1
```

## Export readiness counts

Current Oldenkotte export readiness after hardening:

```text
export_review=8
export_ready=0
export_blocked=1
```

## Field gaps

Expected visible gaps from readiness include:

- `postcode`: usable `9` after detail-header/JSON-LD extraction
- `coordinates`: missing `9`
- `vve_status`: missing `4`
- `energy_label`: review `3`
- `property_type`: review `1`
- `heating`: review `1`

The export does not invent missing data.

## Warning aggregation

Expected warnings include:

- `missing_coordinates`
- `missing_vve_for_apartment`
- `description_not_stored`
- `cv_ketel_ownership_not_clear`
- `energy_label_not_explicit`
- `hot_water_not_normalized`
- `heating_not_normalized`
- `unsupported_property_type_overigog`
- `non_residential_property_type`

## Problem rows

Rows are sorted by a problem score based on blocked/export-blocked status, advisor review status, missing key fields,
review fields, unsupported `OverigOG`, non-residential classification, missing VvE for apartments, and missing
coordinates. Corellistraat now classifies as `non_residential_blocked`, with `quality_status=blocked` and
`export_readiness=export_blocked`, but the exporter does not hardcode that row.

## Generated artifact path

```text
tmp/generated/realworks_oldenkotte_excel_validation_v1.xlsx
```

## Remaining gaps

Oldenkotte is still not ready for automatic client-ready promotion because coordinates are missing for all rows, four
apartments lack explicit VvE evidence, three energy-label values remain review-only, six rows are
inactive status-history rows, and one Corellistraat-like row is non-residential blocked.

## Recommendation

Use the workbook for human Excel validation. Do not treat the current sample as production client-ready output until
postcode/location and review-field handling are hardened.

## Constraints confirmation

- No email.
- No matching.
- No n8n.
- No dashboard.
- No `data/raw`.
- No Funda or Pararius.
- No raw HTML/JSON persistence.
- No long descriptions or images.
- No LLM.
- No parser per makelaar.
- No eligibility changes.
- No automatic client-ready promotion.

## Hardening notes

- Postcode is a critical production field. The extractor reads JSON-LD address fields first and then visible
  Realworks detail headers such as `Magentahof 1 | 5044 SN Tilburg` using the Dutch postcode regex
  `\b[1-9][0-9]{3}\s?[A-Z]{2}\b`. Missing postcode uses `postcode_status=missing` and
  `postcode_source=missing_not_extracted`.
- VvE is explicit for review. Apartments without explicit VvE evidence get `vve_status=missing` and
  `missing_vve_for_apartment`.
- Energy labels are separated into display value, status, raw value, and review reason. `Niet aanwezig` remains raw
  evidence, not a usable label.
- `OverigOG`, garage, storage, parking, and other non-residential terms are blocked or clearly marked for human audit.
- Sold, under-contract, under-offer, and rented rows are retained for source inventory/history via
  `db_persistence_action=store_status_history`, but `active_inventory_eligible=false`.
- Non-residential rows are retained for audit/exclusion via `db_persistence_action=store_excluded_non_residential`, not
  active matching.
