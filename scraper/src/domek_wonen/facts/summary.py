from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .models import FACT_STATUS_REVIEW, FACT_STATUS_USABLE, PropertyFactsRecord


SUMMARY_SCHEMA_VERSION = "client_property_summary_v1"

_SEPARATOR = " \u00b7 "
_EURO = "\u20ac"
_M2 = "m\u00b2"

_KEY_FIELDS = (
    "asking_price",
    "property_type",
    "living_area_m2",
    "bedrooms",
    "energy_label",
    "eigendomssituatie",
)

_PROPERTY_TYPE_LABELS = {
    "appartement": "appartement",
    "tussenwoning": "tussenwoning",
    "hoekwoning": "hoekwoning",
    "vrijstaande_woning": "vrijstaande woning",
    "twee_onder_een_kap": "twee onder een kap",
    "herenhuis": "herenhuis",
    "benedenwoning": "benedenwoning",
    "bovenwoning": "bovenwoning",
    "maisonette": "maisonette",
    "bungalow": "bungalow",
    "studio": "studio",
    "bouwgrond": "bouwgrond",
    "woonhuis": "woonhuis",
    "garage": "garage",
}

_OWNERSHIP_LABELS = {
    "volle_eigendom": "volle eigendom",
    "eigen_grond": "eigen grond",
    "erfpacht": "erfpacht",
    "unknown": "onbekend",
}

_CV_OWNERSHIP_LABELS = {
    "eigendom": "eigendom",
    "huur": "huur",
    "lease": "lease",
    "unknown": "onbekend",
}

_WARNING_LABELS = {
    "conflicting_fact_values": "heeft conflicterende signalen",
    "normalization_failed": "kon niet betrouwbaar worden genormaliseerd",
    "implausible_count": "heeft een onwaarschijnlijke waarde",
    "implausible_area": "heeft een onwaarschijnlijke oppervlakte",
    "ambiguous_fact_candidate": "heeft een ambigue bronwaarde",
}


@dataclass(frozen=True, slots=True)
class ClientReadyPropertySummary:
    schema_version: str
    source_domain: str
    canonical_url: str
    address_raw: str | None
    city: str | None
    status: str | None
    headline: str
    facts_line: str
    financial_line: str
    outdoor_line: str
    energy_line: str
    attention_points: tuple[str, ...]
    missing_key_fields: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def build_client_ready_property_summary(
    record: PropertyFactsRecord,
    *,
    locale: str = "nl",
) -> ClientReadyPropertySummary:
    if locale != "nl":
        raise ValueError("unsupported_locale")

    usable = {fact.field: fact for fact in record.facts if fact.status == FACT_STATUS_USABLE}
    review = {fact.field: fact for fact in record.facts if fact.status == FACT_STATUS_REVIEW}
    warnings = _dedupe((*record.warnings, *(warning for fact in record.facts for warning in fact.warnings)))
    missing_key_fields = tuple(field for field in _KEY_FIELDS if field not in usable)

    return ClientReadyPropertySummary(
        schema_version=SUMMARY_SCHEMA_VERSION,
        source_domain=record.source_domain,
        canonical_url=record.canonical_url,
        address_raw=record.address_raw,
        city=record.city,
        status=record.status,
        headline=_headline(record, usable),
        facts_line=_facts_line(usable),
        financial_line=_financial_line(usable),
        outdoor_line=_outdoor_line(usable),
        energy_line=_energy_line(usable),
        attention_points=_attention_points(review, warnings, missing_key_fields),
        missing_key_fields=missing_key_fields,
        warnings=warnings,
    )


def summary_to_dict(summary: ClientReadyPropertySummary) -> dict[str, object]:
    return {
        "schema_version": summary.schema_version,
        "source_domain": summary.source_domain,
        "canonical_url": summary.canonical_url,
        "address_raw": summary.address_raw,
        "city": summary.city,
        "status": summary.status,
        "headline": summary.headline,
        "facts_line": summary.facts_line,
        "financial_line": summary.financial_line,
        "outdoor_line": summary.outdoor_line,
        "energy_line": summary.energy_line,
        "attention_points": list(summary.attention_points),
        "missing_key_fields": list(summary.missing_key_fields),
        "warnings": list(summary.warnings),
    }


def summary_from_dict(payload: Mapping[str, object]) -> ClientReadyPropertySummary:
    return ClientReadyPropertySummary(
        schema_version=str(payload.get("schema_version", "")),
        source_domain=str(payload.get("source_domain", "")),
        canonical_url=str(payload.get("canonical_url", "")),
        address_raw=_optional_str(payload.get("address_raw")),
        city=_optional_str(payload.get("city")),
        status=_optional_str(payload.get("status")),
        headline=str(payload.get("headline", "")),
        facts_line=str(payload.get("facts_line", "")),
        financial_line=str(payload.get("financial_line", "")),
        outdoor_line=str(payload.get("outdoor_line", "")),
        energy_line=str(payload.get("energy_line", "")),
        attention_points=_str_tuple(payload.get("attention_points")),
        missing_key_fields=_str_tuple(payload.get("missing_key_fields")),
        warnings=_str_tuple(payload.get("warnings")),
    )


def _headline(record: PropertyFactsRecord, usable: Mapping[str, Any]) -> str:
    parts = (
        _format_price(_value(usable, "asking_price")),
        record.city,
        _property_type_label(_value(usable, "property_type")),
        _format_area(_value(usable, "living_area_m2")),
        _format_count(_value(usable, "bedrooms"), "slaapkamer", "slaapkamers"),
        _format_energy_label(_value(usable, "energy_label"), compact=True),
    )
    return _join_parts(parts)


