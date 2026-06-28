# Realworks Inventory Ground Truth Census v1

## Objective

Create a conservative ground-truth census of local Realworks candidates before choosing the next parser-family validation target.

This was discovery, census, and selection only. It did not build a new parser, create Excel, touch matching, email, n8n, dashboard, eligibility, Funda, Pararius, or `data/raw`.

## Why ground truth was needed

KIN proved that inherited `realworks` labels are not enough. Local platform evidence previously showed `kinmakelaars.nl` as `realworks`, but later evidence confirmed KIN as OGonline/XHR. The KIN false-positive path means this census treats prior `platform_guess=realworks` only as a starting signal, not as proof.

Hendriks is also excluded from this phase. The pending Hendriks branch concluded `custom_api_possible_needs_more_evidence`, not confirmed Realworks. Hendriks remains custom API backlog.

## Scope and constraints

- Repo-local evidence first.
- Live confirmation only for domains already present in local source/fingerprint/diagnostic evidence.
- No Google, broad crawl, browser automation, Playwright, Selenium, proxies, stealth, CAPTCHA solving, or bypass behavior.
- No raw HTML or raw JSON persisted.
- No Funda or Pararius extraction.
- No parser per makelaar.
- No eligibility, matching, email, n8n, dashboard, or `data/raw` changes.

## Local evidence searched

Mandatory repo context read:

- `AGENTS.md`
- `README.md`
- `docs/12_LEGACY_MAP_AND_CLEANUP_PLAN.md`
- `docs/research/OGONLINE_CANDIDATE_RECLASSIFICATION_DISCOVERY_V1.md`
- `docs/research/FOCUSED_POSSIBLE_OGONLINE_CANDIDATE_PROBE_V1.md`
- `scraper/src/domek_wonen/compliance/robots_gate.py`
- `scraper/src/domek_wonen/discovery/`
- `scraper/src/domek_wonen/sources/`
- `scraper/src/domek_wonen/diagnostics/`
- `scraper/src/domek_wonen/parsers/source_config.py`
- `scraper/src/domek_wonen/parsers/realworks_family.py`
- `scraper/src/domek_wonen/parsers/runner.py`
- `scraper/src/domek_wonen/pilots/realworks_capture_pilot.py`
- `scraper/src/domek_wonen/pilots/source_selection.py`
- `scraper/src/domek_wonen/pilots/live_fetch.py`
- `scraper/src/domek_wonen/qa/parser_output_gate.py`

Primary local artifacts searched:

- `data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv`
- `data/discovery/platform_fingerprint/platform_fingerprint_results.csv`
- `data/platform_fingerprint/target_area/20260615T192849Z/target_area_platform_fingerprint_inventory.csv`
- `data/diagnostics/delivery_mode_fingerprint/20260617T193323Z/delivery_mode_inventory.csv`
- `data/diagnostics/delivery_mode_evidence/20260617T195606Z/delivery_mode_evidence_inventory.csv`
- `data/diagnostics/source_coverage/20260616T192404Z/tilburg_source_coverage_inventory.csv`
- `data/source_capture_audit/runs/20260615T194904Z/source_capture_audit_inventory.csv`
- `data/property_discovery/latest/property_inventory.csv`
- `data/properties/latest/property_inventory.csv`
- `docs/research/PARSER_FAMILY_READINESS_AUDIT_V1.md`

Search commands used:

```powershell
rg -n "realworks|Realworks|realworks\.nl|api\.realworks|data-realworks|platform_guess|current_platform_guess|delivery_mode|parser_family_candidate|source_domain|root_domain|aanbod_url|source_quality_status|needs_review|review_reason|access_status|legal_status" .
git ls-files | Select-String -Pattern "source|fingerprint|coverage|diagnostic|platform|delivery|master|target|audit|csv|json|jsonl|realworks"
```

