from __future__ import annotations

import ast
from pathlib import Path
import socket
import sys
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.compliance import robots_gate
from domek_wonen.runtime_settings import RuntimeSettings


class _FakeResponse:
    def __init__(self, content: str, status: int = 200) -> None:
        self.status = status
        self._content = content.encode("utf-8")

    def read(self) -> bytes:
        return self._content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_gate_cache() -> None:
    robots_gate.clear_cache()


@pytest.fixture
def runtime_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_runtime_settings(load_dotenv_file: bool = True) -> RuntimeSettings:
        return RuntimeSettings(
            user_agent="TestBot/1.0",
            min_request_interval_seconds=2,
            request_timeout_seconds=9,
        )

    monkeypatch.setattr(robots_gate, "load_runtime_settings", fake_load_runtime_settings)


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    def fake_urlopen(request, timeout: float):
        assert request.full_url.endswith("/robots.txt")
        assert request.headers["User-agent"] == "TestBot/1.0"
        assert timeout == 9.0
        return _FakeResponse(content)

    monkeypatch.setattr(robots_gate, "urlopen", fake_urlopen)


def test_disallow_all(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nDisallow: /\n")

    assert robots_gate.can_fetch("example.com") is False
    assert robots_gate.robots_status("example.com") == "disallow"


def test_allow_all(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nAllow: /\n")

    assert robots_gate.can_fetch("example.com") is True
    assert robots_gate.robots_status("example.com") == "allow"


def test_allow_specific_path(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nDisallow: /admin/\n")

    assert robots_gate.can_fetch("example.com", "/woning/") is True
    assert robots_gate.can_fetch("example.com", "/admin/") is False


def test_crawl_delay_declared(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nCrawl-delay: 5\n")

    assert robots_gate.crawl_delay("example.com") == 5.0


def test_crawl_delay_default(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nDisallow:\n")

    assert robots_gate.crawl_delay("example.com") == 2.0


def test_robots_unreachable_404(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    def fake_urlopen(request, timeout: float):
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(robots_gate, "urlopen", fake_urlopen)

    assert robots_gate.can_fetch("example.com") is True
    assert robots_gate.robots_status("example.com") == "robots_unreachable"
    assert robots_gate.crawl_delay("example.com") == 2.0


def test_robots_unreachable_timeout(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    def fake_urlopen(request, timeout: float):
        raise socket.timeout("timed out")

    monkeypatch.setattr(robots_gate, "urlopen", fake_urlopen)

    assert robots_gate.can_fetch("example.com") is True
    assert robots_gate.robots_status("example.com") == "robots_unreachable"


def test_robots_malformed(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "")

    assert robots_gate.can_fetch("example.com") is True
    assert robots_gate.robots_status("example.com") == "allow"


def test_cache_hit(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    call_count = {"value": 0}

    def fake_urlopen(request, timeout: float):
        call_count["value"] += 1
        return _FakeResponse("User-agent: *\nAllow: /\n")

    monkeypatch.setattr(robots_gate, "urlopen", fake_urlopen)

    robots_gate.fetch_robots("example.com")
    robots_gate.fetch_robots("example.com")

    assert call_count["value"] == 1


def test_clear_cache(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    _patch_urlopen(monkeypatch, "User-agent: *\nAllow: /\n")
    robots_gate.fetch_robots("example.com")

    robots_gate.clear_cache()

    assert robots_gate.robots_status("example.com") == "not_checked"


def test_not_checked_before_fetch(runtime_defaults) -> None:
    assert robots_gate.robots_status("example.com") == "not_checked"


def test_no_legacy_imports() -> None:
    source_path = Path(__file__).resolve().parents[1] / "scraper" / "src" / "domek_wonen" / "compliance" / "robots_gate.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    banned_fragments = (
        "portals.adapters",
        "portals.portal_inventory_spike",
        "portals.huislijn_inventory_spike",
        "portals.huislijn_url_discovery",
        "properties.property_discovery_engine",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module]
        else:
            continue
        for name in names:
            assert not any(fragment in name for fragment in banned_fragments)


def test_fetch_robots_uses_cache_via_can_fetch(monkeypatch: pytest.MonkeyPatch, runtime_defaults) -> None:
    call_count = {"value": 0}

    def fake_urlopen(request, timeout: float):
        call_count["value"] += 1
        return _FakeResponse("User-agent: *\nAllow: /\n")

    monkeypatch.setattr(robots_gate, "urlopen", fake_urlopen)

    assert robots_gate.can_fetch("example.com", "/woning/") is True
    assert robots_gate.can_fetch("example.com", "/other/") is True
    assert call_count["value"] == 1
