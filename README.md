# WoningAlert NL

WoningAlert NL is a real-estate inventory and matching engine for the Dutch housing market.

The project goal is to detect newly available homes, normalize them into a stable inventory, compare daily changes, match relevant properties with active client profiles, and generate advisor-ready recommendations before manual searching becomes necessary.

## Current strategic direction

The active strategy is **parser-family based inventory**, not one scraper per makelaar.

The system should scale through reusable technical delivery modes:

```text
source_registry
  -> access_policy
  -> delivery_mode_fingerprint
  -> parser_family
  -> source_config
  -> normalized_property
  -> inventory_state
  -> matching
  -> advisor_email
```

Examples of parser families:

- `realworks_public`
- `ogonline_xhr`
- `kolibri_public`
- `wordpress_rest`
- `wordpress_html_cards`
- `json_ld`
- `sitemap_detail`
- `static_html_cards`
- `xhr_json`
- `email_alert`
- `iframe_blocked_handler`

The project must not become `makelaar_1_parser.py`, `makelaar_2_parser.py`, etc.

## Non-negotiable rules

- Do not scrape Funda.
- Do not use stealth browser automation, CAPTCHA solving, rotating residential proxies, mouse simulation, or anti-bot evasion.
- Do not treat blocked sources as engineering problems to bypass. Mark them as `permission_required`, `blocked`, or `legal_review`.
- Prefer official websites, authorized feeds, permitted pages, email alerts, and licensed/permissioned adapters.
- Extract only the minimum useful facts needed for matching and change detection.
- Do not copy long descriptions or photos unless explicitly licensed or permitted.

## Repository operating model

This repo is designed to be usable by human developers and coding agents such as Codex or Claude Code.

Core instruction files:

- `AGENTS.md` — primary repo rules for all coding agents.
- `docs/00_AGENT_OS_AND_ROADMAP.md` — agent operating model and build roadmap.
- `docs/01_PARSER_FAMILY_ARCHITECTURE.md` — technical architecture for source fingerprinting, parser families, configs, QA, and compliance.
- `docs/02_CODEX_WORKFLOWS.md` — task workflow rules for Codex-style sessions.
- `.agents/skills/` — reusable project skills for agent-assisted implementation.
- `.claude/CLAUDE.md` — optional Claude Code bridge that points back to the neutral repo rules.

## Development setup

Requirements:

- Windows + PowerShell
- Python 3.12 recommended

Install dependencies:

```powershell
py -3.12 -m pip install -r requirements.txt
```

Run tests:

```powershell
py -3.12 -m pytest
```

## Current codebase status

The existing codebase already contains useful foundations:

- source discovery and makelaar source quality checks;
- property discovery pipeline;
- Realworks/OGonline-oriented parser work;
- generic property card extraction;
- detail page enrichment;
- address/status/URL quality gates;
- matching v1;
- email preview and advisor review artifacts;
- diagnostics for platform and delivery mode fingerprinting.

The next architectural step is to convert this into a cleaner, modern **inventory-first system** with parser families and source configs as the scaling mechanism.