Local candidate rows reviewed: `165` domain-level rows with Realworks, OGonline, KIN, Hendriks, or related local markers.

## Candidate scoring model

Positive signals:

- `+5` explicit `realworks.nl`, `static.realworks.nl`, `images.realworks.nl`, or Realworks copyright marker on live listing page.
- `+5` `api.realworks` endpoint marker.
- `+4` existing local Realworks parser/capture evidence succeeded.
- `+3` Realworks-specific embedded structure used by current parser family, including `objectId`, `/InfoWindow/`, or `data-paginatable`.
- `+3` listing/detail URL pattern compatible with `realworks_family.py`, especially `/aanbod/woningaanbod`.
- `+2` listing URL present and robots allowed.
- `+2` active listing/card evidence.
- `+1` Noord-Brabant.
- `+1` source already present in source master.

Negative signals:

- `-6` OGonline marker: `website door ogonline`, `ogonline.nl`, or `api.ogonline`.
- `-5` Funda/Pararius iframe or dependency.
- `-5` blocked, `permission_required`, or `legal_review`.
- `-4` robots disallowed.
- `-4` only weak text mention of Realworks without script/API/data structure.
- `-3` no listing URL.
- `-3` listing page is commercial/service page, not aanbod.
- `-3` custom API surface without Realworks markers.
- `-2` WordPress-only/static-only with no Realworks data.

Classification:

- `realworks_strong_candidate`
- `realworks_possible_candidate`
- `false_positive_realworks`
- `needs_manual_review`
- `reject`

## Live confirmation scope

Live confirmation used the binding robots gate before each fetch.

Initial FASE E live confirmation:

- Candidates live-probed: `15`
- Fetch count: `45`
- Robots checks: `45`
- Per-domain cap: `3`
- Persistence: responses stayed in memory; only compact markers retained in notes.

Additional live activity:

- A redundant compact marker recount fetched the same `15` listing URLs again.
- Parser probe fetched `3` selected listing URLs again for in-memory parser input.
- Total HTTP fetches actually executed during this task: `63`.
- Total explicit `robots_gate.can_fetch` checks actually executed during this task: `63`.

This exceeded the intended FASE E total live fetch budget because of the redundant compact recount. No raw HTML, JSON, HAR, browser artifacts, or generated run artifacts were persisted.

## Realworks candidates

