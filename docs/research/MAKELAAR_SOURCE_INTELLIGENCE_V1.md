# Makelaar Source Intelligence V1

## What we want to know about each makelaar

- official name and domain
- known homepage and aanbod URL
- province, gemeente, and city scope
- whether the source appears koop-relevant, huur-relevant, commercial, or project-oriented
- whether access is allowed, limited, blocked, or permission-dependent
- whether listings are native, iframe-based, or externally dependent
- which technical delivery mode is most likely
- which parser family candidate should handle it

## What an `aanbod_url` is

`aanbod_url` is the best known source-specific listing entry point. It is not automatically proof that the source is operationally allowed, but it is often the strongest practical starting clue for delivery-mode analysis and source-config authoring.

## Types of makelaars

- local makelaar with direct listings
- regional office with multiple cities
- franchise or network site
- wrapper site that embeds another listing provider
- marketing site with no real listing inventory

## Types of sources

- direct makelaar sites
- portal-like public listing sites
- embedded external listing providers
- email alert channels
- blocked or permission-gated sources

## Delivery modes to classify

- `realworks_public`
- `ogonline_xhr`
- `kolibri_public`
- `wordpress_rest`
- `wordpress_html_cards`
- `static_html_cards`
- `json_ld`
- `sitemap_detail`
- `xhr_json`
- `email_alert`
- `iframe_external`
- `funda_iframe_blocked`
- `pararius_external_blocked`
- `captcha_blocked`
- `login_required`
- `unknown_manual_review`

## Target schema

Use the Source Intelligence schema from [docs/02_SOURCE_INTELLIGENCE_MODEL.md](/C:/Projects/domek-wonen/docs/02_SOURCE_INTELLIGENCE_MODEL.md).

## Target reports

- national counts by delivery mode
- counts by allowed vs blocked policy state
- candidate priority list for onboarding
- queue of manual-review sources
- coverage by geography

## Open questions

- which existing repo datasets already provide durable `aanbod_url` quality?
- where do access-policy signals need fresh evidence instead of legacy inference?
- how should mixed koop/huur or commercial/project sources be ranked?
- which families give the fastest safe coverage lift?

## How to use existing repo data

- start from existing discovery source masters and census outputs;
- reuse diagnostics for delivery-mode evidence;
- inspect `properties/` only to understand parser patterns, not to re-adopt its architecture wholesale;
- treat historical docs as reference, not as current truth.

## Family prioritization

Favor families that combine policy safety, high coverage potential, and config reuse. That likely means source-intelligence conversion first, then Realworks and OGonline/XHR stabilization, then config-driven HTML-card and JSON-LD families.

## Current limitation

A complete national source list does not exist yet as a validated source-intelligence dataset. Building that dataset is the job of `Source Intelligence Conversion v1`, not this architecture reset.
