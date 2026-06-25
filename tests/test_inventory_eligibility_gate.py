from pathlib import Path
import ast
from dataclasses import replace
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.inventory import (  # noqa: E402
    build_active_inventory_qa_result,
    build_inventory_snapshot_from_qa,
    evaluate_inventory_eligibility,
)
from domek_wonen.parsers import ParsedListing, ParserFamilyResult, ParserInput, parse_ogonline_xhr_api_response  # noqa: E402
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


def _single_clean_result(**listing_overrides: object):
    qa_result = _qa_result(
        clean=(
            _qa_listing(
                "example.nl|listing",
                listing=_parsed_listing(**listing_overrides),
            ),
        )
    )
    return evaluate_inventory_eligibility(qa_result)


def test_clean_koop_beschikbaar_house_enters_active_inventory() -> None:
    result = _single_clean_result(property_type="house")

    assert result.active_count == 1
    assert result.active_inventory[0].decision == "active_inventory"
    assert result.active_inventory[0].reasons == ("status_available", "property_type_allowed")


def test_clean_koop_beschikbaar_apartment_enters_active_inventory() -> None:
    result = _single_clean_result(property_type="apartment")

    assert result.active_count == 1
    assert result.active_inventory[0].listing.property_type == "apartment"


def test_clean_koop_onder_bod_goes_to_inactive_status() -> None:
    result = _single_clean_result(status="onder_bod")

    assert result.active_count == 0
    assert result.inactive_status_count == 1
    assert result.inactive_status[0].reasons == ("status_inactive",)


def test_clean_koop_verkocht_goes_to_inactive_status() -> None:
    result = _single_clean_result(status="verkocht")

    assert result.inactive_status_count == 1
    assert result.active_count == 0


def test_clean_koop_verhuurd_goes_to_inactive_status() -> None:
    result = _single_clean_result(status="verhuurd")

    assert result.inactive_status_count == 1
    assert result.active_count == 0


def test_clean_huur_goes_to_unsupported_transaction_type() -> None:
    result = _single_clean_result(transaction_type="huur")

    assert result.unsupported_transaction_type_count == 1
    assert result.unsupported_transaction_type[0].reasons == ("transaction_type_unsupported",)
    assert result.active_count == 0


def test_clean_unknown_transaction_goes_to_review() -> None:
    result = _single_clean_result(transaction_type="unknown")

    assert result.review_count == 1
    assert result.review[0].reasons == ("transaction_type_unknown",)
    assert result.active_count == 0


def test_clean_unknown_status_goes_to_review() -> None:
    result = _single_clean_result(status="unknown")

    assert result.review_count == 1
    assert result.review[0].reasons == ("status_unknown",)
    assert result.active_count == 0


def test_clean_kantoor_goes_to_unsupported_property_type() -> None:
    result = _single_clean_result(property_type="kantoor")

    assert result.unsupported_property_type_count == 1
    assert result.unsupported_property_type[0].reasons == ("property_type_unsupported",)
    assert result.active_count == 0


