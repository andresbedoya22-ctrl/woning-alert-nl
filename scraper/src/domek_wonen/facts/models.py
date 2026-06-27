from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .normalization import (
    normalize_area_m2,
    normalize_boolean_signal,
    normalize_count,
    normalize_cv_ketel_ownership,
    normalize_description_length_bucket,
    normalize_eigendomssituatie,
    normalize_energy_label,
    normalize_price,
    normalize_property_type,
    normalize_vve_monthly_cost,
)


FACT_SCHEMA_VERSION = "property_facts_v1"
EVIDENCE_PREVIEW_LIMIT = 160

FACT_STATUS_USABLE = "usable"
FACT_STATUS_REVIEW = "review"
FACT_STATUS_MISSING = "missing"
FACT_STATUS_STALE = "stale"
FACT_STATUS_UNSUPPORTED = "unsupported"
FACT_STATUSES = frozenset(
    {
        FACT_STATUS_USABLE,
        FACT_STATUS_REVIEW,
        FACT_STATUS_MISSING,
        FACT_STATUS_STALE,
        FACT_STATUS_UNSUPPORTED,
    }
)

EXTRACTION_STATUS_COMPLETE = "complete"
EXTRACTION_STATUS_PARTIAL = "partial"
EXTRACTION_STATUS_FAILED = "failed"
EXTRACTION_STATUS_SKIPPED = "skipped"
EXTRACTION_STATUSES = frozenset(
    {
        EXTRACTION_STATUS_COMPLETE,
        EXTRACTION_STATUS_PARTIAL,
        EXTRACTION_STATUS_FAILED,
        EXTRACTION_STATUS_SKIPPED,
    }
)

PROPERTY_FACT_FIELDS = (
    "property_type",
    "asking_price",
    "living_area_m2",
    "plot_area_m2",
    "rooms",
    "bedrooms",
    "bathrooms",
    "energy_label",
    "eigendomssituatie",
    "erfpacht_details",
    "vve_monthly_cost",
    "vve_active",
    "heating_type",
    "cv_ketel_present",
    "cv_ketel_ownership",
    "outdoor_space",
    "garden",
    "balcony",
    "storage",
    "garage",
    "parking",
    "availability_date",
    "open_huis_badge_or_event",
    "description_length_bucket",
    "short_description_summary_candidate",
    "key_selling_points_candidate",
    "attention_points_candidate",
)
_PROPERTY_FACT_FIELD_SET = frozenset(PROPERTY_FACT_FIELDS)
_STRUCTURED_SOURCES = frozenset({"metadata", "json_ld", "embedded_state"})
_SOURCE_PRIORITY = {
    "json_ld": 4,
    "embedded_state": 4,
    "metadata": 3,
    "listing_fallback": 3,
    "html_text_signal": 1,
}
_SOURCE_CONFIDENCE = {
    "metadata": 1.0,
    "json_ld": 1.0,
    "embedded_state": 0.8,
    "listing_fallback": 0.8,
    "html_text_signal": 0.6,
}
_HIGH_CONFIDENCE_SOURCES = frozenset({"json_ld", "embedded_state", "metadata", "listing_fallback"})
_NON_CONFLICT_FIELDS = frozenset({"description_length_bucket"})
_PROBE_FIELD_ALIASES = {
    "possible_key_selling_points_source": "key_selling_points_candidate",
    "possible_attention_points_source": "attention_points_candidate",
    "short_description_source_available": "short_description_summary_candidate",
}
_NORMALIZERS = {
    "asking_price": normalize_price,
    "living_area_m2": normalize_area_m2,
    "plot_area_m2": normalize_area_m2,
    "rooms": normalize_count,
    "bedrooms": normalize_count,
    "bathrooms": normalize_count,
    "energy_label": normalize_energy_label,
    "property_type": normalize_property_type,
    "vve_monthly_cost": normalize_vve_monthly_cost,
    "vve_active": normalize_boolean_signal,
    "cv_ketel_present": normalize_boolean_signal,
    "cv_ketel_ownership": normalize_cv_ketel_ownership,
    "eigendomssituatie": normalize_eigendomssituatie,
    "description_length_bucket": normalize_description_length_bucket,
}
_UNITS = {
    "asking_price": "EUR",
    "living_area_m2": "m2",
    "plot_area_m2": "m2",
    "vve_monthly_cost": "EUR_month",
}