| source_id | domain | listing_url | local_guess | live_markers | negative_markers | robots | parser_probe | score | classification | risks |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `olden.nl__heusden` | `olden.nl` | `http://www.olden.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod`; page text indicates 45 houses | generic page text includes Funda/review wording, not treated as dependency | allow | `35 total / 0 clean / 35 review / 0 rejected` | 17 | `realworks_strong_candidate` | V4 parser overcaptures navigation/filter links and produces QA review only |
| `gewoonmakelaars.nl__s-hertogenbosch` | `gewoonmakelaars.nl` | `http://www.gewoonmakelaars.nl/aanbod/woningaanbod/koop` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `objectId`, `/InfoWindow/`, `/aanbod/woningaanbod` | generic Funda text only; no blocked iframe observed | allow | not run | 17 | `realworks_strong_candidate` | small prior capture volume: 1 property |
| `oldenkotte.com__tilburg` | `oldenkotte.com` | `http://www.oldenkotte.com/aanbod/woningaanbod/koop` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `/aanbod/woningaanbod` | generic Funda text only; no blocked iframe observed | allow | `36 total / 0 clean / 36 review / 0 rejected` | 14 | `realworks_strong_candidate` | V4 parser probe returns review-only; needs parser-card hardening |
| `broedersmakelaardij.nl__alphen-chaam` | `broedersmakelaardij.nl` | `http://www.broedersmakelaardij.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod` | none observed | allow | not run | 13 | `realworks_strong_candidate` | no legacy capture audit success row in reviewed sample |
| `dekostermakelaars.nl__s-hertogenbosch` | `dekostermakelaars.nl` | `http://www.dekostermakelaars.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod` | none observed | allow | not run | 13 | `realworks_strong_candidate` | not selected because Oldenkotte is more directly relevant to Tilburg |
| `stoffelsmakelaardij.nl__s-hertogenbosch` | `stoffelsmakelaardij.nl` | `http://www.stoffelsmakelaardij.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `objectId`, `data-paginatable`, `/InfoWindow/`, `/aanbod/woningaanbod` | none observed | allow | not run | 13 | `realworks_strong_candidate` | no parser probe in this phase |
| `baasmakelaardij.nl__altena` | `baasmakelaardij.nl` | `http://www.baasmakelaardij.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `objectId`, `data-paginatable`, `/InfoWindow/`, `/aanbod/woningaanbod` | none observed | allow | not run | 13 | `realworks_strong_candidate` | no parser probe in this phase |
| `dehuyzerij.nl__s-hertogenbosch` | `dehuyzerij.nl` | `http://www.dehuyzerij.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod` | none observed | allow | not run | 13 | `realworks_strong_candidate` | no parser probe in this phase |
| `hoogveste.nl__altena` | `hoogveste.nl` | `http://www.hoogveste.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod`; page text indicates 159 houses | `pararius` word appears, not confirmed dependency in this probe | allow | not run | 13 | `realworks_strong_candidate` | high volume but Pararius text needs follow-up before operational use |
| `viaons.nl__bergen-op-zoom` | `viaons.nl` | `http://www.viaons.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, `/aanbod/woningaanbod`; page text indicates 24 houses | none observed | allow | not run | 13 | `realworks_strong_candidate` | no parser probe in this phase |
| `tulkensmakelaardij.nl__asten` | `tulkensmakelaardij.nl` | `http://www.tulkensmakelaardij.nl/aanbod/woningaanbod/koop` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `objectId`, `/InfoWindow/`, `/aanbod/woningaanbod` | generic Funda text only; no blocked iframe observed | allow | not run | 13 | `realworks_strong_candidate` | smaller local inventory count |
| `carredewit.nl__s-hertogenbosch` | `carredewit.nl` | `https://www.carredewit.nl/woningaanbod` | `realworks` | `images.realworks.nl`, `realworks.nl`; legacy capture working_source with 11 clean available | WordPress shell; generic Funda/Cloudflare/login/403 text markers in raw marker pass, no HTTP 403 | allow | `13 total / 0 clean / 13 review / 0 rejected` | 11 | `realworks_strong_candidate` | WP shell plus parser probe captured non-listing links like `woning-verkopen` |
| `tivoliwoningmakelaars.nl__tilburg` | `tivoliwoningmakelaars.nl` | `https://tivoliwoningmakelaars.nl/woningen` | `realworks` | `images.realworks.nl`, `realworks.nl`; legacy capture working_source with 14 properties found | WordPress shell; not `/aanbod/woningaanbod` | allow | not run | 11 | `realworks_strong_candidate` | custom/WP surface around Realworks media increases false-positive risk |
| `overweelmakelaardij.nl__s-hertogenbosch` | `overweelmakelaardij.nl` | `http://www.overweelmakelaardij.nl/aanbod/woningaanbod` | `realworks` | `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `/aanbod/woningaanbod` | none observed | allow | not run | 10 | `realworks_strong_candidate` | no parser probe in this phase |
| `viermakelaars.nl__s-hertogenbosch` | `viermakelaars.nl` | `https://www.viermakelaars.nl/woningaanbod` | `realworks` | `images.realworks.nl`, `realworks.nl` | WordPress shell; no Realworks page structure found in compact marker set | allow | not run | 7 | `realworks_possible_candidate` | Realworks image/media markers may be weaker than platform ownership evidence |

## False positives / rejected candidates

