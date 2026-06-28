# Realworks Parser Family Validation v1

## Objective

Harden the reusable `realworks_public` parser family using Oldenkotte as the live validation target, without creating a parser per makelaar.

This phase did not touch matching, advisor email, n8n, dashboard, Excel, eligibility, Funda, Pararius, `data/raw`, browser automation, Playwright, Selenium, proxies, stealth behavior, CAPTCHA handling, LLM extraction, or raw HTML/JSON persistence.

## Target

- Source: `oldenkotte.com__tilburg`
- Domain: `oldenkotte.com`
- Listing URL: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- Prior classification: `realworks_strong_candidate`
- Prior evidence: `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `/aanbod/woningaanbod`

## Baseline Before

The bounded baseline used the existing Realworks parser path with `robots_gate.can_fetch(domain, path)` before fetching. The live HTML stayed in memory only.

Oldenkotte baseline:

- `parser_total`: `36`
- `qa_clean`: `0`
- `qa_review`: `36`
- `qa_rejected`: `0`
- `inventory_snapshot_count`: `0`
- Top review reasons:
  - `listing_marked_needs_review`: `36`
  - `missing_address`: `36`
  - `missing_price`: `36`
  - `missing_city`: `36`
  - `low_confidence`: `36`
  - `unknown_transaction_type`: `36`
  - `unknown_status`: `33`
- Sample overcaptured URLs:
  - `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
  - `http://www.oldenkotte.com/aanbod/woningaanbod/koop/garage`
  - `http://www.oldenkotte.com/aanbod/woningaanbod/koop/schuur-berging`
  - `http://www.oldenkotte.com/aanbod/woningaanbod/koop/tuin`
  - `http://www.oldenkotte.com/aanbod/woningaanbod/koop/eengezinswoning`

The baseline confirmed that the family parser ran, but it iterated global anchors and accepted navigation/filter/category paths as listing candidates.

## Changes Made

The Realworks parser-family hardening is limited to `scraper/src/domek_wonen/parsers/realworks_family.py`.

- Prefer Realworks listing containers such as `aanbodEntry`, `realworks-card`, `property-card`, and `listing-card`.
- Parse card-level HTML instead of anchor body only, so address, city, price, and status fields inside surrounding card markup are visible.
- Require detail-like Realworks URL shapes with city/status/detail slug specificity.
- Reject category, subtype, archive, open-house, and service URLs such as:
  - `/aanbod/woningaanbod/koop`
  - `/aanbod/woningaanbod/koop/garage`
  - `/aanbod/woningaanbod/open-huis`
  - `/aanbod/woningaanbod/archief/verkocht`
  - `/woning-verkopen`
  - `/woning-kopen`
- Prefer precise class extraction for `street-address`, `locality`, `price`, and `objectstatusbanner`.
- Fall back to full card text for price parsing when nested Realworks spans make the class body incomplete.

No Oldenkotte-specific parser, domain-specific address list, or makelaar-specific selector was added.

## After Metrics

Oldenkotte post-hardening validation:

- `robots_allowed`: `True`
- `parser_total`: `9`
- `qa_clean`: `9`
- `qa_review`: `0`
- `qa_rejected`: `0`
- `inventory_snapshot_count`: `9`
- Top review reasons: none
- Top reject reasons: none
- Parser warnings: none

Sample clean canonical URLs:

- `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10145172-Magentahof-1`
- `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-10129996-Corellistraat-0ong`
- `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9913970-Dirigentenlaan-9b`
- `http://www.oldenkotte.com/aanbod/woningaanbod/goirle/koop/huis-9942076-Fabriekstraat-31`
- `http://www.oldenkotte.com/aanbod/woningaanbod/tilburg/koop/huis-9942120-Oerlesestraat-214`

Sample clean addresses:

- `Magentahof 1`
- `Corellistraat`
- `Dirigentenlaan 9 b`
- `Fabriekstraat 31`
- `Oerlesestraat 214`

No review or rejected URLs were produced after hardening.

## Backup Validation

Backup source: `olden.nl__heusden`

- Listing URL: `http://www.olden.nl/aanbod/woningaanbod`
- `robots_gate.can_fetch`: `True`
- Note: fetching robots for `olden.nl` logged a certificate hostname mismatch and the gate treated robots as unreachable, which currently allows fetches.
- `parser_total`: `10`
- `qa_clean`: `10`
- `qa_review`: `0`
- `qa_rejected`: `0`
- `inventory_snapshot_count`: `10`
- Top review reasons: none
- Top reject reasons: none

Sample clean canonical URLs:

- `http://www.olden.nl/aanbod/woningaanbod/waalwijk/koop/huis-10189896-A.B.-van-Lieshoutlaan-10`
- `http://www.olden.nl/aanbod/woningaanbod/sprang-capelle/koop/huis-10160900-Reiger-9`
- `http://www.olden.nl/aanbod/woningaanbod/waalwijk/koop/huis-10302874-Villa-Spaanse-Ruiter-32`
- `http://www.olden.nl/aanbod/woningaanbod/waalwijk/koop/huis-9808020-Besoyensestraat-18`
- `http://www.olden.nl/aanbod/woningaanbod/waalwijk/koop/huis-10298658-Grotestraat-339w`

Sample clean addresses:

- `A.B. van Lieshoutlaan 10`
- `Reiger 9`
- `Villa Spaanse Ruiter 32`
- `Besoyensestraat 18`
- `Grotestraat 339 w`

## Offline Tests

Added `tests/test_realworks_parser_family_hardening.py` with synthetic/offline coverage for:

- Realworks-style listing card parsing with markers, detail href, address, price, city, status, and QA clean output.
- Rejection of category, subtype, archive, open-house, and service URLs.
- Domain-independent behavior for `olden.nl` and `gewoonmakelaars.nl` style URLs.
- Deterministic canonical URL normalization.
- Explicit QA review and rejection reasons.

## Remaining Gaps

- The parser remains an HTML listing-page parser. It does not fetch details, enrich missing fields, or handle JS-only sources.
- `Corellistraat` is accepted as clean because QA currently requires address text but does not require a parsed house number.
- `olden.nl` validation passed through the current robots gate behavior after a robots certificate warning; that gate behavior was not changed in this phase.
- Further Realworks variants with WordPress shells or unusual card markup still need separate family-level validation before operational promotion.
