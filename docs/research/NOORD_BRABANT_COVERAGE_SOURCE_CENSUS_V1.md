# Noord-Brabant Coverage Source Census Hardened v1

## Objective

Create an auditable source census for makelaars and source domains that may publish koopwoningen in Noord-Brabant, before applying parser families across the province.

This hardened version replaces the earlier `noord_brabant_coverage_source_census_v1.*` artifacts. Manual review found that the original v1 master could expose rejected evidence candidates as operational aanbod URLs, treat property-detail URLs as listing indexes, over-trust stale `platform_guess=realworks`, and hide missing-domain evidence rows. The valid artifacts for this phase are the `*_hardened_v1.*` outputs.

## Strategic context

This is source coverage intelligence only. It prepares reusable parser-family and source-config decisions; it does not perform matching, client alerts, advisor email, n8n orchestration, dashboards, database work, migrations, property inventory parsing, or an apply-to-all Realworks rollout.

## Scope and constraints

This phase adds and hardens:

- `scraper/src/domek_wonen/sources/coverage_census.py`
- `scripts/run_noord_brabant_coverage_source_census.py`
- `tests/test_noord_brabant_coverage_source_census.py`

The runner writes local generated CSV/XLSX artifacts under `tmp/generated/`. Those artifacts are intentionally not committed.

It does not modify `data/raw`, use Funda or Pararius operationally, persist raw HTML/JSON, copy long descriptions, download images, use browser automation, use proxies or bypass controls, use an LLM in runtime, create a parser per makelaar, or change global eligibility.

## Local evidence inputs

The census reads local evidence from:

- `data/processed/sources_seed_noord_brabant.csv`
- `data/discovery/reference/property_discovery_source_overrides.csv`
- `data/discovery/processed/sources_seed_with_gemeente.csv`
- `data/discovery/platform_fingerprint/platform_fingerprint_results.csv`
- `data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv`

Rows without a normalized official source domain are not silently dropped into the operational master. They are written to the `Missing Domain Queue` sheet with search/query follow-up context.

## Coverage model

Office location, coverage location, and accepted listing-index location are separate fields:

- Office location is known only when local evidence explicitly provides office city/gemeente/province.
- Coverage location is the city/gemeente/province where evidence says the source may publish listings.
- Accepted aanbod location is represented only by `accepted_aanbod_url`.

The master no longer has an ambiguous `aanbod_url` column. It writes `accepted_aanbod_url`, raw local candidates, rejected-candidate summaries, and location status fields separately.

Because the available local evidence does not explicitly identify office locations for the deduped source rows, the hardened run reports `office_location_unknown_count=323`. Outside-office coverage is therefore reported as `outside_office_sources_needing_review_count=323`, not as a confirmed outside-office count.

## Investigation loop

The bounded pass names are:

- `pass_1_local_evidence`
- `pass_2_homepage_links`
- `pass_3_derive_listing_index_from_detail_url`
- `pass_4_sitemap`
- `pass_5_common_paths`
- `pass_6_family_fingerprint`
- `pass_7_final_terminal_classification`

The runner defaults to local evidence only. Live HTTP is opt-in with `--allow-live-http`, sequential, capped per domain, standard-library only, and guarded by `robots_gate.can_fetch(domain, path)` before each fetch.

## Aanbod URL hardening

Accepted operational URLs now require an official-domain listing-index candidate. The census rejects:

- Funda and Pararius operational URLs.
- Off-domain URLs.
- Homepage-only candidates without listing-index evidence.
- Property detail URLs such as `/koop/huis-*`, `/koop/appartement-*`, `/huur/huis-*`, and Realworks detail paths under `/aanbod/woningaanbod/.../koop/huis-*`.

When a Realworks-style detail URL is found and live fetching is enabled, the census derives conservative listing-index candidates such as `/aanbod/woningaanbod/<plaats>/koop` and validates those instead of promoting the detail URL.

If the same URL is rejected during an earlier pass but later accepted by stronger evidence, the candidate evidence is reconciled so the workbook does not show the same final URL as both rejected and accepted.

