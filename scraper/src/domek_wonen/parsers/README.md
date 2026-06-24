# Parsers Module

This module will own:

- parser families
- source configs
- normalized parser output

The architecture rule is simple: no parser per makelaar. Shared technical patterns belong in parser families, while domain-specific adjustments belong in source configs.

## Realworks Parser Family Stabilization v1

`realworks_family.py` is the first offline V4 parser-family layer for `realworks_public`.
It accepts already captured HTML through `ParserInput` and returns `ParserFamilyResult`
with `ParsedListing` rows. It does not fetch pages, open browsers, validate robots live,
or persist output.

The legacy Realworks parser remains under `properties/platform_parsers/realworks_parser.py`
for the property-discovery runtime. This V4 family keeps that runtime intact and only
mines the proven parsing direction: listing detail URLs, card-level address, city, price,
status, area, rooms, and evidence signals.

Runner integration, source configs, inventory state, stale-source handling, and QA gate
promotion are later phases.

## Parser Family Runner v1

`runner.py` selects a parser family from `DeliveryFingerprintResult` and applies it
to an already captured `ParserInput`. In v1 the supported families are
`realworks_public` and `ogonline_xhr`, which route to their offline parser-family
implementations and return a `ParserFamilyResult`.

The runner is offline. It does not fetch pages, open browsers, probe robots live, or
decide Access Policy again. Access Policy and Delivery Fingerprint remain upstream;
the runner only respects `can_proceed_to_parser_family`, `delivery_mode`, and
`parser_family_candidate`.

Source-config runner integration, inventory state handling, and QA gate promotion are
later phases.

## KIN OGonline XHR Parser Spike v1

`ogonline_xhr_family.py` is an offline parser spike for JSON responses shaped like
the OGonline XHR API observed on KIN. It accepts caller-provided JSON through
`ParserInput` and returns `ParsedListing` rows for docs with stable identity.

The fixtures are synthetic and stored under `tests/fixtures/parsers/`; no real live
JSON, captured HTML, API output, or generated artifact is committed. The parser does
not make HTTP requests, import browser tooling, validate robots live, or persist
inventory.

This spike maps stable detail URLs or fallback URLs, address fields, postcode, city,
price, sale/rent status, listing status, living area, rooms, bedrooms, property type,
energy label, bounded evidence, confidence, and review flags. Paginated source config
and a live runner remain later phases.

## OGonline XHR Runner Integration v1

`ParserFamilyRunner` now routes permitted `ogonline_xhr` fingerprints to
`OGonlineXHRParserFamily` using caller-provided JSON in `ParserInput`. The runner
still supports `realworks_public`, stays offline, makes no HTTP requests, and does
not use browser automation.

Source config handling and a paginated live runner remain later phases.

## KIN OGonline XHR Source Config v1

`source_config.py` defines the first offline source-config layer for KIN as an
`ogonline_xhr` source. The config records the OGonline API base URL, pagination
parameters, static query parameters, and JSON items path needed to build deterministic
API URLs and `ParserInput` objects from caller-provided JSON.

This layer does not make HTTP requests, call robots live, save real JSON, use browser
automation, or run pagination. A paginated live runner remains a later phase.
