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

## Access Policy v1

Access Policy v1 turns a `SourceIntelligenceRecord` into an explicit `AccessPolicyDecision`.
It decides whether a source can run production extraction, whether a research probe is still allowed,
which action is required, and which risk flags explain the decision.

It does not make HTTP requests, read `robots.txt` live, use Playwright, scrape pages, implement parser
families, or change property-discovery runtime behavior. It only evaluates evidence already present in
Source Intelligence fields.

The policy protects the pipeline by stopping Funda dependencies, Pararius dependencies without permission,
CAPTCHA, login walls, `403`, disabled sources, and legal-review records before parser-family work begins.
Allowed and limited sources may proceed only as deterministic policy decisions; unknown or researching
sources remain manual-review inputs.

Later phases should call this layer before delivery-mode fingerprinting, parser-family selection, and
source-config execution so blocked or permission-bound sources do not enter operational extraction.

## Delivery Mode Fingerprint v2

Delivery Mode Fingerprint v2 turns a `SourceIntelligenceRecord` into an explicit
`DeliveryFingerprintResult`. It calls Access Policy first, then classifies the delivery mode from
existing source-intelligence evidence such as platform hints, visible cards, JSON-LD, sitemap flags,
WordPress REST signals, iframe dependencies, CAPTCHA, login, and `403` markers.

This layer does not make network requests, read `robots.txt` live, use Playwright, scrape pages, or
execute parser families. Its output is a deterministic offline decision with confidence,
evidence signals, blocking signals, a recommended action, and a boolean that says whether the source
may proceed to parser-family work.

If Access Policy blocks production extraction, Delivery Mode Fingerprint v2 always sets
`can_proceed_to_parser_family` to `False`, even when technical parser-family signals are present.

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

## Legacy Source Intelligence Adapter v1

`legacy_source_adapter.py` converts existing offline legacy source artifacts into `SourceIntelligenceRecord`
objects. It is intended for local CSVs such as source masters, discovery outputs, source coverage files, and
platform fingerprint artifacts.

Supported legacy columns include `source_id`, `office_name`, `makelaar_name`, `source_name`, `root_domain`,
`domain`, `source_domain`, `website`, `homepage_url`, `website_url`, `aanbod_url`, `koopaanbod_url`,
`gemeente`, `city`, `province`, `legal_status`, `source_status`, `aanbod_url_quality`, `detected_platform`,
`platform`, `source_quality_status`, `source_quality_reason`, `source_origin`, `evidence`, and `notes`.
Missing columns are allowed.

The adapter does not make HTTP requests, probe robots live, open websites, use Playwright, scrape pages, or
change property-discovery runtime behavior. It only reads local CSV data.

The combined report flow is:

```text
legacy source CSV
-> SourceIntelligenceRecord
-> AccessPolicyDecision
-> DeliveryFingerprintResult
-> combined source intelligence report
```

Run it with:

```powershell
py -3.12 scripts/run_legacy_source_intelligence_report.py --input tests/fixtures/sources/legacy_source_master_seed.csv
py -3.12 scripts/run_legacy_source_intelligence_report.py --input data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv --output tmp/legacy-source-intelligence-report.json
```

The report includes source-intelligence counts, access-policy summary, delivery-fingerprint summary,
top parser-family candidates, manual-review queue, blocked sources, permission-required sources, and
production parser-ready sources.

## Next step

The next focused phase is `Access Policy v1` or a richer `Delivery Mode Fingerprint v2`, not runtime parser expansion.
