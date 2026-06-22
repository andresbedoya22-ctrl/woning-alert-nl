# Next Codex Implementation Queue

This is the recommended queue after the agent OS and parser-family architecture foundation.

## Rule

Do not start with live scraping.

Start with deterministic models, fixtures, source intelligence, and tests. Live adapters come after the inventory core, source intelligence, and access policy exist.

## PR 2 — Inventory Core v1

### Goal

Create deterministic inventory state and daily diff logic.

### Expected files

```text
scraper/src/domek_wonen/inventory/__init__.py
scraper/src/domek_wonen/inventory/models.py
scraper/src/domek_wonen/inventory/diff_engine.py
scraper/src/domek_wonen/inventory/fixture_adapter.py
tests/fixtures/inventory/day_1.json
tests/fixtures/inventory/day_2.json
tests/test_inventory_models.py
tests/test_inventory_diff_engine.py
```

### Acceptance criteria

- detects new listings;
- detects removed listings;
- detects price changes;
- detects status changes;
- keeps unchanged listings stable;
- uses deterministic IDs/hashes;
- no network access;
- `py -3.12 -m pytest` passes.

## PR 3 — Source Intelligence Conversion v1

### Goal

Convert existing makelaar/source discovery data into a measurable source-intelligence dataset before building more parsers.

### Expected files

```text
scraper/src/domek_wonen/sources/__init__.py
scraper/src/domek_wonen/sources/source_intelligence_models.py
scraper/src/domek_wonen/sources/source_intelligence_loader.py
scraper/src/domek_wonen/sources/source_intelligence_report.py
scripts/run_source_intelligence_report.py
tests/fixtures/sources/source_intelligence_seed.csv
tests/test_source_intelligence_report.py
```

### Acceptance criteria

- loads a CSV seed with source/domain/aanbod fields;
- produces counts by source status;
- produces counts by aanbod URL quality;
- produces counts by detected platform / delivery mode;
- recommends parser family placeholders;
- separates missing, suspect, valid, blocked, legal-review and unknown sources;
- creates a prioritized manual review queue;
- no live scraping;
- no generated outputs committed;
- `py -3.12 -m pytest` passes.

## PR 4 — Access Policy v1

### Goal

Add source access status and enforce that only allowed/limited sources can run production extraction.

### Expected files

```text
scraper/src/domek_wonen/sources/access_policy.py
scraper/src/domek_wonen/sources/models.py
tests/test_source_access_policy.py
```

### Acceptance criteria

- source states are explicit;
- blocked/review/permission sources cannot run;
- allowed/limited sources can run;
- decisions include reasons;
- no parser can ignore access state.

## PR 5 — Delivery Mode Fingerprint v2

### Goal

Improve delivery mode classification with evidence and parser-family recommendations.

### Expected files

```text
scraper/src/domek_wonen/sources/delivery_fingerprint.py
scraper/src/domek_wonen/sources/fingerprint_models.py
tests/test_delivery_fingerprint_v2.py
```

### Acceptance criteria

- classifies Realworks/OGonline/WordPress/static cards/JSON-LD/sitemap/XHR/blocked/unknown;
- records evidence;
- recommends parser family;
- stays conservative when evidence is weak.

## PR 6 — Parser Config Runner v1

### Goal

Execute config-driven extraction for static HTML cards.

### Expected files

```text
scraper/src/domek_wonen/properties/parser_config_runner.py
scraper/src/domek_wonen/properties/parser_families/static_html_cards.py
tests/fixtures/parser_configs/static_cards_example_a.json
tests/fixtures/parser_configs/static_cards_example_b.json
tests/fixtures/properties/static_cards_example_a.html
tests/fixtures/properties/static_cards_example_b.html
tests/test_static_html_cards_parser.py
```

### Acceptance criteria

- one parser family supports two different fixtures through configs;
- extracts URL, address/city, price, status, basic attributes;
- produces evidence and confidence;
- rejects weak cards.

## PR 7 — Transaction Type Classifier

### Goal

Separate koop/huur from listing status.

### Expected files

```text
scraper/src/domek_wonen/properties/transaction_type_classifier.py
tests/test_transaction_type_classifier.py
```

### Acceptance criteria

- `te huur` maps to `huur`;
- `te koop`, `k.k.`, `vraagprijs` map to `koop` when sufficient;
- ambiguous data maps to `unknown`;
- koop matching excludes huur/unknown unless explicitly allowed.

## PR 8 — Normalized Listing QA v1

### Goal

Centralize clean inventory gates.

### Expected files

```text
scraper/src/domek_wonen/properties/normalized_listing_qa.py
tests/test_normalized_listing_qa.py
```

### Acceptance criteria

- invalid price rejected;
- invalid address reviewed/rejected;
- missing optional fields are warnings;
- source access is checked;
- only clean available koop listings reach matching.

## PR 9 — n8n Workflow Specs

### Goal

Design workflow specs for n8n without implementing live production workflows yet.

### Expected files

```text
docs/n8n/daily_inventory_sync.md
docs/n8n/failure_triage.md
docs/n8n/advisor_email_draft.md
```

### Acceptance criteria

- n8n calls backend jobs;
- n8n does not perform scraping logic;
- errors create triage outputs;
- AI usage is limited to summaries/drafts/diagnostics.

## PR 10 — First Real Source Family Pilot

Only after PR 2-8.

Pick one family based on Source Intelligence Conversion v1:

- Realworks stabilization; or
- OGonline/XHR stabilization; or
- static HTML cards; or
- WordPress cards.

Acceptance criteria:

- one parser family;
- two source-like fixtures;
- source access policy applied;
- QA applied;
- inventory diff works with extracted output.

## Explicitly not next

Do not start next with:

- dashboard;
- national live crawling;
- all makelaar source expansion;
- Funda or Pararius automation;
- agent browser scraping;
- AI-only extraction.
