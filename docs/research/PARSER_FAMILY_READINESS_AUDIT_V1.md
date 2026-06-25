# Parser Family Readiness Audit v1

## Input report

- Source master usado: `data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv`
- Evidence artifacts usados:
  - `data/discovery/platform_fingerprint/platform_fingerprint_results.csv`
  - `data/diagnostics/delivery_mode_evidence/20260617T195606Z/delivery_mode_evidence_inventory.csv`
  - `data/diagnostics/source_coverage/20260616T192404Z/tilburg_source_coverage_inventory.csv`
- Reporte leido: `tmp/enriched-legacy-source-report.json`
- Fecha local del archivo: `2026-06-23 21:03:44 +02:00`
- `total_sources`: 488
- `unique_domains`: 323
- `production_parser_ready`: 107
- `records_enriched_count`: 438
- `evidence_domains_count`: 325
- `manual_review_queue`: 159
- `blocked_sources`: 6
- `permission_required_sources`: 0

Parser family counts from the enriched delivery fingerprint:

| parser_family_candidate | candidate_count | production_ready_count |
| --- | ---: | ---: |
| realworks_public | 220 | 92 |
| wordpress_html_cards | 87 | 11 |
| static_html_cards | 9 | 4 |
| json_ld | 6 | 0 |
| kolibri_public | 1 | 0 |
| iframe_blocked_handler | 6 | 0 |
| ogonline_xhr | 0 | 0 |
| sitemap_detail | 0 | 0 |
| unknown / empty | 159 | 0 |

Baseline delivery fingerprint, before evidence enrichment, reported `production_parser_ready_count = 0` and `unknown_manual_review = 484`. The readiness decision below is based on the enriched `delivery_fingerprint` section, not the baseline.

## Candidate family summary

| family | candidate_count | production_ready_count | existing_code | tests | complexity | risk | recommended_action |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| realworks_public | 220 | 92 | `scraper/src/domek_wonen/properties/platform_parsers/realworks_parser.py`, `DetailPageExtractor`, `PropertyUrlClassifier` | `tests/test_realworks_parser.py` has 14 focused tests; additional property discovery tests cover Realworks fallback behavior | medium | medium | build_now |
| wordpress_html_cards | 87 | 11 | `source_parser_config.py`, `PropertyCardExtractor`, `harvest/card_parser.py`, config examples | card/parser/config tests exist, but no V4 runner tests | medium | medium | create_config_runner |
| static_html_cards | 9 | 4 | same generic card stack as WordPress/static | card/parser/config tests exist, but no V4 runner tests | medium | medium | create_config_runner |
| json_ld | 6 | 0 | JSON-LD helpers exist inside `DetailPageExtractor`, but no parser family | detail-page tests cover limited extraction | medium | medium | research_more |
| kolibri_public | 1 | 0 | no reusable parser found | delivery fingerprint classification only | high | high | research_more |
| ogonline_xhr | 0 | 0 | OGonline API helpers exist inside `RealworksParser`, mostly for KIN benchmark cases | Realworks tests cover OGonline API pagination and card fallback | medium | medium | research_more |
| sitemap_detail | 0 | 0 | `harvest/mini_harvest.py` has sitemap sampling logic | `tests/test_mini_harvest.py` covers sitemap sample behavior | high | medium | research_more |

## Realworks assessment

Coverage is the strongest in the enriched report: `realworks_public = 220` candidates and `92` production-ready sources after Access Policy plus Delivery Fingerprint gates. This is the largest ready cohort and the only family with both high volume and a substantial existing parser implementation.

Existing code is legacy but useful. `scraper/src/domek_wonen/properties/platform_parsers/realworks_parser.py` can:

- derive listing-page candidates from a `PropertySource`;
- extract detail URLs from listing HTML;
- filter property detail URLs through `PropertyUrlClassifier`;
- extract seed fields from Realworks/OGonline-style listing cards;
- use `DetailPageExtractor` for detail-page enrichment;
- parse OGonline listing API payloads for known Realworks/OGonline hybrid cases;
- return legacy `PropertyCandidate` records.

The main runtime gap is not parsing logic. The gap is architecture fit. The parser currently lives under legacy `properties/`, creates legacy `PropertyCandidate` objects, and its `parse()` method owns fetching through `WebsiteFetcher`. A V4 parser family should accept permitted captured inputs from a runner layer and emit the future normalized parser output without bypassing the binding network gate.

Existing tests are stronger than the other families. `tests/test_realworks_parser.py` has 14 focused tests covering listing fixtures, derived listing URLs, URL filtering, detail enrichment, slug fallback, KIN/OGonline snapshots, OGonline API pagination, status/pagination filtering, and noisy detail recovery. Missing fixtures are not basic Realworks examples; they are V4 contract fixtures:

