# Realworks Property Facts Extractor v1

## Objective

Create a reusable Realworks property facts extractor that converts permitted Realworks detail HTML held in memory into the existing `PropertyFactsRecord` contract.

The extractor uses family-level `kenmerkName` / `kenmerkValue` blocks. It is not an Oldenkotte-specific parser and does not create one parser per makelaar.

## Scope and constraints

- In-memory Realworks detail HTML only.
- No raw HTML or JSON persistence.
- No cache, readiness rows, Excel, matching, email, n8n, dashboard, or eligibility changes.
- No Funda or Pararius work.
- No browser automation, Playwright, Selenium, proxies, stealth behavior, CAPTCHA solving, or bypass.
- No long descriptions copied; only `description_length_bucket` is stored.
- No images downloaded.
- No LLM extraction.

## Extractor design

`scraper/src/domek_wonen/facts/realworks_extractor.py` exposes:

- `extract_realworks_property_facts_from_html(...)`
- `extract_realworks_property_facts_for_listing(...)`
- `realworks_field_completion_counts(...)`

The extractor reads `span.kenmerk` label/value facts, maps known Realworks labels to `PropertyFactValue` rows, and returns a `PropertyFactsRecord`. Listing card fallbacks are limited to price and status when the detail page lacks those facts.

Missing target fields are represented explicitly with status `missing`. Ambiguous or unsupported facts are represented with status `review` and warnings.

## Field mapping

| Realworks label | Contract field |
| --- | --- |
| `soort object` | `property_type` |
| `vraagprijs` | `asking_price` |
| `status` / `aanvaarding` | `availability_date` |
| `aantal kamers` | `rooms` |
| `aantal slaapkamers` | `bedrooms` |
| `aantal badkamers` | `bathrooms` |
| `woonoppervlakte` | `living_area_m2` |
| `perceeloppervlakte` | `plot_area_m2` |
| `inhoud` | `volume_m3` |
| `energieklasse` / `energielabel` | `energy_label` |
| `bouwjaar` | `bouwjaar` |
| `verwarming` | `heating_type` |
| `warmwater` | `hot_water` |
| `isolatie` | `insulation` |
| `tuin` | `garden` |
| `parkeerfaciliteiten` | `parking` |
| `garage` | `garage` |
| `eigendomssituatie` | `eigendomssituatie` |
| `vve` / `vve bijdrage` | `vve_active` / `vve_monthly_cost` |

`subtype woning` is not promoted into the main type field in v1 because the current facts contract has no `property_type_detail` field.

## Conservative rules

- Bedrooms are never inferred from rooms.
- Energy label requires an explicit class value such as `A`, `A+`, `A++`, `B`, `C`, `D`, `E`, `F`, or `G`.
- Non-explicit energy values stay `review`.
- `Volle eigendom` does not become erfpacht.
- Explicit `Erfpacht` maps to `eigendomssituatie=erfpacht`.
- `OverigOG` maps to review with `unsupported_property_type_overigog`.
- `Geen tuin` is a usable explicit value.
- Ambiguous parking or garage values stay review.
- CV-ketel ownership details remain missing unless ownership is explicit.
- VvE remains missing unless a VvE label is present.
- Description text is not stored.

## Offline tests

Added `tests/test_realworks_property_facts_extractor.py` with synthetic Realworks detail fixtures covering:

- Areas, volume, rooms, bedrooms, bathrooms, price, bouwjaar, heating, garden, ownership, and energy labels.
- No bedroom inference from rooms.
- No energy-label extraction from label text alone.
- Review for non-explicit energy labels and `OverigOG`.
- Listing fallback for price/status only when detail is missing.
- Domain-independent behavior.
- Stable `PropertyFactsRecord` metadata, warnings, and capped evidence previews.

Latest focused result:

```text
python -m pytest tests/test_realworks_property_facts_extractor.py -q
22 passed
```

## Live validation

Target:

- `source_id`: `oldenkotte.com__tilburg`
- `listing_url`: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- `max_listing_fetches`: 1
- `max_detail_fetches`: 9
- `timeout_seconds`: 15

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
```

## Field completion matrix

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

Top warnings:

| warning | count |
| --- | ---: |
| `description_not_stored` | 9 |
| `cv_ketel_ownership_not_clear` | 6 |
| `energy_label_not_explicit` | 3 |
| `hot_water_not_normalized` | 2 |
| `heating_not_normalized` | 1 |
| `unsupported_property_type_overigog` | 1 |

## Sample records compact

| canonical_url | address | asking_price | property_type | living_area_m2 | energy_label |
| --- | --- | ---: | --- | ---: | --- |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10145172-Magentahof-1` | Magentahof 1 | 495000 | appartement | 103 | B |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10129996-Corellistraat-0ong` | Corellistraat | 149500 | unknown |  | Niet aanwezig |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9913970-Dirigentenlaan-9b` | Dirigentenlaan 9 b | 279500 | appartement | 76 | Niet aanwezig |

The `Niet aanwezig` energy values are review facts, not usable energy labels.

## Backup validation

Backup source: `olden.nl__heusden`

```text
listing_parser_total=10
listing_qa_clean=10
listing_qa_review=0
listing_qa_rejected=0
detail_attempted=3
detail_succeeded=2
detail_failed=1
facts_records_built=2
```

Both successful backup details used the same Realworks `kenmerkName` / `kenmerkValue` structure.

## Remaining gaps

- `property_type_detail` is not represented in the current facts contract.
- CV-ketel ownership details need explicit ownership evidence before promotion.
- Parking and garage values are intentionally light-touch in v1.
- VvE was not observed in the Oldenkotte sample.
- One Olden backup detail fetch failed during bounded validation.
- `Niet aanwezig` energy values remain review and should not feed client-ready matching.

## Recommendation

Merge this extractor after validation, then consider a narrow `Realworks Readiness Rows v1` only after reviewing how review/missing facts should be gated. Additional hardening can focus on `property_type_detail`, heating/hot-water vocabularies, and VvE samples.

## Constraints confirmation

- No Excel created.
- No readiness rows created.
- No matching touched.
- No email touched.
- No n8n touched.
- No dashboard touched.
- No `data/raw` touched.
- No Funda or Pararius touched.
- No browser automation, Playwright, Selenium, proxies, stealth, CAPTCHA solving, or bypass behavior.
- No raw HTML or JSON persisted.
- No long descriptions copied.
- No images downloaded.
- No LLM used.
- No parser per makelaar created.
- No eligibility changes.
