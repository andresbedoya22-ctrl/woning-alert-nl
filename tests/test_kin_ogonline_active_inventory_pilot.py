from pathlib import Path
import ast
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.pilots import kin_ogonline_active_inventory_pilot as pilot  # noqa: E402
from domek_wonen.pilots import run_kin_ogonline_active_inventory_pilot  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
PAGE_FIXTURES = BASE_DIR / "tests" / "fixtures" / "pilots" / "kin_ogonline_active_inventory_pages"


def _fixture_by_url(api_url: str) -> str:
    if "page=1" in api_url:
        return PAGE_FIXTURES.joinpath("page_1.json").read_text(encoding="utf-8")
    if "page=2" in api_url:
        return PAGE_FIXTURES.joinpath("page_2.json").read_text(encoding="utf-8")
    raise AssertionError(f"unexpected api_url: {api_url}")


def _single_page_docs(*docs: dict[str, object]):
    def fetch_json(api_url: str) -> str:
        if "page=1" in api_url:
            return json.dumps({"docs": list(docs)})
        if "page=2" in api_url:
            return json.dumps({"docs": []})
        raise AssertionError(f"unexpected api_url: {api_url}")

    return fetch_json


def _minimal_doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-enrich-{index:03d}",
        "url": f"https://kinmakelaars.nl/aanbod/wonen/breda/enrich-{index}/kin-enrich-{index:03d}",
        "street": "Enrichstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 400000 + index,
        "isSales": True,
        "status": "available",
    }
    doc.update(overrides)
    return doc


def _detail_html(candidate: str) -> str:
    return f"<script>window.__DETAIL__ = {{\"subtype\":\"{candidate}\"}}</script>"


def test_pilot_counts_parser_qa_eligibility_and_active_only_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _fixture_by_url)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=2)

    assert result.source_id == "kinmakelaars.nl__breda"
    assert result.source_domain == "kinmakelaars.nl"
    assert result.pages_attempted == 2
    assert result.pages_succeeded == 2
    assert result.parser_listing_count == 5
    assert result.qa_clean_count == 4
    assert result.qa_review_count == 1
    assert result.qa_rejected_count == 0
    assert result.active_inventory_count == 2
    assert result.inactive_status_count == 1
    assert result.unsupported_transaction_type_count == 0
    assert result.unsupported_property_type_count == 1
    assert result.eligibility_review_count == 1
    assert result.snapshot_listing_count == result.active_inventory_count
    assert result.detail_enrichment_attempted_count == 0
    assert result.detail_enrichment_succeeded_count == 0
    assert result.detail_enriched_count == 0


def test_onder_bod_clean_listing_stays_inactive_and_out_of_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _fixture_by_url)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=1)

    assert result.parser_listing_count == 3
    assert result.qa_clean_count == 2
    assert result.active_inventory_count == 1
    assert result.inactive_status_count == 1
    assert result.snapshot_listing_count == 1


def test_sold_ur_unknown_status_stays_review_and_out_of_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _fixture_by_url)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=1)

    assert result.qa_review_count == 1
    assert result.eligibility_review_count == 1
    assert result.snapshot_listing_count == 1


def test_unsupported_property_type_stays_out_of_active_inventory(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _fixture_by_url)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=2)

    assert result.unsupported_property_type_count == 1
    assert result.active_inventory_count == 2
    assert result.snapshot_listing_count == 2


def test_max_pages_greater_than_two_is_capped(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    def fetch_json(api_url: str) -> str:
        fetched_urls.append(api_url)
        return _fixture_by_url(api_url)

    monkeypatch.setattr(pilot, "controlled_http_fetch_json", fetch_json)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=99)

    assert len(fetched_urls) == 2
    assert result.pages_attempted == 2
    assert result.pages_succeeded == 2
    assert "max_pages_capped_at_2" in result.warnings


