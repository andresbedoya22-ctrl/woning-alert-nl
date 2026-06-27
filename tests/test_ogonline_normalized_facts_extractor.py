from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.compliance import robots_gate
from domek_wonen.facts import (
    PropertyFactsCache,
    build_property_fact_value,
    build_property_facts_record,
    extract_ogonline_property_facts_from_html,
    record_from_dict,
    record_to_dict,
    run_kin_ogonline_normalized_facts_extraction_batch,
)


CONFIG_FIXTURE = BASE_DIR / "tests" / "fixtures" / "parsers" / "kin_ogonline_xhr_source_config.json"
MODULE_PATH = BASE_DIR / "scraper" / "src" / "domek_wonen" / "facts" / "ogonline_extractor.py"
NOW = datetime(2026, 6, 27, tzinfo=UTC)


def _detail_url(index: int) -> str:
    return f"https://kinmakelaars.nl/aanbod/wonen/breda/facts-{index}/kin-facts-{index:03d}"


def _doc(index: int, **overrides: object) -> dict[str, object]:
    doc: dict[str, object] = {
        "id": f"kin-facts-{index:03d}",
        "url": _detail_url(index),
        "street": "Factsstraat",
        "houseNumber": str(index),
        "postcode": "4811AA",
        "city": "Breda",
        "askingPrice": 410000 + index,
        "isSales": True,
        "status": "available",
        "livingArea": 101 + index,
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
        "plotArea": 234,
        "rooms": 6,
        "bedrooms": 4,
        "bathrooms": 1,
        "energyLabel": "A++",
        "ownership": "Volle eigendom",
        "serviceCosts": 125,
        "heating": "CV-ketel eigendom",
        "garden": True,
        "balcony": True,
        "storage": True,
        "garage": True,
        "parking": "eigen oprit",
        "availability": "in overleg",
        "description": "Omschrijving " + ("ruime woning met licht en tuin. " * 80),
    }
    values.update(overrides)
    embedded = json.dumps(values)
    return f"""
    <html>
      <head><meta name="description" content="Tussenwoning met energielabel A++"></head>
      <body>
        <script>window.__DETAIL__ = {embedded}</script>
        <dl>
          <dt>Vraagprijs</dt><dd>EUR 425.000 k.k.</dd>
          <dt>Perceeloppervlakte</dt><dd>234 m2</dd>
          <dt>Woonoppervlakte</dt><dd>123 m2</dd>
          <dt>Kamers</dt><dd>6 kamers waarvan 4 slaapkamers</dd>
          <dt>Badkamers</dt><dd>1 badkamer</dd>
          <dt>Energielabel</dt><dd>A++</dd>
          <dt>Eigendomssituatie</dt><dd>Volle eigendom, eigen grond</dd>
          <dt>Erfpacht</dt><dd>Geen erfpacht</dd>
          <dt>VvE bijdrage</dt><dd>125 per maand</dd>
          <dt>Verwarming</dt><dd>CV-ketel eigendom</dd>
          <dt>Buitenruimte</dt><dd>Tuin, balkon en berging</dd>
          <dt>Parkeren</dt><dd>Garage en eigen oprit</dd>
          <dt>Aanvaarding</dt><dd>in overleg</dd>
        </dl>
        <span>Open huis</span>
      </body>
    </html>
    """


def _extract(html: str | None = None, **fallbacks: object):
    return extract_ogonline_property_facts_from_html(
        html=html if html is not None else _html(),
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=_detail_url(1),
        address_raw="Factsstraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at=NOW,
        listing_fallbacks=fallbacks,
    )


def _facts(result) -> dict[str, object]:
    return {fact.field: fact for fact in result.record.facts}


def _cached_record(url: str = _detail_url(1), fetched_at: str = "2026-06-27T00:00:00Z", expires_at: str = "2026-07-11T00:00:00Z"):
    return build_property_facts_record(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=url,
        address_raw="Factsstraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at=fetched_at,
        expires_at=expires_at,
        facts=(
            build_property_fact_value(
                field="asking_price",
                value="410000",
                normalized_value=410000,
                unit="EUR",
                source="listing_fallback",
                confidence=0.85,
                status="usable",
                evidence_preview="410000",
            ),
        ),
    )


