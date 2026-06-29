# Realworks Multi-source Validation v1

## Objective

Validate the reusable Realworks parser family end-to-end on at least two locally evidenced makelaar sources so the
family is not treated as Oldenkotte-specific.

## Strategic context

No matching/client alerts yet. Finish parser families first.

This phase validates the Realworks family before a broader Noord-Brabant audit. It does not start the full
Noord-Brabant inventory census.

## Scope and constraints

The run used local evidence only for source selection, standard-library HTTP through the controlled fetch helper, and
`robots_gate.can_fetch(domain, path)` before listing and detail fetches.

No matching, client alerts, advisor email, n8n, dashboard, DB, migrations, Noord-Brabant full census, Funda, Pararius,
browser automation, Playwright, Selenium, proxies, stealth, bypass, raw HTML/JSON persistence, long descriptions,
images, LLM extraction, parser per makelaar, global eligibility changes, force push, or `data/raw` changes were added.

## Source selection

The selector reads local evidence and keeps only rows with source id, domain, listing URL, Realworks delivery/parser
signals, and allowed or limited access status. It excludes Funda, Pararius, blocked, legal-review, permission-required,
login/CAPTCHA/403-style rows, missing domains, and missing listing URLs.

## Sources validated

| source_id | domain | listing_url | selection_reason |
| --- | --- | --- | --- |
| `oldenkotte.com__tilburg` | `oldenkotte.com` | `http://www.oldenkotte.com/aanbod/woningaanbod/koop` | Local processed Noord-Brabant seed row; valid koop aanbod URL and Realworks listing pattern. |
| `olden.nl__heusden` | `olden.nl` | `http://www.olden.nl/aanbod/woningaanbod` | Local processed Noord-Brabant seed row; valid aanbod URL and Realworks listing pattern. |

## Per-source results

Observed at: `2026-06-29T08:00:00Z`.

| source_id | validation_status | parser_total | parser_qa_clean | detail_attempted | detail_succeeded | detail_failed | facts_records_built | readiness_rows_built |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `oldenkotte.com__tilburg` | `passed_with_review_gaps` | 9 | 9 | 9 | 9 | 0 | 9 | 9 |
| `olden.nl__heusden` | `passed_with_review_gaps` | 10 | 10 | 10 | 8 | 2 | 8 | 8 |

## Parser metrics

Both sources produced QA-clean parser rows without source-specific parser code.

Oldenkotte: `9 total / 9 clean / 0 review / 0 rejected`.

Olden: `10 total / 10 clean / 0 review / 0 rejected`.

## Detail/facts metrics

Oldenkotte detail facts succeeded for all 9 attempted detail pages.

Olden detail facts succeeded for 8 of 10 attempted detail pages. Two detail fetch/extract attempts failed, but the
successful detail pages used the same Realworks facts/readiness path and produced usable rows.

## Readiness/export metrics

| source_id | client_ready | advisor_review | blocked | export_ready | export_review | export_blocked |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oldenkotte.com__tilburg` | 0 | 8 | 1 | 0 | 8 | 1 |
| `olden.nl__heusden` | 6 | 2 | 0 | 6 | 2 | 0 |

## Status/history policy results

Oldenkotte kept all 9 rows out of active inventory: 2 `store_active_candidate`, 6 `store_status_history`, and 1
`store_excluded_non_residential`.

Olden produced 5 active-inventory eligible rows and 3 non-active rows: 7 `store_active_candidate` and 1
`store_status_history`.

## Lifecycle/freshness results

Oldenkotte: `new_today=9`; lifecycle events were `new_listing=9`, `sold=5`, `under_offer=1`, and
`non_residential_excluded=1`.

Olden: `new_today=8`; lifecycle events were `new_listing=8` and `sold=1`.

No source-declared publication dates were usable in this run. `source_published_at_missing` remained explicit.

## Field gaps

Top Oldenkotte gaps: `source_published_at=9`, `vve_active=8`, `energy_label=6`, `bathrooms=3`, `bouwjaar=3`,
`parking=3`, `review:energy_label=3`.

Top Olden gaps: `source_published_at=8`, `vve_active=2`, `review:garage=1`.

## Warnings

Top Oldenkotte warnings: `missing_coordinates=9`, `description_not_stored=9`, `source_published_at_missing=9`,
`cv_ketel_ownership_not_clear=6`, `missing_vve_for_apartment=4`, `energy_label_not_explicit=3`.

Top Olden warnings: `missing_coordinates=8`, `description_not_stored=8`, `source_published_at_missing=8`,
`cv_ketel_ownership_not_clear=6`, `missing_vve_for_apartment=1`.

## Problem rows

Oldenkotte produced 9 problem rows, mostly due to review/export review status, missing publication dates, missing VvE
for apartments, review-only energy labels, inactive status-history rows, and one non-residential blocked row.

Olden produced 2 problem rows, driven by review gaps rather than parser-family failure.

## Family decision

`realworks_family_usable_for_broader_audit`

Both Oldenkotte control and Olden second makelaar validated with `passed_with_review_gaps`. The result supports using
the Realworks family for a broader bounded audit, while keeping review gaps visible.

## Recommendation

Proceed to a bounded broader Realworks audit before applying the family across Noord-Brabant. Do not start matching or
advisor alerts yet.

## Constraints confirmation

- No matching/client alerts/advisor email.
- No n8n/dashboard.
- No DB/migrations.
- No Noord-Brabant full census.
- No `data/raw`.
- No Funda/Pararius.
- No raw HTML/JSON.
- No long descriptions/images.
- No browser automation/proxies/bypass.
- No LLM.
- No parser per makelaar.
- No global eligibility changes.
- No force push.
