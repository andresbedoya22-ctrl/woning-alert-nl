from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.properties.models import PropertySource
from domek_wonen.properties.property_card_extractor import PropertyCardExtractor


def test_property_card_extractor_extracts_three_properties_from_fixture() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties" / "listing_page_with_3_cards.html"
    html = fixture_path.read_text(encoding="utf-8")
    source = PropertySource(
        source_id="source-a",
        office_name="Source A",
        root_domain="example.nl",
        website="https://example.nl",
        aanbod_url="https://example.nl/aanbod",
        gemeente="Breda",
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
    )

    properties = PropertyCardExtractor().extract(html, source)

    assert len(properties) == 3
    assert properties[0].property_url == "https://example.nl/woning/breda/kerkstraat-1"
    assert properties[1].status_raw.lower() == "onder bod"
    assert properties[0].candidate_type == "property_card_anchor"
    assert properties[0].extraction_method == "container_card_best_anchor"
