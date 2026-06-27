from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import PropertyFactsCache, extract_ogonline_property_facts_from_html, record_to_dict  # noqa: E402
from domek_wonen.facts.normalization import normalize_energy_label, normalize_property_type  # noqa: E402
from domek_wonen.pilots.kin_full_coverage_audit import (  # noqa: E402
    build_kin_full_coverage_completion_result,
    summarize_key_matching_field_gaps,
)
from domek_wonen.pilots.kin_full_property_readiness import build_kin_property_readiness_row  # noqa: E402
from domek_wonen.parsers.models import ParsedListing  # noqa: E402


MODULE_PATHS = (
    BASE_DIR / "scraper" / "src" / "domek_wonen" / "facts" / "ogonline_extractor.py",
    BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "ogonline_detail_facts_probe.py",
    BASE_DIR / "scraper" / "src" / "domek_wonen" / "pilots" / "kin_full_coverage_audit.py",
)
NOW = datetime(2026, 6, 27, tzinfo=UTC)


def _extract(html: str, **fallbacks: object):
    return extract_ogonline_property_facts_from_html(
        html=html,
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/aanbod/wonen/breda/key-fields/kin-key-fields-001",
        address_raw="Keyfieldstraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at=NOW,
        listing_fallbacks=fallbacks,
    )


def _facts(result):
    return {fact.field: fact for fact in result.record.facts}


