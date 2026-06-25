from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots import ogonline_xhr_live_fetch  # noqa: E402
from domek_wonen.pilots.ogonline_xhr_live_fetch import (  # noqa: E402
    ControlledJSONFetchContentTypeError,
    ControlledJSONFetchParseError,
    ControlledJSONFetchStatusError,
    controlled_http_fetch_json,
    run_kin_ogonline_live_paginated_pilot,
)


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/json") -> None:
        self.body = body
        self.status = status
        self._content_type = content_type

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def getheader(self, name: str) -> str:
        if name.lower() == "content-type":
            return self._content_type
        return ""


def test_controlled_http_fetch_json_returns_valid_json_string(monkeypatch) -> None:
    calls: list[tuple[object, float]] = []

    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(b'{"docs": []}', content_type="application/json; charset=utf-8")

    monkeypatch.setattr(ogonline_xhr_live_fetch, "urlopen", fake_urlopen)

    result = controlled_http_fetch_json("https://cpl01.ogonline.nl/api/listings", timeout_seconds=3.5)

    assert result == '{"docs": []}'
    assert len(calls) == 1
    assert calls[0][1] == 3.5


def test_controlled_http_fetch_json_status_error(monkeypatch) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        return FakeResponse(b'{"error": true}', status=403)

    monkeypatch.setattr(ogonline_xhr_live_fetch, "urlopen", fake_urlopen)

    try:
        controlled_http_fetch_json("https://cpl01.ogonline.nl/api/listings")
    except ControlledJSONFetchStatusError as exc:
        assert "HTTP status 403" in str(exc)
    else:
        raise AssertionError("expected ControlledJSONFetchStatusError")


def test_controlled_http_fetch_json_rejects_non_json_content_type(monkeypatch) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        return FakeResponse(b'{"docs": []}', content_type="text/html")

    monkeypatch.setattr(ogonline_xhr_live_fetch, "urlopen", fake_urlopen)

    try:
        controlled_http_fetch_json("https://cpl01.ogonline.nl/api/listings")
    except ControlledJSONFetchContentTypeError as exc:
        assert "Unsupported content-type text/html" in str(exc)
    else:
        raise AssertionError("expected ControlledJSONFetchContentTypeError")


def test_controlled_http_fetch_json_rejects_invalid_json_body(monkeypatch) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        return FakeResponse(b"{invalid", content_type="text/plain")

    monkeypatch.setattr(ogonline_xhr_live_fetch, "urlopen", fake_urlopen)

    try:
        controlled_http_fetch_json("https://cpl01.ogonline.nl/api/listings")
    except ControlledJSONFetchParseError as exc:
        assert "Invalid JSON payload" in str(exc)
    else:
        raise AssertionError("expected ControlledJSONFetchParseError")


def test_run_kin_ogonline_live_paginated_pilot_uses_runner_with_max_pages(monkeypatch) -> None:
    calls: list[tuple[str, object, int]] = []

    def fake_runner(config, *, fetch_json, max_pages):
        calls.append((config.source_id, fetch_json, max_pages))
        return "sentinel-result"

    monkeypatch.setattr(ogonline_xhr_live_fetch, "run_ogonline_xhr_paginated_config", fake_runner)

    result = run_kin_ogonline_live_paginated_pilot(config_path=CONFIG_FIXTURE, max_pages=2)

    assert result == "sentinel-result"
    assert calls == [("kinmakelaars.nl__breda", controlled_http_fetch_json, 2)]


def test_ogonline_xhr_live_fetch_module_has_no_disallowed_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_xhr_live_fetch.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
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
