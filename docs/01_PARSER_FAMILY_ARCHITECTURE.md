# Parser Family Architecture

## 1. Core principle

WoningAlert NL must not scale through one parser per makelaar.

It must scale through:

```text
source_registry
  -> access_policy
  -> delivery_mode_fingerprint
  -> parser_family
  -> source_config
  -> normalized_property
```

A makelaar is a business entity. A parser family is a technical delivery mode.

Examples:

- one Realworks parser can support many Realworks-powered makelaars;
- one static card parser can support many simple HTML sites through configs;
- one JSON-LD parser can support many pages exposing structured data;
- one sitemap/detail parser can support sites whose index is weak but detail URLs are visible in sitemaps.

## 2. Delivery modes

Target delivery modes:

| Delivery mode | Meaning | Production behavior |
|---|---|---|
| `realworks_public` | Public Realworks-like site or listing pattern | Use Realworks parser family |
| `ogonline_xhr` | OGonline/XHR-backed listing delivery | Use OGonline/XHR parser family |
| `kolibri_public` | Kolibri/Housenet-style public inventory | Use Kolibri parser family when built |
| `wordpress_rest` | WordPress API exposes useful listing data | Use REST adapter |
| `wordpress_html_cards` | WordPress frontend cards with useful DOM | Use config-driven card parser |
| `json_ld` | Structured JSON-LD carries property facts | Use JSON-LD parser |
| `sitemap_detail` | Sitemap exposes detail pages | Use sitemap/detail parser |
| `static_html_cards` | Static visible cards with selectors | Use config-driven card parser |
| `xhr_json` | Public JSON/XHR endpoint, no bypass | Use XHR parser after review |
| `email_alert` | Email source or advisor alert source | Use email ingestion parser |
| `iframe_external` | Listing loaded from external iframe | Review source and permissions |
| `funda_iframe_blocked` | Funda iframe or dependency | Block; no scraping |
| `pararius_external_blocked` | Pararius dependency without permission | Block unless explicitly approved |
| `captcha_blocked` | CAPTCHA or anti-bot challenge | Block or permission required |
| `login_required` | Requires login | Block or permission required |
| `unknown_manual_review` | Not enough evidence | Manual review |

## 3. Source access policy

A parser can only run if the source is allowed.

Required source access fields:

- `source_domain`
- `source_type`
- `access_status`
- `robots_status`
- `terms_status`
- `permission_status`
- `blocking_status`
- `allowed_paths`
- `rate_limit_per_minute`
- `user_agent_policy`
- `notes`

Allowed `access_status` values:

- `allowed`
- `limited`
- `permission_required`
- `legal_review`
- `blocked`
- `disabled`

If `access_status` is not `allowed` or `limited`, production extraction must not run.

## 4. Source config pattern

A domain config should describe how to extract data without custom code.

Example:

```json
{
  "source_domain": "example-makelaar.nl",
  "parser_family": "static_html_cards",
  "listing_url": "https://example-makelaar.nl/aanbod",
  "card_selector": "article.property-card",
  "detail_url_selector": "a[href]",
  "address_selector": ".address",
  "city_selector": ".city",
  "price_selector": ".price",
  "status_selector": ".status",
  "living_area_selector": ".living-area",
  "rooms_selector": ".rooms",
  "image_selector": "img",
  "pagination_strategy": "none",
  "detail_enrichment_required": true,
  "known_noise_selectors": ["nav", "footer", ".cookie-banner"],
  "status_mapping": {
    "beschikbaar": "beschikbaar",
    "te koop": "beschikbaar",
    "onder bod": "onder_bod",
    "verkocht": "verkocht",
    "verkocht onder voorbehoud": "verkocht_ov"
  },
  "price_patterns": ["€"],
  "qa_expectations": {
    "min_card_count": 1,
    "requires_address": true,
    "requires_price": true
  }
}
```

## 5. Normalized output schema

Every parser family must return the same normalized candidate shape.

Minimum fields:

- `source_domain`
- `source_url`
- `canonical_url`
- `address_raw`
- `street`
- `house_number`
- `postcode`
- `city`
- `asking_price_eur`
- `transaction_type`
- `status`
- `living_area_m2`
- `plot_area_m2`
- `rooms_count`
- `bedrooms_count`
- `energy_label`
- `property_type`
- `first_seen_at`
- `last_seen_at`
- `content_hash`
- `description_hash`
- `image_count`
- `confidence_score`
- `evidence`
- `needs_review`
- `review_reason`

## 6. QA gates

A property cannot become clean inventory unless it passes QA.

Core gates:

- URL is canonical and same permitted source domain or authorized external source;
- transaction type is `koop` for purchase matching;
- status is `beschikbaar` for matching;
- price is a plausible asking price;
- address quality is valid or recoverable;
- city/postcode can be normalized;
- duplicate key can be computed;
- source access state permits use.

Recommended future gates:

- BAG/PDOK address validation;
- EP-Online energy label enrichment;
- duplicate detection across portals and makelaar websites;
- stale listing detection;
- sudden volume drop detection.

## 7. Parser family implementation order

Recommended order:

1. `static_html_cards` config runner.
2. `wordpress_html_cards` config runner.
3. `json_ld` parser.
4. `sitemap_detail` parser.
5. `realworks_public` stabilization.
6. `ogonline_xhr` stabilization.
7. `wordpress_rest` parser.
8. `xhr_json` parser.
9. `email_alert` parser.
10. `iframe_blocked_handler`.

Do not build a new parser family without evidence that at least two useful sources need it.

## 8. Anti-patterns

Avoid:

- `makelaar_x_parser.py` for every domain;
- stealth browser logic;
- CSS selectors embedded directly in Python for one domain;
- matching against candidates before QA;
- assuming a missing field means the property is invalid;
- treating `te huur` as purchase inventory;
- treating a detail page as a source-level listing index;
- copying images/descriptions unnecessarily.

## 9. What Codex should do well

Codex tasks should be small and testable:

- create a parser family interface;
- implement one parser family against fixtures;
- add config validation;
- add source config fixture;
- add QA gate;
- add tests for a known failed domain;
- refactor duplicated extraction logic.

Codex should not be asked to build the entire national inventory engine in one task.
