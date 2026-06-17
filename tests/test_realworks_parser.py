from pathlib import Path
import json
from dataclasses import replace

import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.website_fetcher import FetchResponse
from domek_wonen.properties.models import PropertySource
from domek_wonen.properties.platform_parsers.realworks_parser import (
    RealworksParser,
    normalize_kin_city_from_url,
    parse_realworks_address_city_from_url,
)
from domek_wonen.properties.property_status_classifier import parse_price_eur


def _source(
    *,
    aanbod_url: str = "https://example.nl/aanbod/woningaanbod",
    source_id: str = "example.nl",
    root_domain: str = "example.nl",
    website: str = "https://example.nl",
) -> PropertySource:
    return PropertySource(
        source_id=source_id,
        office_name="Example",
        root_domain=root_domain,
        website=website,
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
        "https://example.nl/aanbod/wonen/te-koop",
    ]


def test_realworks_parser_ignores_unrelated_aanbod_urls() -> None:
    parser = RealworksParser()

    aankoop_candidates = parser.build_listing_candidates(_source(aanbod_url="https://example.nl/aankoop_verwerving"))
    verkoopadvies_candidates = parser.build_listing_candidates(_source(aanbod_url="https://example.nl/gratis-verkoopadvies"))

    assert aankoop_candidates[0] == "https://example.nl/aanbod/woningaanbod"
    assert verkoopadvies_candidates[0] == "https://example.nl/aanbod/woningaanbod"
    assert "https://example.nl/aankoop_verwerving" not in aankoop_candidates
    assert "https://example.nl/gratis-verkoopadvies" not in verkoopadvies_candidates


def test_realworks_parser_parses_house_slug_address_and_city() -> None:
    address_raw, city_raw = parse_realworks_address_city_from_url(
        "https://example.nl/aanbod/woningaanbod/asten/koop/huis-8967467-mgr.-van-dijkstraat-2"
    )

    assert address_raw == "Mgr. van Dijkstraat 2"
    assert city_raw == "Asten"


def test_realworks_parser_normalizes_kin_city_from_url() -> None:
    assert (
        normalize_kin_city_from_url("https://www.kinmakelaars.nl/aanbod/wonen/tilburg/trouwlaan-285/6a2bf64c53154f207c087a8e")
        == "Tilburg"
    )


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
    assert candidates[0].rooms_count == "5"
    assert candidates[0].bedrooms_count == "3"
    assert candidates[0].living_area_m2 == "123"
    assert candidates[0].property_type == "apartment"
    assert candidates[0].energy_label == "A"
    assert candidates[0].has_garden == "true"
    assert candidates[0].has_balcony == "true"
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


def test_realworks_parser_detects_kin_ogonline_detail_urls_from_snapshot_fixture() -> None:
    parser = RealworksParser()
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "kin_ogonline_listing.html").read_text(
        encoding="utf-8"
    )

    detail_urls = parser.extract_detail_urls(
        "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
        fixture_html,
        root_domain="kinmakelaars.nl",
    )

    assert detail_urls == [
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/trouwlaan-285/6a2bf64c53154f207c087a8e",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-16/6a29685e53154f207cdd5c04",
    ]


def test_realworks_parser_extracts_kin_benchmark_candidates_from_listing_fixture() -> None:
    parser = RealworksParser()
    fixture_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "kin_ogonline_listing_benchmark_cards.html").read_text(
        encoding="utf-8"
    )

    seed_candidates = parser.extract_listing_seed_candidates(
        "https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
        fixture_html,
        source=_source(
            aanbod_url="https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
            source_id="kinmakelaars.nl",
            root_domain="kinmakelaars.nl",
            website="https://www.kinmakelaars.nl",
        ),
    )

    assert list(seed_candidates) == [
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/trouwlaan-285/6a2bf64c53154f207c087a8e",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-16/6a29685e53154f207cdd5c04",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-29/6a22de7e2b2f318678b94957",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-5/6a22de7e2b2f318678b94983",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-26/6a22e5902b2f318678b9cf46",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/korte-nieuwstraat-112/69fb43a281b2833c1354b74e",
    ]
    assert seed_candidates[
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/korte-nieuwstraat-112/69fb43a281b2833c1354b74e"
    ].status_raw == "Verkocht onder voorbehoud"