def test_clean_parking_and_garage_go_to_unsupported_property_type() -> None:
    qa_result = _qa_result(
        clean=(
            _qa_listing("example.nl|parking", listing=_parsed_listing(property_type="parking")),
            _qa_listing("example.nl|garage", listing=_parsed_listing(property_type="garage")),
        )
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert result.unsupported_property_type_count == 2
    assert result.active_count == 0


def test_clean_empty_property_type_goes_to_review() -> None:
    result = _single_clean_result(property_type="")

    assert result.review_count == 1
    assert result.review[0].reasons == ("property_type_unknown",)
    assert result.active_count == 0


def test_review_listing_never_enters_active_inventory() -> None:
    qa_result = _qa_result(
        review=(
            _qa_listing(
                "example.nl|review",
                qa_status="needs_review",
                listing=_parsed_listing(),
            ),
        )
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert result.active_count == 0
    assert result.review_count == 1
    assert result.review[0].reasons == ("qa_not_clean",)


def test_rejected_listing_never_enters_active_inventory() -> None:
    qa_result = _qa_result(
        rejected=(
            _qa_listing(
                "example.nl|rejected",
                qa_status="rejected",
                listing=_parsed_listing(canonical_url=""),
            ),
        )
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert result.active_count == 0
    assert result.review_count == 1
    assert result.review[0].reasons == ("qa_rejected",)


def test_under_bid_normalized_clean_listing_stays_out_of_active_inventory() -> None:
    result = _single_clean_result(status="onder bod")

    assert result.active_count == 0
    assert result.inactive_status_count == 1


def test_sold_ur_unknown_status_remains_review() -> None:
    result = _single_clean_result(status="unknown")

    assert result.active_count == 0
    assert result.review_count == 1
    assert result.review[0].reasons == ("status_unknown",)


def test_result_counts_are_correct() -> None:
    qa_result = _qa_result(
        clean=(
            _qa_listing("example.nl|active", listing=_parsed_listing()),
            _qa_listing("example.nl|inactive", listing=_parsed_listing(status="verkocht")),
            _qa_listing("example.nl|unsupported-transaction", listing=_parsed_listing(transaction_type="huur")),
            _qa_listing("example.nl|unsupported-property", listing=_parsed_listing(property_type="kantoor")),
            _qa_listing("example.nl|review", listing=_parsed_listing(property_type="")),
        ),
        review=(
            _qa_listing("example.nl|qa-review", qa_status="needs_review", listing=_parsed_listing()),
        ),
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert result.active_count == 1
    assert result.inactive_status_count == 1
    assert result.unsupported_transaction_type_count == 1
    assert result.unsupported_property_type_count == 1
    assert result.review_count == 2
    assert result.total_count == 6


def test_token_normalization_accepts_spaces_hyphens_underscores_and_case() -> None:
    qa_result = _qa_result(
        clean=(
            _qa_listing(
                "example.nl|allowed",
                listing=_parsed_listing(property_type="Twee-Onder Een_Kap"),
            ),
            _qa_listing(
                "example.nl|unsupported",
                listing=_parsed_listing(property_type="PARKEER PLAATS"),
            ),
        )
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert result.active_count == 1
    assert result.unsupported_property_type_count == 1


def test_only_active_inventory_is_passed_to_snapshot_helper() -> None:
    qa_result = _qa_result(
        clean=(
            _qa_listing("example.nl|active", listing=_parsed_listing()),
            _qa_listing("example.nl|inactive", listing=_parsed_listing(status="onder_bod")),
        ),
        review=(
            _qa_listing("example.nl|qa-review", qa_status="needs_review", listing=_parsed_listing()),
        ),
    )

    active_qa_result = build_active_inventory_qa_result(qa_result)
    snapshot = build_inventory_snapshot_from_qa(active_qa_result, "2026-06-25T12:00:00Z")

    assert [listing.inventory_key for listing in snapshot.listings] == ["example.nl|active"]


def test_ogonline_synthetic_fixture_flows_through_qa_to_eligibility() -> None:
    docs = [
        _minimal_ogonline_doc(id="kin-active", status="available", type="house"),
        _minimal_ogonline_doc(id="kin-under-bid", status="under_bid", type="apartment"),
        _minimal_ogonline_doc(id="kin-sold-ur", status="sold_ur", type="house"),
    ]
    parser_result = parse_ogonline_xhr_api_response(_parser_input(json.dumps({"docs": docs})))
    qa_result = qa_parser_family_result(parser_result)

    result = evaluate_inventory_eligibility(qa_result)

    assert result.active_count == 1
    assert result.active_inventory[0].listing.status == "beschikbaar"
    assert result.inactive_status_count == 1
    assert result.inactive_status[0].listing.status == "onder_bod"
    assert result.review_count == 1
    assert result.review[0].listing.status == "unknown"
    assert result.review[0].reasons == ("qa_not_clean",)


def test_inventory_eligibility_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "inventory" / "eligibility.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    imported_roots = {module.split(".")[0] for module in imported_modules}
    assert "requests" not in imported_roots
    assert "httpx" not in imported_roots
    assert "urllib" not in imported_roots
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots


def _parser_input(content: str) -> ParserInput:
    return ParserInput(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        source_url="https://cpl01.ogonline.nl/api/listings?page=1&limit=24",
        content=content,
        content_type="json",
    )


def _minimal_ogonline_doc(**overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": "kin-shape-test",
        "slug": "examplelaan-10-breda",
        "street": "Examplelaan",
        "houseNumber": "10",
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 375000,
        "isSales": True,
        "status": "available",
        "type": "house",
    }
    doc.update(overrides)
    return doc
