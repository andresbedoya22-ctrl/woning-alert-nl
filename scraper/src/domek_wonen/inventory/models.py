from __future__ import annotations

from dataclasses import dataclass

from domek_wonen.qa.parser_output_gate import ParserFamilyQAResult, ParserListingQAResult


ALLOWED_CAPTURE_STATUSES = frozenset({"success", "failed", "partial", "stale"})


@dataclass(frozen=True, slots=True)
class InventoryListing:
    inventory_key: str
    source_id: str
    source_domain: str
    canonical_url: str
    address_raw: str = ""
    city: str = ""
    asking_price_eur: int | None = None
    transaction_type: str = "unknown"
    status: str = "unknown"
    living_area_m2: int | None = None
    rooms_count: int | None = None
    bedrooms_count: int | None = None
    property_type: str = ""
    energy_label: str = ""
    parser_family: str = ""
    confidence_score: float = 0.0
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    source_id: str
    source_domain: str
    captured_at: str
    listings: tuple[InventoryListing, ...]
    capture_status: str = "success"
    safe_to_compare_removals: bool = True
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.capture_status not in ALLOWED_CAPTURE_STATUSES:
            raise ValueError(f"Unsupported capture_status: {self.capture_status}")
        if self.capture_status != "success" and self.safe_to_compare_removals:
            object.__setattr__(self, "safe_to_compare_removals", False)


@dataclass(frozen=True, slots=True)
class InventoryDiff:
    source_id: str
    source_domain: str
    new_listings: tuple[InventoryListing, ...]
    removed_listings: tuple[InventoryListing, ...]
    unchanged_listings: tuple[InventoryListing, ...]
    changed_listings: tuple[InventoryListing, ...]
    safe_to_compare_removals: bool
    warnings: tuple[str, ...] = ()


def build_inventory_snapshot_from_qa(
    qa_result: ParserFamilyQAResult,
    captured_at: str,
    capture_status: str = "success",
    safe_to_compare_removals: bool = True,
) -> InventorySnapshot:
    if capture_status not in ALLOWED_CAPTURE_STATUSES:
        raise ValueError(f"Unsupported capture_status: {capture_status}")

    listings: list[InventoryListing] = []
    warnings = list(qa_result.warnings)

    for qa_listing in qa_result.clean_listings:
        if not qa_listing.normalized_key:
            warnings.append("missing_inventory_key")
            continue
        listings.append(_inventory_listing_from_qa(qa_listing, qa_result.parser_family))

    if capture_status != "success":
        safe_to_compare_removals = False

    return InventorySnapshot(
        source_id=qa_result.source_id,
        source_domain=qa_result.source_domain,
        captured_at=captured_at,
        listings=tuple(listings),
        capture_status=capture_status,
        safe_to_compare_removals=safe_to_compare_removals,
        warnings=tuple(warnings),
    )


def _inventory_listing_from_qa(
    qa_listing: ParserListingQAResult,
    parser_family: str,
) -> InventoryListing:
    listing = qa_listing.listing
    return InventoryListing(
        inventory_key=qa_listing.normalized_key,
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        canonical_url=listing.canonical_url,
        address_raw=listing.address_raw,
        city=listing.city,
        asking_price_eur=listing.asking_price_eur,
        transaction_type=listing.transaction_type,
        status=listing.status,
        living_area_m2=listing.living_area_m2,
        rooms_count=listing.rooms_count,
        bedrooms_count=listing.bedrooms_count,
        property_type=listing.property_type,
        energy_label=listing.energy_label,
        parser_family=parser_family,
        confidence_score=listing.confidence_score,
        evidence=listing.evidence,
    )
