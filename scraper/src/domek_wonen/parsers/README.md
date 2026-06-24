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
to an already captured `ParserInput`. In v1 the only supported family is
`realworks_public`, which routes to `RealworksParserFamily` and returns a
`ParserFamilyResult`.

The runner is offline. It does not fetch pages, open browsers, probe robots live, or
decide Access Policy again. Access Policy and Delivery Fingerprint remain upstream;
the runner only respects `can_proceed_to_parser_family`, `delivery_mode`, and
`parser_family_candidate`.

Source-config runner integration, inventory state handling, and QA gate promotion are
later phases.
