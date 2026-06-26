from pathlib import Path
import ast
from dataclasses import FrozenInstanceError
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.inventory import evaluate_inventory_eligibility  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.pilots import ogonline_detail_property_type_enrichment as enrichment  # noqa: E402
from domek_wonen.qa import ParserFamilyQAResult, ParserListingQAResult  # noqa: E402


MODULE_PATH = (
    BASE_DIR
    / "scraper"
    / "src"
    / "domek_wonen"
    / "pilots"
    / "ogonline_detail_property_type_enrichment.py"
)


def _listing(
    index: int,
    *,
    canonical_url: str | None = None,
    property_type: str = "",
    status: str = "beschikbaar",
    transaction_type: str = "koop",
) -> ParsedListing:
    return ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=canonical_url
        if canonical_url is not None
        else f"https://kinmakelaars.nl/aanbod/wonen/breda/example-{index}/id-{index}",
        address_raw=f"Example Street {index}",
        city="Breda",
        asking_price_eur=400000,
        transaction_type=transaction_type,
        status=status,
        property_type=property_type,
        confidence_score=0.95,
    )


def _html_with_property_type(candidate: str) -> str:
    return f"<script>window.__DETAIL__ = {{\"subtype\":\"{candidate}\"}}</script>"


def test_tussenwoning_maps_to_tussenwoning() -> None:
    assert enrichment.map_ogonline_detail_property_type("Tussenwoning") == "tussenwoning"


def test_vrijstaande_woning_maps_to_vrijstaande_woning() -> None:
    assert enrichment.map_ogonline_detail_property_type("Vrijstaande woning") == "vrijstaande_woning"


def test_appartement_maps_to_appartement() -> None:
    assert enrichment.map_ogonline_detail_property_type("Appartement") == "appartement"


def test_bouwgrond_maps_but_eligibility_excludes_later() -> None:
    mapped = enrichment.map_ogonline_detail_property_type("Bouwgrond")
    listing = _listing(1, property_type=mapped)
    qa_result = ParserFamilyQAResult(
        parser_family="ogonline_xhr",
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        clean_listings=(ParserListingQAResult(listing=listing, qa_status="clean", normalized_key="kin|1"),),
        review_listings=(),
        rejected_listings=(),
        total_count=1,
        clean_count=1,
        review_count=0,
        rejected_count=0,
    )

    result = evaluate_inventory_eligibility(qa_result)

    assert mapped == "bouwgrond"
    assert result.active_count == 0
    assert result.unsupported_property_type_count == 1


def test_open_huis_is_ignored_by_property_type_mapper() -> None:
    assert enrichment.map_ogonline_detail_property_type("Open huis") == ""


def test_unknown_candidate_returns_empty_string() -> None:
    assert enrichment.map_ogonline_detail_property_type("Villa") == ""


def test_enrichment_sets_empty_property_type_from_synthetic_html(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    listing = _listing(1, property_type="")

    result = enrichment.enrich_listings_with_detail_property_type(
        (listing,),
        fetch_html=lambda url: _html_with_property_type("Tussenwoning"),
    )

    assert result.enriched_count == 1
    assert result.enriched_listings[0].property_type == "tussenwoning"
    assert listing.property_type == ""


def test_enrichment_does_not_overwrite_existing_property_type(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    listing = _listing(1, property_type="appartement")
    fetched_urls: list[str] = []

    result = enrichment.enrich_listings_with_detail_property_type(
        (listing,),
        fetch_html=lambda url: fetched_urls.append(url) or _html_with_property_type("Tussenwoning"),
    )

    assert fetched_urls == []
    assert result.attempted_count == 0
    assert result.enriched_listings == (listing,)


def test_multiple_candidates_same_mapping_are_ok(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    html = """
    <script>window.__DETAIL__ = {"subtype":"Tussenwoning", "label":"Tussenwoning"}</script>
    <dl><dt>Woningtype</dt><dd>Tussenwoning</dd></dl>
    """

    result = enrichment.enrich_listings_with_detail_property_type((_listing(1),), fetch_html=lambda url: html)

    assert result.enriched_count == 1
    assert result.enriched_listings[0].property_type == "tussenwoning"


def test_multiple_conflicting_mapped_candidates_leave_unchanged_with_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    html = """
    <script>window.__DETAIL__ = {"subtype":"Tussenwoning", "alt":"Appartement"}</script>
    <dl><dt>Woningtype</dt><dd>Appartement</dd></dl>
    """

    result = enrichment.enrich_listings_with_detail_property_type((_listing(1),), fetch_html=lambda url: html)

    assert result.enriched_count == 0
    assert result.enriched_listings[0].property_type == ""
    assert "ambiguous_property_type_candidates" in result.warnings


def test_robots_false_prevents_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    fetched_urls: list[str] = []

    result = enrichment.enrich_listings_with_detail_property_type(
        (_listing(1),),
        fetch_html=lambda url: fetched_urls.append(url) or _html_with_property_type("Tussenwoning"),
    )

    assert fetched_urls == []
    assert result.blocked_count == 1
    assert result.enriched_listings[0].property_type == ""


def test_fetch_exception_leaves_listing_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    listing = _listing(1)

    def fetch_html(url: str) -> str:
        raise RuntimeError("boom")

    result = enrichment.enrich_listings_with_detail_property_type((listing,), fetch_html=fetch_html)

    assert result.failed_count == 1
    assert result.enriched_listings == (listing,)
    assert "fetch_exception" in result.warnings


def test_max_details_is_respected(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    result = enrichment.enrich_listings_with_detail_property_type(
        tuple(_listing(index) for index in range(1, 5)),
        fetch_html=lambda url: fetched_urls.append(url) or _html_with_property_type("Appartement"),
        max_details=2,
    )

    assert len(fetched_urls) == 2
    assert result.attempted_count == 2
    assert result.enriched_count == 2


def test_original_listing_is_not_mutated(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    listing = _listing(1)

    result = enrichment.enrich_listings_with_detail_property_type(
        (listing,),
        fetch_html=lambda url: _html_with_property_type("Appartement"),
    )

    assert result.enriched_listings[0] is not listing
    assert listing.property_type == ""
    try:
        listing.property_type = "appartement"
    except FrozenInstanceError:
        pass
    else:  # pragma: no cover
        raise AssertionError("ParsedListing should be frozen")


def test_enrichment_module_has_no_disallowed_imports() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
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


def test_enrichment_module_does_not_write_outputs() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods
