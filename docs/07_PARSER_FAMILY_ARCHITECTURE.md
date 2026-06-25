# Parser Family Architecture

## Why parser families exist

The repo should not create one parser per makelaar. Many makelaars expose listings through the same technical platform or content pattern. The correct abstraction is a parser family plus a source config.

## Parser family interface

A parser family should define:

- required evidence and access assumptions;
- accepted input surfaces such as HTML cards, JSON-LD, public JSON, or sitemaps;
- config schema;
- normalized output contract;
- recoverable errors vs blocking errors;
- test fixture expectations.

## Source config

A source config carries domain-specific details such as:

- card selectors;
- detail selectors;
- known JSON paths;
- pagination hints;
- transaction-type defaults;
- status normalization rules;
- city or geography hints;
- expected listing-url patterns.

## How one family serves many sources

- The family owns shared parsing logic.
- The config owns the source-specific mapping.
- New domains should first try config-only onboarding.
- New family code should be rare and justified by repeated technical patterns.

## Example config concepts

- `realworks_public`: card selector, detail URL selector, price field mapping.
- `html_cards`: repeated card selectors, pagination selector, status badge rules.
- `json_ld`: JSON-LD block selection and field path mapping.
- `xhr_json`: endpoint signature, response path mapping, pagination fields.

## Initial priority order

1. Source Intelligence Conversion
2. Realworks stabilization
3. OGonline/XHR stabilization
4. WordPress/static cards config runner
5. JSON-LD
6. sitemap/detail
7. Kolibri research spike
8. email alerts
