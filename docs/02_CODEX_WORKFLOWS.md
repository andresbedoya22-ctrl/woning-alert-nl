# Codex Workflows

This document defines how to use Codex-style coding agents effectively in WoningAlert NL.

## 1. General rule

Codex should work in small, reviewable tasks.

Do not ask for:

- all parsers at once;
- all Netherlands coverage at once;
- dashboard + inventory + matching + emails in one task;
- stealth or anti-bot behavior.

Ask for:

- one model;
- one parser family;
- one QA gate;
- one failing test repair;
- one source config format;
- one deterministic fixture-based workflow.

## 2. Standard task template

Use this shape when asking Codex to implement something:

```text
Task: <short goal>

Context:
- Read AGENTS.md.
- Read docs/01_PARSER_FAMILY_ARCHITECTURE.md.
- Existing relevant files: <paths>.

Goal:
- <specific desired behavior>.

Constraints:
- Windows PowerShell.
- No Funda scraping.
- No stealth, CAPTCHA, proxy, or anti-bot bypass.
- Do not touch generated outputs.
- Do not broad-refactor unrelated code.

Acceptance criteria:
- <testable criteria>
- py -3.12 -m pytest passes.

Expected files:
- <paths likely to change>
```

## 3. Recommended Codex task sequence

### Task A — Inventory Core Models

Goal:

Create models for `InventorySource`, `RawListing`, `NormalizedListing`, `InventoryItem`, and `InventoryChange`.

Acceptance criteria:

- pure Python dataclasses or typed models;
- no network calls;
- tests for serialization and required fields.

### Task B — Fixture Daily Diff

Goal:

Create a fixture adapter that reads two synthetic daily snapshots and detects changes.

Acceptance criteria:

- detects `new`, `removed`, `price_changed`, `status_changed`, `unchanged`;
- no network access;
- tests pass.

### Task C — Source Access Policy

Goal:

Add access-status model and enforcement helper.

Acceptance criteria:

- blocked sources cannot run;
- permission-required sources are reported;
- tests cover each state.

### Task D — Static HTML Cards Parser

Goal:

Implement a config-driven parser family for static HTML cards.

Acceptance criteria:

- reads config;
- extracts at least URL, address, price, status, city;
- works on two different fixtures with same parser family;
- returns normalized candidate shape.

### Task E — WordPress Cards Parser

Goal:

Implement a WordPress HTML card parser using same config interface.

Acceptance criteria:

- no domain-specific parser class;
- two fixtures;
- extraction confidence and evidence included.

### Task F — JSON-LD Parser

Goal:

Extract useful property facts from JSON-LD scripts.

Acceptance criteria:

- supports object and list payloads;
- handles invalid JSON-LD safely;
- tests include missing fields and nested address/offers.

### Task G — Transaction Type Classifier

Goal:

Separate `transaction_type` from `status`.

Acceptance criteria:

- `te huur` does not become koop inventory;
- `te koop`, `k.k.`, `vraagprijs` map to `koop` when appropriate;
- tests cover ambiguous cases.

### Task H — BAG/PDOK Normalization Adapter Stub

Goal:

Create interface and fixture implementation before real API integration.

Acceptance criteria:

- no live API call required;
- tests demonstrate normalized address and BAG-like ID behavior.

## 4. Review workflow

For every Codex change, review:

- Did it read `AGENTS.md`?
- Did it stay within scope?
- Did it avoid generated outputs?
- Did it add tests?
- Did it avoid new dependencies?
- Did it preserve Windows-compatible commands?
- Did it avoid bypass behavior?
- Did it report changed files and validation results?

## 5. Failure handling

If Codex fails tests:

1. Do not continue adding features.
2. Ask for a test repair loop only.
3. Require minimal diff.
4. Require explanation of root cause.
5. Run `py -3.12 -m pytest` again.

## 6. Parallel agent usage

Safe parallel tasks:

- one agent reviews docs;
- one agent writes tests for an isolated module;
- one agent audits a parser fixture;
- one agent analyzes architecture.

Unsafe parallel tasks:

- two agents editing same file;
- one agent refactoring while another writes parser code;
- multiple agents changing source schema simultaneously.

## 7. n8n integration rule

n8n should orchestrate deterministic backend jobs.

n8n should not become the scraper.

Correct:

```text
n8n cron -> backend job -> inventory diff -> matching -> AI summary -> advisor email
```

Incorrect:

```text
n8n AI agent -> browse many websites -> infer inventory -> send results
```

## 8. AI usage rule

Use AI for:

- QA explanations;
- parser config suggestions;
- failure triage;
- email drafts;
- code generation under tests;
- architecture review.

Do not use AI for:

- bulk extraction of every listing;
- bypassing access restrictions;
- replacing deterministic parsers;
- approving legally ambiguous sources.
