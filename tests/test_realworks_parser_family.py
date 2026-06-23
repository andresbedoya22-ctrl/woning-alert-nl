from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import ParserFamilyResult, ParserInput, parse_realworks_listing_page


def _parser_input() -> ParserInput:
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "parsers" / "realworks_listing_fixture.html").read_text(
        encoding="utf-8"
    )
    return ParserInput(
        source_id="example-realworks",
        source_domain="example.nl",
        source_url="https://example.nl/aanbod/woningaanbod",
        content=fixture_html,
    )


def test_parse_listing_page_returns_realworks_result() -> None:
    result = parse_realworks_listing_page(_parser_input())

    assert isinstance(result, ParserFamilyResult)
    assert result.parser_family == "realworks_public"
    assert result.source_id == "example-realworks"
    assert result.source_domain == "example.nl"


def test_parse_listing_page_extracts_three_listings() -> None:
    result = parse_realworks_listing_page(_parser_input())

    assert len(result.listings) == 3
    assert [listing.canonical_url for listing in result.listings] == [
        "https://example.nl/aanbod/woningaanbod/breda/koop/huis-1001-zonnelaan-12",
        "https://example.nl/aanbod/woningaanbod/tilburg/koop/huis-1002-spoorstraat-8",
        "https://example.nl/woningaanbod/koop/eindhoven/appartement-1003",
    ]


def test_parse_listing_page_normalizes_core_fields() -> None:
    result = parse_realworks_listing_page(_parser_input())
    listing = result.listings[0]

    assert listing.asking_price_eur == 425000
    assert listing.transaction_type == "koop"
    assert listing.status == "beschikbaar"
    assert listing.address_raw == "Zonnelaan 12"
    assert listing.street == "Zonnelaan"
    assert listing.house_number == "12"
    assert listing.city == "Breda"
    assert listing.living_area_m2 == 118
    assert listing.rooms_count == 5
    assert listing.bedrooms_count == 3
    assert listing.energy_label == "A"


def test_parse_listing_page_detects_under_offer_status() -> None:
    result = parse_realworks_listing_page(_parser_input())

    assert result.listings[1].status == "onder_bod"
    assert result.listings[1].transaction_type == "koop"


def test_parse_listing_page_marks_incomplete_listing_for_review() -> None:
    result = parse_realworks_listing_page(_parser_input())
    incomplete = result.listings[2]

    assert incomplete.needs_review is True
    assert incomplete.asking_price_eur is None
    assert incomplete.review_reason == "missing_address,missing_price"


def test_confidence_scores_are_bounded() -> None:
    result = parse_realworks_listing_page(_parser_input())

    assert all(0.0 <= listing.confidence_score <= 1.0 for listing in result.listings)
    assert result.listings[0].confidence_score > result.listings[2].confidence_score


def test_realworks_family_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "parsers" / "realworks_family.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "requests" not in imported_modules
    assert "httpx" not in imported_modules
    assert "urllib.request" not in imported_modules
    assert "playwright" not in imported_modules
    assert "selenium" not in imported_modules
    assert "domek_wonen.discovery.website_fetcher" not in imported_modules
