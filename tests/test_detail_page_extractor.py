from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.detail_page_extractor import DetailPageExtractor, derive_address_from_slug
from domek_wonen.properties.models import PropertyCandidate


def _candidate(property_url: str) -> PropertyCandidate:
    return PropertyCandidate(
        source_id="example",
        source_url="https://example.nl/aanbod",
        root_domain="example.nl",
        gemeente="Breda",
        property_url=property_url,
        property_url_classification="property_detail_candidate",
        title="",
    )


def test_detail_page_extractor_extracts_address_from_h1() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties" / "detail_page_with_h1.html"
    html = fixture_path.read_text(encoding="utf-8")

    enriched = DetailPageExtractor().enrich(
        _candidate("https://example.nl/woningen/vier-heultjes-99-sprang-capelle"),
        html,
        "https://example.nl/woningen/vier-heultjes-99-sprang-capelle",
    )

    assert enriched.address_raw == "Vier Heultjes 99"
    assert enriched.city_raw == "Sprang-Capelle"
    assert enriched.price_raw
    assert enriched.status_raw.lower() == "beschikbaar"
    assert enriched.rooms_raw == "5 kamers"
    assert enriched.bedrooms_count == ""
    assert enriched.property_type == ""
    assert enriched.energy_label == "A"
    assert enriched.extraction_source == "detail_page"
    assert enriched.detail_extraction_status == "succeeded"


def test_detail_page_extractor_extracts_bedrooms_without_promoting_ambiguous_kamers() -> None:
    html = """
    <html>
      <body>
        <h1>Voorbeeldstraat 12 Breda</h1>
        <div>Beschikbaar</div>
        <div>Woonoppervlakte 101 m2</div>
        <div>5 kamers</div>
        <div>3 slaapkamers</div>
        <div>Geen balkon</div>
      </body>
    </html>
    """

    enriched = DetailPageExtractor().enrich(
        _candidate("https://example.nl/woningen/voorbeeldstraat-12-breda"),
        html,
        "https://example.nl/woningen/voorbeeldstraat-12-breda",
    )

    assert enriched.rooms_count == "5"
    assert enriched.bedrooms_count == "3"
    assert enriched.living_area_m2 == "101"
    assert enriched.has_balcony == "false"


def test_detail_page_extractor_extracts_property_type_signals() -> None:
    apartment = DetailPageExtractor().enrich(
        _candidate("https://example.nl/woningen/appartement-1-breda"),
        """
        <html><body><div>Type woning Appartement</div></body></html>
        """,
        "https://example.nl/woningen/appartement-1-breda",
    )

    house = DetailPageExtractor().enrich(
        _candidate("https://example.nl/woningen/woonhuis-1-breda"),
        """
        <html><body><div>Soort woning Woonhuis</div></body></html>
        """,
        "https://example.nl/woningen/woonhuis-1-breda",
    )

    assert apartment.property_type == "apartment"
    assert house.property_type == "house"


def test_detail_page_extractor_fallback_from_url_slug_is_legible() -> None:
    address_raw, city_raw = derive_address_from_slug(
        "https://carredewit.nl/woningen/christoffel-wuststraat-34-rosmalen"
    )

    assert address_raw == "Christoffel Wuststraat 34"
    assert city_raw == "Rosmalen"