def test_max_pages_less_than_or_equal_zero_returns_stable_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _fixture_by_url(api_url)

    monkeypatch.setattr(pilot, "controlled_http_fetch_json", fetch_json)

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=0)

    assert fetched is False
    assert result.pages_attempted == 0
    assert result.pages_succeeded == 0
    assert result.snapshot_listing_count == 0
    assert result.warnings == ("max_pages_must_be_positive",)


def test_default_detail_property_type_enrichment_false_preserves_empty_type_behavior(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _single_page_docs(_minimal_doc(1)))

    result = run_kin_ogonline_active_inventory_pilot(config_path=CONFIG_FIXTURE, max_pages=1)

    assert result.qa_clean_count == 1
    assert result.active_inventory_count == 0
    assert result.eligibility_review_count == 1
    assert result.detail_enrichment_attempted_count == 0
    assert result.snapshot_listing_count == 0


def test_detail_property_type_enrichment_can_promote_clean_available_rows_to_active(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(
        pilot,
        "controlled_http_fetch_json",
        _single_page_docs(_minimal_doc(1), _minimal_doc(2)),
    )
    monkeypatch.setattr(
        pilot,
        "controlled_http_fetch_html",
        lambda url: _detail_html("Appartement" if "enrich-2" in url else "Tussenwoning"),
    )

    result = run_kin_ogonline_active_inventory_pilot(
        config_path=CONFIG_FIXTURE,
        max_pages=1,
        enrich_detail_property_type=True,
        max_detail_enrichment=5,
    )

    assert result.detail_enrichment_attempted_count == 2
    assert result.detail_enrichment_succeeded_count == 2
    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2
    assert result.eligibility_review_count == 0
    assert result.snapshot_listing_count == result.active_inventory_count


def test_enriched_onder_bod_listing_stays_inactive_not_active(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _single_page_docs(_minimal_doc(1, status="under_bid")))
    monkeypatch.setattr(pilot, "controlled_http_fetch_html", lambda url: _detail_html("Tussenwoning"))

    result = run_kin_ogonline_active_inventory_pilot(
        config_path=CONFIG_FIXTURE,
        max_pages=1,
        enrich_detail_property_type=True,
    )

    assert result.detail_enriched_count == 1
    assert result.active_inventory_count == 0
    assert result.inactive_status_count == 1
    assert result.snapshot_listing_count == 0


def test_enriched_bouwgrond_goes_to_unsupported_property_type(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(pilot, "controlled_http_fetch_json", _single_page_docs(_minimal_doc(1)))
    monkeypatch.setattr(pilot, "controlled_http_fetch_html", lambda url: _detail_html("Bouwgrond"))

    result = run_kin_ogonline_active_inventory_pilot(
        config_path=CONFIG_FIXTURE,
        max_pages=1,
        enrich_detail_property_type=True,
    )

    assert result.detail_enriched_count == 1
    assert result.active_inventory_count == 0
    assert result.unsupported_property_type_count == 1
    assert result.snapshot_listing_count == result.active_inventory_count


def test_max_detail_enrichment_is_respected(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    monkeypatch.setattr(
        pilot,
        "controlled_http_fetch_json",
        _single_page_docs(_minimal_doc(1), _minimal_doc(2), _minimal_doc(3)),
    )
    fetched_urls: list[str] = []

    def fetch_html(url: str) -> str:
        fetched_urls.append(url)
        return _detail_html("Tussenwoning")

    monkeypatch.setattr(pilot, "controlled_http_fetch_html", fetch_html)

    result = run_kin_ogonline_active_inventory_pilot(
        config_path=CONFIG_FIXTURE,
        max_pages=1,
        enrich_detail_property_type=True,
        max_detail_enrichment=2,
    )

    assert len(fetched_urls) == 2
    assert result.detail_enrichment_attempted_count == 2
    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2
    assert result.eligibility_review_count == 1


def test_pilot_module_has_no_disallowed_imports() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_ogonline_active_inventory_pilot.py"
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


def test_pilot_module_does_not_write_outputs() -> None:
    module_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_ogonline_active_inventory_pilot.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods
