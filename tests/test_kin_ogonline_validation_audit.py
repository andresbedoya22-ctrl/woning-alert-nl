from pathlib import Path
import ast
import json
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.pilots import kin_ogonline_validation_audit as audit  # noqa: E402
from domek_wonen.parsers.source_config import load_parser_source_config  # noqa: E402


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_ogonline_validation_audit.py"


def _config():
    return load_parser_source_config(CONFIG_FIXTURE)


def _minimal_doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-audit-{index:03d}",
        "url": f"https://kinmakelaars.nl/aanbod/wonen/breda/audit-{index}/kin-audit-{index:03d}",
        "street": "Auditstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 390000 + index,
        "isSales": True,
        "status": "available",
    }
    doc.update(overrides)
    return doc


def _api_payload(*docs: dict[str, object]) -> str:
    return json.dumps({"docs": list(docs)})


def _single_doc_per_page_fetch(fetched_urls: list[str] | None = None):
    def fetch_json(api_url: str) -> str:
        if fetched_urls is not None:
            fetched_urls.append(api_url)
        for page in range(1, 6):
            if f"page={page}" in api_url:
                return _api_payload(_minimal_doc(page, type="house"))
        raise AssertionError(f"unexpected api_url: {api_url}")

    return fetch_json


def _single_page_fetch(*docs: dict[str, object]):
    def fetch_json(api_url: str) -> str:
        if "page=1" in api_url:
            return _api_payload(*docs)
        if any(f"page={page}" in api_url for page in range(2, 6)):
            return _api_payload(_minimal_doc(100 + len(api_url), type="house"))
        raise AssertionError(f"unexpected api_url: {api_url}")

    return fetch_json


def _detail_html(candidate: str, *, open_house: bool = False) -> str:
    open_house_text = ', "openHouse": true, "badge": "Open huis"' if open_house else ""
    return f'<script>window.__DETAIL__ = {{"subtype":"{candidate}"{open_house_text}}}</script>'


def test_pages_greater_than_five_is_capped(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_doc_per_page_fetch(fetched_urls),
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=99,
    )

    assert result.pages_requested == 5
    assert result.pages_attempted == 5
    assert len(fetched_urls) == 5
    assert "pages_capped_at_5" in result.warnings


def test_pages_less_than_or_equal_zero_returns_stable_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _api_payload(_minimal_doc(1))

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=0,
    )

    assert fetched is False
    assert result.pages_requested == 0
    assert result.pages_attempted == 0
    assert result.warnings == ("pages_must_be_positive",)


def test_max_detail_enrichment_limits_detail_fetches(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_details: list[str] = []

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1), _minimal_doc(2), _minimal_doc(3)),
        fetch_html=lambda url: fetched_details.append(url) or _detail_html("Appartement"),
        pages=1,
        max_detail_enrichment=2,
    )

    assert len(fetched_details) == 2
    assert result.detail_enrichment_attempted_count == 2
    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2
    assert result.eligibility_review_count == 1


def test_audit_aggregates_parser_qa_enrichment_eligibility_and_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    docs = (
        _minimal_doc(1),
        _minimal_doc(2, status="under_bid"),
        _minimal_doc(3, status="sold_ur"),
        _minimal_doc(4, isSales=False, isRentals=True),
        _minimal_doc(5),
    )

    def fetch_html(url: str) -> str:
        if "audit-5" in url:
            return _detail_html("Bouwgrond")
        return _detail_html("Tussenwoning")

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(*docs),
        fetch_html=fetch_html,
        pages=1,
    )

    assert result.parser_listing_count == 5
    assert result.qa_clean_count == 4
    assert result.qa_review_count == 1
    assert result.qa_rejected_count == 0
    assert result.detail_enrichment_attempted_count == 3
    assert result.detail_enrichment_succeeded_count == 3
    assert result.detail_enriched_count == 3
    assert result.active_inventory_count == 1
    assert result.inactive_status_count == 1
    assert result.unsupported_transaction_type_count == 1
    assert result.unsupported_property_type_count == 1
    assert result.eligibility_review_count == 1
    assert result.snapshot_listing_count == result.active_inventory_count
    assert ("beschikbaar", 3) in result.parser_status_counts
    assert ("unknown", 1) in result.parser_status_counts
    assert ("active_inventory", 1) in result.eligibility_decision_counts
    assert ("bouwgrond", 1) in result.property_type_counts
    assert ("tussenwoning", 2) in result.property_type_counts
    assert ("unknown", 1) in result.property_type_counts


def test_beschikbaar_enriched_tussenwoning_and_appartement_enter_active(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        return _detail_html("Appartement" if "audit-2" in url else "Tussenwoning")

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1), _minimal_doc(2)),
        fetch_html=fetch_html,
        pages=1,
    )

    assert result.detail_enriched_count == 2
    assert result.active_inventory_count == 2
    assert result.snapshot_listing_count == 2


def test_onder_bod_enriched_stays_inactive_status(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1, status="under_bid")),
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=1,
    )

    assert result.detail_enriched_count == 1
    assert result.active_inventory_count == 0
    assert result.inactive_status_count == 1
    assert result.snapshot_listing_count == 0


def test_bouwgrond_enriched_goes_to_unsupported_property_type(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1)),
        fetch_html=lambda url: _detail_html("Bouwgrond"),
        pages=1,
    )

    assert result.detail_enriched_count == 1
    assert result.active_inventory_count == 0
    assert result.unsupported_property_type_count == 1
    assert result.snapshot_listing_count == 0


def test_unknown_sold_ur_stays_review(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1, status="sold_ur")),
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=1,
    )

    assert result.qa_review_count == 1
    assert result.detail_enrichment_attempted_count == 0
    assert result.active_inventory_count == 0
    assert result.eligibility_review_count == 1


def test_open_huis_badge_does_not_affect_availability_status(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1, status="available")),
        fetch_html=lambda url: _detail_html("Tussenwoning", open_house=True),
        pages=1,
    )

    assert result.parser_status_counts == (("beschikbaar", 1),)
    assert result.active_inventory_count == 1
    assert result.snapshot_listing_count == 1


def test_no_real_network_in_tests(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_urls: list[str] = []

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=lambda url: fetched_urls.append(url) or _api_payload(_minimal_doc(1, type="house")),
        fetch_html=lambda url: _detail_html("Appartement"),
        pages=1,
    )

    assert fetched_urls
    assert result.pages_succeeded == 1


def test_audit_module_has_no_disallowed_imports() -> None:
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


def test_audit_module_does_not_write_outputs() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    written_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in written_methods


def test_api_robots_false_prevents_fetch(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: False)
    fetched = False

    def fetch_json(api_url: str) -> str:
        nonlocal fetched
        fetched = True
        return _api_payload(_minimal_doc(1))

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=fetch_json,
        fetch_html=lambda url: _detail_html("Tussenwoning"),
        pages=1,
    )

    assert fetched is False
    assert result.pages_attempted == 1
    assert result.pages_succeeded == 0
    assert result.detail_enrichment_attempted_count == 0
    assert "robots_gate_blocked" in result.warnings


def test_detail_robots_false_prevents_detail_fetch(monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        return domain == "cpl01.ogonline.nl"

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_details: list[str] = []

    result = audit.run_kin_ogonline_validation_audit_config(
        _config(),
        fetch_json=_single_page_fetch(_minimal_doc(1)),
        fetch_html=lambda url: fetched_details.append(url) or _detail_html("Tussenwoning"),
        pages=1,
    )

    assert fetched_details == []
    assert result.detail_enrichment_attempted_count == 1
    assert result.detail_enrichment_succeeded_count == 0
    assert result.detail_enriched_count == 0
    assert "blocked_by_robots" in result.warnings
