# Inventory Module

This module will own:

- normalized listings
- snapshots
- diffs
- stale sources
- daily inventory state

Its responsibility is durable listing state over time. It must protect against false removals when a source fails and provide stable inputs for matching.

## Inventory Core v1

Inventory Core v1 consumes only `ParserFamilyQAResult.clean_listings`. Listings in `review_listings` or
`rejected_listings` do not enter inventory state.

The core creates source-scoped offline snapshots and compares snapshots for new, removed, unchanged, and changed
listings. It does not make network requests, use browser automation, persist to a database, or write generated
run artifacts.

Stale inventory behavior is preserved by carrying `safe_to_compare_removals`. When a capture fails, is partial, or
is stale, `safe_to_compare_removals=false` prevents false removals from being reported while the last successful
inventory remains the comparison reference for a later trusted capture.
