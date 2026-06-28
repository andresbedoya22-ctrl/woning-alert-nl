# Realworks Detail Facts Probe v1

## Objective

Inspect permitted Realworks detail pages for the 9 QA-clean Oldenkotte listings and determine which property facts are available before designing a later `Realworks Property Facts Extractor v1`.

## Target

- Source: `oldenkotte.com__tilburg`
- Domain: `oldenkotte.com`
- Listing URL: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- Parser family: `realworks_public`

## Scope and constraints

- Diagnostic probe only.
- Standard-library HTTP only through the existing controlled live fetch helper.
- `robots_gate.can_fetch(domain, path)` checked before listing and detail fetches.
- No browser automation, Playwright, Selenium, proxies, stealth, CAPTCHA solving, or bypass behavior.
- No raw HTML or JSON persisted.
- No long descriptions copied.
- No image downloads.
- No LLM extraction.
- No parser per makelaar.
- No Excel, matching, email, n8n, dashboard, eligibility, Funda, Pararius, or `data/raw` changes.

## Listing clean input

- `listing_parser_total`: 9
- `listing_qa_clean`: 9
- `listing_qa_review`: 0
- `listing_qa_rejected`: 0
- `clean_canonical_urls_count`: 9

Sample clean URLs:

| canonical_url | address |
| --- | --- |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10145172-Magentahof-1` | Magentahof 1 |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10129996-Corellistraat-0ong` | Corellistraat |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9913970-Dirigentenlaan-9b` | Dirigentenlaan 9 b |
| `http://www.oldenkotte.com/aanbod/woningaanbod/goirle/koop/huis-9942076-Fabriekstraat-31` | Fabriekstraat 31 |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9942120-Oerlesestraat-214` | Oerlesestraat 214 |

## Detail fetch scope

- `detail_pages_attempted`: 9
- `detail_pages_succeeded`: 9
- `detail_pages_failed`: 0
- `robots_allowed_count`: 9
- `robots_blocked_count`: 0
- `max_listing_fetches`: 1
- `max_detail_fetches`: 9
- `timeout_seconds`: 15

## Detail page structure observed

All 9 detail pages exposed Realworks detail markers and reusable fact-like blocks:

| structure signal | count |
| --- | ---: |
| Realworks markers | 9 |
| Fact table / Realworks `kenmerkName` + `kenmerkValue` blocks | 9 |
| Definition list | 0 |
| JSON-LD | 9 |
| Embedded state markers | 9 |
| Description available | 9 |

The reusable Realworks structure is a set of `span.kenmerk` blocks containing nested `kenmerkName` and `kenmerkValue` spans. This looks family-level, not Oldenkotte-specific.

Common labels observed:

`soort object`, `status`, `aanvaarding`, `bouwvorm`, `energieklasse`, `huidig gebruik`, `huidige bestemming`, `gemeente`, `sectie`, `perceelnummer`, `eigendomssituatie`, `woonoppervlakte`, `aantal kamers`, `vraagprijs`, `subtype woning`, `inhoud`, `aantal slaapkamers`, `verwarming`, `warmwater`, `tuin`, `isolatie`, `bouwjaar`, `aantal badkamers`, `parkeerfaciliteiten`, `perceeloppervlakte`, `c.v.-ketel`.

## Field availability matrix

| field | usable | review | missing | notes |
| --- | ---: | ---: | ---: | --- |
| property_type | 9 | 0 | 0 | From `soort object`; later extractor should normalize values like `Appartement`, `Woonhuis`, and `OverigOG`. |
| asking_price | 8 | 0 | 1 | From `vraagprijs`; one non-standard/land row lacked usable price in detail facts. |
| availability | 9 | 0 | 0 | From `status` or `aanvaarding`; keep listing status separate from availability details. |
| rooms | 8 | 0 | 1 | From `aantal kamers`; do not infer bedrooms from this. |
| bedrooms | 8 | 0 | 1 | From `aantal slaapkamers`. |
| bathrooms | 6 | 0 | 3 | From `aantal badkamers`. |
| living_area_m2 | 8 | 0 | 1 | From `woonoppervlakte`. |
| plot_area_m2 | 6 | 0 | 3 | From `perceeloppervlakte`; apartments often missing. |
| volume_m3 | 8 | 0 | 1 | From `inhoud`. |
| energy_label | 6 | 3 | 0 | From `energieklasse`; non-explicit values stay review. |
| bouwjaar | 6 | 0 | 3 | From `bouwjaar`. |
| heating | 8 | 0 | 1 | From `verwarming` / `c.v.-ketel`; needs normalized mapping later. |
| insulation | 7 | 0 | 2 | From `isolatie`. |
| garden | 8 | 0 | 1 | From `tuin`; `geen tuin` is a usable explicit value, not a missing value. |
| parking | 6 | 0 | 3 | From `parkeerfaciliteiten`. |
| garage | 2 | 0 | 7 | From garage labels where present. |
| vve | 0 | 0 | 9 | No clear VvE field in this sample. |
| ownership_or_erfpacht | 9 | 0 | 0 | From `eigendomssituatie`; no false erfpacht promotion. |
| description_length_bucket | 9 | 0 | 0 | Bucket only; no description text persisted. |

