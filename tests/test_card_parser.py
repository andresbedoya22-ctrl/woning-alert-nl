from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.harvest.card_parser import harvest, parse_card


FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "properties"


def test_harvest_listing_fixture_extracts_complete_cards() -> None:
    html = (FIXTURES / "listing_page_with_3_cards.html").read_text(encoding="utf-8")

    listings = harvest(html, base_url="https://example.nl/aanbod")

    assert len(listings) == 3
    assert listings[0].source_url == "https://example.nl/woning/breda/kerkstraat-1"
    assert listings[0].address == "Kerkstraat 1"
    assert listings[0].city == "Breda"
    assert listings[0].postcode == "4811 AA"
    assert listings[0].area == "120 m²"
    assert listings[0].rooms == "4"
    assert listings[0].status == "unknown"
    assert listings[0].location_confidence == 1.0
    assert listings[0].confidence >= 0.75
    assert listings[2].status == "sold"


def test_harvest_dedupes_trailing_slash_duplicates() -> None:
    html = """
    <html><body>
      <article><a href="/woning/tilburg/test-1/">Test 1</a><div>Teststraat 1, 5011 AA Tilburg</div><div>EUR 300.000 k.k.</div><div>90 m2 wonen</div></article>
      <article><a href="/woning/tilburg/test-1#foto">Test 1 dubbel</a><div>Teststraat 1, 5011 AA Tilburg</div><div>EUR 300.000 k.k.</div><div>90 m2 wonen</div></article>
    </body></html>
    """

    listings = harvest(html, base_url="https://example.nl/aanbod")

    assert len(listings) == 1
    assert listings[0].source_url == "https://example.nl/woning/tilburg/test-1"


def test_allround_fixture_prefers_living_area_and_detects_unknown_status() -> None:
    html = (FIXTURES / "allround_listing_cards.html").read_text(encoding="utf-8")

    listings = harvest(html, base_url="https://www.allroundmakelaardij.nl/woningen/")

    assert len(listings) == 2
    assert listings[0].area == "107 m²"
    assert listings[0].city == "Waalwijk"
    assert listings[0].postcode == "5143 AK"
    assert listings[0].status == "unknown"


def test_kin_fixture_uses_city_address_branch() -> None:
    html = (FIXTURES / "kin_ogonline_listing.html").read_text(encoding="utf-8")

    listings = harvest(html, base_url="https://www.kinmakelaars.nl/aanbod/wonen/te-koop")

    assert len(listings) >= 2
    assert listings[0].city == "Tilburg"
    assert listings[0].address == "Trouwlaan 285"
    assert listings[0].location_confidence >= 0.75


def test_parse_card_marks_postcode_without_city_for_resolution() -> None:
    listing = parse_card(
        "https://example.nl/woning/test",
        "Voorbeeldstraat 10 1234 AB EUR 325.000 k.k. 95 m2 wonen 4 kamers Energielabel: A+",
    )

    assert listing.address == ""
    assert listing.city == ""
    assert listing.postcode == "1234 AB"
    assert listing.needs_location_resolution is True
    assert listing.location_confidence == 0.25
    assert listing.energy_label == "A+"
    assert listing.status == "unknown"


def test_parse_card_supports_on_request_card() -> None:
    text = "Breda Wilhelminastraat 8 prijs op aanvraag 88 m2 wonen 3 kamers"

    listing = parse_card("https://example.nl/woning/breda/wilhelminastraat-8", text)

    assert listing.city == "Breda"
    assert listing.address == "Wilhelminastraat 8"
    assert listing.price_on_request is True
    assert listing.price == "Prijs op aanvraag"
    assert listing.confidence >= 0.75


def test_parse_card_detects_verkocht_without_positive_default() -> None:
    listing = parse_card(
        "https://example.nl/woning/eindhoven/markt-9",
        "Markt 9, 5611 EB Eindhoven Verkocht o.v. EUR 450.000 k.k. 140 m2 wonen 5 kamers",
    )

    assert listing.status == "sold"
    assert listing.city == "Eindhoven"
    assert listing.address == "Markt 9"