def test_extracts_property_type_from_embedded_state_and_normalizes() -> None:
    fact = _facts(_extract())["property_type"]

    assert fact.normalized_value == "tussenwoning"
    assert fact.source == "embedded_state"


def test_extracts_asking_price_and_normalizes() -> None:
    assert _facts(_extract())["asking_price"].normalized_value == 425000


def test_extracts_living_and_plot_area() -> None:
    facts = _facts(_extract())

    assert facts["living_area_m2"].normalized_value == 123
    assert facts["plot_area_m2"].normalized_value == 234


def test_extracts_rooms_bedrooms_and_bathrooms() -> None:
    facts = _facts(_extract())

    assert facts["rooms"].normalized_value == 6
    assert facts["bedrooms"].normalized_value == 4
    assert facts["bathrooms"].normalized_value == 1


def test_extracts_energy_label() -> None:
    assert _facts(_extract())["energy_label"].normalized_value == "A++"


def test_extracts_ownership_and_erfpacht() -> None:
    facts = _facts(_extract())

    assert facts["eigendomssituatie"].normalized_value == "volle_eigendom"
    assert facts["erfpacht_details"].normalized_value == "source_available"


def test_extracts_vve_monthly_cost_and_active_signal() -> None:
    facts = _facts(_extract())

    assert facts["vve_monthly_cost"].normalized_value == 125
    assert facts["vve_active"].normalized_value is True


def test_extracts_cv_ketel_present_and_ownership() -> None:
    facts = _facts(_extract())

    assert facts["cv_ketel_present"].normalized_value is True
    assert facts["cv_ketel_ownership"].normalized_value == "eigendom"


def test_extracts_outdoor_garden_balcony_storage_garage_and_parking() -> None:
    facts = _facts(_extract())

    assert {"outdoor_space", "garden", "balcony", "storage", "garage", "parking"}.issubset(facts)


def test_extracts_availability_date() -> None:
    assert _facts(_extract())["availability_date"].normalized_value == "in overleg"


def test_detects_open_huis_without_changing_listing_status() -> None:
    result = _extract()

    assert _facts(result)["open_huis_badge_or_event"].normalized_value == "source_available"
    assert result.record.status == "beschikbaar"


def test_uses_listing_fallbacks_when_detail_has_no_clear_value() -> None:
    result = _extract("<html><body>Geen facts</body></html>", asking_price_eur=399000, bedrooms_count=2)
    facts = _facts(result)

    assert facts["asking_price"].normalized_value == 399000
    assert facts["bedrooms"].normalized_value == 2
    assert facts["asking_price"].source == "listing_fallback"


def test_structured_source_wins_over_html_text_signal() -> None:
    html = _html(askingPrice=425000) + "<p>Vraagprijs EUR 430.000 k.k.</p>"

    assert _facts(_extract(html))["asking_price"].normalized_value == 425000


def test_conflict_generates_review_warning() -> None:
    html = """
    <script>{"askingPrice": 425000}</script>
    <script>{"price":{"amount":430000}}</script>
    """
    result = _extract(html)

    assert _facts(result)["asking_price"].status == "review"
    assert "conflicting_fact_values" in result.record.warnings


def test_does_not_store_long_description_only_bucket() -> None:
    result = _extract()
    facts = _facts(result)
    serialized = json.dumps(record_to_dict(result.record)).casefold()

    assert facts["description_length_bucket"].normalized_value == "long"
    assert "short_description_summary_candidate" not in facts
    assert "ruime woning met licht en tuin" not in serialized
    assert "description_not_stored" in result.warnings


def test_evidence_previews_are_capped_at_contract_limit() -> None:
    result = _extract()

    assert all(len(fact.evidence_preview) <= 160 for fact in result.record.facts)


def test_record_roundtrip_is_compatible_with_facts_models() -> None:
    result = _extract()

    assert record_to_dict(record_from_dict(record_to_dict(result.record))) == record_to_dict(result.record)


