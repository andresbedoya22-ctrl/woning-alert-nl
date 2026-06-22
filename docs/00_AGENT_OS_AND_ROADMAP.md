# Agent OS and Roadmap

This document defines how WoningAlert NL should be built with AI coding agents while staying maintainable, testable, and legally conservative.

## 1. Goal

Build a modern Dutch housing inventory system that can scale through parser families and source configs instead of one scraper per makelaar.

The system should:

- discover or receive permitted housing sources;
- classify delivery mode;
- select a parser family;
- extract minimal property facts;
- normalize and deduplicate listings;
- detect daily changes;
- match properties with active client profiles;
- generate advisor-ready recommendations.

## 2. Agent operating model

Use agents as engineering accelerators, not as uncontrolled autonomous scrapers.

Correct use:

- Codex implements small scoped tasks;
- Codex/Claude review architecture and tests;
- agents generate parser configs from fixtures;
- agents diagnose failures and propose fixes;
- agents generate email drafts for matched properties;
- n8n orchestrates scheduled jobs and notifications.

Incorrect use:

- an agent browsing thousands of sites every day;
- an agent bypassing blocks, CAPTCHA, login, or anti-bot controls;
- LLM-only extraction for every listing;
- copying long descriptions or images without permission.

## 3. Repo control files

Neutral source of truth:

- `AGENTS.md`

Agent skills:

- `.agents/skills/parser-family-implementation/SKILL.md`
- `.agents/skills/source-compliance-audit/SKILL.md`
- `.agents/skills/test-repair-loop/SKILL.md`

Optional tool bridges:

- `.claude/CLAUDE.md`
- `.codex/config.toml`
- `.codex/hooks.json`

These bridge files must point back to `AGENTS.md` and must not create conflicting instructions.

## 4. Roadmap

### Phase 0 — Repo realignment

Deliverables:

- modern README;
- expanded `AGENTS.md`;
- architecture docs;
- agent skills;
- preserved legacy pipeline documentation.

Acceptance criteria:

- repo purpose is clear;
- agents know the active strategy;
- no runtime behavior is changed;
- no generated outputs are committed.

### Phase 1 — Inventory Core v1

Create deterministic core models and local persistence.

Deliverables:

- `InventorySource`;
- `RawListing`;
- `NormalizedListing`;
- `InventoryItem`;
- `InventoryChange`;
- SQLite schema or repository abstraction;
- fixture-based day-1/day-2 diff tests.

Acceptance criteria:

- a fixture adapter can ingest two daily snapshots;
- system detects new, removed, price changed, and status changed listings;
- tests run without network access.

### Phase 2 — Access Policy v1

Build a production gate for sources.

Deliverables:

- source status model: `allowed`, `limited`, `permission_required`, `legal_review`, `blocked`, `disabled`;
- robots/access metadata fields;
- blocked-source behavior;
- no-bypass enforcement in code.

Acceptance criteria:

- blocked sources do not run;
- sources requiring permission are visible in reports;
- no adapter can run without an explicit access state.

### Phase 3 — Delivery Mode Fingerprint v2

Improve source classification.

Deliverables:

- homepage/listing/sitemap probes;
- delivery mode classifier;
- evidence per source;
- recommended parser family;
- manual review queue.

Acceptance criteria:

- output explains why a source is Realworks, OGonline, WordPress, JSON-LD, XHR, static cards, blocked, or unknown;
- no source is promoted without evidence.

### Phase 4 — Parser Family Config Runner

Turn config files into executable extraction.

Deliverables:

- config loader;
- config validation;
- parser family dispatcher;
- CSS-selector based extraction for static cards and WordPress cards;
- normalized candidate output;
- fixtures and tests.

Acceptance criteria:

- one parser family can support multiple domains through configs;
- tests prove two different fixtures work with the same parser family.

### Phase 5 — Parser Families v1

Implement or stabilize:

- Realworks public;
- OGonline/XHR;
- static HTML cards;
- WordPress cards;
- WordPress REST;
- JSON-LD;
- sitemap/detail;
- XHR JSON;
- email alerts;
- blocked iframe handler.

Acceptance criteria:

- each parser has tests;
- each parser returns the same normalized schema;
- each parser produces confidence and evidence.

### Phase 6 — QA and Normalization

Improve reliability.

Deliverables:

- address normalization;
- BAG/PDOK enrichment adapter;
- transaction type separation (`koop`, `huur`, `unknown`);
- status classification;
- price sanity;
- duplicate detection;
- QA report.

Acceptance criteria:

- rentals do not enter koop matching;
- invalid prices are rejected;
- duplicate properties across sources collapse safely.

### Phase 7 — Matching and Advisor Email

Use clean inventory to create value.

Deliverables:

- matching input from inventory core;
- profile-based matching;
- explanation per match;
- email draft generation;
- advisor review pack.

Acceptance criteria:

- only clean available koop inventory reaches matching;
- advisor can review top matches quickly.

### Phase 8 — n8n Orchestration

Automate execution.

Deliverables:

- daily scheduled workflow;
- source failure summary;
- match summary;
- email draft workflow;
- error notification workflow.

Acceptance criteria:

- n8n calls deterministic backend jobs;
- n8n does not scrape directly;
- AI is used for QA summaries and email drafting, not bulk extraction.

### Phase 9 — Production Hardening

Deliverables:

- monitoring;
- source stale handling;
- retry policy;
- admin controls;
- dashboard;
- source permission workflow.

Acceptance criteria:

- a single source failure does not delete inventory;
- stale/blocked sources are reported;
- operators can explain every recommendation.

## 5. Agent task sizing

Every coding task should be small enough to review.

Good task:

- add `InventoryChange` model and tests;
- implement `StaticHtmlCardsParser` against one fixture;
- add transaction type classifier;
- add source access status enum.

Bad task:

- build all scrapers;
- refactor the whole repo;
- make it cover all Netherlands;
- add dashboard, scraping, matching, and email in one session.

## 6. Quality bar

Every implementation should include:

- deterministic tests;
- synthetic fixtures when network behavior is involved;
- clear rejection reasons;
- confidence/evidence fields;
- no hidden generated outputs;
- no evasion behavior.