- parser-family input fixture shape independent from `WebsiteFetcher`;
- normalized parser output fixture, separate from legacy `PropertyCandidate`;
- blocked/permission-required fixture showing Realworks is skipped before parsing;
- stale-source and failed-capture behavior belongs to later inventory, not this parser PR.

Wrapping difficulty is medium. The likely safe path is to split or wrap the pure parsing parts first, keep all tests fixture-based, and leave live fetch orchestration to a later runner. That can be done without scraping and without modifying property-discovery runtime.

Recommendation: `build_now` as **Realworks Parser Family Stabilization v1**, with a narrow offline scope.

## WordPress/static cards assessment

Coverage is meaningful but much smaller at the production-ready gate: `wordpress_html_cards = 87` candidates with `11` production-ready, and `static_html_cards = 9` candidates with `4` production-ready. Together they provide `15` production-ready sources.

Existing code is a collection of building blocks rather than a parser family:

- `scraper/src/domek_wonen/properties/source_parser_config.py` validates configs for `html_static_cards` and `wordpress_cards`.
- `data/config/source_parser_configs/schema_v1.json` plus example configs define selector-style config shape.
- `PropertyCardExtractor` extracts legacy `PropertyCandidate` rows from card anchors and visible card text.
- `harvest/card_parser.py` extracts compact `Listing` values from generic cards using `selectolax`.
- `harvest/mini_harvest.py` can sample listing HTML, sitemap, and WordPress REST paths, but it is a harvest diagnostic path, not a V4 parser runner.

Existing tests cover pieces: 3 tests for `PropertyCardExtractor`, 7 tests for `harvest/card_parser.py`, 12 tests for `mini_harvest.py`, and config validation in delivery-mode audit tests. The missing part is the actual V4 `Parser Config Runner v1`: there is no reviewed runner that takes source intelligence plus access-policy-approved input, resolves a parser config, applies a family, and emits the future normalized output contract.

Implementation complexity is medium and risk is medium because selector config without a runner can drift into one-off source behavior. This family should follow Realworks unless the next PR is explicitly about config runner infrastructure.

Recommendation: `create_config_runner`, not first parser family.

## JSON-LD / sitemap assessment

`json_ld` has `6` candidates and `0` production-ready sources in the enriched report. `DetailPageExtractor` includes `_iter_json_ld_records`, but current tests only prove limited extraction behavior inside the legacy detail enrichment path. There is no standalone JSON-LD parser family, no source config schema for JSON paths, and no normalized output contract.

`sitemap_detail` has `0` candidates and `0` production-ready sources in this enriched report. The local code has sitemap sampling in `harvest/mini_harvest.py`, with tests for fixture-driven sitemap behavior. That code is useful evidence for later design, but the family still needs clear listing URL filtering, detail fetch boundaries, and normalized output rules.

Recommendation: `research_more` for both. They should not block the first parser-family PR.

## Other family notes

`kolibri_public` has only `1` candidate and `0` production-ready sources. No reusable Kolibri parser code was found in the inspected modules. Recommended action: `research_more`.

`ogonline_xhr` has `0` candidates in the enriched report, but OGonline parsing code exists inside the legacy Realworks parser because KIN/OGonline fixtures and API pagination are covered there. This should be treated as a later extraction or split decision, not the first family.

`iframe_blocked_handler` has `6` candidates and `0` production-ready sources. It is a blocked/permission-control path, not a parser-family implementation target.

## Decision

Recommended next PR:
`Realworks Parser Family Stabilization v1`

Reason:

- It has the largest enriched candidate pool: `220` candidates.
- It has the largest production-ready pool: `92` sources.
- Existing legacy code already parses listing pages, detail URLs, detail pages, slug fallback, and OGonline-style payloads.
- Existing test coverage is materially stronger than the other families.
- The first implementation can be fixture-only and offline by wrapping pure parser behavior, without live scraping, Playwright, robots probing, or property-discovery runtime changes.

Out of scope:

- no live HTTP requests;
- no Playwright;
- no scraping Funda or Pararius;
- no dashboard, matching, n8n, or advisor email work;
- no modification of `data/raw`;
- no operational source run;
- no broad parser config runner for all card families;
- no refactor of property-discovery runtime unless explicitly requested.

## Next Codex prompt

Implement `Realworks Parser Family Stabilization v1` as an offline, fixture-tested V4 parser-family wrapper. Use the existing legacy Realworks parsing code only as reusable parsing logic, keep network fetching out of the parser family, define the parser input/output contract needed for normalized listings, add focused tests with local fixtures, and do not run live requests, Playwright, matching, dashboard, n8n, or property-discovery runtime changes.
