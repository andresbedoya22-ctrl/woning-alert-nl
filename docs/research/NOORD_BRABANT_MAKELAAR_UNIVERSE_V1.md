# Noord-Brabant Makelaar Universe v1

## Objective

Build a deterministic Noord-Brabant Makelaar Universe from manual Funda result-page observations without treating Funda
as an operational property source.

## Inputs

Required input:

```text
tmp/manual_inputs/funda_makelaar_names/funda_nb_makelaar_names_raw.csv
```

Optional local evidence inputs:

```text
tmp/generated/noord_brabant_source_completion_scope_verification_v2.csv
tmp/generated/noord_brabant_missing_domain_external_resolution_v1.csv
data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv
data/discovery/platform_fingerprint/platform_fingerprint_results.csv
data/processed/sources_seed_noord_brabant.csv
```

If optional inputs are missing, the runner reports them and continues with the available evidence.

## Scope and constraints

This phase is manual-input consolidation only. It does not open property detail pages, parse property facts, create an
operational Funda property source, persist raw HTML/JSON, download images, copy long descriptions, use browser
automation, use Playwright, use stealth/proxies, or change any `data/raw` artifact.

Funda remains observation-only here:

- names seen on result pages are allowed as manual evidence;
- properties are not imported;
- addresses, prices, photos, and descriptions are not used as core output data;
- no official domain is invented from Funda alone.

## Produced artifacts

The runner writes local/generated outputs only:

```text
tmp/generated/noord_brabant_makelaar_universe_v1.xlsx
tmp/generated/noord_brabant_makelaar_universe_v1.csv
tmp/generated/noord_brabant_makelaar_universe_v1_review_queue.csv
```

These artifacts must not be committed.

## Canonical fields

The Makelaar Universe exposes:

- stable makelaar id
- original display name
- conservative normalized name
- aliases and slogans seen on Funda
- city/province presence from Funda observations
- seen counts and page coverage
- existing source/master/domain matches when local evidence exists
- accepted aanbod URL and parser-family hints when already known
- conservative priority score and tier
- explicit manual-review and gap reasons

## Normalization rules

- lowercase for matching keys
- remove legal suffixes such as `B.V.`, `BV`, `N.V.`
- keep the original `display_name`
- split clear slogans and commercial labels after `,`, `|`, or ` - ` into aliases instead of merging them into the canonical name
- strip labels such as `NVM-QUALIS`, `Qualis`, `Funda-topmakelaar`, `via wie anders?!`, `beste makelaar in jouw regio`, and similar sales/rating text from the normalized key
- keep `Meerdere makelaars` as a generic bucket
- keep truncated names in manual review
- avoid weak over-merges for similar-but-not-identical names

## Matching strategy

Matching is conservative and local-only:

1. exact normalized-name match against source completion, source master, and seed artifacts
2. controlled brand fallback only when the observed row reduces to a strong local brand key and no exact branch-level match exists
3. domain/source-id enrichment when that exact or strong brand match already resolves locally
4. missing-domain resolution reuse when a local resolution file already exists
5. multiple equally strong candidates stay in manual review

Third-party guardrails:

- `official_domain` must never promote `funda.nl`, `pararius.nl`, social-media domains, search domains, maps domains, or similar third-party portals/directories
- `official_aanbod_url` must never accept Funda/Pararius URLs as operational aanbod evidence
- third-party portal/domain evidence may remain visible only as rejected/manual-review context, not as accepted official source data

## Priority strategy

Higher priority goes to makelaars that:

- appear in Tilburg, Den Bosch, Breda, or Eindhoven
- appear many times across Funda result pages
- already have an official domain
- already have an accepted official aanbod URL
- already have a known parser family candidate

Lower priority goes to:

- `Meerdere makelaars`
- truncated names
- ambiguous matches
- rows with no official-domain evidence

Priority tiers:

- `P0_city_critical`
- `P1_high`
- `P2_medium`
- `P3_low`
- `manual_review`

## Quality gates

Hard zero-count gates:

- `makelaar_universe_rows_without_name_count`
- `duplicate_high_confidence_makelaar_count`
- `funda_property_detail_extracted_count`
- `funda_operational_property_source_count`
- `raw_html_json_persisted_count`
- `long_descriptions_exported_count`
- `browser_automation_used_count`

## CLI

```powershell
$env:PYTHONPATH="scraper/src"
python scripts/run_noord_brabant_makelaar_universe.py
```

The runner prints:

- effective input path
- imported raw row count
- deduped makelaar count
- review queue count
- output paths
- missing optional inputs
- quality-gate metrics

## Workbook layout

Workbook sheets:

- `Makelaar Universe`
- `Review Queue`
- `Per City Counts`
- `Quality Gates`
- `Run Summary`

## Recommended next action

Use this universe as a bounded manual-input bridge into source completion and source-intelligence follow-up, not as an
operational portal ingestion path.
