# OGonline Candidate Reclassification Discovery v1

## Objective

Find a second real makelaar candidate compatible with OGonline/XHR, even if current local evidence classifies it as `realworks`, `unknown`, `custom`, `wordpress`, or another ambiguous state.

This phase is discovery and reclassification only. It is not a full validation run.

## Why reclassification was needed

KIN showed that current local classification is not sufficient on its own.

- In [data/platform_fingerprint/target_area/20260615T192849Z/target_area_platform_fingerprint_inventory.csv](C:/Projects/domek-wonen/data/platform_fingerprint/target_area/20260615T192849Z/target_area_platform_fingerprint_inventory.csv), `kinmakelaars.nl` still appeared as `realworks`.
- In [data/source_debug/kin/20260615T200135Z/kin_debug_report.md](C:/Projects/domek-wonen/data/source_debug/kin/20260615T200135Z/kin_debug_report.md), the same source showed both Realworks-like and OGonline-specific signals, including `website door ogonline`, `ogonline`, and `/aanbod/wonen/te-koop`.

That means this discovery cannot rely only on rows already labeled `ogonline_xhr`.

## Scope and constraints

- Repo-local evidence first.
- Controlled live probing only for sources already present in local evidence.
- No Google, no browser automation, no Playwright, no Selenium, no proxies, no stealth.
- No raw HTML persistence.
- No raw JSON persistence.
- No `data/raw` changes.
- No matching, email, n8n, dashboard, eligibility, or parser-per-makelaar work.

## Local evidence searched

Primary local evidence and code paths reviewed:

- [README.md](C:/Projects/domek-wonen/README.md)
- [docs/12_LEGACY_MAP_AND_CLEANUP_PLAN.md](C:/Projects/domek-wonen/docs/12_LEGACY_MAP_AND_CLEANUP_PLAN.md)
- [scraper/src/domek_wonen/sources/README.md](C:/Projects/domek-wonen/scraper/src/domek_wonen/sources/README.md)
- [scraper/src/domek_wonen/discovery/source_master_builder.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/discovery/source_master_builder.py)
- [scraper/src/domek_wonen/discovery/platform_fingerprint.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/discovery/platform_fingerprint.py)
- [scraper/src/domek_wonen/sources/evidence_enrichment.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/sources/evidence_enrichment.py)
- [scraper/src/domek_wonen/sources/delivery_fingerprint.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/sources/delivery_fingerprint.py)
- [scraper/src/domek_wonen/diagnostics/delivery_mode_fingerprint_audit.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/diagnostics/delivery_mode_fingerprint_audit.py)
- [scraper/src/domek_wonen/diagnostics/delivery_mode_evidence_enrichment.py](C:/Projects/domek-wonen/scraper/src/domek_wonen/diagnostics/delivery_mode_evidence_enrichment.py)
- [data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv](C:/Projects/domek-wonen/data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv)
- [data/platform_fingerprint/target_area/20260615T192849Z/target_area_platform_fingerprint_inventory.csv](C:/Projects/domek-wonen/data/platform_fingerprint/target_area/20260615T192849Z/target_area_platform_fingerprint_inventory.csv)
- [data/diagnostics/delivery_mode_fingerprint/20260617T193323Z/delivery_mode_inventory.csv](C:/Projects/domek-wonen/data/diagnostics/delivery_mode_fingerprint/20260617T193323Z/delivery_mode_inventory.csv)
- [data/diagnostics/delivery_mode_evidence/20260617T195606Z/delivery_mode_evidence_inventory.csv](C:/Projects/domek-wonen/data/diagnostics/delivery_mode_evidence/20260617T195606Z/delivery_mode_evidence_inventory.csv)

Fields repeatedly used during reclassification:

- `source_id`
- `root_domain` / `source_domain`
- `aanbod_url`
- `current_platform_guess`
- `current_delivery_mode`
- `detected_delivery_mode_enriched`
- `parser_family_candidate`
- `source_quality_status`
- `needs_review`
- `review_reason`
- `legal_status`
- `detail_url_pattern`
- `xhr_or_api_candidates`

## Live probe scope

- Domains considered in live probe: `10`
- Follow-up homepage probes: `5`
- Total fetches: `15`
- Total robots checks: `15`
- Initial domains:
  - `architectuurmakelaar.nl`
  - `debontmakelaardij.nl`
  - `hendriks.nl`
  - `kernmakelaars.nl`
  - `lemmens.nl`
  - `hrs.nl`
  - `mtbmakelaardij.nl`
  - `tivoliwoningmakelaars.nl`
  - `vandewatergroep.nl`
  - `vandenboschmakelaars.com`
- Follow-up homepages:
  - `architectuurmakelaar.nl`
  - `kernmakelaars.nl`
  - `lemmens.nl`
  - `tivoliwoningmakelaars.nl`
  - `hendriks.nl`
- Persistence policy:
  - responses stayed in memory only
  - no raw HTML written
  - no raw JSON written
  - only compact markers were retained in notes

## Candidate scoring model