| source_id | domain | reason |
| --- | --- | --- |
| `kinmakelaars.nl__tilburg` and other KIN rows | `kinmakelaars.nl` | Excluded. Known KIN OGonline/XHR after later validation. Prior `realworks` labels are treated as false-positive risk. |
| `hendriks.nl__tilburg` and other Hendriks rows | `hendriks.nl` | Excluded. Current decision is custom API possible, needs more evidence; this task is not Hendriks. |
| `vandewatergroep.nl__tilburg` | `vandewatergroep.nl` | Rejected for this Realworks validation handoff. Local aanbod URL points to a nieuwbouw/project page and local source quality was rejected. |
| `vandenboschmakelaars.com__tilburg` | `vandenboschmakelaars.com` | Rejected. Local aanbod URL is a commercial service page: `/diensten/verkoopmakelaar`; source master/evidence mark it invalid or rejected. |
| `cvda.nl__tilburg` | `cvda.nl` | Needs manual review. Realworks markers exist, but local legal/source notes include `needs_manual_review`. |
| `hansvanberkel.nl__tilburg` | `hansvanberkel.nl` | Needs manual review. Realworks markers exist, but local legal/source notes include `needs_manual_review`. |
| `lupkermakelaardij.nl__tilburg` | `lupkermakelaardij.nl` | Needs manual review. Realworks markers exist, but local legal/source notes include `needs_manual_review`. |
| `hoogveste.nl__altena` | `hoogveste.nl` | Not rejected, but flagged. Live page has strong Realworks structure and high volume, while compact markers include `pararius` text; verify this is not a dependency before operational use. |
| `viermakelaars.nl__s-hertogenbosch` | `viermakelaars.nl` | Possible only. Live markers were mostly Realworks media/images inside a WordPress shell, not enough to rank above stronger Realworks pages. |

## Selected primary Realworks candidate

Primary candidate: `oldenkotte.com__tilburg`

- Domain: `oldenkotte.com`
- Listing URL: `http://www.oldenkotte.com/aanbod/woningaanbod/koop`
- Classification: `realworks_strong_candidate`
- Score: `14`
- Access/robots: `allow`
- Evidence summary:
  - local target/source coverage classified it as `realworks`;
  - local source capture audit marked it `working_source`;
  - local capture audit found `9` properties, `9` matching-ready, and `9` clean available;
  - live page exposed `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, and `/aanbod/woningaanbod`;
  - source is a Tilburg candidate and therefore more directly relevant than several higher-volume non-Tilburg rows.
- Parser probe:
  - `parser_total=36`
  - `qa_clean=0`
  - `qa_review=36`
  - `qa_rejected=0`
  - `inventory_snapshot_count=0`
- Risks:
  - current V4 Realworks parser overcaptures links and does not yet extract enough fields for QA-clean live inventory;
  - next validation must harden card extraction against this live page before treating it as operational inventory.
- Next validation step:
  - start `Second Parser Family Validation v1 - Realworks` with `oldenkotte.com` as the primary fixture/live target, keeping the capture bounded and preserving the existing robots gate.

## Backup candidates

Backup 1: `olden.nl__heusden`

- Domain: `olden.nl`
- Listing URL: `http://www.olden.nl/aanbod/woningaanbod`
- Classification: `realworks_strong_candidate`
- Score: `17`
- Access/robots: `allow`
- Evidence summary:
  - legacy capture audit marked it `working_source`;
  - live page exposed `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `data-paginatable`, and `/aanbod/woningaanbod`;
  - live page text indicated a large listing surface of 45 houses.
- Parser probe:
  - `parser_total=35`
  - `qa_clean=0`
  - `qa_review=35`
  - `qa_rejected=0`
  - `inventory_snapshot_count=0`
- Risks:
  - not Tilburg-specific;
  - parser probe is review-only due missing address/price/city/status extraction in current V4 parser.

Backup 2: `gewoonmakelaars.nl__s-hertogenbosch`

- Domain: `gewoonmakelaars.nl`
- Listing URL: `http://www.gewoonmakelaars.nl/aanbod/woningaanbod/koop`
- Classification: `realworks_strong_candidate`
- Score: `17`
- Access/robots: `allow`
- Evidence summary:
  - legacy capture audit marked it `working_source`;
  - live page exposed `images.realworks.nl`, `static.realworks.nl`, `realworks.nl`, `objectId`, `/InfoWindow/`, and `/aanbod/woningaanbod`.
