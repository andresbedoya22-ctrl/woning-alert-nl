# QA Module

This module will own:

- quality gates
- transaction_type handling
- status handling
- address quality
- price sanity
- dedupe

It exists to separate clean inventory from rejected or review-needed records before anything reaches matching or advisor workflows.

## Parser Output QA Gate v1

`parser_output_gate.py` validates `ParserFamilyResult` objects before inventory. It classifies parser-produced
`ParsedListing` records into clean, review, and rejected buckets without making network requests, persisting
inventory, or doing global dedupe.

The gate uses an initial deterministic `normalized_key` for future inventory work. It prefers source domain plus
canonical URL, then source domain plus postcode and house number, then source domain plus raw address and city.
