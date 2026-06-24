from __future__ import annotations

from .models import InventoryDiff, InventoryListing, InventorySnapshot


_CHANGE_FIELDS = (
    "asking_price_eur",
    "status",
    "transaction_type",
    "living_area_m2",
    "rooms_count",
    "bedrooms_count",
    "property_type",
    "energy_label",
)


def diff_inventory_snapshots(
    previous: InventorySnapshot | None,
    current: InventorySnapshot,
) -> InventoryDiff:
    warnings = list(current.warnings)
    if current.safe_to_compare_removals is False:
        warnings.append("unsafe_to_compare_removals")

    if previous is None:
        return InventoryDiff(
            source_id=current.source_id,
            source_domain=current.source_domain,
            new_listings=current.listings,
            removed_listings=(),
            unchanged_listings=(),
            changed_listings=(),
            safe_to_compare_removals=current.safe_to_compare_removals,
            warnings=tuple(warnings),
        )

    previous_by_key = _listings_by_key(previous.listings)
    current_by_key = _listings_by_key(current.listings)

    new_listings = tuple(
        listing for listing in current.listings if listing.inventory_key not in previous_by_key
    )
    removed_listings = (
        tuple(listing for listing in previous.listings if listing.inventory_key not in current_by_key)
        if current.safe_to_compare_removals
        else ()
    )

    unchanged: list[InventoryListing] = []
    changed: list[InventoryListing] = []
    for listing in current.listings:
        previous_listing = previous_by_key.get(listing.inventory_key)
        if previous_listing is None:
            continue
        if _has_relevant_change(previous_listing, listing):
            changed.append(listing)
        else:
            unchanged.append(listing)

    return InventoryDiff(
        source_id=current.source_id,
        source_domain=current.source_domain,
        new_listings=new_listings,
        removed_listings=removed_listings,
        unchanged_listings=tuple(unchanged),
        changed_listings=tuple(changed),
        safe_to_compare_removals=current.safe_to_compare_removals,
        warnings=tuple(warnings),
    )


def _listings_by_key(listings: tuple[InventoryListing, ...]) -> dict[str, InventoryListing]:
    return {listing.inventory_key: listing for listing in listings}


def _has_relevant_change(previous: InventoryListing, current: InventoryListing) -> bool:
    return any(getattr(previous, field) != getattr(current, field) for field in _CHANGE_FIELDS)
