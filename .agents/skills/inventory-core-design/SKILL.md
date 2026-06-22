# Inventory Core Design Skill

Use this skill when designing or implementing inventory state, daily snapshots, or diff logic.

## Required reading

- `AGENTS.md`
- `docs/00_AGENT_OS_AND_ROADMAP.md`
- `docs/02_CODEX_WORKFLOWS.md`

## Goal

Build deterministic inventory state before adding live adapters.

## Core models

Use separate models for:

- inventory source;
- raw listing;
- normalized listing;
- inventory item;
- inventory snapshot;
- inventory change.

## Required behavior

The inventory core should detect:

- new listing;
- removed listing;
- unchanged listing;
- price change;
- status change;
- stale source.

## Implementation rules

- Start with fixture adapters.
- Keep tests offline.
- Use stable IDs and deterministic hashes.
- Keep raw source data separate from normalized inventory.
- Do not remove inventory only because one source failed.
- Prefer local SQLite or repository abstraction first.

## Test scenarios

Create day-1/day-2 fixtures covering:

- one new property;
- one removed property;
- one price change;
- one status change;
- one unchanged property;
- one duplicate from another source.

## Output

Report models, storage approach, diff rules, fixtures, tests, and next step.
