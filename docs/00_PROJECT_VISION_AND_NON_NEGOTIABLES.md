# Project Vision And Non-Negotiables

## Product vision

WoningAlert NL should become a national housing-source intelligence system for Dutch koopwoningen. Its purpose is not to mirror every portal page; it is to identify allowed sources, extract the minimum useful listing signals, maintain a reliable inventory state, and surface opportunities to Domek advisors earlier than manual searching would.

## Operational objective

The operating system behind the product is a pipeline that:

1. finds or ingests candidate sources;
2. determines whether they are usable;
3. classifies how they technically deliver listings;
4. routes them to a parser family and source config;
5. normalizes listing outputs;
6. applies QA gates before matching;
7. compares daily state safely;
8. prepares matching and advisor review workflows.

## Product decisions

- National scope is the direction, but operational honesty matters more than claiming total coverage.
- The project scales through technical patterns, not through one-off parsers for every makelaar.
- Inventory quality and policy compliance come before dashboarding.
- Matching depends on normalized inventory, not raw captures.
- n8n is an orchestrator for approved jobs, not a workaround for missing architecture.

## What is allowed

- Researching existing sources and legacy data already present in the repo.
- Building source intelligence records from internal datasets.
- Rendering public pages only when access policy allows it and only for normal page interpretation.
- Creating parser families around reusable delivery patterns.
- Defining QA gates, inventory state rules, matching, and advisor workflows.

## What is prohibited

- Automatic scraping of Funda.
- Automatic scraping of Pararius without explicit permission or license.
- Stealth browser automation.
- CAPTCHA solving.
- Residential proxies.
- IP rotation to evade source controls.
- Human-simulation tactics to bypass anti-bot systems.
- Bypass of robots, login walls, `403`, or explicit blocking.
- Copying long source descriptions into the core dataset.
- Downloading listing images without explicit right to do so.

## Legal and technical constraints

- Every networked runtime path must go through the compliance gate.
- Robots, terms, and explicit source behavior take precedence over convenience.
- Failure of one source must not corrupt inventory state for other sources.
- A blocked source is a classification result, not an invitation to bypass it.

## Browser rendering vs prohibited evasion

Allowed:

- rendering a public, already-permitted page to understand its structure;
- observing whether cards, JSON-LD, iframes, or XHR patterns are visible;
- collecting evidence for delivery-mode classification.

Prohibited:

- automation meant to disguise the client;
- repeated retry behavior intended to beat rate limits;
- login replay, CAPTCHA handling, or anti-bot workarounds;
- using rendering to continue after an explicit block signal.