## Parser-family hardening

The census recognizes Realworks, OGonline XHR, WordPress JSON/static, Kolibri, Skarabee, iframe vendor, custom HTML, custom XHR, and custom JS app signals. It uses technical delivery classifications when exact vendor evidence is not available.

Realworks is no longer accepted from `platform_guess=realworks` alone. A `realworks_public` final classification requires strong structural evidence, such as a Realworks listing-index URL shape or static Realworks listing markers. Weak Realworks candidates are reclassified and recorded in `Realworks Verification` and `Family Conflicts`.

KIN is explicitly resolved away from stale Realworks evidence. The hardened run keeps `kinmakelaars.nl` as `ogonline_xhr` with accepted URL `http://kinmakelaars.nl/aanbod/wonen/te-koop`.

Custom JS app rows are re-fingerprinted before finalization. The hardened live run reduced the previous broad `custom_js_app` bucket from `126` rows to `9` rows and records refingerprint attempts in `Custom JS Refingerprint`.

## Quality gates

Hard gates in the hardened run:

- `operational_unknown_family_count = 0`
- `missing_aanbod_url_without_terminal_reason_count = 0`
- `rejected_candidate_used_as_master_aanbod_url_count = 0`
- `property_detail_url_as_aanbod_url_count = 0`
- `funda_or_pararius_operational_aanbod_url_count = 0`
- `realworks_without_strong_evidence_count = 0`
- `platform_guess_realworks_but_family_custom_js_app_unreviewed_count = 0`
- `kin_family_conflict_count = 0`
- `custom_js_app_without_fingerprint_attempt_count = 0`
- `gemeente_normalization_conflict_count = 0`

Reported review metrics:

- `missing_domain_queue_count = 136`
- `office_location_unknown_count = 323`
- `outside_office_sources_needing_review_count = 323`
- `review_queue_count = 5`

The final controlled live run passed all hard gates.

## Output artifacts

Generated locally:

- `tmp/generated/noord_brabant_coverage_source_census_hardened_v1.xlsx`
- `tmp/generated/noord_brabant_coverage_source_census_hardened_v1.csv`
- `tmp/generated/noord_brabant_coverage_source_census_hardened_v1_review_queue.csv`
- `tmp/generated/noord_brabant_coverage_source_census_hardened_v1_live_run.log`

Workbook sheets:

- `Master Sources`
- `Aanbod URL Evidence`
- `Family Fingerprints`
- `Investigation Attempts`
- `Coverage Matrix`
- `Realworks Candidates`
- `Realworks Verification`
- `OGonline Candidates`
- `Custom Needs Parser`
- `Custom JS Refingerprint`
- `Family Conflicts`
- `Blocked or Legal Review`
- `Duplicates`
- `Missing Domain Queue`
- `Normalization Issues`
- `Review Queue`
- `Quality Gates`

Note: Excel does not permit `/` in worksheet names, so the requested `Custom/Needs Parser` sheet is written as `Custom Needs Parser`.

## Results

Controlled live artifact run:

- total evidence rows: `1812`
- deduped operational sources: `323`
- missing-domain queue rows: `136`
- in-scope Noord-Brabant coverage sources: `323`
- review queue count: `5`
- hard quality gates passed: `true`

Original v1 parser-family distribution:

- `blocked_or_legal_review`: `5`
- `custom_js_app`: `126`
- `no_public_aanbod`: `140`
- `realworks_public`: `73`
- `wordpress_json`: `18`
- `wordpress_static`: `1`

Hardened live parser-family distribution:

- `blocked_or_legal_review`: `5`
- `custom_html`: `100`
- `custom_js_app`: `9`
- `custom_xhr`: `3`
- `iframe_vendor`: `6`
- `kolibri`: `1`
- `no_public_aanbod`: `58`
- `ogonline_xhr`: `4`
- `realworks_public`: `91`
- `skarabee`: `1`
- `wordpress_json`: `41`
- `wordpress_static`: `4`

