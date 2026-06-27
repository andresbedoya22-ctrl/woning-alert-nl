from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.facts import (
    FACT_SCHEMA_VERSION,
    PROPERTY_FACT_FIELDS,
    PropertyFactValue,
    build_property_fact_value,
    build_property_facts_record,
    property_facts_record_from_probe_sample,
    record_from_dict,
    record_to_dict,
)
from domek_wonen.pilots.ogonline_detail_facts_probe import OGonlineDetailFactsProbeSample


def _fact(**overrides: object) -> PropertyFactValue:
    values = {
        "field": "asking_price",
        "value": "425000",
        "normalized_value": 425000,
        "unit": "EUR",
        "source": "metadata",
        "confidence": 1.0,
        "status": "usable",
        "evidence_preview": "425000",
    }
    values.update(overrides)
    return PropertyFactValue(**values)


def test_property_fact_value_validates_allowlist() -> None:
    with pytest.raises(ValueError, match="Unsupported property fact field"):
        _fact(field="raw_html")


def test_property_fact_value_caps_evidence_preview() -> None:
    fact = _fact(evidence_preview="x" * 200)

    assert len(fact.evidence_preview) == 160


def test_property_fact_value_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        _fact(confidence=1.2)


def test_property_facts_record_requires_core_identifiers() -> None:
    with pytest.raises(ValueError, match="canonical_url"):
        build_property_facts_record(
            source_id="kin",
            source_domain="kinmakelaars.nl",
            canonical_url="",
            fetched_at="2026-06-27T00:00:00Z",
        )


def test_record_roundtrip_is_stable() -> None:
    record = build_property_facts_record(
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/aanbod/wonen/breda/test",
        fetched_at="2026-06-27T00:00:00Z",
        facts=(_fact(),),
        warnings=("b", "a", "a"),
    )

    assert record_to_dict(record_from_dict(record_to_dict(record))) == record_to_dict(record)


def test_facts_are_sorted_and_warnings_deduped() -> None:
    record = build_property_facts_record(
        source_id="kin",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/a",
        fetched_at="2026-06-27T00:00:00Z",
        facts=(
            _fact(field="bedrooms", value="3", normalized_value=3, unit=None),
            _fact(field="asking_price", value="425000", normalized_value=425000),
        ),
        warnings=("z", "a", "z"),
    )

    assert tuple(fact.field for fact in record.facts) == ("asking_price", "bedrooms")
    assert record.warnings == ("a", "z")


def test_conflicting_facts_generate_review_warning() -> None:
    record = build_property_facts_record(
        source_id="kin",
        source_domain="kinmakelaars.nl",
        canonical_url="https://kinmakelaars.nl/a",
        fetched_at="2026-06-27T00:00:00Z",
        facts=(
            _fact(value="425000", normalized_value=425000, source="metadata", confidence=0.8),
            _fact(value="430000", normalized_value=430000, source="embedded_state", confidence=0.75),
        ),
    )

    assert record.facts[0].status == "review"
    assert "conflicting_fact_values" in record.facts[0].warnings
    assert "conflicting_fact_values" in record.warnings


def test_property_fact_fields_allowlist_contains_requested_fields() -> None:
    assert "short_description_summary_candidate" in PROPERTY_FACT_FIELDS
    assert "key_selling_points_candidate" in PROPERTY_FACT_FIELDS
    assert "attention_points_candidate" in PROPERTY_FACT_FIELDS


def test_probe_sample_bridge_converts_previews_and_caps_description() -> None:
    sample = OGonlineDetailFactsProbeSample(
        canonical_url="https://kinmakelaars.nl/aanbod/wonen/breda/test",
        address_raw="Factsstraat 1",
        city="Breda",
        fields_present=("asking_price", "property_type", "short_description_source_available"),
        field_values_preview=(
            ("asking_price", "EUR 425.000 k.k."),
            ("property_type", "Tussenwoning"),
            ("short_description_source_available", "x" * 200),
        ),
        extraction_sources=(
            ("asking_price", "metadata"),
            ("property_type", "embedded_state"),
            ("short_description_source_available", "html_text_signal"),
        ),
        warnings=("ambiguous_fact_candidate",),
    )

    record = property_facts_record_from_probe_sample(
        sample,
        source_id="kinmakelaars.nl__breda",
        source_domain="kinmakelaars.nl",
        fetched_at=datetime(2026, 6, 27, tzinfo=UTC),
    )

    facts = {fact.field: fact for fact in record.facts}
    assert record.schema_version == FACT_SCHEMA_VERSION
    assert facts["asking_price"].normalized_value == 425000
    assert facts["property_type"].normalized_value == "tussenwoning"
    assert facts["short_description_summary_candidate"].status == "review"
    assert len(facts["short_description_summary_candidate"].evidence_preview) == 160