def _facts_line(usable: Mapping[str, Any]) -> str:
    parts = (
        _label("Type", _property_type_label(_value(usable, "property_type"))),
        _label("Woonoppervlakte", _format_area(_value(usable, "living_area_m2"))),
        _label("Perceel", _format_area(_value(usable, "plot_area_m2"))),
        _label("Kamers", _format_plain(_value(usable, "rooms"))),
        _label("Slaapkamers", _format_plain(_value(usable, "bedrooms"))),
    )
    return _join_parts(parts)


def _financial_line(usable: Mapping[str, Any]) -> str:
    parts = (
        _label("Vraagprijs", _format_price(_value(usable, "asking_price"))),
        _label("Eigendom", _ownership_label(_value(usable, "eigendomssituatie"))),
        _label("VvE", _format_vve(usable)),
    )
    return _join_parts(parts)


def _outdoor_line(usable: Mapping[str, Any]) -> str:
    outdoor = _dedupe(
        (
            _raw_text(_value(usable, "outdoor_space")),
            "tuin" if _truthy_signal(_value(usable, "garden")) else "",
            "balkon" if _truthy_signal(_value(usable, "balcony")) else "",
            "berging" if _truthy_signal(_value(usable, "storage")) else "",
        )
    )
    parking = _dedupe(
        (
            "garage" if _truthy_signal(_value(usable, "garage")) else "",
            _raw_text(_value(usable, "parking")),
        )
    )
    parts = (
        _label("Buitenruimte", ", ".join(outdoor) if outdoor else None),
        _label("Parkeren", "/".join(parking) if parking else None),
    )
    return _join_parts(parts)


def _energy_line(usable: Mapping[str, Any]) -> str:
    heating = _raw_text(_value(usable, "heating_type"))
    if not heating and _truthy_signal(_value(usable, "cv_ketel_present")):
        heating = "CV-ketel"
    parts = (
        _label("Energielabel", _format_energy_label(_value(usable, "energy_label"))),
        _label("CV-ketel", _cv_ownership_label(_value(usable, "cv_ketel_ownership"))),
        _label("Verwarming", heating),
    )
    return _join_parts(parts)


def _attention_points(
    review: Mapping[str, Any],
    warnings: tuple[str, ...],
    missing_key_fields: tuple[str, ...],
) -> tuple[str, ...]:
    points: list[str] = []
    for field, fact in sorted(review.items()):
        fact_warnings = tuple(fact.warnings)
        if "conflicting_fact_values" in fact_warnings:
            points.append(f"{field} heeft conflicterende signalen.")
        else:
            points.append(f"{field} staat in review.")
        for warning in fact_warnings:
            if warning == "conflicting_fact_values":
                continue
            label = _WARNING_LABELS.get(warning)
            if label:
                points.append(f"{field} {label}.")
    if "conflicting_fact_values" in warnings and not any("conflicterende signalen" in point for point in points):
        points.append("Er zijn conflicterende fact-signalen.")
    for field in missing_key_fields:
        points.append(f"{field} ontbreekt.")
    return _dedupe(points)


def _value(usable: Mapping[str, Any], field: str) -> object | None:
    fact = usable.get(field)
    if fact is None:
        return None
    return fact.normalized_value if fact.normalized_value is not None else fact.value


def _label(label: str, value: str | None) -> str | None:
    return f"{label}: {value}" if value else None


def _format_price(value: object | None) -> str | None:
    if not isinstance(value, int):
        return None
    return f"{_EURO}{value:,}".replace(",", ".")


def _format_area(value: object | None) -> str | None:
    if not isinstance(value, int):
        return None
    return f"{value} {_M2}"


def _format_count(value: object | None, singular: str, plural: str) -> str | None:
    if not isinstance(value, int):
        return None
    label = singular if value == 1 else plural
    return f"{value} {label}"


def _format_plain(value: object | None) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    return str(value)


def _format_energy_label(value: object | None, *, compact: bool = False) -> str | None:
    text = _raw_text(value)
    if not text:
        return None
    return f"label {text}" if compact else text


def _format_vve(usable: Mapping[str, Any]) -> str | None:
    monthly = _value(usable, "vve_monthly_cost")
    if isinstance(monthly, int):
        return f"{_EURO}{monthly} p/m"
    active = _value(usable, "vve_active")
    if active is False:
        return "n.v.t."
    if active is True:
        return "actief"
    return None


def _property_type_label(value: object | None) -> str | None:
    text = _raw_text(value)
    return _PROPERTY_TYPE_LABELS.get(text, text.replace("_", " ") if text else None)


def _ownership_label(value: object | None) -> str | None:
    text = _raw_text(value)
    return _OWNERSHIP_LABELS.get(text, text.replace("_", " ") if text else None)


def _cv_ownership_label(value: object | None) -> str | None:
    text = _raw_text(value)
    return _CV_OWNERSHIP_LABELS.get(text, text.replace("_", " ") if text else None)


def _truthy_signal(value: object | None) -> bool:
    return value is True or _raw_text(value) in {"source_available", "available", "aanwezig", "ja", "yes"}


def _raw_text(value: object | None) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = " ".join(str(value).split())
    if text == "source_available":
        return None
    lowered = text.casefold()
    if any(marker in lowered for marker in ("<html", "<script", "</", '{"', "{'", '"docs"', "window.__", '":', "\\\"")):
        return None
    return text or None


def _join_parts(parts: Iterable[str | None]) -> str:
    return _SEPARATOR.join(part for part in parts if part)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return ()
    return tuple(str(item) for item in value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
