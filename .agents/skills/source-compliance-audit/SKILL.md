# Source Compliance Audit Skill

Use this skill when evaluating whether a source can be used in production.

## Purpose

Prevent WoningAlert NL from treating every reachable website as a permitted data source.

## Required reading

- `AGENTS.md`
- `docs/01_PARSER_FAMILY_ARCHITECTURE.md`
- source registry/config files relevant to the task

## Source states

Use only these states:

- `allowed`
- `limited`
- `permission_required`
- `legal_review`
- `blocked`
- `disabled`

## Audit checklist

For each source, record:

- source domain;
- source type;
- relevant URLs;
- robots/access status;
- terms or permission status when known;
- login/CAPTCHA/403/anti-bot signals;
- whether extraction is minimal;
- whether photos/descriptions are avoided;
- recommended parser family;
- final recommended state.

## Hard blocks

Mark as blocked or permission-required if:

- source requires login;
- CAPTCHA appears;
- 403 or explicit blocking appears;
- source depends on Funda scraping;
- source requires stealth or proxy behavior to work;
- source terms clearly prohibit intended automated reuse.

## Allowed output

The audit should produce structured rows or markdown with:

- `source_domain`
- `access_status`
- `blocking_status`
- `delivery_mode`
- `parser_family_candidate`
- `recommended_action`
- `evidence`
- `notes`

## Prohibited output

Do not provide instructions for:

- bypassing CAPTCHA;
- evading anti-bot systems;
- rotating IPs;
- spoofing fingerprints;
- scraping Funda.
