from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

import pytest

from domek_wonen.harvest import mini_harvest


class FakeResponse:
    def __init__(self, url: str, status_code: int, text: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def test_listing_html_harvest(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html><body>
      <article><a href="/woning/a">Voorbeeldstraat 1</a><div>EUR 300.000 k.k.</div><div>Tilburg</div><div>91 m2</div></article>
      <article><a href="/woning/b">Voorbeeldstraat 2</a><div>EUR 310.000 k.k.</div><div>Breda</div><div>88 m2</div></article>
      <article><a href="/woning/c">Voorbeeldstraat 3</a><div>EUR 320.000 k.k.</div><div>Eindhoven</div><div>95 m2</div></article>
    </body></html>
    """

    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    def fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        return FakeResponse(url, 200, html)

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "listing_html",
        aanbod_url="https://example.nl/aanbod",
        fetcher=fetcher,
        max_listings=10,
    )

    assert result.listings_found == 3
    assert result.listings_parsed == 3
    assert result.fill_rate_price == 1.0
    assert result.fill_rate_city == 1.0
    assert result.fill_rate_area == 1.0
    assert result.harvest_ok is True
    assert result.zero_reason is None


def test_sitemap_harvest(monkeypatch: pytest.MonkeyPatch) -> None:
    sitemap = """
    <urlset>
      <url><loc>https://example.nl/woning/a</loc></url>
      <url><loc>https://example.nl/woning/b</loc></url>
      <url><loc>https://example.nl/woning/c</loc></url>
      <url><loc>https://example.nl/woning/d</loc></url>
      <url><loc>https://example.nl/woning/e</loc></url>
    </urlset>
    """
    detail = """
    <html><body>
      <h1>Voorbeeldstraat 1</h1>
      <div>EUR 400.000 k.k.</div>
      <div>5011 AA Tilburg</div>
      <div>103 m2</div>
    </body></html>
    """

    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    def fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("sitemap.xml"):
            return FakeResponse(url, 200, sitemap)
        return FakeResponse(url, 200, detail)

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "sitemap_with_listings",
        listing_pattern="/woning/",
        fetcher=fetcher,
        max_listings=5,
        max_detail_pages=5,
    )

    assert result.listings_found == 5
    assert result.listings_parsed == 5
    assert result.fill_rate_price == 1.0
    assert result.fill_rate_city == 1.0
    assert result.zero_reason is None


def test_wp_json_harvest(monkeypatch: pytest.MonkeyPatch) -> None:
    types_payload = '{"listing":{"rest_base":"listing","name":"Listings"}}'
    collection_payload = """
    [
      {"title":{"rendered":"Object A"},"link":"https://example.nl/woning/a","excerpt":{"rendered":"EUR 250.000 k.k. Tilburg 80 m2"}},
      {"title":{"rendered":"Object B"},"link":"https://example.nl/woning/b","excerpt":{"rendered":"EUR 260.000 k.k. Breda 85 m2"}}
    ]
    """

    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    def fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        if url.endswith("/wp-json/wp/v2/types"):
            return FakeResponse(url, 200, types_payload)
        return FakeResponse(url, 200, collection_payload)

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "wp_json",
        fetcher=fetcher,
        max_listings=10,
    )

    assert result.listings_found == 2
    assert result.listings_parsed == 2
    assert result.fill_rate_price == 1.0
    assert result.fill_rate_city == 1.0
    assert result.fill_rate_area == 1.0
    assert result.zero_reason is None


def test_iframe_only_skipped() -> None:
    result = mini_harvest.harvest_domain_sample("example.nl", "iframe_only")

    assert result.harvest_ok is False
    assert result.blocker_reason == "unsupported_strategy"


def test_blocked_during_harvest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    calls = {"count": 0}

    def fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        calls["count"] += 1
        if url.endswith("sitemap.xml"):
            return FakeResponse(url, 200, "<urlset><url><loc>https://example.nl/woning/a</loc></url></urlset>")
        return FakeResponse(url, 403, "Forbidden")

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "sitemap_with_listings",
        listing_pattern="/woning/",
        fetcher=fetcher,
        max_listings=5,
        max_detail_pages=5,
    )

    assert calls["count"] >= 2
    assert result.blocker_reason == "http_403"
    assert result.harvest_ok is False


def test_max_listings_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html><body>
      <article><a href="/woning/a">A</a><div>EUR 1</div><div>Tilburg</div><div>80 m2</div></article>
      <article><a href="/woning/b">B</a><div>EUR 2</div><div>Tilburg</div><div>81 m2</div></article>
      <article><a href="/woning/c">C</a><div>EUR 3</div><div>Tilburg</div><div>82 m2</div></article>
    </body></html>
    """
    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "listing_html",
        aanbod_url="https://example.nl/aanbod",
        fetcher=lambda url, headers, timeout: FakeResponse(url, 200, html),
        max_listings=2,
    )

    assert result.listings_found == 2
    assert result.listings_parsed == 2


def test_robots_gate_called(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []

    def fake_can_fetch(domain: str, path: str) -> bool:
        seen.append((domain, path))
        return True

    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", fake_can_fetch)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)
    monkeypatch.setattr(
        mini_harvest,
        "_default_fetcher",
        lambda url, headers, timeout: FakeResponse(url, 200, "<html><body><article><a href='/woning/a'>A</a><div>EUR 1</div><div>Tilburg</div><div>80 m2</div></article></body></html>"),
    )

    mini_harvest.harvest_domain_sample("example.nl", "listing_html", aanbod_url="https://example.nl/aanbod")

    assert seen
    assert seen[0][0] == "example.nl"
    assert seen[0][1] == "/aanbod"


def test_fill_rate_calculation() -> None:
    listings = [
        mini_harvest.MiniHarvestListing(source_url="https://example.nl/a", price="EUR 1", city="Tilburg", area="80 m2"),
        mini_harvest.MiniHarvestListing(source_url="https://example.nl/b", price="", city="Breda", area=""),
    ]

    result = mini_harvest.summarize_result("example.nl", "listing_html", 2, listings, None)

    assert result.fill_rate_price == 0.5
    assert result.fill_rate_city == 1.0
    assert result.fill_rate_area == 0.5
    assert result.fill_rate_url == 1.0


def test_no_legacy_imports() -> None:
    source = Path(mini_harvest.__file__).read_text(encoding="utf-8")

    assert "domek_wonen.properties" not in source
    assert "domek_wonen.portals" not in source


def test_zero_reason_for_listing_html_without_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "listing_html",
        aanbod_url="https://example.nl/aanbod",
        fetcher=lambda url, headers, timeout: FakeResponse(
            url,
            200,
            "<html><body><h1>Geen aanbod</h1></body></html>",
            {"content-type": "text/html"},
        ),
    )

    assert result.listings_found == 0
    assert result.blocker_reason is None
    assert result.zero_reason == "listing_html_without_detectable_cards"


def test_zero_reason_for_sitemap_without_matching_listing_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mini_harvest.robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(mini_harvest.robots_gate, "crawl_delay", lambda domain: 0.0)

    def fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        return FakeResponse(url, 200, "<urlset><url><loc>https://example.nl/contact</loc></url></urlset>", {"content-type": "application/xml"})

    result = mini_harvest.harvest_domain_sample(
        "example.nl",
        "sitemap_with_listings",
        listing_pattern="/woning/",
        fetcher=fetcher,
    )

    assert result.listings_found == 0
    assert result.zero_reason == "sitemap_urls_missing_or_listing_pattern_unmatched"


def test_verdict_thresholds() -> None:
    cosechable = [
        mini_harvest.MiniHarvestResult("a", "listing_html", 1, 1, 0.8, 0.8, 0.5, 1.0, [], None, True)
        for _ in range(10)
    ]
    parcial = [
        mini_harvest.MiniHarvestResult("a", "listing_html", 1, 1, 0.5, 0.5, 0.5, 1.0, [], None, True)
        for _ in range(4)
    ]
    pobre = [
        mini_harvest.MiniHarvestResult("a", "listing_html", 1, 1, 0.3, 0.3, 0.5, 1.0, [], None, True)
        for _ in range(4)
    ]

    assert mini_harvest.verdict_from_results(cosechable) == "COSECHABLE"
    assert mini_harvest.verdict_from_results(parcial) == "PARCIAL"
    assert mini_harvest.verdict_from_results(pobre) == "POBRE"
