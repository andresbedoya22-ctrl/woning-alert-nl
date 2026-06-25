from pathlib import Path
from urllib.error import HTTPError
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots.live_fetch import (  # noqa: E402
    ControlledFetchContentTypeError,
    ControlledFetchStatusError,
    controlled_http_fetch_html,
    keep_first_source_per_domain,
    run_selected_realworks_live_pilot,
)
from domek_wonen.pilots.realworks_capture_pilot import CapturePilotSource  # noqa: E402


CAPTURED_AT = "2026-06-24T12:00:00Z"


class FakeHeaders(dict):
    def get_content_charset(self) -> str | None:
        content_type = self.get("Content-Type", "")
        for part in content_type.split(";")[1:]:
            key, separator, value = part.strip().partition("=")
            if separator and key.lower() == "charset":
                return value.strip()
        return None


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        self.body = body
        self.status = status
        self.headers = FakeHeaders({"Content-Type": content_type})

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def getheader(self, name: str) -> str | None:
        return self.headers.get(name)

    def read(self) -> bytes:
        return self.body


def _source(source_id: str, domain: str, url: str | None = None) -> CapturePilotSource:
    return CapturePilotSource(
        source_id=source_id,
        source_domain=domain,
        listing_url=url or f"https://{domain}/woningaanbod",
    )


def test_keep_first_source_per_domain_eliminates_duplicate_domains() -> None:
    sources = (
        _source("kin-breda", "kinmakelaars.nl", "https://kinmakelaars.nl/breda"),
        _source("kin-tilburg", "kinmakelaars.nl", "https://kinmakelaars.nl/tilburg"),
        _source("hypodomus", "hypodomus-breda.nl"),
    )

    selected = keep_first_source_per_domain(sources)

    assert [source.source_id for source in selected] == ["kin-breda", "hypodomus"]


def test_keep_first_source_per_domain_respects_max_sources() -> None:
    sources = (
        _source("one", "one.nl"),
        _source("two", "two.nl"),
        _source("three", "three.nl"),
    )

    selected = keep_first_source_per_domain(sources, max_sources=2)

    assert [source.source_id for source in selected] == ["one", "two"]
    assert keep_first_source_per_domain(sources, max_sources=0) == ()


def test_run_selected_realworks_live_pilot_passes_default_max_sources(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_run_realworks_capture_pilot(*, sources, fetch_html, captured_at, max_sources):
        calls["sources"] = sources
        calls["fetch_html"] = fetch_html
        calls["captured_at"] = captured_at
        calls["max_sources"] = max_sources
        return []

    monkeypatch.setattr(
        "domek_wonen.pilots.live_fetch.run_realworks_capture_pilot",
        fake_run_realworks_capture_pilot,
    )
    sources = [_source("one", "one.nl")]

    assert run_selected_realworks_live_pilot(sources, captured_at=CAPTURED_AT) == []

    assert calls == {
        "sources": sources,
        "fetch_html": controlled_http_fetch_html,
        "captured_at": CAPTURED_AT,
        "max_sources": 3,
    }


def test_controlled_http_fetch_html_returns_valid_html(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse("<html>ok</html>".encode("utf-8"))

    monkeypatch.setattr("domek_wonen.pilots.live_fetch.urlopen", fake_urlopen)

    html = controlled_http_fetch_html("https://example.nl/woningaanbod", timeout_seconds=3.5)

    assert html == "<html>ok</html>"
    assert captured["timeout"] == 3.5
    assert captured["request"].headers["User-agent"].startswith("WoningAlertNL-ControlledPilot")


def test_controlled_http_fetch_html_status_error_from_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "domek_wonen.pilots.live_fetch.urlopen",
        lambda request, timeout: FakeResponse(b"blocked", status=403),
    )

    try:
        controlled_http_fetch_html("https://example.nl/forbidden")
    except ControlledFetchStatusError as exc:
        assert "HTTP status 403" in str(exc)
    else:
        raise AssertionError("Expected ControlledFetchStatusError")


def test_controlled_http_fetch_html_status_error_from_http_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("domek_wonen.pilots.live_fetch.urlopen", fake_urlopen)

    try:
        controlled_http_fetch_html("https://example.nl/not-found")
    except ControlledFetchStatusError as exc:
        assert "HTTP status 404" in str(exc)
    else:
        raise AssertionError("Expected ControlledFetchStatusError")


def test_controlled_http_fetch_html_rejects_non_text_content_type(monkeypatch) -> None:
    monkeypatch.setattr(
        "domek_wonen.pilots.live_fetch.urlopen",
        lambda request, timeout: FakeResponse(b"{}", content_type="application/json"),
    )

    try:
        controlled_http_fetch_html("https://example.nl/data.json")
    except ControlledFetchContentTypeError as exc:
        assert "Unsupported content-type application/json" in str(exc)
    else:
        raise AssertionError("Expected ControlledFetchContentTypeError")


def test_controlled_live_fetch_module_has_no_browser_or_external_http_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "live_fetch.py"
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