def test_realworks_parser_extracts_kin_listing_fields_when_detail_fetch_fails(monkeypatch) -> None:
    listing_html = (BASE_DIR / "tests" / "fixtures" / "properties" / "kin_ogonline_listing.html").read_text(
        encoding="utf-8"
    )

    class FakeFetcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def fetch(self, url: str) -> FetchResponse:
            if url.rstrip("/") == "https://www.kinmakelaars.nl/aanbod/wonen/te-koop":
                return FetchResponse(url=url, status_code=200, text=listing_html)
            return FetchResponse(url=url, error="detail fetch intentionally skipped")

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

    candidates = RealworksParser().parse(
        _source(
            aanbod_url="http://www.kinmakelaars.nl/aanbod/wonen/te-koop",
            source_id="kinmakelaars.nl",
            root_domain="kinmakelaars.nl",
            website="http://www.kinmakelaars.nl",
        ),
        max_properties_per_source=2,
        page_timeout_seconds=5,
    )

    assert len(candidates) == 2
    assert [candidate.property_url for candidate in candidates] == [
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/trouwlaan-285/6a2bf64c53154f207c087a8e",
        "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-16/6a29685e53154f207cdd5c04",
    ]
    assert candidates[0].source_url == "https://www.kinmakelaars.nl/aanbod/wonen/te-koop"
    assert candidates[0].address_raw == "Trouwlaan 285"
    assert candidates[0].city_raw == "Tilburg"
    assert candidates[0].city_raw != "Galerijflat In Tilburg"
    assert "220.000" in candidates[0].price_raw
    assert parse_price_eur(candidates[0].price_raw) == "220000"
    assert candidates[0].status_raw == "Nieuw"
    assert candidates[0].living_area_raw.startswith("38")
    assert candidates[0].rooms_raw == "2 kamers"
    assert candidates[0].rooms_count == "2"
    assert candidates[0].living_area_m2 == "38"
    assert candidates[0].property_type == "apartment"
    assert candidates[0].image_url == "https://media02.ogonline.nl/pl-import/66aa38af0773b21cac8f8da0/6a2bf64c53154f207c087a8e/rw-api-sha/trouwlaan-285.jpg"
    assert candidates[0].detail_extraction_status == "failed"
    assert candidates[1].address_raw == "Roemerhof 16"


def test_realworks_parser_uses_ogonline_api_pagination_for_missing_kin_candidates(monkeypatch) -> None:
    listing_html = """
    <html><body>
      <a href="/aanbod/wonen/tilburg/trouwlaan-285/6a2bf64c53154f207c087a8e" class="property-card">
        <p>Tilburg</p>
        <span class="sr-only">Galerijflat in Tilburg</span>
        <h3>Trouwlaan 285</h3>
        <p>EUR 220.000 k.k.</p>
        <div>38 m2</div>
        <div>2 kamers</div>
      </a>
      <script>
        const api = "https://cpl01.ogonline.nl/api/listings?page=1&amp;limit=2&amp;depth=1&amp;locale=nl&amp;account=kin";
      </script>
    </body></html>
    """

    page_1_payload = {
        "docs": [
            {
                "id": "6a2bf64c53154f207c087a8e",
                "title": "Trouwlaan 285",
                "status": "available",
                "address": {"street": "Trouwlaan", "houseNumber": 285, "settlement": "Tilburg"},
                "salesPrice": {"amount": 220000, "condition": {"title": "k.k."}},
                "consumer": {
                    "isApartment": True,
                    "details": {"rooms": 2, "bedrooms": 1, "livingSurface": 38},
                },
                "energyDetails": {"energyLabel": "A"},
            },
        ],
        "hasNextPage": True,
        "nextPage": 2,
    }
    page_2_payload = {
        "docs": [
            {
                "id": "6a22de7e2b2f318678b94957",
                "title": "Roemerhof 29",
                "status": "available",
                "address": {"street": "Roemerhof", "houseNumber": 29, "settlement": "Tilburg"},
                "salesPrice": {"amount": 165000, "condition": {"title": "k.k."}},
                "consumer": {
                    "isApartment": True,
                    "details": {"rooms": 1, "bedrooms": 1, "livingSurface": 21},
                },
                "energyDetails": {"energyLabel": "B"},
            },
            {
                "id": "69fb43a281b2833c1354b74e",
                "title": "Korte Nieuwstraat 112",
                "status": "sold_ur",
                "address": {"street": "Korte Nieuwstraat", "houseNumber": 112, "settlement": "Tilburg"},
                "salesPrice": {"amount": 250000, "condition": {"title": "k.k."}},
                "consumer": {
                    "isApartment": True,
                    "details": {"rooms": 2, "bedrooms": 1, "livingSurface": 59},
                },
                "energyDetails": {"energyLabel": "C"},
            },
        ],
        "hasNextPage": False,
        "nextPage": None,
    }

    class FakeFetcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def fetch(self, url: str) -> FetchResponse:
            normalized = url.rstrip("/")
            if normalized == "https://www.kinmakelaars.nl/aanbod/wonen/te-koop":
                return FetchResponse(url=url, status_code=200, text=listing_html)
            if "api/listings" in url and "page=1" in url:
                return FetchResponse(url=url, status_code=200, text=json.dumps(page_1_payload))
            if "api/listings" in url and "page=2" in url:
                return FetchResponse(url=url, status_code=200, text=json.dumps(page_2_payload))
            return FetchResponse(url=url, error="detail fetch intentionally skipped")

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

    candidates = RealworksParser().parse(
        _source(
            aanbod_url="https://www.kinmakelaars.nl/aanbod/wonen/te-koop",
            source_id="kinmakelaars.nl",
            root_domain="kinmakelaars.nl",
            website="https://www.kinmakelaars.nl",
        ),
        max_properties_per_source=10,
        page_timeout_seconds=5,
    )

    assert [candidate.address_raw for candidate in candidates] == [
        "Trouwlaan 285",
        "Roemerhof 29",
        "Korte Nieuwstraat 112",
    ]
    assert candidates[1].property_url == "https://www.kinmakelaars.nl/aanbod/wonen/tilburg/roemerhof-29/6a22de7e2b2f318678b94957"
    assert candidates[2].status_raw == "verkocht onder voorbehoud"


