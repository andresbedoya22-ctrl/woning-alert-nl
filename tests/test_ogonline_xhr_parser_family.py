from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import (  # noqa: E402
    ParserFamilyResult,
    ParserInput,
    parse_ogonline_xhr_api_response,
)
from domek_wonen.qa.parser_output_gate import qa_parser_family_result  # noqa: E402


def _fixture(name: str) -> str:
    return (BASE_DIR / "tests" / "fixtures" / "parsers" / name).read_text(encoding="utf-8")


def _parser_input(content: str | None = None) -> ParserInput:
    return ParserInput(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        source_url="https://cpl01.ogonline.nl/api/listings?page=1&limit=24",
        content=content or _fixture("ogonline_xhr_page_1_fixture.json"),
        content_type="json",
    )


def test_parse_page_1_fixture_returns_ogonline_result() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input())

    assert isinstance(result, ParserFamilyResult)
    assert result.parser_family == "ogonline_xhr"
    assert result.source_id == "kinmakelaars.nl__breda"
    assert result.source_domain == "kinmakelaars.nl"
    assert len(result.listings) == 3


def test_parse_page_1_fixture_maps_core_listing_fields() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input())
    listing = result.listings[0]

    assert listing.canonical_url == "https://kinmakelaars.nl/aanbod/wonen/zonnelaan-12-breda"
    assert listing.address_raw == "Zonnelaan 12"
    assert listing.street == "Zonnelaan"
    assert listing.house_number == "12"
    assert listing.postcode == "4811AA"
    assert listing.city == "Breda"
    assert listing.asking_price_eur == 425000
    assert listing.transaction_type == "koop"
    assert listing.status == "beschikbaar"
    assert listing.living_area_m2 == 118
    assert listing.rooms_count == 5
    assert listing.bedrooms_count == 3
    assert listing.property_type == "house"
    assert listing.energy_label == "A"
    assert "ogonline_xhr" in listing.evidence
    assert "doc_id:kin-001" in listing.evidence
    assert "image_count:1" in listing.evidence
    assert listing.needs_review is False


def test_missing_price_is_marked_for_review() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input())
    listing = result.listings[1]

    assert listing.canonical_url == "https://kinmakelaars.nl/aanbod/wonen/marktstraat-8-tilburg"
    assert listing.asking_price_eur is None
    assert listing.needs_review is True
    assert listing.review_reason == "missing_price"


def test_under_offer_maps_to_onder_bod() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input())

    assert result.listings[2].status == "onder_bod"
    assert result.listings[2].transaction_type == "koop"


def test_page_2_fixture_returns_distinct_ids_and_listings() -> None:
    page_1 = parse_ogonline_xhr_api_response(_parser_input())
    page_2 = parse_ogonline_xhr_api_response(_parser_input(_fixture("ogonline_xhr_page_2_fixture.json")))

    page_1_doc_ids = {signal for listing in page_1.listings for signal in listing.evidence if signal.startswith("doc_id:")}
    page_2_doc_ids = {signal for listing in page_2.listings for signal in listing.evidence if signal.startswith("doc_id:")}

    assert len(page_2.listings) == 2
    assert page_1_doc_ids.isdisjoint(page_2_doc_ids)
    assert page_2.listings[0].canonical_url == "https://kinmakelaars.nl/aanbod/wonen/breda/havenstraat-4/kin-101"
    assert page_2.listings[0].status == "onder_bod"


def test_invalid_json_returns_warning() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input("{not-json"))

    assert result.listings == ()
    assert result.warning_count == 1
    assert result.warnings == ("invalid_json",)


def test_missing_docs_returns_warning() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input('{"items": []}'))

    assert result.listings == ()
    assert result.warning_count == 1
    assert result.warnings == ("missing_docs",)


def test_docs_not_list_returns_warning() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input('{"docs": {"id": "kin-001"}}'))

    assert result.listings == ()
    assert result.warning_count == 1
    assert result.warnings == ("invalid_docs",)


def test_qa_gate_splits_clean_and_review_rows() -> None:
    result = parse_ogonline_xhr_api_response(_parser_input())
    qa_result = qa_parser_family_result(result)

    assert qa_result.clean_count >= 1
    assert qa_result.review_count >= 1
    assert qa_result.rejected_count == 0


def test_ogonline_family_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "parsers" / "ogonline_xhr_family.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
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
