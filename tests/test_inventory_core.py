from pathlib import Path
import sys
from dataclasses import replace


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.inventory import (  # noqa: E402
    InventoryListing,
    InventorySnapshot,
    build_inventory_snapshot_from_qa,
    diff_inventory_snapshots,
)
from domek_wonen.parsers import ParsedListing, ParserFamilyResult, ParserInput, parse_realworks_listing_page  # noqa: E402
from domek_wonen.qa import ParserFamilyQAResult, ParserListingQAResult, qa_parser_family_result  # noqa: E402


def _parsed_listing(**overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="example-source",
        source_domain="example.nl",
        canonical_url="https://example.nl/aanbod/woning-1",
        address_raw="Zonnelaan 12",
        street="Zonnelaan",
        house_number="12",
        postcode="4811AA",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        living_area_m2=118,
        rooms_count=5,
        bedrooms_count=3,
        property_type="house",
        energy_label="A",
        evidence=("fixture",),
        confidence_score=0.95,
    )
    return replace(listing, **overrides)


def _qa_listing(
    key: str,
    *,
    qa_status: str = "clean",
    listing: ParsedListing | None = None,
) -> ParserListingQAResult:
    return ParserListingQAResult(
        listing=listing or _parsed_listing(),
        qa_status=qa_status,
        normalized_key=key,
    )


def _qa_result(
    *,
    clean: tuple[ParserListingQAResult, ...] = (),
    review: tuple[ParserListingQAResult, ...] = (),
    rejected: tuple[ParserListingQAResult, ...] = (),
    warnings: tuple[str, ...] = (),
) -> ParserFamilyQAResult:
    return ParserFamilyQAResult(
        parser_family="test_family",
        source_id="example-source",
        source_domain="example.nl",
        clean_listings=clean,
        review_listings=review,
        rejected_listings=rejected,
        total_count=len(clean) + len(review) + len(rejected),
        clean_count=len(clean),
        review_count=len(review),
        rejected_count=len(rejected),
        warnings=warnings,
    )


def _inventory_listing(key: str, **overrides: object) -> InventoryListing:
    listing = InventoryListing(
        inventory_key=key,
        source_id="example-source",
        source_domain="example.nl",
        canonical_url=f"https://example.nl/{key}",
        address_raw="Zonnelaan 12",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        living_area_m2=118,
        rooms_count=5,
        bedrooms_count=3,
        property_type="house",
        energy_label="A",
        parser_family="test_family",
        confidence_score=0.95,
        evidence=("fixture",),
    )
    return replace(listing, **overrides)


def _snapshot(
    *listings: InventoryListing,
    safe_to_compare_removals: bool = True,
    capture_status: str = "success",
    warnings: tuple[str, ...] = (),
) -> InventorySnapshot:
    return InventorySnapshot(
        source_id="example-source",
        source_domain="example.nl",
        captured_at="2026-06-24T12:00:00Z",
        listings=tuple(listings),
        capture_status=capture_status,
        safe_to_compare_removals=safe_to_compare_removals,
        warnings=warnings,
    )


def test_build_inventory_snapshot_from_qa_consumes_only_clean_listings() -> None:
    clean_listing = _qa_listing("example.nl|clean")
    qa_result = _qa_result(
        clean=(clean_listing,),
        review=(_qa_listing("example.nl|review", qa_status="needs_review"),),
        rejected=(_qa_listing("example.nl|rejected", qa_status="rejected"),),
    )

    snapshot = build_inventory_snapshot_from_qa(qa_result, "2026-06-24T12:00:00Z")

    assert [listing.inventory_key for listing in snapshot.listings] == ["example.nl|clean"]


def test_inventory_key_comes_from_normalized_key() -> None:
    qa_result = _qa_result(clean=(_qa_listing("example.nl|normalized-key"),))

    snapshot = build_inventory_snapshot_from_qa(qa_result, "2026-06-24T12:00:00Z")

    assert snapshot.listings[0].inventory_key == "example.nl|normalized-key"


def test_missing_normalized_key_is_omitted_with_warning() -> None:
    qa_result = _qa_result(clean=(_qa_listing(""),), warnings=("parser_warning",))

    snapshot = build_inventory_snapshot_from_qa(qa_result, "2026-06-24T12:00:00Z")

    assert snapshot.listings == ()
    assert snapshot.warnings == ("parser_warning", "missing_inventory_key")


