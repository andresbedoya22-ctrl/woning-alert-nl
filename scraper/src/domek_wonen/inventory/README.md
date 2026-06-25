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

## Inventory Eligibility Gate v1

Inventory Eligibility Gate v1 is an offline layer between parser QA and active inventory. It consumes
`ParserFamilyQAResult`, allows only QA-clean listings to be considered for active inventory, and keeps QA review or
rejected listings in review.

The gate separates clean listings into `active_inventory`, `inactive_status`, `unsupported_transaction_type`,
`unsupported_property_type`, and `review`. Only `koop + beschikbaar + allowed_property_type` enters active inventory.
`onder_bod`, `verkocht`, `verhuurd`, unknown or empty status, unsupported or unknown transaction type, and empty or
unsupported property type do not enter active inventory.

This layer does not make HTTP requests, run live fetch, relax QA, modify matching, write generated artifacts, or change
n8n or dashboard behavior. Snapshot creation can be fed through `build_active_inventory_qa_result` so only eligible
active listings are passed to `build_inventory_snapshot_from_qa`.