@dataclass(frozen=True, slots=True)
class PropertyFactValue:
    field: str
    value: str | int | float | bool | None
    normalized_value: str | int | float | bool | None
    unit: str | None
    source: str
    confidence: float
    status: str
    evidence_preview: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.field not in _PROPERTY_FACT_FIELD_SET:
            raise ValueError(f"Unsupported property fact field: {self.field}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.status not in FACT_STATUSES:
            raise ValueError(f"Unsupported fact status: {self.status}")
        object.__setattr__(self, "evidence_preview", _cap_preview(self.evidence_preview))
        object.__setattr__(self, "warnings", _dedupe_sorted(self.warnings))


@dataclass(frozen=True, slots=True)
class PropertyFactsRecord:
    schema_version: str
    source_id: str
    source_domain: str
    canonical_url: str
    address_raw: str | None
    city: str | None
    status: str | None
    facts: tuple[PropertyFactValue, ...]
    extraction_status: str
    fetched_at: str
    expires_at: str | None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_version:
            raise ValueError("schema_version is required")
        if not self.source_domain:
            raise ValueError("source_domain is required")
        if not self.canonical_url:
            raise ValueError("canonical_url is required")
        if self.extraction_status not in EXTRACTION_STATUSES:
            raise ValueError(f"Unsupported extraction_status: {self.extraction_status}")
        facts, warnings = _dedupe_facts(self.facts)
        object.__setattr__(self, "facts", tuple(sorted(facts, key=lambda fact: fact.field)))
        object.__setattr__(self, "warnings", _dedupe_sorted((*self.warnings, *warnings)))


def build_property_fact_value(
    *,
    field: str,
    value: str | int | float | bool | None,
    normalized_value: str | int | float | bool | None = None,
    unit: str | None = None,
    source: str,
    confidence: float,
    status: str = FACT_STATUS_USABLE,
    evidence_preview: str = "",
    warnings: Iterable[str] = (),
) -> PropertyFactValue:
    if normalized_value is None:
        normalized_value = _normalize_field_value(field, value)
    return PropertyFactValue(
        field=field,
        value=value,
        normalized_value=normalized_value,
        unit=unit,
        source=source,
        confidence=confidence,
        status=status,
        evidence_preview=evidence_preview,
        warnings=tuple(warnings),
    )


def build_property_facts_record(
    *,
    source_id: str,
    source_domain: str,
    canonical_url: str,
    fetched_at: str,
    facts: Iterable[PropertyFactValue] = (),
    schema_version: str = FACT_SCHEMA_VERSION,
    address_raw: str | None = None,
    city: str | None = None,
    status: str | None = None,
    extraction_status: str = EXTRACTION_STATUS_COMPLETE,
    expires_at: str | None = None,
    warnings: Iterable[str] = (),
) -> PropertyFactsRecord:
    return PropertyFactsRecord(
        schema_version=schema_version,
        source_id=source_id,
        source_domain=source_domain,
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        status=status,
        facts=tuple(facts),
        extraction_status=extraction_status,
        fetched_at=fetched_at,
        expires_at=expires_at,
        warnings=tuple(warnings),
    )


def record_to_dict(record: PropertyFactsRecord) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "source_id": record.source_id,
        "source_domain": record.source_domain,
        "canonical_url": record.canonical_url,
        "address_raw": record.address_raw,
        "city": record.city,
        "status": record.status,
        "facts": [
            {
                "field": fact.field,
                "value": fact.value,
                "normalized_value": fact.normalized_value,
                "unit": fact.unit,
                "source": fact.source,
                "confidence": fact.confidence,
                "status": fact.status,
                "evidence_preview": fact.evidence_preview,
                "warnings": list(fact.warnings),
            }
            for fact in record.facts
        ],
        "extraction_status": record.extraction_status,
        "fetched_at": record.fetched_at,
        "expires_at": record.expires_at,
        "warnings": list(record.warnings),
    }


def record_from_dict(payload: Mapping[str, Any]) -> PropertyFactsRecord:
    facts = tuple(
        PropertyFactValue(
            field=str(item.get("field", "")),
            value=item.get("value"),
            normalized_value=item.get("normalized_value"),
            unit=item.get("unit"),
            source=str(item.get("source", "")),
            confidence=float(item.get("confidence", 0.0)),
            status=str(item.get("status", "")),
            evidence_preview=str(item.get("evidence_preview", "")),
            warnings=tuple(str(warning) for warning in item.get("warnings", ())),
        )
        for item in payload.get("facts", ())
        if isinstance(item, Mapping)
    )
    return PropertyFactsRecord(
        schema_version=str(payload.get("schema_version", "")),
        source_id=str(payload.get("source_id", "")),
        source_domain=str(payload.get("source_domain", "")),
        canonical_url=str(payload.get("canonical_url", "")),
        address_raw=_optional_str(payload.get("address_raw")),
        city=_optional_str(payload.get("city")),
        status=_optional_str(payload.get("status")),
        facts=facts,
        extraction_status=str(payload.get("extraction_status", "")),
        fetched_at=str(payload.get("fetched_at", "")),
        expires_at=_optional_str(payload.get("expires_at")),
        warnings=tuple(str(warning) for warning in payload.get("warnings", ())),
    )


