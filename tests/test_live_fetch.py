from __future__ import annotations

from email.message import Message
from pathlib import Path
import socket
import sys
from urllib import error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.portals.adapters import funda, huislijn, pararius
from domek_wonen.portals.live_fetch import (
    DEFAULT_USER_AGENT,
    FetchResult,
    classify_http_status,
    fetch_url,
    polite_sleep,
)
from domek_wonen.portals.models import PortalMode, SourceStatus


class _StubResponse:
    def __init__(self, status: int, html: str, charset: str = "utf-8") -> None:
        self.status = status
        self._payload = html.encode(charset)
        self.headers = Message()
        self.headers.add_header("Content-Type", f"text/html; charset={charset}")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _StubResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def test_classify_http_status_maps_success_and_http_codes() -> None:
    html = "<html><body><main>" + ("x" * 100) + "</main></body></html>"
    assert classify_http_status(200, html) == SourceStatus.SUCCESS
    assert classify_http_status(403, "<html></html>") == SourceStatus.HTTP_403
    assert classify_http_status(429, "<html></html>") == SourceStatus.HTTP_429


def test_classify_http_status_detects_captcha_and_login_wall() -> None:
    assert classify_http_status(200, "<html>captcha challenge</html>") == SourceStatus.BLOCKED_CAPTCHA
    assert classify_http_status(200, "<html>Please sign in to continue</html>") == SourceStatus.PERMISSION_REQUIRED


def test_classify_http_status_distinguishes_requires_js_from_parser_broken() -> None:
    assert classify_http_status(200, "<html><body>Enable JavaScript to continue</body></html>") == SourceStatus.REQUIRES_JS
    assert classify_http_status(200, " ") == SourceStatus.PARSER_BROKEN


def test_polite_sleep_clamps_negative_values(monkeypatch) -> None:
    calls: list[float] = []

    def _fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr("domek_wonen.portals.live_fetch.time.sleep", _fake_sleep)
    polite_sleep(-1)
    polite_sleep(0.25)
    assert calls == [0.0, 0.25]


def test_fetch_url_returns_success_without_real_network(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_urlopen(request_obj, timeout: int):
        captured["url"] = request_obj.full_url
        captured["timeout"] = timeout
        captured["user_agent"] = request_obj.get_header("User-agent")
        return _StubResponse(200, "<html><body><main>" + ("ok" * 60) + "</main></body></html>")

    monkeypatch.setattr("domek_wonen.portals.live_fetch.request.urlopen", _fake_urlopen)
    result = fetch_url("https://example.test/listings", timeout_seconds=7)

    assert isinstance(result, FetchResult)
    assert result.url == "https://example.test/listings"
    assert result.status_code == 200
    assert result.source_status == SourceStatus.SUCCESS
    assert result.error_message == ""
    assert result.elapsed_ms >= 0
    assert captured == {
        "url": "https://example.test/listings",
        "timeout": 7,
        "user_agent": DEFAULT_USER_AGENT,
    }


def test_fetch_url_maps_http_403_and_http_429_without_real_network(monkeypatch) -> None:
    def _http_error(status_code: int) -> error.HTTPError:
        headers = Message()
        headers.add_header("Content-Type", "text/html; charset=utf-8")
        return error.HTTPError(
            url="https://example.test/listings",
            code=status_code,
            msg=f"HTTP {status_code}",
            hdrs=headers,
            fp=None,
        )

    monkeypatch.setattr(
        "domek_wonen.portals.live_fetch.request.urlopen",
        lambda request_obj, timeout: (_ for _ in ()).throw(_http_error(403)),
    )
    result_403 = fetch_url("https://example.test/listings")
    assert result_403.source_status == SourceStatus.HTTP_403

    monkeypatch.setattr(
        "domek_wonen.portals.live_fetch.request.urlopen",
        lambda request_obj, timeout: (_ for _ in ()).throw(_http_error(429)),
    )
    result_429 = fetch_url("https://example.test/listings")
    assert result_429.source_status == SourceStatus.HTTP_429


def test_fetch_url_maps_timeout_without_real_network(monkeypatch) -> None:
    monkeypatch.setattr(
        "domek_wonen.portals.live_fetch.request.urlopen",
        lambda request_obj, timeout: (_ for _ in ()).throw(socket.timeout("timed out")),
    )

    result = fetch_url("https://example.test/listings")
    assert result.status_code is None
    assert result.source_status == SourceStatus.TIMEOUT
    assert "timed out" in result.error_message


def test_build_search_url_accepts_page_argument() -> None:
    assert huislijn.build_search_url("Tilburg", page=1) == "https://www.huislijn.nl/koopwoning/nederland/tilburg"
    assert pararius.build_search_url("Tilburg", page=1) == "https://www.pararius.nl/koopwoningen/tilburg"
    assert funda.build_search_url("Tilburg", page=1) == (
        "https://www.funda.nl/zoeken/koop?selected_area=%5B%22tilburg%22%5D"
    )


def test_benchmark_only_portals_remain_restricted() -> None:
    assert funda.portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED
    assert pararius.portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED
