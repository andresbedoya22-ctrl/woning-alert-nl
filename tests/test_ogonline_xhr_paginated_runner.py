from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.parsers.source_config import ParserSourceConfig, load_parser_source_config  # noqa: E402
from domek_wonen.pilots import run_ogonline_xhr_paginated_config  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
PAGE_1_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "ogonline_xhr_page_1_fixture.json"
PAGE_2_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "ogonline_xhr_page_2_fixture.json"


def _config() -> ParserSourceConfig:
    return load_parser_source_config(CONFIG_FIXTURE)


def _fixture_by_url(api_url: str) -> str:
    if "page=1" in api_url:
        return PAGE_1_FIXTURE.read_text(encoding="utf-8")
    if "page=2" in api_url:
        return PAGE_2_FIXTURE.read_text(encoding="utf-8")
    raise AssertionError(f"unexpected api_url: {api_url}")


def test_runs_page_1_and_page_2_with_injected_fetch_json(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    def fetch_json(api_url: str) -> str:
        fetched_urls.append(api_url)
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=2)

    assert result.source_id == "kinmakelaars.nl__breda"
    assert result.source_domain == "kinmakelaars.nl"
    assert result.pages_attempted == 2
    assert result.pages_succeeded == 2
    assert len(result.page_results) == 2
    assert len(fetched_urls) == 2
    assert "page=1" in fetched_urls[0]
    assert "page=2" in fetched_urls[1]
    assert all("limit=24" in api_url for api_url in fetched_urls)


def test_robots_gate_false_does_not_call_fetch_json(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def can_fetch(domain: str, path: str) -> bool:
        calls.append((domain, path))
        return False

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_urls: list[str] = []

    def fetch_json(api_url: str) -> str:
        fetched_urls.append(api_url)
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=1)

    assert fetched_urls == []
    assert calls == [
        (
            "cpl01.ogonline.nl",
            "/api/listings?depth=1&locale=nl&sort=-id&where%5Bmarket%5D%5Bequals%5D=consumer&where%5Bcategory%5D%5Bequals%5D=listing&where%5BisSales%5D%5Bequals%5D=true&where%5Bstatus%5D%5Bnot_in%5D=sold%2Crented&where%5Baccount%5D%5Bequals%5D=66aa38af0773b21cac8f8da0&page=1&limit=24",
        )
    ]
    assert result.pages_attempted == 1
    assert result.pages_succeeded == 0
    assert result.page_results[0].fetch_status == "blocked_by_robots"
    assert result.page_results[0].can_fetch is False
    assert "robots_gate_blocked" in result.page_results[0].warnings


def test_robots_gate_exception_blocks_fetch_with_warning(monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        raise RuntimeError("robots unavailable")

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=1)

    assert fetched is False
    assert result.page_results[0].fetch_status == "blocked_by_robots"
    assert "robots_gate_exception" in result.page_results[0].warnings


def test_fetch_json_exception_records_fetch_failed_and_continues(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    def fetch_json(api_url: str) -> str:
        fetched_urls.append(api_url)
        if "page=1" in api_url:
            raise RuntimeError("network disabled in test")
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=2)

    assert len(fetched_urls) == 2
    assert result.pages_attempted == 2
    assert result.pages_succeeded == 1
    assert result.page_results[0].fetch_status == "fetch_failed"
    assert result.page_results[0].warnings == ("fetch_json_exception",)
    assert result.page_results[1].fetch_status == "success"


def test_invalid_json_records_parser_failed_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=lambda api_url: "{invalid", max_pages=1)

    assert result.pages_attempted == 1
    assert result.pages_succeeded == 0
    assert result.page_results[0].fetch_status == "parser_failed"
    assert result.page_results[0].parser_listing_count == 0
    assert "invalid_json" in result.page_results[0].warnings


def test_accumulates_parser_and_qa_counts(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=_fixture_by_url, max_pages=2)

    assert [page.parser_listing_count for page in result.page_results] == [3, 2]
    assert result.total_parser_listings == 5
    assert result.total_clean == 4
    assert result.total_review == 1
    assert result.total_rejected == 0


def test_max_pages_1_runs_only_one_page(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    def fetch_json(api_url: str) -> str:
        fetched_urls.append(api_url)
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=1)

    assert len(fetched_urls) == 1
    assert result.pages_attempted == 1
    assert result.total_parser_listings == 3
    assert "page=1" in fetched_urls[0]


def test_max_pages_less_than_or_equal_zero_returns_empty_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _fixture_by_url(api_url)

    result = run_ogonline_xhr_paginated_config(_config(), fetch_json=fetch_json, max_pages=0)

    assert fetched is False
    assert result.pages_attempted == 0
    assert result.pages_succeeded == 0
    assert result.page_results == ()
    assert result.warnings == ("max_pages_must_be_positive",)


def test_non_ogonline_config_fails_stably() -> None:
    config = ParserSourceConfig(
        source_id="example-realworks",
        source_domain="example.nl",
        listing_url="https://example.nl/aanbod",
        parser_family="realworks_public",
        delivery_mode="realworks_public",
    )

    try:
        run_ogonline_xhr_paginated_config(config, fetch_json=lambda api_url: "{}")
    except ValueError as exc:
        assert str(exc) == "unsupported_parser_family"
    else:
        raise AssertionError("expected ValueError")


def test_config_without_api_fails_stably() -> None:
    config = ParserSourceConfig(
        source_id="example",
        source_domain="example.nl",
        listing_url="https://example.nl/aanbod",
        parser_family="ogonline_xhr",
        delivery_mode="ogonline_xhr",
    )

    try:
        run_ogonline_xhr_paginated_config(config, fetch_json=lambda api_url: "{}")
    except ValueError as exc:
        assert str(exc) == "missing_paginated_api_config"
    else:
        raise AssertionError("expected ValueError")


def test_ogonline_xhr_paginated_runner_module_has_no_fetcher_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_xhr_paginated_runner.py"
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
    assert "urllib" not in imported_roots
    assert "playwright" not in imported_roots
    assert "selenium" not in imported_roots
