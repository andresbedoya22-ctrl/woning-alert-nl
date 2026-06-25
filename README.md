# WoningAlert NL

WoningAlert NL is a discovery-first housing intelligence system for the Dutch koopwoning market. The product goal is to identify allowed housing sources, classify their technical delivery patterns, build a safe normalized inventory, compare daily changes, match opportunities against active client searches, and prepare advisor-facing outputs.

## What problem it solves

Advisors should not depend on manual searching across dozens of heterogeneous housing sources. The repo exists to turn scattered public source signals into a controlled inventory pipeline with explicit access policy, reliable change tracking, and matching-ready records.

## What it is not

- It is not a full-market scraper.
- It is not an operational pipeline built on automatic Funda scraping.
- It is not an operational pipeline built on automatic Pararius scraping.
- It is not a parser-per-makelaar strategy.
- It is not a dashboard-first project.
- It is not a stealth automation project.

## Core scaling principle

WoningAlert NL does not scale by creating one parser per makelaar.

WoningAlert NL scales by using source intelligence, delivery modes, parser families, and source configs.

## Target flow

```text
source_registry
-> source_intelligence
-> access_policy
-> delivery_mode_fingerprint
-> parser_family
-> source_config
-> normalized_listing
-> inventory_state
-> client_matching
-> advisor_email
-> n8n_orchestration
```

## High-level architecture

```text
Discovery / Existing Sources
        |
        v
Source Intelligence
        |
        v
Access Policy
        |
        v
Delivery Mode Fingerprint
        |
        v
Parser Family + Source Config
        |
        v
Normalized Listing
        |
        v
QA / Normalization Gates
        |
        v
Inventory State Engine
        |
        v
Client Matching
        |
        v
Advisor Email / Review Pack
        |
        v
n8n Orchestration
```

## Main modules

- `scraper/src/domek_wonen/sources/`: source registry, source intelligence, access policy, delivery fingerprinting.
- `scraper/src/domek_wonen/parsers/`: parser families and domain-level source configs.
- `scraper/src/domek_wonen/pilots/`: small controlled pilots that connect permitted source capture to parser, QA, and inventory layers.
- `scraper/src/domek_wonen/inventory/`: normalized listings, snapshots, diffs, stale-source handling.
- `scraper/src/domek_wonen/qa/`: quality gates, normalization, dedupe, review states.
- `scraper/src/domek_wonen/matching/`: current and future matching logic.
- `scraper/src/domek_wonen/orchestration/`: n8n-facing jobs, schedules, alerts, retries.
- `scraper/src/domek_wonen/portals/`: legacy or diagnostic portal experiments, not the strategic V4 path.
- `scraper/src/domek_wonen/properties/`: legacy property-discovery stack to mine for reusable parser-family ideas.

## Non-negotiable rules

- No automatic scraping of Funda.
- No automatic scraping of Pararius without explicit permission, license, or review.
- No stealth browser automation.
- No CAPTCHA solving.
- No residential proxies.
- No IP rotation to evade controls.
- No human simulation to bypass detection.
- No bypass of login walls, `403`, paywalls, robots, or explicit blocking.
- If a source blocks access, mark it `blocked`, `permission_required`, or `legal_review`.
- Extract only minimum necessary data.
- Do not copy long descriptions.
- Do not download images without explicit permission or license.
- Do not move properties into matching before QA gates pass.
- Do not build dashboard flows before inventory and matching are stable.
- Do not modify `data/raw` unless the user explicitly asks.
- Do not commit generated outputs.

## Working with Codex

- Read [AGENTS.md](/C:/Projects/domek-wonen/AGENTS.md) first.
- Inspect real files before claiming they exist.
- Prefer small, phase-bounded tasks.
- Do not broaden scope from docs to runtime code without need.
- Add or update tests when runtime code changes.
- Run `python -m pytest` after code changes; for docs-only work, run it when practical and report the exact outcome.
- Report changed files, validation status, branch, and residual risks.

