from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.pilots import (  # noqa: E402
    CapturePilotSource,
    can_capture_source,
    run_realworks_capture_pilot,
    run_realworks_capture_pilot_for_source,
)


CAPTURED_AT = "2026-06-24T12:00:00Z"


def _source(listing_url: str = "https://example.nl/aanbod/woningaanbod") -> CapturePilotSource:
    return CapturePilotSource(
        source_id="example-realworks",
        source_domain="example.nl",
        listing_url=listing_url,
    )


def _fixture_html() -> str:
    return (BASE_DIR / "tests" / "fixtures" / "parsers" / "realworks_listing_fixture.html").read_text(
        encoding="utf-8"
    )


def test_robots_gate_blocked_does_not_call_fetch_html(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    called = False

    def fetch_html(url: str) -> str:
        nonlocal called
        called = True
        return _fixture_html()

    result = run_realworks_capture_pilot_for_source(_source(), fetch_html, CAPTURED_AT)

    assert called is False
    assert result.capture_status == "blocked_by_robots"
    assert result.can_fetch is False
    assert result.safe_to_compare_removals is False
    assert result.warnings == ("robots_gate_blocked",)


def test_invalid_url_is_blocked_without_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    called = False

    def fetch_html(url: str) -> str:
        nonlocal called
        called = True
        return _fixture_html()

    result = run_realworks_capture_pilot_for_source(_source("not-a-url"), fetch_html, CAPTURED_AT)

    assert called is False
    assert result.capture_status == "blocked_by_robots"
    assert result.can_fetch is False
    assert result.safe_to_compare_removals is False
    assert result.warnings == ("invalid_listing_url",)


def test_can_capture_source_uses_listing_url_domain_and_path(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def can_fetch(domain: str, path: str) -> bool:
        calls.append((domain, path))
        return True

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)

    assert can_capture_source(_source("https://Example.nl/aanbod/woningaanbod?page=1")) is True
    assert calls == [("example.nl", "/aanbod/woningaanbod?page=1")]


def test_fetch_html_exception_produces_fetch_failed(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        raise RuntimeError("network disabled in test")

    result = run_realworks_capture_pilot_for_source(_source(), fetch_html, CAPTURED_AT)

    assert result.capture_status == "fetch_failed"
    assert result.can_fetch is True
    assert result.safe_to_compare_removals is False
    assert result.warnings == ("fetch_html_exception",)


def test_empty_fetch_html_produces_fetch_failed(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_realworks_capture_pilot_for_source(_source(), lambda url: "   ", CAPTURED_AT)

    assert result.capture_status == "fetch_failed"
    assert result.safe_to_compare_removals is False
    assert result.warnings == ("empty_html",)


def test_successful_fake_html_flows_through_parser_qa_and_inventory(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_realworks_capture_pilot_for_source(_source(), lambda url: _fixture_html(), CAPTURED_AT)

    assert result.capture_status == "success"
    assert result.can_fetch is True
    assert result.parser_listing_count == 3
    assert result.clean_count == 2
    assert result.review_count == 1
    assert result.rejected_count == 0
    assert result.inventory_count == 2
    assert result.safe_to_compare_removals is True


def test_parser_no_listings_is_not_safe_to_compare(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_realworks_capture_pilot_for_source(_source(), lambda url: "<html></html>", CAPTURED_AT)

    assert result.capture_status == "parser_failed"
    assert result.parser_listing_count == 0
    assert result.inventory_count == 0
    assert result.safe_to_compare_removals is False
    assert "parser_no_listings" in result.warnings


def test_run_realworks_capture_pilot_respects_default_max_sources(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    sources = [
        _source(f"https://example.nl/aanbod/woningaanbod/{index}")
        for index in range(7)
    ]
    fetched_urls: list[str] = []

    def fetch_html(url: str) -> str:
        fetched_urls.append(url)
        return _fixture_html()

    results = run_realworks_capture_pilot(sources, fetch_html, CAPTURED_AT)

    assert len(results) == 5
    assert len(fetched_urls) == 5
    assert [result.capture_status for result in results] == ["success"] * 5


def test_run_realworks_capture_pilot_respects_explicit_max_sources(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    sources = [_source(f"https://example.nl/aanbod/woningaanbod/{index}") for index in range(3)]

    results = run_realworks_capture_pilot(sources, lambda url: _fixture_html(), CAPTURED_AT, max_sources=2)

    assert len(results) == 2


def test_realworks_capture_pilot_module_has_no_fetcher_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "realworks_capture_pilot.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    imported_roots = {module.split(".")[0] for module in imported_modules}
    assert "requests" not in imported_roots
    assert "httpx" not in imported_roots
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots
