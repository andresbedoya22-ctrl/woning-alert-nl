from pathlib import Path

import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.website_fetcher import FetchResponse
from domek_wonen.properties.models import PropertySource
from domek_wonen.properties.platform_parsers.realworks_parser import RealworksParser


def _source(*, aanbod_url: str = "https://example.nl/aanbod/woningaanbod") -> PropertySource:
    return PropertySource(
        source_id="example.nl",
        office_name="Example",
        root_domain="example.nl",
        website="https://example.nl",
        aanbod_url=aanbod_url,
        gemeente="Breda",
        province="Noord-Brabant",
        legal_status="allowed_official_source",
        aanbod_url_quality="valid",
        is_active=True,
        detected_platform="realworks",
    )


def test_realworks_parser_detects_property_urls_from_listing_fixture() -> None:
    parser = RealworksParser()
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "realworks_listing.html").read_text(encoding="utf-8")

    detail_urls = parser.extract_detail_urls(
        "https://example.nl/aanbod/woningaanbod",
        fixture_html,
        root_domain="example.nl",
    )

    assert detail_urls == [
        "https://example.nl/aanbod/woningaanbod/koop/breda/huis-lange-straat-10",
        "https://example.nl/woningaanbod/koop/tilburg/appartement-stationsstraat-22",
        "https://example.nl/woningen/markt-5-oudenbosch",
    ]


def test_realworks_parser_derives_listing_candidates_when_aanbod_url_missing() -> None:
    parser = RealworksParser()
    source = _source(aanbod_url="")

    candidates = parser.build_listing_candidates(source)

    assert candidates == [
        "https://example.nl/aanbod/woningaanbod",
        "https://example.nl/woningaanbod",
        "https://example.nl/aanbod/koop",
        "https://example.nl/aanbod/woningaanbod/koop",
        "https://example.nl/aanbod/woningen",
        "https://example.nl/wonen",
    ]


def test_realworks_parser_ignores_unrelated_aanbod_urls() -> None:
    parser = RealworksParser()

    aankoop_candidates = parser.build_listing_candidates(_source(aanbod_url="https://example.nl/aankoop_verwerving"))
    verkoopadvies_candidates = parser.build_listing_candidates(_source(aanbod_url="https://example.nl/gratis-verkoopadvies"))

    assert aankoop_candidates[0] == "https://example.nl/aanbod/woningaanbod"
    assert verkoopadvies_candidates[0] == "https://example.nl/aanbod/woningaanbod"
    assert "https://example.nl/aankoop_verwerving" not in aankoop_candidates
    assert "https://example.nl/gratis-verkoopadvies" not in verkoopadvies_candidates


def test_realworks_parser_extracts_address_price_and_status_from_detail_fixture(monkeypatch) -> None:
    listing_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "realworks_listing.html").read_text(encoding="utf-8")
    detail_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "realworks_detail.html").read_text(encoding="utf-8")

    class FakeFetcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def fetch(self, url: str) -> FetchResponse:
            if url.endswith("/aanbod/woningaanbod"):
                return FetchResponse(url=url, status_code=200, text=listing_html)
            if url.endswith("/huis-lange-straat-10"):
                return FetchResponse(url=url, status_code=200, text=detail_html)
            if url.endswith("/appartement-stationsstraat-22"):
                return FetchResponse(url=url, status_code=200, text=detail_html.replace("Lange Straat 10", "Stationsstraat 22"))
            if url.endswith("/markt-5-oudenbosch"):
                return FetchResponse(url=url, status_code=200, text=detail_html.replace("Lange Straat 10", "Markt 5"))
            return FetchResponse(url=url, error="not found")

        def extract_internal_links(self, base_url: str, html: str) -> list[str]:
            from domek_wonen.discovery.website_fetcher import WebsiteFetcher

            helper = WebsiteFetcher(timeout_seconds=1, delay_seconds=0)
            try:
                return helper.extract_internal_links(base_url, html)
            finally:
                helper.close()

        def close(self) -> None:
            return None

    monkeypatch.setattr("domek_wonen.properties.platform_parsers.realworks_parser.WebsiteFetcher", FakeFetcher)

    candidates = RealworksParser().parse(_source(), max_properties_per_source=1, page_timeout_seconds=5)

    assert len(candidates) == 1
    assert candidates[0].address_raw == "Lange Straat 10"
    assert candidates[0].price_raw == "EUR 425.000 k.k."
    assert candidates[0].status_raw == "beschikbaar"
    assert candidates[0].city_raw == "Breda"
    assert candidates[0].living_area_raw == "123 m2 woonoppervlakte"
    assert candidates[0].rooms_raw == "5 kamers"
    assert candidates[0].energy_label == "A"
    assert candidates[0].extraction_source == "realworks_parser"
    assert candidates[0].detail_extraction_status == "succeeded"


def test_realworks_parser_uses_slug_fallback_when_address_missing(monkeypatch) -> None:
    listing_html = """
    <html><body><a href="/woningen/vier-heultjes-99-sprang-capelle">Detail</a></body></html>
    """
    detail_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "realworks_detail_slug_only.html").read_text(
        encoding="utf-8"
    )

    class FakeFetcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def fetch(self, url: str) -> FetchResponse:
            if url.endswith("/aanbod/woningaanbod"):
                return FetchResponse(url=url, status_code=200, text=listing_html)
            if url.endswith("/vier-heultjes-99-sprang-capelle"):
                return FetchResponse(url=url, status_code=200, text=detail_html)
            return FetchResponse(url=url, error="not found")

        def extract_internal_links(self, base_url: str, html: str) -> list[str]:
            return ["https://example.nl/woningen/vier-heultjes-99-sprang-capelle"]

        def close(self) -> None:
            return None

    monkeypatch.setattr("domek_wonen.properties.platform_parsers.realworks_parser.WebsiteFetcher", FakeFetcher)

    candidates = RealworksParser().parse(_source(), max_properties_per_source=1, page_timeout_seconds=5)

    assert len(candidates) == 1
    assert candidates[0].address_raw == "Vier Heultjes 99"
    assert candidates[0].city_raw == "Sprang-Capelle"
    assert candidates[0].detail_extraction_status == "succeeded"


def test_realworks_parser_ignores_realworks_filter_urls() -> None:
    parser = RealworksParser()
    listing_html = """
    <html><body>
        <a href="/aanbod/woningaanbod/koop/bouwperiode-1906-1930">Filter bouwperiode</a>
        <a href="/aanbod/woningaanbod/asten/koop/provincie-noord-brabant">Filter provincie</a>
        <a href="/aanbod/woningaanbod/asten/koop/huis-10218392-hulterman-29">Hulterman 29</a>
    </body></html>
    """

    detail_urls = parser.extract_detail_urls(
        "https://example.nl/aanbod/woningaanbod/koop",
        listing_html,
        root_domain="example.nl",
    )

    assert detail_urls == [
        "https://example.nl/aanbod/woningaanbod/asten/koop/huis-10218392-hulterman-29",
    ]