Task template for Codex lives in [docs/09_CODEX_WORKFLOW.md](/C:/Projects/domek-wonen/docs/09_CODEX_WORKFLOW.md).

## Install dependencies

```powershell
py -3.12 -m pip install -r requirements.txt
```

## Run tests

```powershell
python -m pytest
```

Pytest is configured to keep its temporary and cache paths under `tmp/` in this repo.

## Current repo status

As of this architecture reset, the repo already contains:

- discovery and diagnostics code under `scraper/src/domek_wonen/discovery/` and `diagnostics/`;
- legacy portal and property-discovery modules under `portals/` and `properties/`;
- current matching code under `matching/`;
- multiple historical planning docs under `docs/`;
- scripts for source master, coverage, fingerprinting, matching, and audits under `scripts/`.

This PR reframes that codebase under a professional architecture without deleting existing functional modules.

## Controlled Realworks Capture Pilot v1

`scraper/src/domek_wonen/pilots/realworks_capture_pilot.py` adds the first controlled pilot for a small batch of permitted `realworks_public` listing sources. The pilot calls `robots_gate.can_fetch(domain, path)` before any injected fetch function is allowed to run, caps batches at five sources by default, and connects captured HTML through `ParserFamilyRunner`, the parser output QA gate, and `InventorySnapshot` creation.

The pilot does not include a real HTTP fetcher, Playwright, Selenium, stealth automation, proxies, CAPTCHA handling, bypass behavior, persistence, dashboard work, matching, or n8n orchestration. Captured HTML and generated run outputs remain local/generated artifacts and must not be committed.

## Controlled Source Selection for Realworks Pilot v1

`scraper/src/domek_wonen/pilots/source_selection.py` selects up to five `realworks_public` sources from local enriched source-intelligence evidence and converts them into `CapturePilotSource` inputs for the capture pilot.

This selection layer is offline. It does not make network requests, call `robots_gate`, capture HTML, use browser automation, or touch generated capture outputs. It excludes Funda, Pararius, blocked, permission-required, legal-review, manual-review, missing-domain, and missing-URL rows before the capture pilot gets a source list.

## Controlled Realworks Live Fetch v1

`scraper/src/domek_wonen/pilots/live_fetch.py` adds an explicit controlled HTTP fetcher for a small `realworks_public` live pilot. It uses only standard-library HTTP, a clear non-stealth User-Agent, one GET, a required timeout, stable fetch exceptions, and accepts only HTML or text responses.

The fetcher does not call `robots_gate` itself: the capture pilot remains responsible for checking `robots_gate.can_fetch(domain, path)` before invoking any fetch function. The live helper defaults to `max_sources=3`, includes domain dedupe so the first run avoids several variants from the same source domain, and adds no Playwright, Selenium, proxies, stealth behavior, CAPTCHA handling, bypass logic, persistence, or generated outputs.

## KIN OGonline XHR Paginated Runner v1

`scraper/src/domek_wonen/pilots/ogonline_xhr_paginated_runner.py` adds a controlled paginated runner for `ogonline_xhr` source configs, starting with the KIN fixture. It builds deterministic API URLs with `build_paginated_api_url`, checks `robots_gate.can_fetch(api_domain, api_path)` before each injected `fetch_json` call, then sends caller-provided JSON through `build_parser_input_from_api_json`, `ParserFamilyRunner`, and the parser output QA gate.

This phase does not implement real HTTP, live fetch orchestration, Playwright, Selenium, stealth behavior, proxies, CAPTCHA handling, bypass logic, JSON persistence, property-discovery runtime changes, matching, dashboard work, or n8n orchestration. A real live runner can be added later after this offline config-to-parser path remains stable.

## Recommended next PRs

- `PR 2: Source Intelligence Conversion v1`
- `PR 3: Access Policy v1`
- `PR 4: Delivery Mode Fingerprint v2`
- `PR 5: Inventory Core v1`
- `PR 6: Parser Config Runner v1`

For the detailed staged plan, see [docs/11_ROADMAP.md](/C:/Projects/domek-wonen/docs/11_ROADMAP.md).
