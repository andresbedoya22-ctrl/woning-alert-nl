# Realworks Readiness Rows v1

## Objective

Create an in-memory Realworks readiness runner that combines QA-clean Realworks listing rows, Realworks
`PropertyFactsRecord` detail facts, the existing `ClientReadyPropertySummary`, location readiness, export readiness,
field gap aggregation, and compact problem rows.

This phase answers whether Realworks rows are ready for a later Excel validation phase. It does not create Excel.

## Scope and constraints

- In-memory only.
- Bounded Oldenkotte validation: one listing fetch and nine detail fetches.
- `robots_gate.can_fetch(domain, path)` is checked before the listing URL and before every detail URL.
- Standard-library controlled HTML fetch only.
- No cache and no generated output required.
- No Excel, matching, email, n8n, dashboard, or inventory eligibility changes.
- No Funda or Pararius work.
- No browser automation, Playwright, Selenium, proxies, stealth behavior, CAPTCHA solving, or bypass.
- No raw HTML or JSON persistence.
- No long descriptions copied; only `description_length_bucket` is used.
- No image downloads.
- No LLM extraction.
- No parser per makelaar.

## Row model

`scraper/src/domek_wonen/pilots/realworks_property_readiness.py` adds `RealworksPropertyReadinessRow` with:

- source identity: `source_id`, `source_domain`, `canonical_url`, `property_link`;
- location: `address`, `postcode`, `city`, `location_readiness`;
- normalized facts: `asking_price`, `property_type`, `status`, `availability`, `rooms`, `bedrooms`, `bathrooms`,
  `living_area_m2`, `plot_area_m2`, `volume_m3`, `energy_label`, `bouwjaar`, `heating`, `garden`, `parking`,
  `garage`, `ownership_or_erfpacht`, `description_length_bucket`;
- readiness output: `client_summary`, `export_readiness`, `quality_status`, `missing_key_fields`, `review_fields`,
  and `warnings`.

Postcode is never invented. Latitude and longitude are reported as `missing_coordinates` when absent, but they do not
block rows when address and city are usable.

## Readiness rules

`quality_status` values:

- `client_ready`: canonical URL, address, city, asking price, supported property type, and at least one area signal are
  usable; no missing key fields; no review fields; no critical warnings.
- `advisor_review`: real and usable row with review or missing nonfatal fields, such as missing postcode, energy label
  review, missing bedrooms, missing bathrooms, missing bouwjaar, unclear heating, or `OverigOG`.
- `blocked`: missing canonical URL, address, city, price, usable property type, or area signal, or a definitely
  unsupported non-residential type.

`export_readiness` maps directly:

- `client_ready` -> `export_ready`
- `advisor_review` -> `export_review`
- `blocked` -> `export_blocked`

This does not modify global inventory eligibility.

## Live validation

Target:

- `source_id`: `oldenkotte.com__tilburg`
- `listing_url`: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- `max_listing_fetches`: `1`
- `max_detail_fetches`: `9`
- `timeout_seconds`: `15`

Result:

```text
listing_parser_total=9
listing_qa_clean=9
listing_qa_review=0
listing_qa_rejected=0
detail_attempted=9
detail_succeeded=9
detail_failed=0
facts_records_built=9
readiness_rows_built=9
excel_validation_ready=True
```

## Quality status counts

| quality_status | count |
| --- | ---: |
| advisor_review | 9 |

No row is `client_ready` because Oldenkotte does not expose postcode in the current listing/detail facts. No row is
blocked.

## Export readiness counts

| export_readiness | count |
| --- | ---: |
| export_review | 9 |

## Field completion

| field | usable | review | missing |
| --- | ---: | ---: | ---: |
| property_type | 8 | 1 | 0 |
| asking_price | 9 | 0 | 0 |
| availability | 9 | 0 | 0 |
| rooms | 8 | 0 | 1 |
| bedrooms | 8 | 0 | 1 |
| bathrooms | 6 | 0 | 3 |
| living_area_m2 | 8 | 0 | 1 |
| plot_area_m2 | 6 | 0 | 3 |
| volume_m3 | 8 | 0 | 1 |
| energy_label | 6 | 3 | 0 |
| bouwjaar | 6 | 0 | 3 |
| heating | 7 | 1 | 1 |
| garden | 8 | 0 | 1 |
| parking | 6 | 0 | 3 |
| garage | 2 | 0 | 7 |
| ownership_or_erfpacht | 9 | 0 | 0 |
| description_length_bucket | 9 | 0 | 0 |

