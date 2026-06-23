# AGENTS.md

## Product objective

WoningAlert NL builds a disciplined housing-source intelligence pipeline for the Dutch koopwoning market. The operational goal is to identify allowed sources, classify technical delivery patterns, build a normalized inventory, compare daily changes safely, match relevant opportunities to active clients, and support advisor review plus later orchestration.

## Strategic architecture

The canonical architecture is:

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

The repo must optimize for reusable parser families and source configs, not one parser per makelaar. A makelaar is a commercial entity; a parser family is a reusable technical delivery pattern.

## Forbidden behaviors

- No automatic scraping of Funda.
- No automatic scraping of Pararius without explicit permission, license, or review.
- No stealth browser automation.
- No CAPTCHA solving.
- No residential proxies.
- No IP rotation to evade controls.
- No human-simulation anti-bot bypass.
- No bypass of login walls, `403`, paywalls, robots, or explicit source blocking.
- No scraping-oriented Playwright path as the MVP for JS-heavy sources.
- No modification of `data/raw` unless the user explicitly asks.
- No `git add .`.
- No push unless the user explicitly asks.
- No commit without explicit permission, unless the task explicitly authorizes an atomic commit.

## Non-negotiable rules

- Work in Windows PowerShell.
- Work in bounded phases.
- Make small, traceable, tested changes.
- Do not mix architectural phases in one task.
- Do not claim a file, module, script, or behavior exists without reading the repo state.
- Preserve functional code, tests, and scripts unless the task explicitly requires a runtime change.
- If a source fails, do not erase prior successful inventory from that source.
- Set `safe_to_compare_removals=false` when source capture fails.
- Keep last successful source inventory as stale reference until recovery.

## Source access policy

- `allowed`: source is publicly reachable and passes robots plus legal checks for the intended request pattern.
- `limited`: source can be used only with narrower scope, lower frequency, or reduced fields.
- `permission_required`: source may be technically reachable but cannot be used operationally without approval.
- `legal_review`: legal or contractual ambiguity blocks operational use until reviewed.
- `blocked`: the source presents login, CAPTCHA, `403`, explicit anti-bot, paywall, or equivalent stop signals.

Funda and Pararius stay outside the operational pipeline. They may be benchmark, manual reference, or permission-track inputs only.

Browser rendering is allowed only to render an already-permitted public page. Rendering or automation to evade controls is forbidden.

## Parser-family rules

- No parser per makelaar as the default strategy.
- Build reusable parser families around technical delivery modes.
- Add source-specific configs before adding a new parser family.
- Treat unsupported or ambiguous sources as `unknown_manual_review` until evidence supports a family decision.
- Legacy `properties/` code can inform future parser families, but it is not the target architecture itself.

## Data minimization

- Extract only the minimum fields needed for inventory, QA, matching, and advisor review.
- Do not copy long listing descriptions into the core model.
- Do not download images unless permission or license is explicit.
- Do not move listings into matching before QA and normalization gates pass.

## Generated artifacts that must not be committed

- `.env`
- `.env.*`
- `tmp/`
- `.pytest_cache/`
- `cache/`
- `data/raw/`
- `data/diagnostics/`
- `data/cache/`
- `data/discovery/latest/`
- `data/discovery/runs/`
- `data/discovery/platform_fingerprint/`
- `data/email_previews/`
- `data/matching/`
- `data/property_discovery/`
- `data/properties/latest/`
- `data/properties/runs/`
- `data/source_debug/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `*.sqlite-wal`
- `*.sqlite-shm`
- generated HTML, HAR, preview, and run artifacts

## Validation requirements

- If runtime code changes: run `py -3.12 -m pytest`.
- If only docs or structure change: tests are still recommended; if skipped, explain why.
- Do not report success for tests that did not run.
- Do not report a task complete if runtime code changed and validation failed, unless the user explicitly accepts that state.

## Matching rules

- Matching consumes only normalized, QA-passed inventory.
- Keep `transaction_type` separate from listing `status`.
- Do not mix koop and huur logic accidentally.
- Dashboard or scanner work waits until inventory and matching are stable.
- Advisor email generation comes after matching, not before.

## Agent workflow discipline

- Read this file before acting in the repo.
- Start with `git status --short` and `git branch --show-current` when the task changes files or asks for repo work.
- Inspect real files before editing.
- Prefer explicit path allowlists for staging.
- Keep commits atomic and phase-scoped.
- Report branch, changed files, validation, final `git status -s`, and risks at close.
- Never invent repo state, test outcomes, or command results.

## Current priority order

1. Repo Architecture Reset v1.
2. Source Intelligence Conversion v1.
3. Access Policy v1.
4. Delivery Mode Fingerprint v2.
5. Inventory Core v1.
6. Parser Config Runner v1.
7. Parser Families.
8. QA and Normalization.
9. Matching and Advisor Emails.
10. n8n Orchestration.
11. Dashboard only after inventory and matching are stable.

## Binding network gate

`scraper/src/domek_wonen/compliance/robots_gate.py` remains the single network gate for V4 pipeline work. No runtime module may make HTTP requests without first checking `can_fetch(domain, path)` and receiving `True`.
