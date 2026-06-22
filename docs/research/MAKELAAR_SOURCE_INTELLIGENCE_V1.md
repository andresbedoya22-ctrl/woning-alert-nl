# Makelaar Source Intelligence v1

This document is the first structured research pass for classifying Dutch makelaar sources by aanbod delivery mode.

It is not yet a complete national source registry. It is the intelligence layer that defines what must be collected, how it must be grouped, and what the current confirmed baseline already tells us.

## 1. Executive conclusion

WoningAlert NL should not start by coding more parsers.

It should first create a source-intelligence dataset that maps:

```text
makelaar / organization / portal
  -> domain
  -> aanbod URL
  -> access state
  -> delivery mode
  -> parser family candidate
  -> quality status
  -> recommended action
```

The current repo already has a meaningful legacy baseline, but it is not yet transformed into the new parser-family intelligence model.

## 2. Confirmed baseline from existing repo

Existing documented baseline:

| Metric | Count | Meaning |
|---|---:|---|
| Seed sources | 413 | Existing NVM/harvester baseline for earlier Noord-Brabant-oriented discovery |
| Valid aanbod count | 303 | Sources with a valid aanbod URL according to older strategy |
| Initial validated base | 295 | Trusted-ish initial base after validation |
| AanbodAuditor additions | 8 rows / 7 unique URLs | Additional valid URLs found by auditor |
| Suspect queue | 35 | Needs review |
| Missing queue | 75 | No reliable aanbod path yet |
| Overpass additions | 50 domains | Additional domains from OSM/Overpass, should be cached |

Interpretation:

- We already have enough historical data to start a source-intelligence conversion.
- The old data is not enough for production-scale parser-family routing because it does not fully answer delivery mode, access policy, parser family, config path, and QA expectations.
- The first real source intelligence job should consume the existing source master / discovery outputs and reclassify them into the new model.

## 3. Confirmed external market signals

### NVM

NVM describes itself as the largest association of real-estate professionals in the Netherlands. This confirms NVM remains an important source universe, but membership category is not enough to decide parser strategy.

Source reference:

- `https://www.nvm.nl/`

### Realworks

Realworks positions itself as CRM software for makelaars and states that it is used by 80% of Dutch makelaars.

Implication:

- `realworks_public` must be a top-priority parser family.
- Realworks should be treated as a platform/delivery family, not a one-off parser.
- The source registry should track Realworks-like evidence signals separately from general makelaar membership.

Source reference:

- `https://www.realworks.nl/`

### Vastgoed Nederland

Vastgoed Nederland presents itself as a branchevereniging for makelaars, taxateurs, huurmakelaars, and bouwkundige keurders.

Observed public signals:

- `14925 objecten` on its aanbod portal;
- `2236 vastgoedprofessionals` / `2236+ leden`;
- an aanbod portal under `aanbod.vastgoednederland.nl`;
- a visible Kolibri software subdomain reference: `vastgoedned.kolibri.software`.

Implication:

- Vastgoed Nederland is not just a membership source; it is also a national aanbod/portal layer.
- Its aanbod portal returned 403 in the current browser fetch attempt, so it must be treated as `permission_required` or `legal_review` until access terms are clarified.
- Kolibri should be treated as a likely platform family to research.

Source reference:

- `https://vastgoednederland.nl/`

### OGonline

OGonline publicly positions itself as a specialist in websites and online marketing for makelaars and project developers.

Observed client/showcase signals include, among others:

- Qualis;
- The House of Expats;
- Unique Real Estate;
- Jelle Ooteman;
- Find a House;
- 't Huys Makelaardij;
- Verra Makelaars;
- 27 huis makelaars;
- Van Daal Makelaardij;
- Cato Makelaars;
- 070 Vastgoed;
- Carla van den Brink;
- HVM Vastgoed;
- Kolf Makelaardij;
- Maison Management;
- Roos Makelaars;
- OVDM makelaars;
- Keij & Stefels;
- Wolf Rentals;
- Ditters Makelaars;
- Huis van Delft;
- Von Poll Real Estate;
- R365 / Christie's International Real Estate;
- Villa van Oranje;
- ServiceImmo;
- Pastorale Delft;
- Lankhuijzen Makelaars;
- Dorenbos / Rasch Makelaars;
- Deerenberg & van Leeuwen Makelaars;
- Residence Makelaars;
- Expat & Real Estate;
- Perfect Rent;
- CSV Makelaars;
- Aerdenhout & Omstreken;
- Prominent Vastgoed;
- Lightcity Housing;
- Stad & Zeeland;
- Jan Weide Makelaars.

Implication:

- `ogonline_xhr` and `ogonline_site` evidence must be part of the fingerprint engine.
- OGonline sources may include purchase, rental, expat, commercial, and mixed-use sources, so transaction-type separation is critical.

Source reference:

- `https://www.ogonline.nl/`

### Huislijn

