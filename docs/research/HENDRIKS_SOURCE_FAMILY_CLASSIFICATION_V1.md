# Hendriks Source Family Classification v1

## Objective

Classify `hendriks.nl` as a housing source family candidate from local evidence plus a bounded controlled probe of the user-provided seed URL. This phase is source-family discovery only: it does not create a Hendriks parser, does not change eligibility, and does not move anything into matching or downstream advisor flows.

## Seed URL

https://hendriks.nl/woningaanbod

## Why Hendriks

- not OGonline
- possible Realworks/custom API evidence
- user-provided aanbod URL for this phase

## KIN lessons reused

- access policy first
- robots gate
- bounded fetch
- no raw persistence
- compact evidence
- parser family before parser per makelaar
- QA gates before downstream use
- facts/Excel only after source is validated

## Local evidence

| source_id | domain | listing_url | current_platform_guess | current_delivery_mode | parser_family_candidate | access_status | source_quality_status | needs_review | review_reason | known_api_hints | known_realworks_hints | known_blocking_or_verification_hints | evidence_file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `hendriks.nl__tilburg` | `hendriks.nl` | `https://hendriks.nl/woningaanbod` plus local detail-like evidence under `/woningaanbod/koop/...` | `custom / unknown_manual_review` | not confirmed | not confirmed | robots allowed in prior probe | manual review | yes in prior source intelligence | source master still flags review; no clear API | `/api` hint; `/api/offices` previously fetched | prior page exposed `realworks` text on one page, but not confirmed usable | none confirmed | `docs/research/OGONLINE_CANDIDATE_RECLASSIFICATION_DISCOVERY_V1.md` |
| `hendriks.nl__tilburg` | `hendriks.nl` | `https://hendriks.nl/woningaanbod` | not OGonline | not OGonline/XHR | not OGonline/XHR | allow for fetched URLs | manual/custom source | no OGonline follow-up | no deterministic OGonline endpoint | `https://hendriks.nl/api/offices` JSON, not inventory | none strong in focused probe | none | `docs/research/FOCUSED_POSSIBLE_OGONLINE_CANDIDATE_PROBE_V1.md` |
| Hendriks offices in Noord-Brabant | `hendriks.nl` | `https://hendriks.nl/woningaanbod/koop/rijsbergsebaan-13-4836-mc-breda` | not set | not set | not set | not set | `valid` seed URL quality | `false` | empty | none | none | none | `data/processed/sources_seed_noord_brabant.csv`; `data/discovery/processed/sources_seed_with_gemeente.csv` |
| fixture-style enrichment test row | `hendriks.nl` | `https://hendriks.nl/wonen` | `custom` | `unknown_manual_review` then enriched to `json_ld` in synthetic test | not set | manual review in fixture | test-only | yes in fixture | `manual_review_needed` | none | none | none | `tests/test_delivery_mode_evidence_enrichment.py` |

Local evidence says Hendriks should stay outside OGonline/XHR. It also does not prove `realworks_public`; the strongest local Realworks signal is an earlier textual marker, not a successful parser-family validation.

## Live probe scope

- fetch count: 8 total fetch events, 7 unique URLs
- robots checks: 8 total checks, all allowed
- URLs probed:
  - `https://hendriks.nl/woningaanbod`
  - `https://hendriks.nl/`
  - `https://hendriks.nl/dist/objects.BOECZNb_.min.js` (fetched twice: once in the main marker pass, once for compact endpoint inspection)
  - `https://hendriks.nl/dist/app.x8QYJ2Fr.min.js`
  - `https://hendriks.nl/dist/custom-select.BD6PAQAF.min.js`
  - `https://hendriks.nl/dist/home.DyoIR2L-.min.js`
  - `https://hendriks.nl/api/offices`
- persistence policy:
  - responses stayed in memory only
  - no raw HTML written
  - no raw JSON written
  - no generated capture artifact written
  - only compact markers and shape summaries are retained here

Compact marker evidence:

| marker | source URL | status | content-type | robots | classification | compact snippet |
| --- | --- | ---: | --- | --- | --- | --- |
| `woningaanbod` | `https://hendriks.nl/woningaanbod` | 200 | `text/html; charset=UTF-8` | allowed | listing-page marker | page title says current housing aanbod |
| `properties` | `https://hendriks.nl/woningaanbod` | 200 | `text/html; charset=UTF-8` | allowed | app marker | route state uses path `/woningaanbod` and name `properties` |
| `objects` | `https://hendriks.nl/woningaanbod` | 200 | `text/html; charset=UTF-8` | allowed | app asset marker | `objects` CSS and app container references |
| `woningen` | `https://hendriks.nl/` | 200 | `text/html; charset=UTF-8` | allowed | homepage related-property text | homepage references most-viewed homes |
| `/api/` | `https://hendriks.nl/dist/objects.BOECZNb_.min.js` | 200 | `application/javascript` | allowed | false-positive external map API | Google Maps API loader, not Hendriks inventory |
| `fetch(` | `https://hendriks.nl/dist/objects.BOECZNb_.min.js` | 200 | `application/javascript` | allowed | non-inventory helper | compact snippet showed `geo/geocode`, not listing inventory |
| `/api/` | `https://hendriks.nl/dist/app.x8QYJ2Fr.min.js` | 200 | `application/javascript` | allowed | same-domain API marker | `prefixFetchUrl="/api/offices"` |
| `api/offices` | `https://hendriks.nl/dist/app.x8QYJ2Fr.min.js` | 200 | `application/javascript` | allowed | offices endpoint marker | office/location component only |

