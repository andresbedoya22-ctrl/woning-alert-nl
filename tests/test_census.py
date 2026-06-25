from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.compliance import robots_gate
from domek_wonen.discovery.census import (  # noqa: E402
    DiscoveryStrategy,
    DomainClassification,
    classify_domain,
)
from domek_wonen.runtime_settings import RuntimeSettings


@pytest.fixture(autouse=True)
def _reset_gate_cache() -> None:
    robots_gate.clear_cache()


@pytest.fixture(autouse=True)
def runtime_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_runtime_settings(load_dotenv_file: bool = True) -> RuntimeSettings:
        return RuntimeSettings(
            user_agent="TestBot/1.0",
            min_request_interval_seconds=2,
            request_timeout_seconds=9,
        )

    monkeypatch.setattr("domek_wonen.discovery.census.load_runtime_settings", fake_load_runtime_settings)


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}


class FakeFetcher:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        assert headers["User-Agent"] == "TestBot/1.0"
        assert timeout == 9.0
        self.calls.append(url)
        path = Path(url).as_posix()
        if "://" in url:
            path = "/" + url.split("/", 3)[3] if "/" in url[8:] else "/"
        return self.responses.get(path, FakeResponse("not found", status_code=404))


def _allow_all(monkeypatch: pytest.MonkeyPatch, call_log: list[str] | None = None) -> None:
    def fake_can_fetch(domain: str, path: str = "/") -> bool:
        if call_log is not None:
            call_log.append(path)
        return True

    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.can_fetch", fake_can_fetch)
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.robots_status", lambda domain: "allow")
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.crawl_delay", lambda domain: 0.0)


def test_robots_disallow_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.can_fetch", lambda domain, path="/": False)
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.robots_status", lambda domain: "disallow")
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.crawl_delay", lambda domain: 7.0)

    result = classify_domain("example.com", fetcher=lambda *_args: pytest.fail("content fetch should not run"))

    assert result.discovery_strategy is DiscoveryStrategy.robots_disallow
    assert result.requests_used == 0
    assert result.recommended_action == "skip_blocked"
    assert result.robots_status == "disallow"
    assert result.robots_crawl_delay == 7.0


def test_fingerprint_ogonline(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse("<footer>Website door OGonline</footer>")})

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "ogonline"


def test_fingerprint_sumedia(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse('<script src="/assets/Sumedia/app.js"></script>')})

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "sumedia"


def test_fingerprint_silverstripe(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse('<link href="/_resources/themes/site/app.css" rel="stylesheet">')})

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "silverstripe"


def test_fingerprint_wordpress(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse('<meta name="generator" content="Elementor">')})

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "wordpress"


def test_fingerprint_wordpress_realworks(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse('<img src="/wp-content/uploads/realworks/logo.png">')})

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "wordpress"


