from pathlib import Path
import ast
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.pilots import kin_ogonline_full_validation_audit as full_audit  # noqa: E402
from domek_wonen.pilots import kin_ogonline_validation_audit as five_page_audit  # noqa: E402
from domek_wonen.parsers.source_config import load_parser_source_config  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_ogonline_full_validation_audit.py"


def _config():
    return load_parser_source_config(CONFIG_FIXTURE)


def _minimal_doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-full-{index:03d}",
        "url": f"https://kinmakelaars.nl/aanbod/wonen/breda/full-{index}/kin-full-{index:03d}",
        "street": "Fullstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 410000 + index,
        "isSales": True,
        "status": "available",
    }
    doc.update(overrides)
    return doc


def _api_payload(
    *docs: dict[str, object],
    total_pages: int | None = None,
    total_docs: int | None = None,
    has_next: bool | None = None,
) -> str:
    payload: dict[str, object] = {"docs": list(docs)}
    if total_pages is not None:
        payload["totalPages"] = total_pages
    if total_docs is not None:
        payload["totalDocs"] = total_docs
    if has_next is not None:
        payload["hasNextPage"] = has_next
    return json.dumps(payload)


def _page_number(api_url: str) -> int:
    for page in range(1, 30):
        if f"page={page}" in api_url:
            return page
    raise AssertionError(f"unexpected api_url: {api_url}")


def _detail_html(candidate: str, *, open_house: bool = False) -> str:
    open_house_text = ', "openHouse": true, "badge": "Open huis"' if open_house else ""
    return f'<script>window.__DETAIL__ = {{"subtype":"{candidate}"{open_house_text}}}</script>'


def test_uses_total_pages_when_available(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[int] = []

    def fetch_json(api_url: str) -> str:
        page = _page_number(api_url)
        fetched_pages.append(page)
        return _api_payload(_minimal_doc(page), total_pages=3, total_docs=3, has_next=page < 3)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        max_api_pages=25,
    )

    assert fetched_pages == [1, 2, 3]
    assert result.total_pages_reported == 3
    assert result.total_docs_reported == 3
    assert result.pages_requested == 3
    assert result.pages_attempted == 3


def test_uses_has_next_page_when_total_pages_missing(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[int] = []

    def fetch_json(api_url: str) -> str:
        page = _page_number(api_url)
        fetched_pages.append(page)
        return _api_payload(_minimal_doc(page), has_next=page < 3)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Appartement"),
        max_api_pages=25,
    )

    assert fetched_pages == [1, 2, 3]
    assert result.total_pages_reported is None
    assert result.pages_requested == 3
    assert result.pages_attempted == 3


def test_max_api_pages_caps_reported_pages(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[int] = []

    def fetch_json(api_url: str) -> str:
        page = _page_number(api_url)
        fetched_pages.append(page)
        return _api_payload(_minimal_doc(page), total_pages=99, total_docs=99, has_next=True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        max_api_pages=2,
    )

    assert fetched_pages == [1, 2]
    assert result.pages_requested == 2
    assert result.pages_attempted == 2
    assert "full_audit_api_pages_capped" in result.warnings


def test_max_detail_enrichment_limits_detail_fetches(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_details: list[str] = []

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(
            _minimal_doc(1),
            _minimal_doc(2),
            _minimal_doc(3),
            total_pages=1,
            total_docs=3,
        ),
        fetch_html=lambda url: fetched_details.append(url) or _detail_html("Tussenwoning"),
        max_detail_enrichment=2,
    )

    assert len(fetched_details) == 2
    assert result.detail_enrichment_attempted_count == 2
    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2
    assert result.eligibility_review_count == 1
    assert "full_audit_detail_enrichment_capped" in result.warnings


def test_api_robots_false_prevents_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _api_payload(_minimal_doc(1))

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        max_api_pages=1,
    )

    assert fetched is False
    assert result.pages_attempted == 1
    assert result.pages_failed == 1
    assert "robots_gate_blocked" in result.warnings


def test_detail_robots_false_prevents_detail_fetch(monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        return domain == "cpl01.ogonline.nl"

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_details: list[str] = []

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1), total_pages=1),
        fetch_html=lambda url: fetched_details.append(url) or _detail_html("Tussenwoning"),
    )

    assert fetched_details == []
    assert result.detail_enrichment_attempted_count == 1
    assert result.detail_enrichment_succeeded_count == 0
    assert result.detail_enrichment_failed_count == 1
    assert "blocked_by_robots" in result.warnings


