# Noord-Brabant Realworks Audit v1

## Objective

Audit the reusable `realworks_public` parser family across the verified Noord-Brabant Realworks handoff set before any
matching, advisor email, n8n, dashboard, or DB work.

## Strategic context

This phase sits after Source Completion & Scope Verification v1 and before any operational inventory or matching
promotion. It validates whether the family-level Realworks parser, QA gate, detail facts extractor, readiness rows, and
lifecycle fields can run across the provincial ready set without makelaar-specific parsers.

## Input source

The only allowed input is:

```text
tmp/generated/noord_brabant_realworks_audit_input_v1.csv
```

The runner validates this CSV strictly before live work. It must contain only rows with
`audit_input_status=ready_for_noord_brabant_realworks_audit`, `parser_family_candidate=realworks_public`,
`realworks_verification_status=verified`, and a present official-domain `accepted_aanbod_url`.

## Why only 65 sources

The previous completion run separated the 91 verified Realworks sources into 65 ready audit inputs and 26 manual scope
checks. This audit is intentionally limited to the 65 ready rows. KIN, unclear scope rows, missing accepted URL rows,
property-detail URLs, Funda/Pararius URLs, and blocked/legal/manual-review rows are hard-gated out.

## Scope and constraints

This is a bounded audit only. It does not create matching, client alerts, advisor emails, n8n flows, dashboards, DB
state, migrations, full property inventory, `data/raw` writes, raw HTML/JSON persistence, long-description export,
image downloads, browser automation, proxies, bypass logic, LLM runtime, parser-per-makelaar code, or global eligibility
changes.

## Audit runner

The CLI is:

```powershell
python scripts/run_noord_brabant_realworks_audit.py `
  --input-csv tmp/generated/noord_brabant_realworks_audit_input_v1.csv `
  --output-workbook tmp/generated/noord_brabant_realworks_audit_v1.xlsx `
  --output-summary tmp/generated/noord_brabant_realworks_audit_v1_summary.csv `
  --output-problem-sources tmp/generated/noord_brabant_realworks_audit_v1_problem_sources.csv `
  --max-sources 65 `
  --max-listings-per-source 15 `
  --max-detail-per-source 10 `
  --timeout-seconds 15 `
  --runtime-budget-seconds 1800
```

Execution is sequential and bounded. The runner delegates live page handling to the existing controlled Realworks
readiness path.

## Source-level validation

Input validation rejects missing files, empty rows, row-count mismatch, non-ready rows, non-Realworks rows, KIN rows,
missing accepted URLs, property-detail accepted URLs, Funda/Pararius URLs, off-domain URLs, and duplicate
`domain + accepted_aanbod_url` rows.

## Parser and QA path

Each source reuses the existing Realworks readiness runner, which checks `robots_gate.can_fetch(domain, path)` before
listing and detail fetches, fetches through the standard-library controlled HTTP helper, runs `ParserFamilyRunner`, and
then runs `qa_parser_family_result`.

## Detail facts and readiness path

QA-clean listings are capped per source, detail pages are robots-checked before fetch, detail HTML remains in memory,
and `extract_realworks_property_facts_for_listing` builds compact normalized facts. Readiness rows expose quality,
export readiness, status/lifecycle, field gaps, warnings, and active-inventory eligibility signals without sending rows
to matching.

## Workbook artifacts

The workbook path is caller-provided, normally:

```text
tmp/generated/noord_brabant_realworks_audit_v1.xlsx
```

Required sheets are `Source Summary`, `Realworks Properties`, `Field Gaps`, `Warnings`, `Problem Sources`,
`Parser Failure Patterns`, `Access Policy`, `Audit Input`, `Family Audit Decision`, and `Manual Verification`.

## Source metrics

Per-source metrics include fetch status, robots/access status, parser totals, QA clean/review/rejected counts, detail
attempt/success/failure counts, readiness rows, export ready/review/blocked counts, active-inventory eligibility,
inactive/non-residential counts, top warning, validation status, decision, and recommended next action.

## Field gaps

Field gaps aggregate readiness field completion and row-level missing/review fields. Known expected review areas include
postcode, coordinates, source publication dates, VvE, energy labels, and heating/hot-water normalization depending on
source detail completeness.

## Failure patterns

The audit records compact source-level patterns such as `no_current_listings`, `parser_zero_qa_clean`,
`detail_systemic_failure`, `blocked_by_robots`, `listing_fetch_failed`, and Realworks parser warnings. Repeated parser
or detail failures are treated as hardening signals.

## Family decision

Possible decisions are:

- `realworks_ready_for_nb_family_coverage`
- `realworks_partially_ready_with_exclusions`
- `realworks_needs_hardening_v2`
- `blocked_by_access_policy`
- `insufficient_successful_sources`

The decision includes confidence, reasons, recommended next action, source exclusions, and hardening targets.

## Recommended next action

If the family is ready, merge after manual workbook review and keep matching out of scope. If failures are systemic,
open Realworks Hardening v2. If failures are isolated, keep exclusions/review rows explicit and rerun those sources
after access or source-state review.

## Constraints confirmation

No matching/client alerts/advisor email, no n8n/dashboard, no DB/migrations, no full property inventory, no `data/raw`,
no Funda/Pararius operational source, no raw HTML/JSON, no long descriptions/images, no browser automation/proxies/bypass,
no LLM runtime, no parser per makelaar, no global eligibility changes, no force push, and no merge to main.
