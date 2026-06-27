from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate  # noqa: E402
from domek_wonen.facts import PropertyFactsCache, build_property_fact_value, build_property_facts_record  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402
from domek_wonen.parsers.source_config import load_parser_source_config  # noqa: E402
from domek_wonen.pilots.kin_full_property_readiness import (  # noqa: E402
    build_kin_property_readiness_row,
    build_location_readiness_from_listing,
    classify_export_readiness,
    run_kin_full_property_readiness_config,
)


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_full_property_readiness.py"
NOW = datetime(2026, 6, 27, tzinfo=UTC)


def _config():
    return load_parser_source_config(CONFIG_FIXTURE)


def _listing(**overrides: object) -> ParsedListing:
    listing = ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001",
        address_raw="Readinessstraat 1",
        street="Readinessstraat",
        house_number="1",
        postcode="4811AA",
        city="Breda",
        asking_price_eur=425000,
        transaction_type="koop",
        status="beschikbaar",
        living_area_m2=123,
        rooms_count=5,
        bedrooms_count=3,
        property_type="Tussenwoning",
        energy_label="A",
        confidence_score=0.95,
    )
    return _replace_listing(listing, **overrides)


def _replace_listing(listing: ParsedListing, **overrides: object) -> ParsedListing:
    values = {field: getattr(listing, field) for field in listing.__dataclass_fields__}
    values.update(overrides)
    return ParsedListing(**values)


def _doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-readiness-{index:03d}",
        "url": f"https://kinmakelaars.nl/aanbod/wonen/breda/readiness-{index}/kin-readiness-{index:03d}",
        "street": "Readinessstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 425000 + index,
        "isSales": True,
        "status": "available",
        "livingArea": 120 + index,
        "rooms": 5,
        "bedrooms": 3,
        "propertyType": "Tussenwoning",
    }
    doc.update(overrides)
    return doc


def _payload(*docs: dict[str, object]) -> str:
    return json.dumps({"docs": list(docs), "totalPages": 1, "totalDocs": len(docs), "hasNextPage": False})


def _html(**overrides: object) -> str:
    values = {
        "subtype": "Tussenwoning",
        "askingPrice": 425000,
        "livingArea": 123,
        "bedrooms": 3,
        "energyLabel": "A++",
        "ownership": "Volle eigendom",
    }
    values.update(overrides)
    return f"<html><script>window.__DETAIL__ = {json.dumps(values)}</script></html>"


def _record(*facts, url: str = "https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001"):
    return build_property_facts_record(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=url,
        address_raw="Readinessstraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at="2026-06-27T00:00:00Z",
        expires_at="2026-07-11T00:00:00Z",
        facts=facts,
    )


def _fact(field: str, value: object, *, normalized_value: object | None = None, status: str = "usable"):
    return build_property_fact_value(
        field=field,
        value=value,
        normalized_value=value if normalized_value is None else normalized_value,
        source="metadata",
        confidence=1.0,
        status=status,
        evidence_preview=str(value),
    )


def _full_record(url: str = "https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001"):
    return _record(
        _fact("asking_price", 425000),
        _fact("property_type", "Tussenwoning", normalized_value="tussenwoning"),
        _fact("living_area_m2", 123),
        _fact("bedrooms", 3),
        _fact("energy_label", "A++"),
        _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
        url=url,
    )


def test_location_readiness_usable_with_address_postcode_city() -> None:
    location = build_location_readiness_from_listing(_listing())

    assert location.location_status == "usable"
    assert location.postcode == "4811 AA"
    assert location.location_confidence == 0.85


def test_location_readiness_review_with_address_city_no_postcode() -> None:
    location = build_location_readiness_from_listing(_listing(postcode=""))

    assert location.location_status == "review"
    assert "missing_postcode" in location.warnings


def test_location_readiness_missing_with_no_location() -> None:
    location = build_location_readiness_from_listing(_listing(address_raw="", street="", postcode="", city=""))

    assert location.location_status == "missing"
    assert "missing_location" in location.warnings


def test_missing_coordinates_does_not_block_export_with_full_text_location() -> None:
    row = build_kin_property_readiness_row(_listing(), _full_record())

    assert "missing_coordinates" in row.warnings
    assert row.export_readiness == "export_ready"


def test_export_readiness_ready_with_canonical_summary_location_and_price() -> None:
    row = build_kin_property_readiness_row(_listing(), _full_record())

    assert classify_export_readiness(row) == "export_ready"
    assert row.quality_status == "client_ready"


