# QA And Normalization Gates

## Purpose

QA gates decide whether a normalized listing is clean inventory, rejected inventory, or `needs_review`.

## Required separations

- `transaction_type` must be separate from listing `status`.
- koop and huur logic must stay separate.
- `beschikbaar`, `onder bod`, and `verkocht` must not collapse into one state.

## Gate categories

### Transaction type

- classify koop vs huur explicitly;
- reject mixed or unknown values unless the source is intentionally dual-mode and clearly tagged.

### Status

- keep `available`, `under_offer`, and `sold` distinct;
- map ambiguous badges to `needs_review` rather than guessing.

### Price sanity

- reject impossible or empty prices when price is expected;
- flag suspicious values for review rather than silently normalizing bad data.

### Address quality

- require enough address signal for matching and dedupe;
- tolerate partial address only when the source legitimately withholds more detail and the workflow can handle it.

### Duplicate keys

- use stable comparison keys based on source, listing URL, normalized address, and other canonical hints;
- reject duplicate collisions that cannot be safely resolved.

## Future enrichment

- BAG and PDOK remain future enrichment layers, not prerequisites for this architecture reset.

## Output states

- `clean_inventory`
- `rejected_inventory`
- `needs_review`