## Missing key fields

| field | count |
| --- | ---: |
| postcode | 9 |
| bathrooms | 3 |
| bouwjaar | 3 |
| energy_label | 3 |
| parking | 3 |
| bedrooms | 1 |
| heating_type | 1 |
| living_area_m2 | 1 |
| property_type | 1 |

## Review fields

| field | count |
| --- | ---: |
| energy_label | 3 |
| heating | 1 |
| property_type | 1 |

## Warning aggregation

| warning | count |
| --- | ---: |
| missing_coordinates | 9 |
| missing_postcode | 9 |
| description_not_stored | 9 |
| cv_ketel_ownership_not_clear | 6 |
| energy_label_not_explicit | 3 |
| hot_water_not_normalized | 2 |
| heating_not_normalized | 1 |
| unsupported_property_type_overigog | 1 |

## Sample rows compact

| canonical_url | address | city | price | property_type | quality_status | missing_key_fields | review_fields |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| `.../huis-10145172-Magentahof-1` | Magentahof 1 | Tilburg | 495000 | appartement | advisor_review | postcode |  |
| `.../huis-10129996-Corellistraat-0ong` | Corellistraat | Tilburg | 149500 | unknown | advisor_review | property_type, living_area_m2, bedrooms, energy_label, postcode, bathrooms, bouwjaar, heating_type, parking | property_type, energy_label |
| `.../huis-9913970-Dirigentenlaan-9b` | Dirigentenlaan 9 b | Tilburg | 279500 | appartement | advisor_review | energy_label, postcode, bathrooms | energy_label |
| `.../huis-9942076-Fabriekstraat-31` | Fabriekstraat 31 | Goirle | 450000 | woonhuis | advisor_review | postcode, bouwjaar |  |
| `.../huis-9942120-Oerlesestraat-214` | Oerlesestraat 214 | Tilburg | 369500 | woonhuis | advisor_review | postcode | heating |

## Problem rows compact

Highest-ranked problem rows:

| canonical_url | issue summary |
| --- | --- |
| `.../huis-10129996-Corellistraat-0ong` | `OverigOG` review, missing area/bedrooms/energy/postcode/bathrooms/bouwjaar/heating/parking |
| `.../huis-9510128-Vazalstraat-21` | energy label review, missing postcode, bouwjaar, parking |
| `.../huis-9913970-Dirigentenlaan-9b` | energy label review, missing postcode and bathrooms |
| `.../huis-9942076-Fabriekstraat-31` | missing postcode and bouwjaar |
| `.../huis-9942120-Oerlesestraat-214` | heating review and missing postcode |

## Remaining gaps

- Postcode is absent for all nine Oldenkotte rows in the current listing/detail extraction path.
- Coordinates are absent for all nine rows and are kept as a known completeness gap.
- One `OverigOG` row remains advisor-review, not client-ready.
- Energy label has three review cases with non-explicit values.
- Bathrooms, bouwjaar, parking, and garage are incomplete in the sample.
- Heating and hot-water normalization need additional vocabulary hardening.

## Recommendation

Proceed to `Realworks Excel Validation v1` as a human-validation artifact, exporting all rows with
`export_review` labels. Do not treat the current Oldenkotte sample as client-ready production inventory until postcode
and review-field handling are hardened.

## Constraints confirmation

- No Excel created.
- No matching touched.
- No email touched.
- No n8n touched.
- No dashboard touched.
- No `data/raw` touched.
- No Funda or Pararius touched.
- No raw HTML or JSON persisted.
- No long descriptions copied.
- No images downloaded.
- No LLM used.
- No parser per makelaar created.
- No eligibility changes.