def property_facts_record_from_probe_sample(
    sample: Any,
    *,
    source_id: str,
    source_domain: str,
    fetched_at: datetime,
    ttl_days: int = 14,
) -> PropertyFactsRecord:
    source_by_field = {field: source for field, source in getattr(sample, "extraction_sources", ())}
    sample_warnings = tuple(str(warning) for warning in getattr(sample, "warnings", ()))
    facts: list[PropertyFactValue] = []
    for raw_field, preview in getattr(sample, "field_values_preview", ()):
        field = _PROBE_FIELD_ALIASES.get(raw_field, raw_field)
        if field not in _PROPERTY_FACT_FIELD_SET:
            continue
        source = source_by_field.get(raw_field, source_by_field.get(field, "html_text_signal"))
        normalized_value = _normalize_field_value(field, preview)
        status = FACT_STATUS_REVIEW if "ambiguous_fact_candidate" in sample_warnings else FACT_STATUS_USABLE
        fact_warnings = ("ambiguous_fact_candidate",) if status == FACT_STATUS_REVIEW else ()
        facts.append(
            build_property_fact_value(
                field=field,
                value=preview,
                normalized_value=normalized_value,
                unit=_UNITS.get(field),
                source=source,
                confidence=_SOURCE_CONFIDENCE.get(source, 0.4),
                status=status,
                evidence_preview=str(preview),
                warnings=fact_warnings,
            )
        )
    fetched = _datetime_to_utc_iso(fetched_at)
    expires_at = _datetime_to_utc_iso(fetched_at + timedelta(days=ttl_days)) if ttl_days > 0 else None
    return build_property_facts_record(
        source_id=source_id,
        source_domain=source_domain,
        canonical_url=str(getattr(sample, "canonical_url", "")),
        address_raw=getattr(sample, "address_raw", None),
        city=getattr(sample, "city", None),
        facts=facts,
        extraction_status=EXTRACTION_STATUS_PARTIAL if sample_warnings else EXTRACTION_STATUS_COMPLETE,
        fetched_at=fetched,
        expires_at=expires_at,
        warnings=sample_warnings,
    )


def _dedupe_facts(facts: tuple[PropertyFactValue, ...]) -> tuple[tuple[PropertyFactValue, ...], tuple[str, ...]]:
    by_field: dict[str, list[PropertyFactValue]] = {}
    for fact in facts:
        by_field.setdefault(fact.field, []).append(fact)

    selected: list[PropertyFactValue] = []
    warnings: list[str] = []
    for field, candidates in by_field.items():
        if len(candidates) == 1:
            selected.append(candidates[0])
            continue
        choice = sorted(candidates, key=_fact_rank, reverse=True)[0]
        conflicts = [
            fact
            for fact in candidates
            if fact is not choice
            and _is_material_conflict(choice, fact)
        ]
        if conflicts:
            conflict_warnings = tuple(warning for fact in (choice, *conflicts) for warning in fact.warnings)
            choice = PropertyFactValue(
                field=choice.field,
                value=choice.value,
                normalized_value=choice.normalized_value,
                unit=choice.unit,
                source=choice.source,
                confidence=choice.confidence,
                status=FACT_STATUS_REVIEW,
                evidence_preview=choice.evidence_preview,
                warnings=(*conflict_warnings, "conflicting_fact_values"),
            )
            warnings.append("conflicting_fact_values")
        selected.append(choice)
    return tuple(selected), tuple(warnings)


def _fact_rank(fact: PropertyFactValue) -> tuple[float, int, int]:
    status_rank = 1 if fact.status == FACT_STATUS_USABLE else 0
    return (fact.confidence, status_rank, _SOURCE_PRIORITY.get(fact.source, 0))


def _is_material_conflict(left: PropertyFactValue, right: PropertyFactValue) -> bool:
    return (
        left.field not in _NON_CONFLICT_FIELDS
        and left.normalized_value is not None
        and right.normalized_value is not None
        and left.normalized_value != right.normalized_value
        and left.source != right.source
        and left.source in _HIGH_CONFIDENCE_SOURCES
        and right.source in _HIGH_CONFIDENCE_SOURCES
        and left.confidence >= 0.75
        and right.confidence >= 0.75
    )


def _normalize_field_value(field: str, value: object) -> str | int | float | bool | None:
    normalizer = _NORMALIZERS.get(field)
    if normalizer is None:
        return value if isinstance(value, (str, int, float, bool)) else None
    return normalizer(value)


def _cap_preview(value: object) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= EVIDENCE_PREVIEW_LIMIT:
        return normalized
    return normalized[:EVIDENCE_PREVIEW_LIMIT].rstrip()


def _dedupe_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