## Sample rows compact

| canonical_url | address | price | property_type | rooms | bedrooms | living_area_m2 | plot_area_m2 | energy_label | bouwjaar | warnings |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10145172-Magentahof-1` | Magentahof 1 | 495000 | appartement | 3 | 2 | 103 |  | B | 1998 | `missing_fact_source` |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10129996-Corellistraat-0ong` | Corellistraat | 149500 | overigog |  |  |  | 108 |  |  | `missing_fact_source` |
| `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9913970-Dirigentenlaan-9b` | Dirigentenlaan 9 b | 279500 | appartement | 3 | 2 | 76 |  |  | 2004 | `missing_fact_source` |

## Backup sample if any

Backup source: `olden.nl__heusden`

- Listing result: `10 total / 10 clean / 0 review / 0 rejected`
- Detail result: `3 attempted / 2 succeeded / 1 failed`
- Robots: `3 allowed / 0 blocked`

The 2 successful detail pages used the same Realworks `kenmerkName` / `kenmerkValue` labels and yielded usable property type, price, availability, rooms, bedrooms, bathrooms, living area, plot area, volume, energy label, bouwjaar, heating, insulation, garden, parking, garage, ownership, and description bucket. This supports a family-level Realworks extractor design rather than an Oldenkotte-specific extractor.

## Extraction rules learned

- Prefer Realworks `kenmerkName` / `kenmerkValue` pairs as the primary visible facts source.
- Treat JSON-LD and embedded state as present structure signals, but do not use them until the extractor design reviews exact payload shape.
- Use strong labels only.
- Do not infer bedrooms from rooms.
- Do not infer energy label from the word `Energielabel`; require an explicit label value such as `B`, `C`, or `A+`.
- Do not mark erfpacht unless explicit affirmative evidence is present.
- Keep description handling to availability and length bucket only.
- Keep status/availability separate from listing transaction status.
- Normalize later; the probe intentionally reports compact candidate values rather than client-ready facts.

## Risks and limitations

- Energy label had 3 review cases where a Realworks label existed but the value was not a clear energy class.
- VvE was not observed in the Oldenkotte sample; apartment VvE handling needs more Realworks samples.
- Parking/garage labels vary and need careful normalization.
- `OverigOG` appears as a property type candidate and should likely be review or unsupported in a later extractor.
- One `olden.nl` backup detail fetch failed despite robots allowing the URL, so backup coverage is partial.
- The probe is not a normalized facts contract and should not feed matching or advisor outputs directly.

## Recommendation

Proceed to `Realworks Property Facts Extractor v1` only as a family-level extractor over Realworks detail `kenmerkName` / `kenmerkValue` blocks, with tests for Oldenkotte plus at least one backup Realworks domain. Keep VvE, `OverigOG`, non-explicit energy labels, parking/garage normalization, and ownership/erfpacht as conservative review paths until stronger evidence is available.

## Constraints confirmation

- No Excel created.
- No matching touched.
- No advisor email touched.
- No n8n touched.
- No dashboard touched.
- No eligibility changed.
- No `data/raw` touched.
- No Funda or Pararius extraction.
- No browser automation, Playwright, Selenium, proxies, stealth, CAPTCHA solving, or bypass behavior.
- No raw HTML or JSON persisted.
- No long descriptions copied.
- No images downloaded.
- No LLM used for extraction.
- No parser per makelaar created.