def test_sitemap_with_listings(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse(
                "<urlset><url><loc>https://example.com/woning/teststraat-1</loc></url></urlset>"
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.sitemap_with_listings
    assert result.sitemap_has_listing_urls is True
    assert result.listing_url_pattern == "/woning/"
    assert result.recommended_action == "build_discovery"


def test_wp_json_listings(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse('<meta name="generator" content="WordPress">'),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse('{"namespaces":["wp/v2"]}'),
            "/wp-json/wp/v2/types": FakeResponse(
                '{"woning":{"slug":"woning","public":true,"rest_base":"woning"}}'
            ),
            "/wp-json/wp/v2/woning?per_page=1": FakeResponse('[{"id":1}]'),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.wp_json
    assert result.wp_json_listings_found is True
    assert result.structured_channel_open is True
    assert result.recommended_action == "build_discovery"


def test_listing_html_with_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
            "/aanbod": FakeResponse(
                """
                <div class="card">
                  <a href="/woning/teststraat-1">Bekijk woning</a>
                  <span class="price">€ 395.000 k.k.</span>
                  <span class="area">120 m2</span>
                </div>
                """
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.listing_html
    assert result.card_fields_extractable == ["url", "price", "area"]
    assert result.recommended_action == "build_discovery"


def test_needs_js(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
            "/aanbod": FakeResponse('<div id="app"></div><script src="/app.js"></script>'),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.needs_js is True
    assert result.discovery_strategy is DiscoveryStrategy.listing_js
    assert result.recommended_action == "needs_js_playwright"


def test_iframe_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
            "/aanbod": FakeResponse('<iframe src="https://portal.example/listings"></iframe>'),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.iframe_only
    assert result.recommended_action == "commercial_only"


def test_blocked_403(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap_index.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-json/": FakeResponse("forbidden", status_code=403),
            "/wp-json/wp/v2/types": FakeResponse("forbidden", status_code=403),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.blocked
    assert result.blocker_reason == "http_403"
    assert result.recommended_action == "skip_blocked"


def test_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>plain site</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
            "/woningen": FakeResponse("<html><body>Geen aanbod momenteel.</body></html>"),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.no_signal
    assert result.recommended_action == "manual_review"


def test_max_requests_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse('<meta name="generator" content="WordPress">'),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("{}", status_code=200),
            "/aanbod": FakeResponse("<html><body>should not be fetched</body></html>"),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.requests_used == 8
    assert len(fetcher.calls) == 8
    assert "https://example.com/aanbod" in fetcher.calls
    assert "https://example.com/woningen" not in fetcher.calls


def test_uses_compliance_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    gate_calls: list[str] = []
    _allow_all(monkeypatch, call_log=gate_calls)

    def checked_fetcher(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        assert gate_calls
        return FakeResponse("<html><body>home</body></html>")

    result = classify_domain("example.com", fetcher=checked_fetcher)

    assert result.requests_used >= 1
    assert gate_calls[0] == "/"


def test_known_aanbod_url_used_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
            "/aanbod": FakeResponse(
                """
                <div class="card">
                  <a href="/woning/teststraat-1">Bekijk woning</a>
                  <span class="price">â‚¬ 395.000 k.k.</span>
                  <span class="area">120 m2</span>
                </div>
                """
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher, known_aanbod_url="https://example.com/aanbod")

    assert result.discovery_strategy is DiscoveryStrategy.listing_html
    assert "https://example.com/aanbod" in fetcher.calls


def test_funda_aanbod_url_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    gate_calls: list[str] = []

    def fake_can_fetch(domain: str, path: str = "/") -> bool:
        gate_calls.append(f"{domain}{path}")
        return True

    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.can_fetch", fake_can_fetch)
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.robots_status", lambda domain: "allow")
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.crawl_delay", lambda domain: 0.0)

    result = classify_domain(
        "example.com",
        fetcher=lambda *_args: pytest.fail("funda aanbod should not fetch content"),
        known_aanbod_url="https://www.funda.nl/makelaars/test/woningaanbod",
    )

    assert result.discovery_strategy is DiscoveryStrategy.blocked
    assert result.blocker_reason == "aanbod_on_funda_pararius"
    assert result.recommended_action == "commercial_only"
    assert result.requests_used == 0
    assert gate_calls == ["example.com/"]


def test_pararius_aanbod_url_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    gate_calls: list[str] = []

    def fake_can_fetch(domain: str, path: str = "/") -> bool:
        gate_calls.append(f"{domain}{path}")
        return True

    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.can_fetch", fake_can_fetch)
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.robots_status", lambda domain: "allow")
    monkeypatch.setattr("domek_wonen.discovery.census.robots_gate.crawl_delay", lambda domain: 0.0)

    result = classify_domain(
        "example.com",
        fetcher=lambda *_args: pytest.fail("pararius aanbod should not fetch content"),
        known_aanbod_url="https://www.pararius.nl/koopwoningen/test",
    )

    assert result.discovery_strategy is DiscoveryStrategy.blocked
    assert result.blocker_reason == "aanbod_on_funda_pararius"
    assert result.recommended_action == "commercial_only"
    assert result.requests_used == 0
    assert gate_calls == ["example.com/"]


def test_known_aanbod_url_none_uses_generic_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
        }
    )

    classify_domain("example.com", fetcher=fetcher, known_aanbod_url=None)

    assert "https://example.com/aanbod" in fetcher.calls


def test_no_legacy_imports() -> None:
    source_path = Path(__file__).resolve().parents[1] / "scraper" / "src" / "domek_wonen" / "discovery" / "census.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    banned_fragments = (
        "portals",
        "properties",
        "adapters",
        "property_discovery_engine",
        "legacy",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not any(fragment in name for fragment in banned_fragments)


def test_captcha_marks_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>Attention Required! g-recaptcha</body></html>", status_code=403),
            "/sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap_index.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-json/": FakeResponse("forbidden", status_code=403),
            "/wp-json/wp/v2/types": FakeResponse("forbidden", status_code=403),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.blocked
    assert result.blocker_reason == "captcha"


def test_domain_classification_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher({"/": FakeResponse("<html><body>home</body></html>")})

    result = classify_domain("example.com", fetcher=fetcher)

    assert isinstance(result, DomainClassification)
    assert result.domain == "example.com"
    assert result.robots_status == "allow"
    assert result.structured_channel_open is False
    assert result.html_blocked_but_structured_open is False


def test_html_captcha_but_sitemap_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>Attention Required! g-recaptcha</body></html>", status_code=403),
            "/sitemap.xml": FakeResponse(
                "<urlset><url><loc>https://example.com/woning/teststraat-1</loc></url></urlset>"
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.sitemap_with_listings
    assert result.structured_channel_open is True
    assert result.html_blocked_but_structured_open is True
    assert result.recommended_action == "build_discovery"


def test_html_captcha_but_wpjson_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>Attention Required! g-recaptcha</body></html>", status_code=403),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse('{"namespaces":["wp/v2"]}'),
            "/wp-json/wp/v2/types": FakeResponse(
                '{"woning":{"slug":"woning","public":true,"rest_base":"woning"}}'
            ),
            "/wp-json/wp/v2/woning?per_page=1": FakeResponse('[{"id":1}]'),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.wp_json
    assert result.structured_channel_open is True
    assert result.html_blocked_but_structured_open is True
    assert result.recommended_action == "build_discovery"


def test_wp_sitemap_core_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse(
                "<urlset><url><loc>https://example.com/woning/teststraat-1</loc></url></urlset>"
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.sitemap_with_listings
    assert result.sitemap_found is True
    assert result.sitemap_has_listing_urls is True


def test_sitemap_index_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>home</body></html>"),
            "/sitemap.xml": FakeResponse(
                "<sitemapindex><sitemap><loc>https://example.com/woningen-sitemap.xml</loc></sitemap></sitemapindex>"
            ),
            "/woningen-sitemap.xml": FakeResponse(
                "<urlset><url><loc>https://example.com/woning/teststraat-1</loc></url></urlset>"
            ),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.sitemap_with_listings
    assert "https://example.com/woningen-sitemap.xml" in fetcher.calls


def test_wpjson_probed_even_if_not_wordpress_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>plain site</body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse('{"namespaces":["wp/v2"]}'),
            "/wp-json/wp/v2/types": FakeResponse(
                '{"woning":{"slug":"woning","public":true,"rest_base":"woning"}}'
            ),
            "/wp-json/wp/v2/woning?per_page=1": FakeResponse('[{"id":1}]'),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.cms_fingerprint_guess == "unknown"
    assert result.discovery_strategy is DiscoveryStrategy.wp_json


def test_captcha_false_positive_footer_word(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body><footer>captcha support line</footer></body></html>"),
            "/sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap_index.xml": FakeResponse("missing", status_code=404),
            "/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-sitemap.xml": FakeResponse("missing", status_code=404),
            "/sitemap/sitemap-index.xml": FakeResponse("missing", status_code=404),
            "/wp-json/": FakeResponse("missing", status_code=404),
            "/wp-json/wp/v2/types": FakeResponse("missing", status_code=404),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.no_signal
    assert result.blocker_reason is None


def test_all_channels_blocked_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_all(monkeypatch)
    fetcher = FakeFetcher(
        {
            "/": FakeResponse("<html><body>Attention Required! g-recaptcha</body></html>", status_code=403),
            "/sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap_index.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-sitemap.xml": FakeResponse("forbidden", status_code=403),
            "/sitemap/sitemap-index.xml": FakeResponse("forbidden", status_code=403),
            "/wp-json/": FakeResponse("forbidden", status_code=403),
            "/wp-json/wp/v2/types": FakeResponse("forbidden", status_code=403),
        }
    )

    result = classify_domain("example.com", fetcher=fetcher)

    assert result.discovery_strategy is DiscoveryStrategy.blocked
    assert result.blocker_reason == "captcha"
