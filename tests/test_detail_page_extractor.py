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
    assert enriched.energy_label == "A"
    assert enriched.extraction_source == "detail_page"
    assert enriched.detail_extraction_status == "succeeded"


def test_detail_page_extractor_fallback_from_url_slug_is_legible() -> None:
    address_raw, city_raw = derive_address_from_slug(
        "https://carredewit.nl/woningen/christoffel-wuststraat-34-rosmalen"
    )

    assert address_raw == "Christoffel Wuststraat 34"
    assert city_raw == "Rosmalen"
