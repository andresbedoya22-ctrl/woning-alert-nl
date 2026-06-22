# Skill System Design

This document defines the project skill system for agent-assisted development.

## 1. Why skills matter

Skills are reusable procedural instructions for recurring work.

For WoningAlert NL, skills are useful because the project has repeated patterns:

- classify source delivery mode;
- audit source access/compliance;
- author parser configs;
- implement parser families;
- repair tests;
- design inventory diff logic;
- triage failed runs;
- prepare Codex tasks;
- design n8n workflows.

The goal is not to make the AI autonomous. The goal is to make repeated agent work more consistent and less error-prone.

## 2. Skill design principles

A good project skill should be:

- narrow;
- procedural;
- test-aware;
- safety-aware;
- reusable;
- independent from one model provider;
- aligned with `AGENTS.md`.

A bad skill is:

- vague;
- too broad;
- not testable;
- encouraging agent autonomy without checkpoints;
- duplicating conflicting policy;
- mixing coding, scraping, legal review, and deployment in one instruction.

## 3. Current skill set

Existing skills:

- `parser-family-implementation`
- `source-compliance-audit`
- `test-repair-loop`

Added/target skills:

- `delivery-mode-fingerprint`
- `source-onboarding`
- `parser-config-authoring`
- `inventory-core-design`
- `normalization-qa-gates`
- `failure-triage`
- `codex-task-planning`
- `n8n-orchestration`
- `advisor-email-generation`

## 4. Skill map

| Skill | Use when | Output |
|---|---|---|
| `delivery-mode-fingerprint` | Researching how a source delivers aanbod | delivery mode + evidence + parser family candidate |
| `source-compliance-audit` | Deciding if a source can run | access status + blockers + recommended action |
| `source-onboarding` | Moving a source toward production | source registry row + QA plan + promotion decision |
| `parser-config-authoring` | Existing parser family can handle a domain | config JSON + fixture/test plan |
| `parser-family-implementation` | New or improved parser family needed | parser code + tests + fixture |
| `inventory-core-design` | Building state/diff logic | models + storage + diff tests |
| `normalization-qa-gates` | Hardening clean inventory | validation gates + rejection reasons |
| `failure-triage` | A source/job failed | root cause category + safe next action |
| `test-repair-loop` | Tests fail | minimal fix + root cause + validation |
| `codex-task-planning` | Preparing a Codex task | scoped prompt + acceptance criteria |
| `n8n-orchestration` | Designing workflow automation | safe workflow design, not scraping logic |
| `advisor-email-generation` | Matches need human-readable output | email draft + match explanation |

## 5. Skill loading rule

Agents should load only the skill needed for the current task.

Examples:

- Building inventory models: load `inventory-core-design`.
- Auditing Huislijn: load `source-compliance-audit` and `delivery-mode-fingerprint`.
- Creating a config for a WordPress card site: load `parser-config-authoring`.
- Repairing broken tests: load `test-repair-loop` only.

## 6. Safety boundary

No skill may instruct an agent to:

- scrape Funda;
- bypass CAPTCHA;
- evade anti-bot protections;
- rotate residential proxies;
- fake browser fingerprints;
- ignore robots or access policy;
- store unnecessary descriptions/images/personal data.

## 7. Future skill improvements

Later, once implementation starts, each skill can include:

- example prompts;
- known file paths;
- fixture templates;
- expected test names;
- common failure modes;
- command snippets.

Do not overfit skills before the code exists. Skills should evolve with real tasks.
