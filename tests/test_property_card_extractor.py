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


def test_property_card_extractor_prefers_allround_card_fields_over_page_noise() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties" / "allround_listing_cards.html"
    html = fixture_path.read_text(encoding="utf-8")
    source = PropertySource(
        source_id="allroundmakelaardij.nl__tilburg",
        office_name="Allround Makelaardij",
        root_domain="allroundmakelaardij.nl",
        website="https://www.allroundmakelaardij.nl",
        aanbod_url="https://www.allroundmakelaardij.nl/woningen/",
        gemeente="Tilburg",
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
    )

    properties = PropertyCardExtractor().extract(html, source)

    assert len(properties) == 2
    assert properties[0].address_raw == "Poelruitstraat 20"
    assert properties[0].city_raw == "5143 AK Waalwijk"
    assert properties[0].price_raw == "€ 385.000,- k.k."
    assert properties[0].status_raw.lower() == "te koop"
    assert properties[1].address_raw == "Vredeman de Vriesstraat 24"
    assert properties[1].city_raw == "5041 GS Tilburg"
    assert properties[1].price_raw == "€ 1.150,- p/m"
    assert properties[1].status_raw.lower() == "te huur"


def test_property_card_extractor_extracts_jurgens_price_and_status_without_m2_leak() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties" / "jurgens_listing_cards.html"
    html = fixture_path.read_text(encoding="utf-8")
    source = PropertySource(
        source_id="jurgensmakelaardij.nl__tilburg",
        office_name="Jurgens Makelaardij",
        root_domain="jurgensmakelaardij.nl",
        website="https://jurgensmakelaardij.nl",
        aanbod_url="https://jurgensmakelaardij.nl/wonen/",
        gemeente="Tilburg",
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
    )

    properties = PropertyCardExtractor().extract(html, source)

    assert len(properties) == 2
    assert properties[0].address_raw == "Telefoonstraat 14"
    assert properties[0].city_raw == "Tilburg"
    assert properties[0].price_raw == "€ 450.000 K.K."
    assert properties[0].status_raw == "Verkocht onder voorbehoud"
    assert properties[1].price_raw == "€ 1.495.000 K.K."
    assert properties[1].status_raw == "Beschikbaar"