- `+4` explicit `api.ogonline` marker
- `+4` parser probe succeeds with `qa_clean > 0`
- `+3` deterministic API endpoint found
- `+2` listing URL present and robots allowed
- `+2` detail URL pattern present
- `+2` active listings detected
- `+1` Noord-Brabant
- `+1` source already in local master
- `-5` blocked, `permission_required`, or `legal_review`
- `-5` Funda or Pararius dependency
- `-4` robots disallowed
- `-3` no listing URL
- `-3` no technical OGonline evidence
- `-3` synthetic-only evidence

## Top candidates

| source_id | domain | listing_url | current_guess | discovered_markers | robots | parser_probe | score | classification | risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `kernmakelaars.nl__tilburg` | `kernmakelaars.nl` | `https://www.kernmakelaars.nl/aanbod/nu-in-verkoop` | `custom / unknown_manual_review` | listing page reachable, listing cards present, allowed source in source master | allow | no clear API | 5 | `possible_candidate` | no `ogonline` marker, no deterministic API, detail pattern collapsed to listing path |
| `lemmens.nl__tilburg` | `lemmens.nl` | `http://www.lemmens.nl/woningaanbod/koop/tilburg/valentijnstraat/20` | `custom / unknown_manual_review` | listing page reachable, `/api` hint in local evidence, residential card fields visible | allow | no clear API | 5 | `possible_candidate` | `/api` hint was generic only, no `ogonline` marker, listing URL appears detail-like |
| `architectuurmakelaar.nl__tilburg` | `architectuurmakelaar.nl` | `http://www.architectuurmakelaar.nl/aanbod` | `custom / unknown_manual_review` | listing page reachable, cards visible, allowed source in source master | allow | no clear API | 5 | `possible_candidate` | no XHR signal, no OGonline marker, detail pattern looks site-specific |
| `hendriks.nl__tilburg` | `hendriks.nl` | `https://hendriks.nl/woningaanbod` local master, evidence-selected detail URL under same family | `custom / unknown_manual_review` | reachable residential pages, `/api` hint in local evidence | allow | no clear API | 2 | `needs_manual_review` | source master still flags review, selected evidence URL looked like property detail, homepage/listing probe did not show OGonline and did expose `realworks` text on one page |
| `tivoliwoningmakelaars.nl__tilburg` | `tivoliwoningmakelaars.nl` | `https://tivoliwoningmakelaars.nl/woningen` | `realworks` | reachable, but homepage exposed `realworks`, `realworks.nl`, and WordPress markers | allow | no | 0 | `reject` | strong non-OGonline evidence from live page |

## Selected candidate

No `strong_candidate` was found.

Best current handoff candidate: `kernmakelaars.nl__tilburg`

- Why it ranks first:
  - local source master row is `allowed_official_source`
  - listing URL is stable and robots-allowed
  - local evidence shows residential cards and a non-trivial listing surface
  - it is a real source in Noord-Brabant already present in local master
- Why it is not strong yet:
  - no `website door ogonline`
  - no `ogonline.nl`
  - no deterministic API endpoint
  - no `docs / totalDocs / totalPages / hasNextPage` payload hint
  - no parser probe could be run safely

## Rejected candidates

- `naber.nl__tilburg`
  - local evidence already classified it as `iframe_funda_blocked`
  - excluded by policy
- `viapaulmakelaardij.nl__tilburg`
  - local evidence already classified it as `iframe_funda_blocked`
  - excluded by policy
- `huijsmansmakelaardij.nl__tilburg`
  - selected listing page returned `http_404`
  - source master suggests aanbod URL needs fixing first
- `vandenboschmakelaars.com__tilburg`
  - local aanbod URL is a `diensten/verkoopmakelaar` commercial/service page
  - source master already marks it invalid/rejected
- `vandewatergroep.nl__tilburg`
  - local aanbod URL is a nieuwbouw/project page, not a reusable residential listing index
  - live page showed `realworks` plus WordPress markers, not OGonline
- `tivoliwoningmakelaars.nl__tilburg`
  - live homepage showed explicit `realworks` and `realworks.nl`
  - also exposed WordPress markers
- `hrs.nl__tilburg`
  - local aanbod URL was `binnenkort-in-de-verkoop`
  - source master marks it invalid/rejected

## Parser probe results, if any

No parser probe was executed.

Reason:

- no candidate exposed a deterministic JSON endpoint with clear OGonline/XHR evidence
- no candidate exposed payload hints compatible with `build_parser_input_from_api_json`

## Recommendation

1. Do not start `Second OGonline Makelaar Validation v1` yet.
2. Treat `kernmakelaars.nl__tilburg` as the best current `possible_candidate`.
3. If a next phase is approved, it should be a narrower controlled discovery pass focused on:
   - recovering a better listing entry point for `hendriks.nl`
   - checking whether `kernmakelaars.nl` has hidden XHR/API calls behind the current listing page
   - rechecking only the best `possible_candidate` domains, not the whole corpus

## Constraints confirmation

- No matching.
- No email.
- No n8n.
- No dashboard.
- No `data/raw` edits.
- No Funda or Pararius extraction.
- No Playwright or Selenium.
- No proxies or stealth.
- No raw HTML persistence.
- No raw JSON persistence.
- No LLM-generated extraction logic.
- No parser per makelaar.
- No eligibility changes.
