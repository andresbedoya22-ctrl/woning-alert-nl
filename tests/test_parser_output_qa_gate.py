from pathlib import Path
import ast
import sys
from dataclasses import replace


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import ParsedListing, ParserFamilyResult, ParserInput, parse_realworks_listing_page
from domek_wonen.qa import build_listing_normalized_key, qa_parser_family_result, qa_parser_results


def _realworks_result() -> ParserFamilyResult:
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "parsers" / "realworks_listing_fixture.html").read_text(
        encoding="utf-8"
    )
    return parse_realworks_listing_page(
        ParserInput(
            source_id="example-realworks",
            source_domain="example.nl",
            source_url="https://example.nl/aanbod/woningaanbod",
            content=fixture_html,
        )
    )


def _result(*listings: ParsedListing) -> ParserFamilyResult:
    return ParserFamilyResult(
        parser_family="test_family",
        source_id="example-source",
        source_domain="example.nl",
        listings=tuple(listings),
        warnings=("parser_warning",),
    )


def _listing(**overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="example-source",
        source_domain="Example.nl",
        canonical_url=" HTTPS://Example.nl/Aanbod/Woning-1/ ",
        address_raw=" Zonnelaan 12 ",
        street="Zonnelaan",
        house_number="12",
        postcode="4811AA",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        confidence_score=0.95,
        needs_review=False,
    )
    return replace(listing, **overrides)


def _single_qa(listing: ParsedListing):
    qa_result = qa_parser_family_result(_result(listing))
    return (
        qa_result.clean_listings
        or qa_result.review_listings
        or qa_result.rejected_listings
    )[0]


def test_realworks_fixture_produces_expected_clean_and_review_counts() -> None:
    qa_result = qa_parser_family_result(_realworks_result())

    assert qa_result.parser_family == "realworks_public"
    assert qa_result.total_count == 3
    assert qa_result.clean_count == 2
    assert qa_result.review_count == 1
    assert qa_result.rejected_count == 0
    assert qa_result.clean_listings[0].qa_status == "clean"
    assert qa_result.review_listings[0].qa_status == "needs_review"
    assert qa_result.review_listings[0].issues == ("listing_marked_needs_review", "missing_address", "missing_price")


def test_valid_listing_is_clean() -> None:
    qa_result = _single_qa(_listing())

    assert qa_result.qa_status == "clean"
    assert qa_result.issues == ()


def test_incomplete_listing_needs_review() -> None:
    qa_result = _single_qa(_listing(address_raw="", street="", needs_review=True))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("listing_marked_needs_review", "missing_address")


def test_missing_canonical_url_is_rejected() -> None:
    qa_result = _single_qa(_listing(canonical_url=""))

    assert qa_result.qa_status == "rejected"
    assert "missing_canonical_url" in qa_result.issues


def test_invalid_canonical_url_is_rejected() -> None:
    qa_result = _single_qa(_listing(canonical_url="example.nl/woning-1"))

    assert qa_result.qa_status == "rejected"
    assert "invalid_canonical_url" in qa_result.issues


def test_invalid_transaction_type_is_rejected() -> None:
    qa_result = _single_qa(_listing(transaction_type="sale"))

    assert qa_result.qa_status == "rejected"
    assert qa_result.issues == ("invalid_transaction_type",)


def test_invalid_status_is_rejected() -> None:
    qa_result = _single_qa(_listing(status="available"))

    assert qa_result.qa_status == "rejected"
    assert qa_result.issues == ("invalid_status",)


def test_missing_price_needs_review() -> None:
    qa_result = _single_qa(_listing(asking_price_eur=None))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("missing_price",)


def test_missing_city_needs_review() -> None:
    qa_result = _single_qa(_listing(city=""))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("missing_city",)


def test_low_confidence_needs_review() -> None:
    qa_result = _single_qa(_listing(confidence_score=0.49))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("low_confidence",)


def test_unknown_transaction_type_needs_review() -> None:
    qa_result = _single_qa(_listing(transaction_type="unknown"))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("unknown_transaction_type",)


def test_unknown_status_needs_review() -> None:
    qa_result = _single_qa(_listing(status="unknown"))

    assert qa_result.qa_status == "needs_review"
    assert qa_result.issues == ("unknown_status",)


def test_reject_has_priority_over_needs_review() -> None:
    qa_result = _single_qa(_listing(canonical_url="", asking_price_eur=None, city="", needs_review=True))

    assert qa_result.qa_status == "rejected"
    assert qa_result.issues == ("missing_canonical_url",)


def test_normalized_key_uses_canonical_url_when_present() -> None:
    key = build_listing_normalized_key(_listing())

    assert key == "example.nl|https://example.nl/aanbod/woning-1"


def test_normalized_key_fallback_uses_postcode_and_house_number() -> None:
    key = build_listing_normalized_key(
        _listing(
            canonical_url="",
            postcode=" 4811 AA ",
            house_number=" 12 A ",
            address_raw="Different address",
            city="Tilburg",
        )
    )

    assert key == "example.nl|4811aa|12 a"


def test_normalized_key_final_fallback_uses_address_and_city() -> None:
    key = build_listing_normalized_key(
        _listing(
            canonical_url="",
            postcode="",
            house_number="",
            address_raw="  Zonnelaan   12 ",
            city=" Breda ",
        )
    )

    assert key == "example.nl|zonnelaan 12|breda"


def test_qa_parser_results_batch_helper_returns_each_result() -> None:
    results = qa_parser_results([_result(_listing()), _result(_listing(status="unknown"))])

    assert len(results) == 2
    assert results[0].clean_count == 1
    assert results[1].review_count == 1


def test_qa_result_preserves_parser_warnings() -> None:
    qa_result = qa_parser_family_result(_result(_listing()))

    assert qa_result.warnings == ("parser_warning",)


def test_parser_output_gate_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "qa" / "parser_output_gate.py"
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
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots
    assert "WebsiteFetcher" not in source