def _listing(index: int = 1) -> ParsedListing:
    return ParsedListing(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url=f"https://kinmakelaars.nl/aanbod/wonen/breda/key-{index}/kin-key-{index:03d}",
        address_raw=f"Keyfieldstraat {index}",
        street="Keyfieldstraat",
        house_number=str(index),
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


def test_bedrooms_extracted_from_strong_aantal_slaapkamers_label() -> None:
    result = _extract("<dl><dt>Aantal slaapkamers</dt><dd>3</dd></dl>")

    assert _facts(result)["bedrooms"].normalized_value == 3
    assert _facts(result)["bedrooms"].status == "usable"


def test_bedrooms_extracted_from_structured_state_field() -> None:
    result = _extract('<script>{"aantalSlaapkamers": 2}</script>')

    assert _facts(result)["bedrooms"].normalized_value == 2


def test_bedrooms_not_extracted_from_aantal_kamers() -> None:
    result = _extract("<dl><dt>Aantal kamers</dt><dd>5</dd></dl>")

    assert "bedrooms" not in _facts(result)
    assert _facts(result)["rooms"].normalized_value == 5


def test_bedrooms_not_inferred_from_rooms_fallback() -> None:
    result = _extract("<html><body>Geen slaapkamers</body></html>", rooms_count=5)

    assert "rooms" in _facts(result)
    assert "bedrooms" not in _facts(result)


def test_bedrooms_conflict_requires_two_strong_different_values() -> None:
    result = _extract(
        """
        <script type="application/ld+json">{"bedrooms": 2}</script>
        <script>{"bedrooms": 3}</script>
        """
    )

    assert _facts(result)["bedrooms"].status == "review"
    assert "conflicting_fact_values" in result.record.warnings


def test_living_area_extracted_from_woonoppervlakte() -> None:
    result = _extract("<dl><dt>Woonoppervlakte</dt><dd>87 m2</dd></dl>")

    assert _facts(result)["living_area_m2"].normalized_value == 87


def test_living_area_extracted_from_gebruiksoppervlakte_wonen() -> None:
    result = _extract("<dl><dt>Gebruiksoppervlakte wonen</dt><dd>91 m2</dd></dl>")

    assert _facts(result)["living_area_m2"].normalized_value == 91


def test_living_area_not_confused_with_perceel_plot_area() -> None:
    result = _extract("<dl><dt>Perceeloppervlakte</dt><dd>240 m2</dd></dl>")

    assert "living_area_m2" not in _facts(result)
    assert _facts(result)["plot_area_m2"].normalized_value == 240


def test_living_area_not_confused_with_inhoud_volume() -> None:
    result = _extract("<dl><dt>Inhoud</dt><dd>410 m3</dd></dl>")

    assert "living_area_m2" not in _facts(result)


def test_implausible_living_area_from_structured_source_is_review() -> None:
    result = _extract('<script>{"livingArea": 1001}</script>')

    assert _facts(result)["living_area_m2"].status == "review"
    assert "implausible_area" in _facts(result)["living_area_m2"].warnings


def test_property_type_structured_beats_weak_text() -> None:
    result = _extract('<script>{"typeWoning": "Appartement"}</script><p>Tussenwoning in de buurt.</p>')

    assert _facts(result)["property_type"].normalized_value == "appartement"
    assert _facts(result)["property_type"].status == "usable"


def test_property_type_conflict_retained_for_two_strong_different_types() -> None:
    result = _extract(
        """
        <script type="application/ld+json">{"propertyType": "Appartement"}</script>
        <script>{"typeWoning": "Tussenwoning"}</script>
        """
    )

    assert _facts(result)["property_type"].status == "review"
    assert "conflicting_fact_values" in result.record.warnings


def test_property_type_weak_secondary_does_not_block_strong_usable() -> None:
    result = _extract('<script>{"soortWoonhuis": "Vrijstaande woning"}</script><p>Open huis appartement route.</p>')

    assert _facts(result)["property_type"].normalized_value == "vrijstaande_woning"
    assert _facts(result)["property_type"].status == "usable"


def test_energy_label_normalized_equivalents_do_not_conflict() -> None:
    result = _extract(
        """
        <script type="application/ld+json">{"energyLabel": "Energielabel A++"}</script>
        <script>{"energyLabel": "A ++"}</script>
        """
    )

    assert _facts(result)["energy_label"].normalized_value == "A++"
    assert _facts(result)["energy_label"].status == "usable"
    assert "conflicting_fact_values" not in result.record.warnings


def test_real_energy_label_mismatch_remains_review_conflict() -> None:
    result = _extract(
        """
        <script type="application/ld+json">{"energyLabel": "A"}</script>
        <script>{"energyLabel": "B"}</script>
        """
    )

    assert _facts(result)["energy_label"].status == "review"
    assert "conflicting_fact_values" in result.record.warnings


def test_no_raw_html_json_or_long_description_in_cache_and_diagnostic(tmp_path: Path) -> None:
    long_description = "ruime woning met licht en tuin " * 80
    result = _extract(f'<script>{{"bedrooms": 3}}</script><section>Omschrijving {long_description}</section>')
    cache_path = tmp_path / "facts.jsonl"
    PropertyFactsCache(cache_path).upsert(result.record)
    row = build_kin_property_readiness_row(_listing(), result.record)
    diagnostic = summarize_key_matching_field_gaps((row,), limit=1)
    payload = json.dumps(
        {
            "cache": cache_path.read_text(encoding="utf-8"),
            "diagnostic": repr(diagnostic),
            "record": record_to_dict(result.record),
        },
        ensure_ascii=False,
    ).casefold()

    assert "<html" not in payload
    assert "<script" not in payload
    assert '"docs"' not in payload
    assert "window.__" not in payload
    assert "photo.jpg" not in payload
    assert "ruime woning met licht en tuin" not in payload


def test_no_disallowed_imports_in_key_matching_field_modules() -> None:
    disallowed = {"requests", "httpx", "playwright", "selenium"}
    imported_modules: set[str] = set()
    for path in MODULE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    assert disallowed.isdisjoint({module.split(".")[0] for module in imported_modules})


def test_coverage_audit_field_gaps_reflect_improved_usable_facts() -> None:
    improved = _extract(
        """
        <dl>
          <dt>Aantal slaapkamers</dt><dd>3</dd>
          <dt>Gebruiksoppervlakte wonen</dt><dd>91 m2</dd>
          <dt>Type woning</dt><dd>Appartement</dd>
        </dl>
        """
    )
    missing = _extract("<html><body>Geen key fields</body></html>")
    result = build_kin_full_coverage_completion_result(
        _readiness_rows(
            build_kin_property_readiness_row(_listing(1), improved.record),
            build_kin_property_readiness_row(_listing(2), missing.record),
        )
    )
    gaps = {gap.field: gap for gap in result.field_gaps}

    assert gaps["bedrooms"].usable_count == 1
    assert gaps["bedrooms"].missing_count == 1
    assert gaps["living_area_m2"].usable_count == 1
    assert gaps["property_type"].usable_count == 1


def test_normalizers_keep_expected_key_field_variants() -> None:
    assert normalize_energy_label("Energielabel A ++") == "A++"
    assert normalize_property_type("Studio") == "studio"
    assert normalize_property_type("Bungalow") == "bungalow"


def _readiness_rows(*rows):
    from domek_wonen.pilots.kin_full_property_readiness import KINFullPropertyReadinessResult

    rows = tuple(rows)
    return KINFullPropertyReadinessResult(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        listings_seen=len(rows),
        qa_clean_count=len(rows),
        rows_built=len(rows),
        summaries_built=len(rows),
        active_count=len(rows),
        inactive_count=0,
        review_count=0,
        cache_hits=0,
        cache_misses=len(rows),
        detail_fetch_attempted=len(rows),
        detail_fetch_succeeded=len(rows),
        detail_fetch_failed=0,
        records_written=0,
        location_usable_count=len(rows),
        location_review_count=0,
        location_missing_count=0,
        export_ready_count=sum(1 for row in rows if row.export_readiness == "export_ready"),
        export_review_count=sum(1 for row in rows if row.export_readiness == "export_review"),
        export_blocked_count=sum(1 for row in rows if row.export_readiness == "export_blocked"),
        field_completion_counts=(),
        missing_key_field_counts=(),
        attention_point_counts=(),
        warning_counts=(),
        sample_rows=rows[:5],
        rows=rows,
        warnings=(),
    )
