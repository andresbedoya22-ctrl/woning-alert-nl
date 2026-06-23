# Inventory Module

This module will own:

- normalized listings
- snapshots
- diffs
- stale sources
- daily inventory state

Its responsibility is durable listing state over time. It must protect against false removals when a source fails and provide stable inputs for matching.
