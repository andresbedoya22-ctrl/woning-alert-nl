# System Architecture

## Canonical flow

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

## Module responsibilities

- `sources/`: source registry, source intelligence records, access-policy decisions, delivery fingerprint evidence.
- `parsers/`: reusable parser-family interfaces and domain-level configs.
- `qa/`: normalization checks, field quality checks, dedupe keys, review routing.
- `inventory/`: snapshots, state transitions, daily diffs, stale-source preservation.
- `matching/`: client rules and relevance scoring.
- `orchestration/`: job wiring, schedules, retries, advisor notifications.

## Data flow

1. Candidate source data enters from discovery outputs or existing source registries.
2. Source intelligence consolidates what is known about each domain or organization.
3. Access policy decides whether runtime usage is allowed, limited, blocked, or deferred.
4. Delivery fingerprinting identifies the technical listing pattern.
5. Parser family plus source config turn approved sources into normalized listings.
6. QA gates separate clean inventory from rejected or review-needed records.
7. Inventory state compares snapshots and protects against false removals during source failure.
8. Matching consumes only approved inventory.
9. Advisor review packages and future emails are prepared from matching outputs.
10. n8n orchestrates approved jobs and notifications around the pipeline.

## Separation boundaries

- Source intelligence answers "what is this source and what do we know about it?"
- Access policy answers "may we use it and under what limits?"
- Delivery fingerprint answers "how does it technically deliver listings?"
- Parser families answer "how do we extract a normalized card or detail payload from this technical pattern?"
- Inventory answers "what is the durable listing state over time?"
- Matching answers "which clients should see this listing?"
- n8n answers "when and how do approved jobs run?"

## Legacy vs future modules

Legacy or diagnostic:

- `scraper/src/domek_wonen/portals/`
- `scraper/src/domek_wonen/properties/`
- existing portal-first docs such as `docs/WONING_ALERT_NL_ROADMAP.md`

Active V4 runtime or near-runtime:

- `compliance/`
- `discovery/`
- `diagnostics/`
- `harvest/`
- `matching/`

Future architecture targets created in this reset:

- `sources/`
- `parsers/`
- `qa/`
- `orchestration/`
- expanded `inventory/`