def test_export_readiness_review_when_missing_noncritical_key_fields() -> None:
    row = build_kin_property_readiness_row(_listing(), _record(_fact("asking_price", 425000)))

    assert row.export_readiness == "export_review"
    assert row.quality_status == "advisor_review"
    assert "property_type" in row.missing_key_fields


def test_export_readiness_blocked_without_canonical_url() -> None:
    record = _full_record(url="https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001")
    row = build_kin_property_readiness_row(_listing(canonical_url=""), record)

    assert row.export_readiness == "export_blocked"


def test_export_readiness_blocked_without_location() -> None:
    row = build_kin_property_readiness_row(_listing(address_raw="", postcode="", city=""), _full_record())

    assert row.export_readiness == "export_blocked"
    assert row.quality_status == "insufficient_location"


def test_builds_row_from_synthetic_listing_facts_record_and_summary() -> None:
    row = build_kin_property_readiness_row(_listing(), _full_record())

    assert row.source_domain == "kinmakelaars.nl"
    assert row.summary.headline
    assert row.address_raw == "Readinessstraat 1"


def test_field_completion_counts_usable_facts_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert ("asking_price", 1) in result.field_completion_counts
    assert ("energy_label", 1) in result.field_completion_counts


def test_missing_key_field_counts_aggregate_correctly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=2,
        fetch_json=lambda url: _payload(_doc(1), _doc(2)),
        fetch_html=lambda url: "<html></html>",
        now=NOW,
    )

    assert ("energy_label", 2) in result.missing_key_field_counts


def test_attention_point_counts_aggregate_correctly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache_path = tmp_path / "facts.jsonl"
    url = "https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001"
    PropertyFactsCache(cache_path).upsert(
        _record(
            _fact("asking_price", 425000),
            _fact("property_type", "Tussenwoning", normalized_value="tussenwoning", status="review"),
            url=url,
        )
    )

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=cache_path,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert ("property_type staat in review.", 1) in result.attention_point_counts


def test_cache_fresh_hit_avoids_detail_fetch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache_path = tmp_path / "facts.jsonl"
    url = "https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001"
    PropertyFactsCache(cache_path).upsert(_full_record(url=url))
    fetched_details: list[str] = []

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=cache_path,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: fetched_details.append(url) or _html(),
        now=NOW,
    )

    assert result.cache_hits == 1
    assert result.detail_fetch_attempted == 0
    assert fetched_details == []


def test_cache_stale_forces_detail_fetch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache_path = tmp_path / "facts.jsonl"
    url = "https://kinmakelaars.nl/aanbod/wonen/breda/readiness-1/kin-readiness-001"
    PropertyFactsCache(cache_path).upsert(
        build_property_facts_record(
            source_id="kinmakelaars.nl__breda",
            source_domain="kinmakelaars.nl",
            canonical_url=url,
            address_raw="Readinessstraat 1",
            city="Breda",
            status="beschikbaar",
            fetched_at="2026-06-01T00:00:00Z",
            expires_at="2026-06-02T00:00:00Z",
            facts=(_fact("asking_price", 410000),),
        )
    )

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=cache_path,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.cache_misses == 1
    assert result.detail_fetch_attempted == 1
    assert "cache_stale" in result.warnings


def test_no_cache_path_does_not_write(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=None,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.records_written == 0
    assert list(tmp_path.iterdir()) == []


def test_runtime_budget_returns_partial_result(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        max_runtime_seconds=0,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.rows_built == 0
    assert "kin_readiness_runtime_budget_exhausted" in result.warnings


def test_sample_rows_max_five(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    docs = tuple(_doc(index) for index in range(1, 8))

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=7,
        fetch_json=lambda url: _payload(*docs),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.rows_built == 7
    assert len(result.sample_rows) == 5


def test_no_raw_html_in_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(description="<html>raw</html>"),
        now=NOW,
    )

    assert "<html>raw</html>" not in repr(result).casefold()


def test_no_raw_json_in_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert '"docs"' not in repr(result)


def test_no_image_urls_in_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_full_property_readiness_config(
        _config(),
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1, photos=["https://cdn.example.test/photo.jpg"])),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert "photo.jpg" not in repr(result)


def test_no_disallowed_imports() -> None:
    disallowed = {"requests", "httpx", "playwright", "selenium"}
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert disallowed.isdisjoint({module.split(".")[0] for module in imported_modules})


def test_no_writes_outside_explicit_cache_path() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    write_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in write_methods
