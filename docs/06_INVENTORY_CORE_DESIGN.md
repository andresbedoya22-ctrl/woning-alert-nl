# Inventory Core Design

## Normalized listing

A normalized listing is the minimum canonical record produced by a parser family after policy approval. It should capture source identity, listing identity, transaction type, status, address-quality signals, pricing, URLs, timestamps, and enough evidence to support QA and diffing.

## Inventory item

An inventory item is the durable tracked state of a listing across runs. It combines:

- normalized listing identity;
- source identity;
- canonical comparison keys;
- last successful snapshot state;
- QA status;
- stale-source markers;
- change history.

## Daily snapshot

A daily snapshot is the set of normalized listings produced for a source on a given run. Snapshots must be source-scoped and timestamped so that one source failure does not contaminate another source.

## Diff engine

Required diff outputs:

- `new`
- `removed`
- `price_changed`
- `status_changed`
- `unchanged`

The diff engine must compare only against the last successful snapshot for that source when removals are considered safe.

## Stale source rule

If a source fails, mark the source snapshot stale and set `safe_to_compare_removals=false`. Keep the last successful inventory as reference state. Do not infer true removals from a failed source run.

## Core safety rule

Do not delete inventory simply because a source returned fewer rows during a blocked, partial, or failed run. Removals require a trustworthy comparison baseline.