def test_cache_hit_fresh_avoids_detail_fetch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    cache.upsert(_cached_record())
    fetched_details: list[str] = []

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=cache.path,
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
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    cache.upsert(_cached_record(expires_at="2026-06-26T00:00:00Z"))

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=cache.path,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.cache_misses == 1
    assert result.detail_fetch_attempted == 1
    assert "cache_stale" in result.warnings


def test_force_refresh_forces_detail_fetch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache = PropertyFactsCache(tmp_path / "facts.jsonl")
    cache.upsert(_cached_record())

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=cache.path,
        max_api_pages=1,
        max_details=1,
        force_refresh=True,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.cache_hits == 0
    assert result.cache_misses == 1
    assert result.detail_fetch_attempted == 1


def test_cache_path_none_does_not_write_and_reports_warning(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=None,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.records_written == 0
    assert "no_cache_path_no_write" in result.warnings


def test_max_api_pages_caps_at_25(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    fetched_pages: list[str] = []

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=99,
        max_details=1,
        fetch_json=lambda url: fetched_pages.append(url) or _payload(_doc(len(fetched_pages))),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert len(fetched_pages) == 25
    assert "max_api_pages_capped_at_25" in result.warnings


def test_max_details_caps_at_300(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    docs = tuple(_doc(index) for index in range(1, 351))

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=999,
        fetch_json=lambda url: _payload(*docs),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.details_requested == 300
    assert "max_details_capped_at_300" in result.warnings


def test_robots_false_avoids_detail_fetch(tmp_path: Path, monkeypatch) -> None:
    def can_fetch(domain: str, path: str) -> bool:
        return domain == "cpl01.ogonline.nl"

    monkeypatch.setattr(robots_gate, "can_fetch", can_fetch)
    fetched_details: list[str] = []

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: fetched_details.append(url) or _html(),
        now=NOW,
    )

    assert fetched_details == []
    assert result.detail_fetch_attempted == 0
    assert result.detail_fetch_failed == 1
    assert "blocked_by_robots" in result.warnings


def test_detail_fetch_exception_does_not_abort_batch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    def fetch_html(url: str) -> str:
        if "facts-1" in url:
            raise RuntimeError("boom")
        return _html()

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=2,
        fetch_json=lambda url: _payload(_doc(1), _doc(2)),
        fetch_html=fetch_html,
        now=NOW,
    )

    assert result.detail_fetch_failed == 1
    assert result.detail_fetch_succeeded == 1
    assert "detail_fetch_exception" in result.warnings


def test_runtime_budget_cuts_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=1,
        max_runtime_seconds=0,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.records_built == 0
    assert "facts_batch_runtime_budget_exhausted" in result.warnings


def test_sample_records_caps_at_five(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    docs = tuple(_doc(index) for index in range(1, 8))

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=7,
        fetch_json=lambda url: _payload(*docs),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert len(result.sample_records) == 5


def test_records_written_matches_upserts_when_cache_path_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=tmp_path / "facts.jsonl",
        max_api_pages=1,
        max_details=2,
        fetch_json=lambda url: _payload(_doc(1), _doc(2)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.records_written == 2
    assert len(PropertyFactsCache(tmp_path / "facts.jsonl").load_all()) == 2


def test_no_raw_html_or_json_in_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)
    cache_path = tmp_path / "facts.jsonl"

    run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=cache_path,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    content = cache_path.read_text(encoding="utf-8").casefold()
    assert "<html" not in content
    assert "window.__detail__" not in content
    assert '"docs"' not in content


def test_no_real_network(monkeypatch) -> None:
    monkeypatch.setattr(robots_gate, "can_fetch", lambda domain, path: True)

    result = run_kin_ogonline_normalized_facts_extraction_batch(
        config_path=CONFIG_FIXTURE,
        cache_path=None,
        max_api_pages=1,
        max_details=1,
        fetch_json=lambda url: _payload(_doc(1)),
        fetch_html=lambda url: _html(),
        now=NOW,
    )

    assert result.records_built == 1


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


def test_no_writes_outside_cache_module_path_explicit() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    write_methods = {"write_text", "write_bytes", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in write_methods


def test_existing_property_type_enrichment_behavior_is_not_modified() -> None:
    enrichment_path = BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_detail_property_type_enrichment.py"

    assert enrichment_path.read_text(encoding="utf-8")