Realworks verification:

- `verified`: `91`
- `rejected`: `64`

The hardened master contains no exact `aanbod_url` column, no accepted Funda/Pararius operational URL, and no accepted property-detail URL.

## Recommended next action

1. Use only the hardened workbook/CSV as the source-census evidence.
2. Treat verified `realworks_public` rows as candidates for a later Noord-Brabant Realworks audit.
3. Treat `custom_html`, `custom_js_app`, WordPress, iframe/vendor, OGonline, Kolibri, and Skarabee groups as parser-family/source-config planning inputs, not parser-per-makelaar work.
4. Resolve `Missing Domain Queue` rows before using missing-domain source evidence operationally.

## Source Completion & Scope Verification v1

Source Completion & Scope Verification adds a final bounded pass on top of the hardened census before merge. It exists
because the hardened census had strong parser-family gates, but still left manual-risk areas: missing-domain evidence,
unverified `no_public_aanbod`, accepted aanbod URLs whose path scope needed review, Realworks audit readiness, and
unknown office locations.

The explicit runner mode is:

```powershell
python scripts/run_noord_brabant_coverage_source_census.py --allow-live-http --completion-scope-verification --max-passes 8 --max-requests-per-domain 10 --timeout-seconds 15
```

The live pass remains controlled HTTP only. It is sequential, capped, uses a clear User-Agent, checks
`robots_gate.can_fetch(domain, path)` before each fetch, and writes only compact evidence previews. It does not persist
raw HTML/JSON.

### Added verification tables

- `Domain Resolution`: every Missing Domain Queue row receives a resolution attempt, confidence, evidence preview, and
  next action. Rows can resolve to an existing source when local name evidence matches; unresolved rows stay in manual
  domain research with an explicit reason.
- `No Public Verification`: `no_public_aanbod` rows record homepage, sitemap, and common-path attempt history before
  remaining confirmed no-public.
- `Aanbod Scope Check`: each accepted aanbod URL is classified as `confirmed_nb_scope`, `broad_official_index`,
  `official_scope_unclear`, or `needs_scope_review`. Out-of-scope-looking URLs are not silent; they carry review status
  and reason.
- `Realworks Audit Input`: verified Realworks candidates are separated into
  `ready_for_noord_brabant_realworks_audit` or `needs_manual_scope_check`. KIN remains `ogonline_xhr` and cannot enter
  the Realworks audit input.
- `Office Location Verification`: office location remains separate from coverage location. Missing office evidence is
  reported as unknown, not fabricated as Noord-Brabant.

### Added hard gates

- `missing_domain_without_resolution_attempt_count = 0`
- `no_public_without_full_attempt_history_count = 0`
- `accepted_aanbod_out_of_scope_unreviewed_count = 0`
- `realworks_audit_input_without_scope_confirmation_count = 0`
- `realworks_audit_input_kin_count = 0`
- `realworks_audit_input_property_detail_url_count = 0`
- `realworks_audit_input_without_accepted_aanbod_count = 0`
- `office_location_fabricated_count = 0`

### Live completion results

The live completion run produced:

- total evidence rows: `1812`
- deduped operational sources: `323`
- accepted aanbod URLs: `262`
- missing-domain initial rows: `136`
- missing-domain resolved rows: `6`
- missing-domain remaining rows: `130`, all with `manual_official_domain_research_required`
- `no_public_aanbod` confirmed rows: `56`
- office location unknown rows: `323`
- outside-office sources needing review: `323`
- verified Realworks rows: `91`
- Realworks ready for audit: `65`
- Realworks requiring manual scope check: `26`
- KIN final classification: `ogonline_xhr`
- accepted aanbod scope distribution: `27` confirmed NB scope, `158` broad official index, `77` needs scope review
- quality gates passed: `true`

Generated local artifacts:

- `tmp/generated/noord_brabant_source_completion_scope_verification_v1.xlsx`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v1.csv`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v1_review_queue.csv`
- `tmp/generated/noord_brabant_realworks_audit_input_v1.csv`
- `tmp/generated/noord_brabant_realworks_audit_input_reconciliation_v1.csv`

Generated artifacts remain local and must not be committed.

## Missing Domain External Resolution v1

Missing Domain External Resolution adds an explicit controlled mode after Source Completion:

```powershell
python scripts/run_noord_brabant_coverage_source_census.py --allow-live-http --completion-scope-verification --missing-domain-external-resolution --max-passes 8 --max-requests-per-domain 10 --timeout-seconds 15
```

The mode reads the Missing Domain Queue, attempts a bounded resolution for every row, and writes all outcomes with
attempt counts, candidate counts, evidence previews, reasons, and next actions. It first matches existing sources by
normalized name, alias, or raw id. If no existing source matches, it generates at most eight conservative candidate
domains from local domain hints and deterministic official-domain guesses.

Candidate verification is deliberately strict. Funda, Pararius, search/social pages, maps, directories, comparison
sites, and third-party portal domains are rejected as official domains. HTTP checks use only standard-library requests,
a clear User-Agent, request caps, and `robots_gate.can_fetch(domain, path)` before fetching. Root/homepage content must
show source-name or alias evidence plus makelaar/real-estate context; common contact and aanbod paths are checked only
after the candidate remains plausible. Evidence previews are capped and sanitized; raw HTML/JSON, long descriptions,
and images are not written.

Resolution statuses are `resolved_to_existing_source`, `resolved_to_new_source`, `confirmed_duplicate`,
`confirmed_inactive_or_no_longer_trading`, `confirmed_no_official_domain_found`, and
`needs_manual_domain_research`. Verified new domains are deduped by normalized domain before being added as source
candidates. New-source candidates start conservatively as no-public-aanbod until accepted aanbod URL and parser-family
verification can prove stronger operational readiness. Accepted aanbod URL checks continue to reject Funda/Pararius,
off-domain URLs, property-detail URLs, and third-party-only URLs.

Generated local artifacts:

- `tmp/generated/noord_brabant_missing_domain_external_resolution_v1.xlsx`
- `tmp/generated/noord_brabant_missing_domain_external_resolution_v1.csv`
- `tmp/generated/noord_brabant_missing_domain_external_resolution_v1_review_queue.csv`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v2.csv`
- `tmp/generated/noord_brabant_source_completion_scope_verification_v2.xlsx`

Added hard gates include unresolved rows without attempts, resolved third-party domains, resolved domains without
official evidence, duplicate domain creation, Funda/Pararius or property-detail accepted aanbod URLs, raw payload
markers, and long-description export.

### Realworks audit handoff repair

The first Noord-Brabant Realworks Audit v1 attempt found that the handoff CSV could be regenerated with an incomplete
schema: `coverage_province` and `parser_family_candidate` were missing from
`tmp/generated/noord_brabant_realworks_audit_input_v1.csv`. The source-completion master already had those fields, so
the defect was in the handoff producer, not in the Realworks parser or live audit.

The handoff producer now emits the canonical audit-input schema, including `coverage_province`,
`coverage_province_source`, `parser_family_candidate`, `root_url`, `source_quality_status`, `access_policy_status`, and
`family_confidence`. It also writes `tmp/generated/noord_brabant_realworks_audit_input_reconciliation_v1.csv`.

The current regenerated completion run reconciles to `88` verified Realworks rows: `62` ready audit inputs and `26`
`needs_manual_scope_check` exclusions. The previous documented `65` ready count is therefore stale for the current
source-completion run. The unexplained row-count delta gate is `realworks_audit_input_row_count_unexplained_delta = 0`.

## Constraints confirmation

No matching/client alerts/advisor email, no n8n/dashboard, no DB/migrations, no apply-to-all Realworks yet, no property inventory parsing, no `data/raw`, no Funda/Pararius operational source, no raw HTML/JSON, no long descriptions/images, no browser automation/proxies/bypass, no LLM runtime, no parser per makelaar, no global eligibility changes, no force push, and no merge to main.
