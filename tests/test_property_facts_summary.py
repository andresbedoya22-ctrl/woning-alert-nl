from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import (
    SUMMARY_SCHEMA_VERSION,
    build_client_ready_property_summary,
    build_property_fact_value,
    build_property_facts_record,
    summary_from_dict,
    summary_to_dict,
)


def _fact(
    field: str,
    value: object,
    *,
    normalized_value: object | None = None,
    status: str = "usable",
    source: str = "metadata",
    warnings: tuple[str, ...] = (),
):
    return build_property_fact_value(
        field=field,
        value=value,
        normalized_value=normalized_value,
        unit=None,
        source=source,
        confidence=1.0,
        status=status,
        evidence_preview=str(value),
        warnings=warnings,
    )


def _record(*facts, warnings: tuple[str, ...] = ()):
    return build_property_facts_record(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/aanbod/wonen/breda/facts-1",
        address_raw="Factsstraat 1",
        city="Breda",
        status="beschikbaar",
        fetched_at="2026-06-27T00:00:00Z",
        facts=facts,
        warnings=warnings,
    )


def _full_record():
    return _record(
        _fact("asking_price", "425000", normalized_value=425000),
        _fact("property_type", "Tussenwoning", normalized_value="tussenwoning"),
        _fact("living_area_m2", "123", normalized_value=123),
        _fact("plot_area_m2", "234", normalized_value=234),
        _fact("rooms", "6", normalized_value=6),
        _fact("bedrooms", "4", normalized_value=4),
        _fact("energy_label", "A++", normalized_value="A++"),
        _fact("eigendomssituatie", "Volle eigendom", normalized_value="volle_eigendom"),
        _fact("vve_monthly_cost", "125", normalized_value=125),
        _fact("garden", True, normalized_value=True),
        _fact("balcony", True, normalized_value=True),
        _fact("storage", True, normalized_value=True),
        _fact("garage", True, normalized_value=True),
        _fact("parking", "eigen oprit", normalized_value="eigen oprit"),
        _fact("cv_ketel_present", True, normalized_value=True),
        _fact("cv_ketel_ownership", "eigendom", normalized_value="eigendom"),
        _fact("heating_type", "CV-ketel", normalized_value="CV-ketel"),
    )


def _summary_text(summary) -> str:
    payload = summary_to_dict(summary)
    return json.dumps(payload, ensure_ascii=False).casefold()


def test_builds_headline_from_usable_facts() -> None:
    summary = build_client_ready_property_summary(_full_record())

    assert summary.schema_version == SUMMARY_SCHEMA_VERSION
    assert summary.headline == "€425.000 · Breda · tussenwoning · 123 m² · 4 slaapkamers · label A++"


def test_omits_missing_usable_facts_instead_of_inventing() -> None:
    summary = build_client_ready_property_summary(_record(_fact("asking_price", "425000", normalized_value=425000)))

    assert summary.headline == "€425.000 · Breda"
    assert "tussenwoning" not in summary.headline


def test_review_facts_become_attention_points() -> None:
    summary = build_client_ready_property_summary(
        _record(_fact("property_type", "Tussenwoning", normalized_value="tussenwoning", status="review"))
    )

    assert "property_type staat in review." in summary.attention_points


def test_conflicting_fact_warning_becomes_attention_points() -> None:
    record = _record(
        _fact("asking_price", "425000", normalized_value=425000),
        _fact("asking_price", "430000", normalized_value=430000, source="embedded_state"),
    )
    summary = build_client_ready_property_summary(record)

    assert "asking_price heeft conflicterende signalen." in summary.attention_points
    assert "conflicting_fact_values" in summary.warnings


def test_missing_key_fields_are_reported() -> None:
    summary = build_client_ready_property_summary(_record())

    assert summary.missing_key_fields == (
        "asking_price",
        "property_type",
        "living_area_m2",
        "bedrooms",
        "energy_label",
        "eigendomssituatie",
    )


def test_financial_line_includes_price_eigendom_and_vve_when_usable() -> None:
    summary = build_client_ready_property_summary(_full_record())

    assert summary.financial_line == "Vraagprijs: €425.000 · Eigendom: volle eigendom · VvE: €125 p/m"


def test_outdoor_line_includes_garden_balcony_storage_and_parking_when_usable() -> None:
    summary = build_client_ready_property_summary(_full_record())

    assert summary.outdoor_line == "Buitenruimte: tuin, balkon, berging · Parkeren: garage/eigen oprit"


def test_energy_line_includes_label_cv_and_heating_when_usable() -> None:
    summary = build_client_ready_property_summary(_full_record())

    assert summary.energy_line == "Energielabel: A++ · CV-ketel: eigendom · Verwarming: CV-ketel"


def test_does_not_include_long_description_text() -> None:
    record = _record(
        _fact("description_length_bucket", "long", normalized_value="long"),
        _fact(
            "attention_points_candidate",
            "ruime woning met licht en tuin " * 50,
            normalized_value="ruime woning met licht en tuin " * 50,
            status="review",
        ),
    )

    assert "ruime woning met licht en tuin" not in _summary_text(build_client_ready_property_summary(record))


def test_does_not_include_raw_html_or_json() -> None:
    record = _record(
        _fact("property_type", "<html><script>{\"price\":425000}</script>", normalized_value="tussenwoning", status="review")
    )

    text = _summary_text(build_client_ready_property_summary(record))
    assert "<html" not in text
    assert "{\"price\"" not in text


def test_does_not_include_image_urls() -> None:
    record = _record(
        _fact("key_selling_points_candidate", "https://cdn.example.test/photo.jpg", normalized_value="https://cdn.example.test/photo.jpg", status="review")
    )

    assert "photo.jpg" not in _summary_text(build_client_ready_property_summary(record))


def test_summary_roundtrip_is_stable() -> None:
    summary = build_client_ready_property_summary(_full_record())

    assert summary_to_dict(summary_from_dict(summary_to_dict(summary))) == summary_to_dict(summary)


def test_unsupported_locale_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unsupported_locale"):
        build_client_ready_property_summary(_full_record(), locale="es")


def test_empty_record_produces_safe_empty_summary_with_missing_key_fields() -> None:
    summary = build_client_ready_property_summary(_record())

    assert summary.headline == "Breda"
    assert summary.facts_line == ""
    assert summary.financial_line == ""
    assert summary.outdoor_line == ""
    assert summary.energy_line == ""
    assert set(summary.missing_key_fields) == {
        "asking_price",
        "property_type",
        "living_area_m2",
        "bedrooms",
        "energy_label",
        "eigendomssituatie",
    }


def test_review_facts_never_appear_as_confirmed_line_values() -> None:
    summary = build_client_ready_property_summary(
        _record(
            _fact("property_type", "Tussenwoning", normalized_value="tussenwoning", status="review"),
            _fact("asking_price", "425000", normalized_value=425000),
        )
    )

    confirmed = " ".join((summary.headline, summary.facts_line, summary.financial_line, summary.outdoor_line, summary.energy_line))
    assert "tussenwoning" not in confirmed
    assert "property_type staat in review." in summary.attention_points
