# Source And Property Discovery Strategy

## Current Baseline

- Seed NVM/harvester currently produces 413 sources.
- Current valid aanbod count: 303.
- Initial validated base: 295.
- AanbodAuditor added 8 valid rows and 7 unique URLs.
- Current suspect queue: 35.
- Current missing queue: 75.
- Overpass previously added 50 new domains, but it should run with cache for stability and repeatability.

## 1. Base Principle

Domek Wonen does not optimize for "100% automatic" discovery.

The operating target is:

- high coverage;
- zero false positives in production;
- evidence per source;
- a small, prioritized manual queue;
- a monthly refresh cadence.

This means the system may intentionally leave some sources or properties in `suspect`, `missing`, or manual review states instead of promoting weak evidence into production.

## 2. Source Layers

### Layer 1: Makelaar Official Website

This is the primary and preferred source layer.

Components:

- seed NVM;
- Overpass/OSM;
- AanbodAuditor with Playwright;
- WebsiteResolver for `missing_website`.

Rules:

- prefer official makelaar domains over aggregators;
- require source-level evidence before marking `aanbod_url` as valid;
- keep a reproducible audit trail for why a URL was accepted, rejected, or left suspect.

### Layer 2: Aggregator Fallback

Fallback sources may include:

- Huispedia;
- Huislijn;
- other aggregators.

Rules:

- only use an aggregator if robots.txt, TOS, license terms, or API terms permit the intended usage;
- do not copy photos or long textual descriptions;
- do not evade protections;
- do not scrape Funda.

Aggregator fallback exists to improve coverage when an official website is missing, broken, incomplete, or legally unusable for structured discovery, but it is not the default path.

### Layer 3: Manual/Admin Input

Manual input remains part of the official strategy.

Examples:

- sources added manually by advisors;
- prioritized domains;
- review of `suspect` and `missing`.

Manual/admin input is the safety valve that prevents weak automation from polluting production data.

## 3. Source States

Official source states:

- `valid`
- `suspect`
- `missing`
- `rejected`
- `missing_website`
- `needs_manual_review`
- `aggregator_fallback`
- `disabled_legal_review`

Interpretation:

- `valid`: source and aanbod path are sufficiently verified for production use.
- `suspect`: likely useful, but not trusted enough for production without review or additional evidence.
- `missing`: no reliable aanbod path found yet.
- `rejected`: examined and not suitable as a valid residential source.
- `missing_website`: source exists but no reliable official website has been resolved.
- `needs_manual_review`: should enter the small prioritized review queue.
- `aggregator_fallback`: source is covered through an authorized aggregator fallback path.
- `disabled_legal_review`: source is intentionally blocked pending legal or licensing review.

## 4. Monthly Pipeline

### Step 1: Run seed harvester

Refresh the NVM/seed baseline and keep it as the canonical starting point.

### Step 2: Run Overpass with cache

Use Overpass/OSM to discover additional domains and candidate makelaars, but only with caching enabled for repeatability and stability.

### Step 3: Dedupe by `root_domain + gemeente`

Collapse obvious duplicates before deeper auditing.

### Step 4: Audit `missing` and `suspect` with AanbodAuditor

Use Playwright to validate the official website and attempt to confirm a residential listing index.

### Step 5: Resolve `missing_website` with WebsiteResolver

Attempt to recover missing official websites in a controlled and traceable way.

### Step 6: Generate `makelaar_sources_master.csv`

Produce a single consolidated monthly source file with status, evidence, and review flags.

### Step 7: Execute property discovery for each `valid` source

Run property discovery only against trusted source records.

### Step 8: Normalize properties with BAG/PDOK/EP-Online

Standardize addresses, identifiers, and housing attributes.

### Step 9: Dedupe by BAG ID or normalized address

Prevent duplicate property records across makelaars, aggregator fallback, and manual sources.

### Step 10: Client matching

Only normalized and deduped relevant properties should enter the matching process.

### Step 11: Admin report

Generate the monthly report covering source quality, property counts, duplicates, and downstream client outcomes.

## 5. Property Discovery

Property discovery may use:

- official `aanbod_url` from the makelaar;
- authorized aggregator fallback;
- manual/admin source.

Official property states:

- `beschikbaar`
- `onder_bod`
- `verkocht`
- `verkocht_ov`
- `verdwenen`

Rule:

- only `beschikbaar` properties enter matching.

Additional guidance:

- do not treat a property detail page as a source-level aanbod index;
- keep evidence for how a property state was inferred;
- prefer source freshness over aggressive retention of stale listings.

## 6. Aggregators

Aggregators are not free by default.

Official rule:

- Huispedia and Huislijn are not "free by default";
- create adapters as `disabled_by_default`;
- before production use, review robots.txt, TOS, and licensing, and request permission or a license if reuse is commercial;
- if an API or formal agreement exists, use the API/license before scraping.

The legal and operational default is conservative.

## 7. Success Metrics

Track at least:

- valid `aanbod_url` count;
- unique valid domains;
- false positive rate;
- `missing_website` count;
- suspect queue count;
- properties discovered;
- duplicate properties removed;
- matches sent;
- client actions;
- offers/bezichtigingen.

Interpretation rules:

- rising coverage is good only if false positives remain near zero;
- a shrinking suspect queue is good only if it does not come from weak promotion to `valid`;
- property growth matters only after address normalization and dedupe.

## 8. Next Technical Steps

Priority technical work:

- Overpass cache;
- WebsiteResolver v1;
- `makelaar_sources_master.csv`;
- `property_discovery` module;
- aggregator legal review registry;
- admin monthly refresh job.

## Operational Notes

- The official website remains the default source of truth.
- AanbodAuditor should favor precision over recall.
- Commercial-only aanbod such as `bedrijfsaanbod` must not be promoted as residential production inventory.
- Project pages and property detail pages may be useful evidence, but they are not valid listing indexes.
- Every monthly run should be reproducible enough to explain why counts moved.

