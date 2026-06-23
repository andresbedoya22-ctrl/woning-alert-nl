# Sources Module

## What Source Intelligence does

Source Intelligence is the deterministic conversion layer between legacy source data and future parser work.

In this phase it:

- loads CSV-based source evidence;
- normalizes domains, booleans, IDs, and basic counts;
- classifies conservative delivery-mode and parser-family candidates;
- builds measurable reports for prioritization and manual review.

## What it does not do

This module does not:

- make HTTP requests;
- probe robots live;
- scrape listing pages;
- implement parser families;
- change property-discovery runtime;
- decide final access policy runtime enforcement.

## Relationship to nearby phases

- `source_intelligence` turns existing evidence into a stable record set.
- `access_policy` will later formalize operational use decisions.
- `delivery_mode_fingerprint` will later improve evidence collection and confidence.

This module only prepares deterministic inputs for those later phases.

## CLI usage

```powershell
py -3.12 scripts/run_source_intelligence_report.py --input tests/fixtures/sources/source_intelligence_seed.csv
py -3.12 scripts/run_source_intelligence_report.py --input tests/fixtures/sources/source_intelligence_seed.csv --output tmp/source-intelligence-report.json
```

## Reports produced

The JSON report includes:

- `total_sources`
- `unique_domains`
- counts by `aanbod_url_status`, `access_status`, `detected_platform`, `delivery_mode`, `parser_family_candidate`, and `recommended_action`
- `manual_review_queue`
- `parser_family_priority`

The CLI also prints a compact stdout summary with top delivery modes, top parser families, and manual-review volume.

## Next step

The next focused phase is `Access Policy v1` or a richer `Delivery Mode Fingerprint v2`, not runtime parser expansion.
