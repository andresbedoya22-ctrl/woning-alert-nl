# Makelaar Delivery Research Loop

This document captures the research loop that should happen before building or expanding parser families.

## 1. Purpose

The goal is to understand how Dutch makelaar websites deliver housing inventory (`aanbod`) so WoningAlert NL can scale through technical patterns instead of one parser per domain.

A makelaar category such as NVM, VBO, VastgoedPRO, franchise, independent office, or local specialist is not enough to decide parsing strategy.

The relevant question is:

> How is the aanbod technically delivered?

## 2. Known market/platform signals

Research and existing project evidence show the Dutch makelaar web ecosystem is mixed.

Relevant platform or delivery families include:

- Realworks-powered sites;
- OGonline/XHR style sites;
- Kolibri-powered CRM/websites;
- WordPress custom sites;
- static HTML listing card sites;
- JSON-LD structured data;
- sitemap-exposed detail pages;
- custom XHR/JSON APIs;
- iframe embeds from external portals;
- Funda-dependent iframes or links;
- Pararius/Huislijn/Huispedia-style portal layers;
- email alerts/newsletters.

External reference points:

- Kolibri publicly positions itself as software for makelaars and offers CRM, websites, AppXchange, and developer documentation. This supports treating Kolibri as a likely platform family, not as a single website pattern.
- The OpenAI Agents SDK documentation distinguishes simple tool calls from agent workflows where the application owns orchestration, tool execution, approvals, and state. That reinforces our rule: AI should assist research and QA, not become the scraper.
- n8n provides workflow orchestration, AI Agent nodes, schedule triggers, HTTP request nodes, code nodes, and queue-mode scaling. This supports using n8n as orchestrator, not as the extraction engine.
- RFC 9309 defines robots.txt behavior and user-agent matching. WoningAlert must implement an explicit access policy before source extraction.

## 3. Delivery mode taxonomy

Every source should be assigned one of these delivery modes:

| Mode | Evidence | Parser family | Production action |
|---|---|---|---|
| `realworks_public` | Realworks URL patterns, scripts, listing/detail paths | `realworks_public` | Use allowed parser if access policy permits |
| `ogonline_xhr` | OGonline API/listing paths, XHR endpoints, `/aanbod/wonen/...` patterns | `ogonline_xhr` | Use OGonline parser if allowed |
| `kolibri_public` | Kolibri website footprint, developer/API hints, structured CRM website output | `kolibri_public` | Build after sample evidence |
| `wordpress_rest` | `wp-json`, post types, listing custom post types | `wordpress_rest` | Prefer REST when clean and allowed |
| `wordpress_html_cards` | WordPress assets plus visible listing cards | `wordpress_html_cards` | Use config-driven parser |
| `static_html_cards` | Visible cards with price/address/detail links | `static_html_cards` | Use config-driven parser |
| `json_ld` | `application/ld+json` with address/offers/item list | `json_ld` | Use structured extraction |
| `sitemap_detail` | Sitemap exposes property detail URLs | `sitemap_detail` | Use detail parser with strict QA |
| `xhr_json` | Public JSON endpoint without bypass | `xhr_json` | Manual review before adapter |
| `email_alert` | Email/newsletter source with listing data | `email_alert` | Ingest with explicit mailbox/workflow |
| `iframe_external` | External iframe not owned by source | `iframe_blocked_handler` or manual review | Do not treat as automatic source |
| `funda_iframe_blocked` | Funda iframe/dependency | `iframe_blocked_handler` | Block automated scraping |
| `pararius_external_blocked` | Pararius dependency without approval | `iframe_blocked_handler` | Block unless approved |
| `captcha_blocked` | CAPTCHA challenge | none | Mark blocked or permission required |
| `login_required` | Login wall | none | Mark permission required |
| `unknown_manual_review` | Not enough evidence | none | Manual research queue |

## 4. Research loop

For each source domain, do not start by coding.

Use this loop:

```text
1. Identify source domain and listing URL candidates.
2. Run access policy pre-check.
3. Probe minimal pages only.
4. Classify delivery mode.
5. Collect evidence.
6. Choose parser family candidate.
7. Decide if source config is enough or parser family work is needed.
8. Create fixture from minimal synthetic or approved HTML sample.
9. Write/adjust tests.
10. Only then implement parser/config changes.
```

## 5. Minimal probe set

Allowed research probes should be conservative:

```text
/
/robots.txt
/sitemap.xml
/aanbod
/woningaanbod
/huizen-te-koop
/te-koop
/koopwoningen
/wonen
```

Optional only after source appears allowed:

```text
/wp-json
/wp-json/wp/v2/types
/wp-json/wp/v2/search
sitemap sub-files
listing page pagination links
```

Do not perform open crawling during research.

## 6. Evidence fields

Every fingerprint result should record:

- `source_domain`
- `homepage_url`
- `listing_url_candidate`
- `robots_status`
- `http_status_homepage`
- `http_status_listing`
- `blocking_signals`
- `technology_signals`
- `delivery_mode`
- `confidence`
- `parser_family_candidate`
- `config_required`
- `evidence`
- `recommended_action`

## 7. Recommended actions

Allowed actions:

- `use_existing_parser_family`
- `create_source_config`
- `build_parser_family`
- `improve_fingerprint`
- `manual_review_needed`
- `permission_required`
- `legal_review`
- `blocked_no_bypass`
- `ignore_not_residential`
- `ignore_commercial_only`

## 8. When to build a new parser family

Build a new parser family only when:

- at least two useful sources need the same technical pattern; or
- one high-value source has many listings and cannot be handled by existing families; or
- the pattern is foundational for a major Dutch platform family.

Do not build a parser family based on one weak or low-value source.

## 9. Common research mistakes

Avoid:

- confusing makelaar membership with technical delivery mode;
- treating every listing detail page as a listing index;
- accepting commercial-only pages as residential aanbod;
- using `te huur` as koop inventory;
- promoting a source without access policy;
- building parser code before collecting evidence;
- storing raw HTML or screenshots in committed files;
- allowing one failing source to fail the full run.

## 10. Loop exit criteria

A source is ready for implementation when it has:

- access state: `allowed` or `limited`;
- delivery mode with evidence;
- parser family candidate;
- expected fields;
- QA expectations;
- fixture plan;
- test plan;
- known limitations.

If any of these are missing, the source remains in research/manual review.