- Parser probe: not run in this phase.
- Risks:
  - prior local capture volume was only `1` property, so it is less attractive for first family validation than `oldenkotte.com` or `olden.nl`.

Additional high-volume backup to keep visible: `hoogveste.nl__altena`

- Strong live Realworks structure and page text indicating 159 houses.
- Not selected because compact markers included `pararius` text; verify this is not a dependency before promotion.

## Parser probe results if any

Parser probes used the existing Realworks path only: `ParserFamilyRunner`, `qa_parser_family_result`, and `InventorySnapshot` creation. No new parser was built.

| source_id | domain | parser_total | qa_clean | qa_review | qa_rejected | inventory_snapshot_count | sample canonical URLs compact | probe_error |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `oldenkotte.com__tilburg` | `oldenkotte.com` | 36 | 0 | 36 | 0 | 0 | `/aanbod/woningaanbod/koop`, `/aanbod/woningaanbod/koop/garage` | none |
| `olden.nl__heusden` | `olden.nl` | 35 | 0 | 35 | 0 | 0 | `/aanbod/woningaanbod/open-huis`, `/aanbod/woningaanbod/archief/verkocht` | none |
| `carredewit.nl__s-hertogenbosch` | `carredewit.nl` | 13 | 0 | 13 | 0 | 0 | `/woning-verkopen`, `/woning-kopen` | none |

The parser probes show the current V4 parser path can run without persistence, but it is not yet QA-clean on these live pages. This is useful validation input: the next Realworks phase should focus on card/listing extraction quality, not on access discovery.

## Recommendation

Start the next Realworks validation phase with `oldenkotte.com__tilburg` as the primary target.

Reason:

- confirmed Realworks markers on live listing page;
- robots allowed;
- stable `/aanbod/woningaanbod/koop` listing URL;
- local legacy capture audit already found usable inventory;
- Tilburg relevance;
- enough volume for a focused parser-family validation without investing in a one-off makelaar.

Use `olden.nl` and `gewoonmakelaars.nl` as backups. Keep `hoogveste.nl` as a high-volume manual-review candidate after confirming the `pararius` text is not a dependency.

Do not use KIN, Hendriks, `vandewatergroep.nl`, or `vandenboschmakelaars.com` for this Realworks validation.

## Constraints confirmation

- No new parser built.
- No parser per makelaar.
- No Excel created.
- No matching touched.
- No advisor email touched.
- No n8n touched.
- No dashboard touched.
- No eligibility changed.
- No `data/raw` touched.
- No Funda or Pararius extraction.
- No Playwright, Selenium, browser automation, proxies, stealth, CAPTCHA solving, or bypass behavior.
- No raw HTML or raw JSON persisted.
- No LLM was used to extract listing data from pages.
- Runtime code was not modified.

## Limitations

- The live fetch budget was exceeded because a redundant compact marker recount was run after the initial 45-fetch confirmation pass. The actual total was 63 HTTP fetches and 63 robots checks.
- Marker matching is conservative but still lexical. Generic page text containing words like `funda`, `login`, or `403` was not treated as a blocker unless supported by HTTP status, iframe/dependency, or policy evidence.
- The current V4 Realworks parser probe produced review-only outputs for the three tested live pages. That blocks inventory promotion but does not negate the Realworks platform classification.
- Local generated artifacts under `data/diagnostics`, `data/properties`, and `data/property_discovery` were read as evidence but not modified or committed.
