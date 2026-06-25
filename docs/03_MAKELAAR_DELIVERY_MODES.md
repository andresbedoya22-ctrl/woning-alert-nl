# Makelaar Delivery Modes

## Purpose

Delivery modes describe how listings are technically exposed. They allow one parser family to support many makelaars.

## Modes

### `realworks_public`

- Meaning: listings are publicly exposed in a Realworks pattern.
- Evidence: Realworks paths, scripts, markup, or stable card/detail structure.
- Parser family candidate: `realworks_public`.
- Production eligible: yes, if access policy is allowed.
- Risks: markup drift, partial field variation.
- Recommended action: stabilize one reusable family and extend via config.

### `ogonline_xhr`

- Meaning: listings are exposed through OGonline page structure or XHR endpoints.
- Evidence: recognizable OGonline assets, XHR calls, or response formats.
- Parser family candidate: `ogonline_xhr`.
- Production eligible: yes, if allowed and stable.
- Risks: endpoint drift, JS-only assumptions, anti-bot escalation.
- Recommended action: extract cards via shared transport and config.

### `kolibri_public`

- Meaning: a Kolibri-style public listing pattern is present.
- Evidence: public card structure, scripts, API hints, or hosted assets.
- Parser family candidate: `kolibri_public`.
- Production eligible: maybe after research spike.
- Risks: low current evidence, unknown field stability.
- Recommended action: research before implementation.

### `wordpress_rest`

- Meaning: listings are reachable through a WordPress REST surface or custom post endpoint.
- Evidence: `wp-json`, structured listing objects, or predictable REST routes.
- Parser family candidate: `wordpress_rest`.
- Production eligible: yes when allowed and proven stable.
- Risks: plugin-specific schemas.
- Recommended action: support through config-based field mapping.

### `wordpress_html_cards`

- Meaning: WordPress renders public cards in HTML without a clean API.
- Evidence: visible cards, repeated selectors, pagination patterns.
- Parser family candidate: `html_cards`.
- Production eligible: yes if selectors are stable.
- Risks: theme drift and inconsistent card fields.
- Recommended action: prefer source config before new family code.

### `static_html_cards`

- Meaning: plain HTML cards expose minimum listing data.
- Evidence: repeated card markup and detail links.
- Parser family candidate: `html_cards`.
- Production eligible: yes if structure is stable.
- Risks: weak metadata quality, fragile selectors.
- Recommended action: use shared card parser with config.

### `json_ld`

- Meaning: the source exposes useful listing data in JSON-LD.
- Evidence: structured data blocks with address, offer, or listing context.
- Parser family candidate: `json_ld`.
- Production eligible: yes when fields are sufficient.
- Risks: partial coverage or stale structured data.
- Recommended action: treat as high-value low-complexity family.

### `sitemap_detail`

- Meaning: listing URLs are discoverable via sitemap and extractable from detail pages.
- Evidence: relevant sitemap entries and stable detail-page patterns.
- Parser family candidate: `sitemap_detail`.
- Production eligible: maybe, depending on policy and volume.
- Risks: weak card-level state and expensive detail crawling.
- Recommended action: use only where card-based access is not available and policy allows it.

### `xhr_json`

- Meaning: listings are exposed by public XHR or JSON endpoints.
- Evidence: network responses with listing payloads and no policy block.
- Parser family candidate: `xhr_json`.
- Production eligible: yes when explicitly allowed.
- Risks: endpoint drift, hidden throttling.
- Recommended action: treat as reusable family with strict policy checks.

### `email_alert`

- Meaning: listing data arrives via allowed subscription email workflows.
- Evidence: email templates, fields, and source terms permitting that path.
- Parser family candidate: `email_alert`.
- Production eligible: later phase only.
- Risks: account management, formatting drift.
- Recommended action: defer until inventory core is stable.

### `iframe_external`

- Meaning: the site embeds listings from another domain or service.
- Evidence: public iframe element and external source domain.
- Parser family candidate: follows embedded platform, not the wrapper site.
- Production eligible: only if the embedded source itself is allowed.
- Risks: hidden dependency on blocked external source.
- Recommended action: classify the iframe domain first.

### `funda_iframe_blocked`

- Meaning: listings appear through Funda dependency.
- Evidence: iframe or outbound dependency to Funda.
- Parser family candidate: none for operational use.
- Production eligible: no.
- Risks: policy violation and unstable dependency.
- Recommended action: mark blocked or benchmark-only.

### `pararius_external_blocked`

- Meaning: listings depend on Pararius.
- Evidence: iframe, embed, outbound listing dependency, or mirrored content.
- Parser family candidate: none for operational use.
- Production eligible: no without permission.
- Risks: licensing and policy constraints.
- Recommended action: mark permission-required or blocked.

### `captcha_blocked`

- Meaning: anti-bot challenge blocks ordinary access.
- Evidence: CAPTCHA page, challenge script, or equivalent signal.
- Parser family candidate: none.
- Production eligible: no.
- Risks: policy breach if bypass is attempted.
- Recommended action: block and move on.

### `login_required`

- Meaning: listings are available only behind authenticated access.
- Evidence: login wall or authenticated API dependency.
- Parser family candidate: none until permission path exists.
- Production eligible: no.
- Risks: unauthorized access and terms issues.
- Recommended action: mark blocked or permission-required.

### `unknown_manual_review`

- Meaning: the technical pattern is still unclear.
- Evidence: incomplete or conflicting source evidence.
- Parser family candidate: unknown.
- Production eligible: no.
- Risks: wasted parser work and wrong policy assumptions.
- Recommended action: collect more evidence before implementation.
