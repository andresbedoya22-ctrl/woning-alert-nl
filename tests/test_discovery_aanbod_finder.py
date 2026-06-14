from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.discovery.aanbod_finder import (
    _score_listing_page,
    classify_aanbod_url,
    classify_aanbod_url_type,
    detect_live_aanbod_url,
    derive_listing_index_url,
    suggest_common_aanbod_paths,
)
from domek_wonen.discovery.models import SourceCandidate
from domek_wonen.discovery.website_fetcher import FetchResponse, WebsiteFetcher


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "discovery"


class FixtureFetcher(WebsiteFetcher):
    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self.responses = {key.rstrip("/"): value for key, value in responses.items()}

    def fetch(self, url: str) -> FetchResponse:
        return self.responses.get(url.rstrip("/"), FetchResponse(url=url.rstrip("/"), status_code=404, text=""))


def test_gratis_verkoopadvies_is_not_valid_listing() -> None:
    result = classify_aanbod_url("https://example.nl/gratis-verkoopadvies")

    assert result.status in {"suspect", "rejected"}


def test_aanbod_koopwoningen_is_classified_valid() -> None:
    result = classify_aanbod_url("https://example.nl/aanbod/koopwoningen")

    assert result.status == "valid"


def test_huis_id_url_is_classified_as_property_detail() -> None:
    result = classify_aanbod_url("https://example.nl/aanbod/woningaanbod/den-bosch/koop/huis-10187874-Uilenburg-32")

    assert result.status == "suspect"
    assert result.url_type == "property_detail"


def test_woningaanbod_url_is_classified_as_listing_index() -> None:
    assert classify_aanbod_url_type("https://example.nl/woningaanbod") == "listing_index"


def test_property_detail_derives_parent_listing_url() -> None:
    derived = derive_listing_index_url(
        "https://example.nl/aanbod/woningaanbod/'s-hertogenbosch/koop/huis-10187874-Uilenburg-32"
    )

    assert derived == "https://example.nl/aanbod/woningaanbod"


def test_missing_aanbod_url_suggests_common_paths() -> None:
    suggestions = suggest_common_aanbod_paths("https://example.nl")

    assert "https://example.nl/aanbod" in suggestions
    assert "https://example.nl/koopwoningen" in suggestions


def test_homepage_link_finds_aanbod_url() -> None:
    homepage_html = (FIXTURES_DIR / "homepage_with_aanbod_link.html").read_text(encoding="utf-8")
    listing_html = (FIXTURES_DIR / "aanbod_listing_page.html").read_text(encoding="utf-8")
    fetcher = FixtureFetcher(
        {
            "https://example.nl": FetchResponse(url="https://example.nl", status_code=200, text=homepage_html),
            "https://example.nl/aanbod": FetchResponse(
                url="https://example.nl/aanbod",
                status_code=200,
                text=listing_html,
            ),
            "https://example.nl/sitemap.xml": FetchResponse(url="https://example.nl/sitemap.xml", status_code=404, text=""),
        }
    )
    candidate = SourceCandidate(office_name="Example Makelaardij", website="https://example.nl")

    result = detect_live_aanbod_url(candidate, fetcher)

    assert result.classification.status == "valid"
    assert result.classification.url == "https://example.nl/aanbod"
    assert result.classification.detection_method == "homepage_link"


def test_sitemap_finds_koopwoningen_url() -> None:
    sitemap_xml = (FIXTURES_DIR / "sitemap_with_koopwoningen.xml").read_text(encoding="utf-8")
    listing_html = (FIXTURES_DIR / "aanbod_listing_page.html").read_text(encoding="utf-8")
    fetcher = FixtureFetcher(
        {
            "https://example.nl": FetchResponse(url="https://example.nl", status_code=200, text="<html><body>home</body></html>"),
            "https://example.nl/sitemap.xml": FetchResponse(
                url="https://example.nl/sitemap.xml",
                status_code=200,
                text=sitemap_xml,
            ),
            "https://example.nl/koopwoningen": FetchResponse(
                url="https://example.nl/koopwoningen",
                status_code=200,
                text=listing_html,
            ),
        }
    )
    candidate = SourceCandidate(office_name="Example Makelaardij", website="https://example.nl")

    result = detect_live_aanbod_url(candidate, fetcher)

    assert result.classification.status == "valid"
    assert result.classification.url == "https://example.nl/koopwoningen"
    assert result.classification.detection_method == "sitemap"


def test_verkoopadvies_page_is_rejected() -> None:
    page_html = (FIXTURES_DIR / "verkoopadvies_page.html").read_text(encoding="utf-8")

    result = _score_listing_page(
        "https://example.nl/verkoopadvies",
        FetchResponse(url="https://example.nl/verkoopadvies", status_code=200, text=page_html),
    )

    assert result.status == "rejected"


def test_listing_page_with_prices_kk_and_kamers_is_valid() -> None:
    listing_html = (FIXTURES_DIR / "aanbod_listing_page.html").read_text(encoding="utf-8")

    result = _score_listing_page(
        "https://example.nl/aanbod",
        FetchResponse(url="https://example.nl/aanbod", status_code=200, text=listing_html),
    )

    assert result.status == "valid"
    assert result.score >= 50