def test_capture_status_failed_forces_safe_to_compare_removals_false() -> None:
    qa_result = _qa_result(clean=(_qa_listing("example.nl|clean"),))

    snapshot = build_inventory_snapshot_from_qa(
        qa_result,
        "2026-06-24T12:00:00Z",
        capture_status="failed",
        safe_to_compare_removals=True,
    )

    assert snapshot.capture_status == "failed"
    assert snapshot.safe_to_compare_removals is False


def test_snapshot_preserves_qa_warnings() -> None:
    qa_result = _qa_result(
        clean=(_qa_listing("example.nl|clean"),),
        warnings=("parser_warning",),
    )

    snapshot = build_inventory_snapshot_from_qa(qa_result, "2026-06-24T12:00:00Z")

    assert snapshot.warnings == ("parser_warning",)


def test_realworks_qa_clean_listings_flow_into_inventory_snapshot() -> None:
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "parsers" / "realworks_listing_fixture.html").read_text(
        encoding="utf-8"
    )
    parser_result = parse_realworks_listing_page(
        ParserInput(
            source_id="example-realworks",
            source_domain="example.nl",
            source_url="https://example.nl/aanbod/woningaanbod",
            content=fixture_html,
        )
    )

    snapshot = build_inventory_snapshot_from_qa(
        qa_parser_family_result(parser_result),
        "2026-06-24T12:00:00Z",
    )

    assert len(snapshot.listings) == 2
    assert {listing.parser_family for listing in snapshot.listings} == {"realworks_public"}


def test_previous_none_produces_all_current_listings_as_new() -> None:
    current = _snapshot(_inventory_listing("one"), _inventory_listing("two"))

    diff = diff_inventory_snapshots(None, current)

    assert [listing.inventory_key for listing in diff.new_listings] == ["one", "two"]
    assert diff.removed_listings == ()
    assert diff.unchanged_listings == ()
    assert diff.changed_listings == ()


def test_listing_present_without_changes_is_unchanged() -> None:
    listing = _inventory_listing("same")

    diff = diff_inventory_snapshots(_snapshot(listing), _snapshot(listing))

    assert diff.unchanged_listings == (listing,)
    assert diff.changed_listings == ()


def test_new_listing_is_reported_as_new() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("existing")),
        _snapshot(_inventory_listing("existing"), _inventory_listing("new")),
    )

    assert [listing.inventory_key for listing in diff.new_listings] == ["new"]


def test_absent_listing_is_removed_when_removals_are_safe() -> None:
    removed = _inventory_listing("removed")

    diff = diff_inventory_snapshots(
        _snapshot(removed, _inventory_listing("kept")),
        _snapshot(_inventory_listing("kept")),
    )

    assert diff.removed_listings == (removed,)


def test_absent_listing_is_not_removed_when_removals_are_unsafe() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("removed"), _inventory_listing("kept")),
        _snapshot(_inventory_listing("kept"), safe_to_compare_removals=False),
    )

    assert diff.removed_listings == ()


def test_asking_price_change_is_reported_as_changed() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("changed", asking_price_eur=425000)),
        _snapshot(_inventory_listing("changed", asking_price_eur=435000)),
    )

    assert [listing.inventory_key for listing in diff.changed_listings] == ["changed"]


def test_status_change_is_reported_as_changed() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("changed", status="beschikbaar")),
        _snapshot(_inventory_listing("changed", status="onder_bod")),
    )

    assert [listing.inventory_key for listing in diff.changed_listings] == ["changed"]


def test_unsafe_to_compare_removals_warning_is_added_when_applicable() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("removed")),
        _snapshot(safe_to_compare_removals=False),
    )

    assert "unsafe_to_compare_removals" in diff.warnings


def test_capture_status_failed_snapshot_blocks_removed_listings() -> None:
    diff = diff_inventory_snapshots(
        _snapshot(_inventory_listing("removed")),
        _snapshot(capture_status="failed"),
    )

    assert diff.safe_to_compare_removals is False
    assert diff.removed_listings == ()
    assert "unsafe_to_compare_removals" in diff.warnings
