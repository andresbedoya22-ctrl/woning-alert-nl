# Realworks Broader Bounded Audit v1

## Objective

Validate the reusable Realworks family with 2-3 additional Realworks makelaars beyond Oldenkotte and Olden, using a manual-verification-ready Excel workbook.

## Strategic context

No matching/client alerts yet. Finish parser-family validation first.

## Scope and constraints

This phase validates whether the existing reusable Realworks parser-family, QA, detail facts, readiness, lifecycle, workbook, and summary paths work across additional locally evidenced Realworks makelaars. It is a bounded audit phase only, not a production rollout.

## Sources audited

- `alstedevanmierlomakelaardij.nl__tilburg`
- `cvda.nl__tilburg`
- `hansvanberkel.nl__tilburg`

## Live audit results

| source_id | parser_total | QA clean | detail_succeeded | rows_built |
| --- | ---: | ---: | ---: | ---: |
| `alstedevanmierlomakelaardij.nl__tilburg` | 10 | 10 | 10 | 10 |
| `cvda.nl__tilburg` | 10 | 10 | 10 | 10 |
| `hansvanberkel.nl__tilburg` | 10 | 9 | 9 | 9 |

Manual verification row count: `29`.

## Manual-verification workbook

Path: `tmp/generated/realworks_broader_bounded_audit_v1.xlsx`

The workbook was generated locally and is not committed. It contains `29` manual verification rows, includes property links, and includes `manual_check_result` and `manual_check_notes` columns for Andres' review.

Summary CSV path: `tmp/generated/realworks_broader_bounded_audit_v1_summary.csv`

## Field gaps

- coordinates
- `source_published_at`
- VvE
- heating/hot-water normalization

## Family audit decision

Decision: `realworks_ready_for_noord_brabant_realworks_audit`

Meaning: Realworks is ready for a bounded Noord-Brabant Realworks audit, not yet matching/client alerts.

## Recommendation

- Andres should manually review the workbook.
- Merge if the review confirms the Excel is reliable.
- Then run a Noord-Brabant Realworks audit after source inventory confirms all Realworks makelaars.

## Constraints confirmation

This phase does not add matching, client alerts, advisor email, n8n, dashboard, DB, migrations, Noord-Brabant full census, apply-to-all Realworks execution, `data/raw` changes, Funda/Pararius work, raw HTML/JSON persistence, long descriptions, images, browser automation, proxies, bypass behavior, LLM use, parser-per-makelaar logic, or global eligibility changes.