No fetched page, script, API response, or compact detail evidence showed a challenge page, CAPTCHA, Cloudflare block, login wall, paywall, or `403`.

## Realworks evidence

Current live probe found no strong Realworks marker:

- no `realworks`
- no `realworks.nl`
- no `api.realworks`
- no `data-realworks`

Prior local research mentions one previous `realworks` text marker on one Hendriks page, but this phase did not reproduce a strong Realworks signal on the seed URL, homepage, same-domain scripts, or fetched offices endpoint.

## Custom API evidence

| endpoint | classification | top_level_keys | looks_like_inventory | sample_item_keys | next_step |
| --- | --- | --- | --- | --- | --- |
| `https://hendriks.nl/api/offices` | `offices_api` | `status`, `statusCode`, `time`, `locale`, `offices`, `_links` | no | none retained; endpoint shape is office/location oriented | ignore for inventory |

The JS app surface includes `objects`, `properties`, and a `geo/geocode` helper, but the controlled probe did not discover a same-domain listing inventory endpoint such as `/api/properties`, `/api/listings`, `/api/objects`, or `/api/woningen`.

Because an API surface exists but only an offices endpoint was confirmed, the custom API status is `custom_api_possible_needs_more_evidence`, not `custom_api_candidate_ready`.

## Detail page evidence

No detail URL was discovered from `https://hendriks.nl/woningaanbod` during this bounded probe. The local seed files contain a detail-like URL under `/woningaanbod/koop/...`, but the phase rules limited detail probing to URLs discovered from the listing page, so no detail page was fetched.

Detail page probe result:

- address-like text present: not probed
- price-like text present: not probed
- energy label-like text present: not probed
- facts table present: not probed
- realworks marker present: not probed
- raw JSON/state present: not probed
- verification/challenge present: not probed

## Parser/QA probe result if any

Realworks parser probe result:

- realworks_probe_attempted: no
- reason: no strong Realworks marker in current live probe
- parser_total: not applicable
- qa_clean: not applicable
- qa_review: not applicable
- qa_rejected: not applicable
- inventory_snapshot_count: not applicable
- sample canonical_urls: not applicable
- sample addresses: not applicable

The existing Realworks path could be used for a single manual source only if source-family evidence supports `realworks_public`: `CapturePilotSource`, `run_realworks_capture_pilot_for_source`, `ParserFamilyRunner`, `qa_parser_family_result`, and `InventorySnapshot` are already available. This phase did not meet the threshold to run it.

## Final classification

`custom_api_possible_needs_more_evidence`

Rationale:

- Hendriks is not an OGonline/XHR candidate based on prior focused research.
- Current live probe did not find strong Realworks markers.
- Current live probe confirmed a same-domain JSON API surface, but the only confirmed endpoint is `/api/offices`, which is not listing inventory.
- The seed listing page is reachable and app-backed, but no detail URL or clear inventory endpoint was discovered within the bounded probe.
- No verification/challenge blocker appeared.

Rejected classifications for this phase:

- `realworks_candidate_ready`: no strong Realworks marker and no Realworks parser QA-clean output.
- `realworks_possible_needs_more_evidence`: prior weak marker exists, but current seed/home/script/API evidence did not reproduce Realworks.
- `custom_api_candidate_ready`: no listing-like inventory API confirmed.
- `static_html_candidate`: listing page is reachable, but no listing/detail HTML was discovered from the seed page.
- `blocked_or_verification_limited`: no blocking/challenge evidence appeared.
- `not_viable_now`: too strong; there is a reachable listing app and same-domain API surface worth a narrower later probe.

## Recommended next step

Run a separate Hendriks custom API/source-config discovery phase, still bounded and still source-family oriented:

- inspect only the listing app network/config surface already visible from `objects`/`properties` JS;
- keep max fetches low and robots-gated;
- classify whether the app has a reusable custom inventory API;
- do not build a Hendriks parser until an inventory endpoint or reusable static listing/detail pattern is confirmed.

Do not start Realworks validation for Hendriks yet unless a later page or endpoint exposes strong Realworks evidence.

## Constraints confirmation

- No email.
- No matching.
- No n8n.
- No dashboard.
- No `data/raw` changes.
- No Funda or Pararius probing.
- No browser automation.
- No Playwright or Selenium.
- No proxies, stealth, CAPTCHA solving, or bypass.
- No raw HTML persisted.
- No raw JSON persisted.
- No LLM extraction used.
- No parser per makelaar created.
- No eligibility changes.
- No README or legacy map update needed because this phase only created a research report.
