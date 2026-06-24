from pathlib import Path
import ast
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.parsers import ParserFamilyResult, ParserFamilyRunner, ParserInput  # noqa: E402
from domek_wonen.parsers.source_config import (  # noqa: E402
    ParserSourceConfig,
    SourceConfigError,
    build_paginated_api_url,
    build_parser_input_from_api_json,
    load_parser_source_config,
)
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
PAGE_1_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "ogonline_xhr_page_1_fixture.json"


def _config() -> ParserSourceConfig:
    return load_parser_source_config(CONFIG_FIXTURE)


def _fingerprint(config: ParserSourceConfig) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        access_status="allowed",
        delivery_mode=config.delivery_mode,
        parser_family_candidate=config.parser_family,
        confidence=0.84,
        evidence_signals=("ogonline",),
        blocking_signals=(),
        recommended_action="build_source_config",
        can_proceed_to_parser_family=True,
        reason="ogonline_evidence",
    )


def test_load_parser_source_config_loads_kin_fixture() -> None:
    config = _config()

    assert config.source_id == "kinmakelaars.nl__breda"
    assert config.source_domain == "kinmakelaars.nl"
    assert config.listing_url == "http://www.kinmakelaars.nl/aanbod/wonen/te-koop"
    assert config.parser_family == "ogonline_xhr"
    assert config.delivery_mode == "ogonline_xhr"
    assert config.api is not None
    assert config.api.api_base_url == "https://cpl01.ogonline.nl/api/listings"
    assert config.api.items_path == "docs"


def test_build_paginated_api_url_page_1_contains_page_and_limit() -> None:
    url = build_paginated_api_url(_config(), page=1)

    assert url.startswith("https://cpl01.ogonline.nl/api/listings?")
    assert "page=1" in url
    assert "limit=24" in url


def test_build_paginated_api_url_page_2_contains_page_2() -> None:
    url = build_paginated_api_url(_config(), page=2)

    assert "page=2" in url
    assert "limit=24" in url


def test_build_paginated_api_url_includes_url_encoded_static_query_params() -> None:
    url = build_paginated_api_url(_config(), page=1)

    assert "where%5Bmarket%5D%5Bequals%5D=consumer" in url
    assert "where%5Bcategory%5D%5Bequals%5D=listing" in url
    assert "where%5BisSales%5D%5Bequals%5D=true" in url
    assert "where%5Bstatus%5D%5Bnot_in%5D=sold%2Crented" in url
    assert "where%5Baccount%5D%5Bequals%5D=66aa38af0773b21cac8f8da0" in url
    assert "sort=-id" in url


def test_build_paginated_api_url_rejects_page_after_max_pages() -> None:
    try:
        build_paginated_api_url(_config(), page=3)
    except SourceConfigError as exc:
        assert str(exc) == "page_after_max_pages"
    else:
        raise AssertionError("expected SourceConfigError")


def test_build_paginated_api_url_rejects_page_before_start_page() -> None:
    try:
        build_paginated_api_url(_config(), page=0)
    except SourceConfigError as exc:
        assert str(exc) == "page_before_start_page"
    else:
        raise AssertionError("expected SourceConfigError")


def test_build_paginated_api_url_rejects_config_without_api() -> None:
    config = ParserSourceConfig(
        source_id="example",
        source_domain="example.nl",
        listing_url="https://example.nl/aanbod",
        parser_family="ogonline_xhr",
        delivery_mode="ogonline_xhr",
    )

    try:
        build_paginated_api_url(config, page=1)
    except SourceConfigError as exc:
        assert str(exc) == "missing_paginated_api_config"
    else:
        raise AssertionError("expected SourceConfigError")


def test_build_parser_input_from_api_json_creates_json_parser_input() -> None:
    content = PAGE_1_FIXTURE.read_text(encoding="utf-8")
    parser_input = build_parser_input_from_api_json(_config(), content, page=1)

    assert isinstance(parser_input, ParserInput)
    assert parser_input.source_id == "kinmakelaars.nl__breda"
    assert parser_input.source_domain == "kinmakelaars.nl"
    assert parser_input.content == content
    assert parser_input.content_type == "json"
    assert parser_input.metadata["parser_family"] == "ogonline_xhr"
    assert parser_input.metadata["page"] == "1"
    assert parser_input.metadata["limit"] == "24"
    assert parser_input.metadata["listing_url"] == "http://www.kinmakelaars.nl/aanbod/wonen/te-koop"


def test_parser_input_from_config_can_run_through_parser_family_runner() -> None:
    config = _config()
    parser_input = build_parser_input_from_api_json(config, PAGE_1_FIXTURE.read_text(encoding="utf-8"), page=1)

    result = ParserFamilyRunner().run(_fingerprint(config), parser_input)

    assert isinstance(result, ParserFamilyResult)
    assert result.parser_family == "ogonline_xhr"
    assert result.source_id == "kinmakelaars.nl__breda"
    assert result.source_domain == "kinmakelaars.nl"
    assert len(result.listings) == 3


def test_source_config_module_has_no_network_or_browser_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "parsers" / "source_config.py"
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
    assert "WebsiteFetcher" not in source
