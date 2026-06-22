# Claude Code Bridge

This repository is agent-neutral.

Before doing any work, read:

1. `AGENTS.md`
2. `docs/00_AGENT_OS_AND_ROADMAP.md`
3. `docs/01_PARSER_FAMILY_ARCHITECTURE.md`
4. `docs/02_CODEX_WORKFLOWS.md`

Claude-specific behavior must not contradict `AGENTS.md`.

## Project summary

WoningAlert NL is a Dutch housing inventory and matching system.

The active architecture is parser-family based inventory:

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

Do not build one parser per makelaar.

## Hard rules

- No Funda scraping.
- No stealth, CAPTCHA solving, residential proxies, anti-bot bypass, or simulated human browsing.
- Block or mark permission-required sources that cannot be accessed cleanly.
- Use tests and fixtures.
- Do not commit generated outputs.
- Use Windows PowerShell command examples.

## Recommended Claude use

Use Claude for:

- long implementation sessions;
- refactors with careful continuity;
- parser family implementation;
- architecture review;
- test repair loops.

Keep task scope small and traceable.