def test_realworks_parser_ignores_pagination_and_status_listing_urls() -> None:
    parser = RealworksParser()
    listing_html = """
    <html><body>
        <a href="/aanbod/woningaanbod/pagina-2">Pagina 2</a>
        <a href="/aanbod/woningaanbod/verkocht-onder-voorbehoud">Verkocht onder voorbehoud</a>
        <a href="/aanbod/woningaanbod/street-ringbaan-oost">Street filter</a>
        <a href="/aanbod/woningaanbod/tilburg/koop/huis-10218392-hulterman-29">Hulterman 29</a>
    </body></html>
    """

    detail_urls = parser.extract_detail_urls(
        "https://example.nl/aanbod/woningaanbod",
        listing_html,
        root_domain="example.nl",
    )

    assert detail_urls == [
        "https://example.nl/aanbod/woningaanbod/tilburg/koop/huis-10218392-hulterman-29",
    ]


def test_realworks_parser_recovers_address_and_city_from_title_when_detail_fields_are_noisy(monkeypatch) -> None:
    listing_html = """
    <html><body>
        <a href="/aanbod/woningaanbod/tilburg/koop/huis-10291668-besterdplein-2505">Besterdplein 25 05</a>
    </body></html>
    """

    class FakeFetcher:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def fetch(self, url: str) -> FetchResponse:
            normalized = url.rstrip("/")
            if normalized == "https://example.nl/aanbod/woningaanbod":
                return FetchResponse(url=url, status_code=200, text=listing_html)
            if normalized.endswith("/huis-10291668-besterdplein-2505"):
                return FetchResponse(url=url, status_code=200, text="<html><body>detail</body></html>")
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

    class FakeDetailExtractor:
        def enrich(self, candidate, html: str, final_url: str):
            return replace(
                candidate,
                title="Besterdplein 25 05 in Tilburg 5014 HP: Appartement te koop.",
                address_raw="in Tilburg 5014",
                city_raw="HP",
                price_raw="€ 269.500,- k.k.",
                status_raw="te koop",
                detail_extraction_status="succeeded",
                detail_error="",
            )

    monkeypatch.setattr("domek_wonen.properties.platform_parsers.realworks_parser.WebsiteFetcher", FakeFetcher)
    parser = RealworksParser()
    monkeypatch.setattr(parser, "_detail_extractor", FakeDetailExtractor())

    candidates = parser.parse(_source(), max_properties_per_source=5, page_timeout_seconds=5)

    assert len(candidates) == 1
    assert candidates[0].address_raw == "Besterdplein 25 05"
    assert candidates[0].city_raw == "Tilburg"
    assert candidates[0].price_raw == "€ 269.500,- k.k."
