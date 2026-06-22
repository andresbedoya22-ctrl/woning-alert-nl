# Delivery Mode Fingerprint Skill

Use this skill when classifying how a makelaar or portal source technically delivers its woningaanbod.

## Required reading

- `AGENTS.md`
- `docs/03_MAKELAAR_DELIVERY_RESEARCH_LOOP.md`
- `docs/04_SOURCE_ONBOARDING_PLAYBOOK.md`

## Goal

Classify a source into a delivery mode with evidence before writing parser code.

## Allowed delivery modes

- `realworks_public`
- `ogonline_xhr`
- `kolibri_public`
- `wordpress_rest`
- `wordpress_html_cards`
- `static_html_cards`
- `json_ld`
- `sitemap_detail`
- `xhr_json`
- `email_alert`
- `iframe_external`
- `funda_iframe_blocked`
- `pararius_external_blocked`
- `captcha_blocked`
- `login_required`
- `unknown_manual_review`

## Minimal probe policy

Use only conservative probes:

- homepage;
- robots;
- sitemap;
- known listing URL;
- common listing paths.

Do not perform broad crawling.

## Evidence checklist

Collect:

- URL tested;
- HTTP status;
- relevant script/CMS/platform signals;
- visible card signals;
- detail link patterns;
- price/status/address signals;
- sitemap/detail URL patterns;
- iframe/portal dependencies;
- blocking signals;
- parser family candidate.

## Output format

Return structured output:

```text
source_domain:
access_precheck:
delivery_mode:
confidence:
parser_family_candidate:
config_required:
evidence:
recommended_action:
blocking_reason:
next_test_or_fixture:
```

## Hard stop

If CAPTCHA, login, 403, Funda dependency, or anti-bot blocking appears, stop and classify safely. Do not propose bypass.