def test_api_fetch_exception_does_not_abort_audit(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_json(api_url: str) -> str:
        page = _page_number(api_url)
        if page == 2:
            raise RuntimeError("boom")
        return _api_payload(_minimal_doc(page), total_pages=2, total_docs=2, has_next=page < 2)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
    )

    assert result.pages_attempted == 2
    assert result.pages_succeeded == 1
    assert result.pages_failed == 1
    assert ("fetch_exception", 1) in result.warning_counts
    assert "fetch_exception" in result.warnings


def test_detail_fetch_exception_does_not_abort_audit(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        raise RuntimeError("boom")

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1), total_pages=1),
        fetch_html=fetch_html,
    )

    assert result.detail_enrichment_attempted_count == 1
    assert result.detail_enrichment_succeeded_count == 0
    assert result.detail_enrichment_failed_count == 1
    assert result.active_inventory_count == 0
    assert "fetch_exception" in result.warnings


def test_active_inventory_count_equals_snapshot_listing_count(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1), total_pages=1),
        fetch_html=lambda url: _detail_html("Appartement"),
    )

    assert result.snapshot_listing_count == result.active_inventory_count


def test_beschikbaar_enriched_tussenwoning_and_appartement_enter_active(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        return _detail_html("Appartement" if "full-2" in url else "Tussenwoning")

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1), _minimal_doc(2), total_pages=1),
        fetch_html=fetch_html,
    )

    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2


def test_onder_bod_enriched_stays_inactive_status(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1, status="under_bid"), total_pages=1),
        fetch_html=lambda url: _detail_html("Tussenwoning"),
    )

    assert result.active_inventory_count == 0
    assert result.inactive_status_count == 1
    assert result.snapshot_listing_count == 0


def test_bouwgrond_enriched_goes_to_unsupported_property_type(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1), total_pages=1),
        fetch_html=lambda url: _detail_html("Bouwgrond"),
    )

    assert result.active_inventory_count == 0
    assert result.unsupported_property_type_count == 1


def test_unknown_sold_ur_stays_review(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1, status="sold_ur"), total_pages=1),
        fetch_html=lambda url: _detail_html("Tussenwoning"),
    )

    assert result.qa_review_count == 1
    assert result.detail_enrichment_attempted_count == 0
    assert result.active_inventory_count == 0
    assert result.eligibility_review_count == 1


def test_open_huis_badge_does_not_affect_availability_status(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(_minimal_doc(1, status="available"), total_pages=1),
        fetch_html=lambda url: _detail_html("Tussenwoning", open_house=True),
    )

    assert result.parser_status_counts == (("beschikbaar", 1),)
    assert result.active_inventory_count == 1


def test_warning_counts_aggregate_expected_warnings(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    docs = (_minimal_doc(1), _minimal_doc(2), _minimal_doc(3))

    def fetch_html(url: str) -> str:
        if "full-1" in url:
            return '<script>window.__DETAIL__ = {"subtype":"Villa"}</script>'
        if "full-2" in url:
            return '<script>window.__DETAIL__ = {"subtype":"Tussenwoning", "alt":"Appartement"}</script>'
        raise RuntimeError("boom")

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: _api_payload(*docs, total_pages=1),
        fetch_html=fetch_html,
    )

    assert ("no_mapped_property_type", 1) in result.warning_counts
    assert ("ambiguous_property_type_candidates", 1) in result.warning_counts
    assert ("fetch_exception", 1) in result.warning_counts


def test_no_real_network_in_tests(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    result = full_audit.run_kin_ogonline_full_validation_audit_config(
        _config(),
        fetch_json=lambda url: fetched_urls.append(url) or _api_payload(_minimal_doc(1), total_pages=1),
        fetch_html=lambda url: _detail_html("Appartement"),
    )

    assert fetched_urls
    assert result.pages_succeeded == 1


def test_full_audit_module_has_no_disallowed_imports() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
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


def test_full_audit_module_does_not_write_outputs() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods


def test_five_page_audit_behavior_is_not_modified(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[int] = []

    def fetch_json(api_url: str) -> str:
        page = _page_number(api_url)
        fetched_pages.append(page)
        return _api_payload(_minimal_doc(page, type="house"))

    result = five_page_audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=99,
    )

    assert result.pages_requested == 5
    assert result.pages_attempted == 5
    assert fetched_pages == [1, 2, 3, 4, 5]
    assert "pages_capped_at_5" in result.warnings