Huislijn exposes broad koop/huur city pages and “nieuwste aanbod” navigation. It is a useful portal/benchmark/fallback candidate, but not automatically production-allowed.

Implication:

- Treat Huislijn as `portal_fallback_candidate` / `permission_required` until robots/TOS/licensing is reviewed.
- It may be useful for benchmark, source discovery, or permissioned feed strategy.

Source reference:

- `https://www.huislijn.nl/`

## 4. Source universe to classify

The source universe must be split into layers.

### Layer A — Official makelaar websites

Primary target for parser-family routing.

Examples of source types:

- independent local makelaar;
- NVM office;
- Vastgoed Nederland/VBO-style member office;
- franchise office;
- luxury broker;
- expat broker;
- rental broker;
- mixed koop/huur office;
- commercial-only office;
- nieuwbouw/project developer.

Classification requirement:

Membership type is metadata only. Delivery mode decides parsing.

### Layer B — Platform / software families

High-priority technical families:

| Family | Why it matters | Parser priority |
|---|---|---:|
| Realworks | Very high claimed market penetration | 1 |
| OGonline | Many visible makelaar website clients | 2 |
| Kolibri | Visible link through Vastgoed Nederland ecosystem | 3 |
| WordPress custom | Very common for smaller offices | 4 |
| Static HTML cards | Common for custom/local websites | 5 |
| JSON-LD | Cross-cutting structured-data fallback | 6 |
| Sitemap/detail | Useful when index pages are weak | 7 |
| Custom XHR JSON | Valuable but needs manual endpoint review | 8 |
| Email alerts | Very useful for new listings and legally safer when opt-in | 9 |

### Layer C — National/aggregator/portal sources

These are not free by default.

| Source | Proposed default | Notes |
|---|---|---|
| Funda | `benchmark_only_blocked_for_scraping` | Do not scrape; no evasion |
| Pararius | `permission_required` | Only use if explicitly approved/licensed |
| Huislijn | `permission_required` / benchmark candidate | Useful but needs legal/robots review |
| Huispedia | `permission_required` / benchmark candidate | Useful but not free by default |
| Vastgoed Nederland aanbod | `permission_required` / `legal_review` | 403 observed in fetch; possible Kolibri ecosystem |
| Email alerts | `allowed_if_opt_in` | Strong future layer |

## 5. Delivery mode taxonomy for real classification

Every source must be classified into one delivery mode.

| Delivery mode | Description | Evidence to collect | Parser family candidate |
|---|---|---|---|
| `realworks_public` | Public Realworks-like listing/detail paths | Realworks scripts, URL patterns, detail path shape, existing parser success | `realworks_public` |
| `ogonline_xhr` | OGonline website/XHR/API pattern | OGonline assets, known client footprint, XHR endpoints, aanbod/wonen paths | `ogonline_xhr` |
| `kolibri_public` | Kolibri-powered site/portal | Kolibri domain/subdomain/scripts/API hints | `kolibri_public` |
| `wordpress_rest` | WordPress REST exposes usable listing types | `/wp-json`, custom post types, property endpoints | `wordpress_rest` |
| `wordpress_html_cards` | WordPress frontend cards, no useful REST | WordPress assets + visible property cards | `wordpress_html_cards` |
| `static_html_cards` | Non-WordPress visible HTML cards | cards contain URL/address/price/status | `static_html_cards` |
| `json_ld` | Structured data embedded in pages | `application/ld+json`, `Offer`, `Residence`, `Place`, `PostalAddress` | `json_ld` |
| `sitemap_detail` | Sitemap exposes property detail pages | sitemap URLs match property patterns | `sitemap_detail` |
| `xhr_json` | Public JSON endpoint without evasion | network/API endpoint visible, no auth/block | `xhr_json` |
| `email_alert` | Listings arrive via email/newsletter | opt-in mailbox, structured links | `email_alert` |
| `iframe_external` | External iframe holds listings | iframe domain, source not controlled | `iframe_blocked_handler` or manual |
| `funda_iframe_blocked` | Funda dependency | Funda iframe/link dependency | blocked |
| `pararius_external_blocked` | Pararius dependency | Pararius external dependency | permission required |
| `captcha_blocked` | Challenge present | CAPTCHA/reCAPTCHA | blocked/no bypass |
| `login_required` | Auth required | login wall | permission required |
| `unknown_manual_review` | Insufficient evidence | weak/ambiguous signals | manual review |

## 6. Required source-intelligence schema

Future source intelligence CSV/DB table should contain:

```csv
source_id,source_domain,source_name,organization_type,membership_hint,province,gemeente,city_scope,homepage_url,aanbod_url,aanbod_url_status,access_status,robots_status,terms_status,blocking_status,has_login,has_captcha,has_403,has_sitemap,has_wp_json,has_json_ld,has_visible_cards,has_iframe,iframe_domain,is_funda_dependent,is_pararius_dependent,technology_signals,delivery_mode,delivery_mode_confidence,parser_family_candidate,config_required,config_path,estimated_listing_count,koop_signal,huur_signal,commercial_signal,project_signal,quality_score,recommended_action,priority_score,evidence,last_reviewed_at,notes
```

## 7. Required reports

### Report A — National source coverage

Counts:

- total sources;
- unique domains;
- valid aanbod URLs;
- missing aanbod URLs;
- suspect aanbod URLs;
- source status counts;
- sources by province/gemeente;
- sources by organization type;
- sources by delivery mode;
- sources by parser family candidate.

### Report B — Delivery mode coverage

Counts by:

- Realworks;
- OGonline;
- Kolibri;
- WordPress REST;
- WordPress HTML cards;
- static HTML cards;
- JSON-LD;
- sitemap/detail;
- XHR JSON;
- iframe blocked;
- Funda/Pararius dependency;
- CAPTCHA/login blocked;
- unknown manual review.

### Report C — Aanbod page quality

For each aanbod URL:

- HTTP status;
- final URL;
- redirects;
- card count estimate;
- detail link count;
- price signal count;
- status signal count;
- koop/huur/commercial signal;
- candidate parser family;
- quality score;
- recommended action.

### Report D — Parser build priority

Sort by:

```text
(number_of_sources_supported * estimated_listing_value * active_client_area_relevance)
- legal_uncertainty_penalty
- blocker_penalty
- implementation_complexity
```

## 8. Initial parser-family priority decision

Based on confirmed evidence, the implementation order should be:

1. `realworks_public` stabilization and platform evidence enrichment.
2. `ogonline_xhr` fingerprint and parser stabilization.
3. `source_access_policy_v1` so blocked/permission sources cannot run.
4. `delivery_mode_fingerprint_v2` over the existing 413-source baseline.
5. `static_html_cards` config runner.
6. `wordpress_html_cards` config runner.
7. `json_ld` parser.
8. `sitemap_detail` parser.
9. `kolibri_public` research spike.
10. `email_alert` ingestion.

This order may change after the first source-intelligence report gives real counts by delivery mode.

## 9. Why this research changes the roadmap

The previous next step was `Access Policy v1` after `Inventory Core v1`.

After this research pass, the better immediate next step is:

```text
Source Intelligence Conversion v1
```

Goal:

- load existing source discovery outputs;
- convert them into source-intelligence rows;
- summarize counts by aanbod status and delivery mode;
- identify top parser-family opportunities;
- produce a prioritized manual review queue.

Only after that should Codex start expanding parser families.

## 10. Codex task for next implementation

```text
Task: Source Intelligence Conversion v1

Context:
- Read AGENTS.md.
- Read docs/research/MAKELAAR_SOURCE_INTELLIGENCE_V1.md.
- Read docs/03_MAKELAAR_DELIVERY_RESEARCH_LOOP.md.
- Inspect existing discovery/source files before coding.

Goal:
Create a deterministic source intelligence layer that loads existing source records and produces a normalized report with delivery-mode placeholders and actionable counts.

Constraints:
- Windows PowerShell.
- No live scraping.
- No Funda scraping.
- No stealth, CAPTCHA, proxy, or anti-bot bypass.
- Do not commit generated run outputs.
- Use fixtures for tests.

Expected files:
- scraper/src/domek_wonen/sources/__init__.py
- scraper/src/domek_wonen/sources/source_intelligence_models.py
- scraper/src/domek_wonen/sources/source_intelligence_loader.py
- scraper/src/domek_wonen/sources/source_intelligence_report.py
- scripts/run_source_intelligence_report.py
- tests/fixtures/sources/source_intelligence_seed.csv
- tests/test_source_intelligence_report.py

Acceptance criteria:
- loads a CSV seed with source/domain/aanbod fields;
- produces counts by source status;
- produces counts by detected platform/delivery mode;
- marks missing/suspect/blocked separately;
- recommends parser family placeholders;
- writes no generated outputs in tests;
- py -3.12 -m pytest passes.
```

## 11. Key unresolved questions

These require implementation or manual research:

1. How many of the existing 413 sources are still reachable?
2. How many of the 303 valid aanbod URLs are truly residential koop pages?
3. How many are Realworks vs OGonline vs WordPress vs static vs iframe?
4. Which valid aanbod URLs are actually detail pages, not listing indexes?
5. How many sources are rental-only or commercial-only?
6. Which sources are Funda/Pararius dependent?
7. Which sources have enough common structure for config-only onboarding?
8. Which top 20 sources should be manually reviewed first?
9. Which family gives the highest coverage per engineering hour?
10. Which sources require explicit permission/API/license?

## 12. Current answer to Andres's core question

No, we do not yet have a complete national classified makelaar list.

Yes, we do have a meaningful starting baseline and enough market evidence to build the source intelligence layer.

The immediate objective is not to write more parsers. The immediate objective is to convert the existing source universe into a measurable, grouped, prioritized source-intelligence dataset.
