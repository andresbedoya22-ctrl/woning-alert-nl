from __future__ import annotations

import re
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import unescape

from domek_wonen.parsers.models import ParsedListing

from .models import (
    FACT_STATUS_MISSING,
    FACT_STATUS_REVIEW,
    FACT_STATUS_USABLE,
    PropertyFactValue,
    PropertyFactsRecord,
    build_property_fact_value,
    build_property_facts_record,
)
from .normalization import (
    normalize_area_m2,
    normalize_count,
    normalize_description_length_bucket,
    normalize_eigendomssituatie,
    normalize_energy_label,
    normalize_heating_system,
    normalize_price,
    normalize_property_type,
    normalize_small_count,
)


REALWORKS_FACT_SOURCE = "realworks_kenmerk"
LISTING_FALLBACK_SOURCE = "listing_fallback"
REALWORKS_EVIDENCE_PREVIEW_LIMIT = 120

REALWORKS_TRACKED_FIELDS = (
    "property_type",
    "asking_price",
    "availability_date",
    "rooms",
    "bedrooms",
    "bathrooms",
    "living_area_m2",
    "plot_area_m2",
    "volume_m3",
    "energy_label",
    "bouwjaar",
    "heating_type",
    "hot_water",
    "insulation",
    "garden",
    "parking",
    "garage",
    "eigendomssituatie",
    "cv_ketel_present",
    "cv_ketel_ownership",
    "vve_monthly_cost",
    "vve_active",
    "description_length_bucket",
)

REPORT_FIELD_ALIASES = {
    "availability": "availability_date",
    "heating": "heating_type",
    "ownership_or_erfpacht": "eigendomssituatie",
}

_LABEL_TO_FIELD = {
    "aanvaarding": "availability_date",
    "aantal badkamers": "bathrooms",
    "aantal kamers": "rooms",
    "aantal slaapkamers": "bedrooms",
    "bouwjaar": "bouwjaar",
    "bijdrage vve": "vve_monthly_cost",
    "c.v.-ketel": "cv_ketel_present",
    "cv ketel": "cv_ketel_present",
    "cv-ketel": "cv_ketel_present",
    "eigendomssituatie": "eigendomssituatie",
    "energieklasse": "energy_label",
    "energielabel": "energy_label",
    "garage": "garage",
    "garagetypes": "garage",
    "inhoud": "volume_m3",
    "isolatie": "insulation",
    "parkeerfaciliteiten": "parking",
    "parkeertypes": "parking",
    "perceeloppervlakte": "plot_area_m2",
    "postcode": "postcode",
    "status": "availability_date",
    "servicekosten": "vve_monthly_cost",
    "soort object": "property_type",
    "tuin": "garden",
    "tuintypes": "garden",
    "verwarming": "heating_type",
    "vraagprijs": "asking_price",
    "warmwater": "hot_water",
    "warm water": "hot_water",
    "woonoppervlakte": "living_area_m2",
    "vve": "vve_active",
    "vve bijdrage": "vve_monthly_cost",
}
_POSTCODE_PATTERN = re.compile(r"\b(?P<postcode>[1-9][0-9]{3})\s?(?P<letters>[A-Z]{2})\b", re.IGNORECASE)
_JSON_LD_PATTERN = re.compile(
    r"<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_PATTERN = re.compile(r"<[^>]+>", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_KENMERK_BLOCK_PATTERN = re.compile(
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*\bkenmerk\b[^'\"]*['\"][^>]*>(?P<body>.*?)</span>\s*</span>",
    re.IGNORECASE | re.DOTALL,
)
_KENMERK_PAIR_PATTERN = re.compile(
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*kenmerkName[^'\"]*['\"][^>]*>(?P<label>.*?)</span>\s*"
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*kenmerkValue[^'\"]*['\"][^>]*>(?P<value>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
_META_DESCRIPTION_PATTERN = re.compile(
    r"<meta\b(?=[^>]*(?:name|property)\s*=\s*['\"](?:description|og:description)['\"])(?=[^>]*content\s*=\s*['\"](?P<content>[^'\"]*)['\"])[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_PAIR_LABELS = frozenset({"omschrijving", "description", "beschrijving"})
_YEAR_PATTERN = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_DATE_TOKEN_PATTERN = re.compile(
    r"\b(?:20\d{2}-\d{1,2}-\d{1,2}(?:T[0-9:.+-]+Z?)?|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}|\d{1,2}\s+[A-Za-z]+\s+20\d{2})\b",
    re.IGNORECASE,
)
_SOURCE_PUBLISHED_LABELS = frozenset(
    {
        "aangemeld",
        "gepubliceerd",
        "publicatiedatum",
        "datum plaatsing",
        "sinds",
        "beschikbaar sinds",
        "plaatsingsdatum",
        "online sinds",
    }
)
_DUTCH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True, slots=True)
class RealworksFactsExtractionResult:
    record: PropertyFactsRecord
    fields_usable: tuple[str, ...]
    fields_review: tuple[str, ...]
    fields_missing: tuple[str, ...]
    warning_counts: tuple[tuple[str, int], ...]
    address_raw: str | None = None
    postcode: str | None = None
    city: str | None = None
    postcode_status: str = "missing"
    postcode_source: str = "missing_not_extracted"
    postcode_review_reason: str | None = None
    source_published_at: datetime | None = None
    source_published_at_raw: str | None = None
    source_published_at_source: str | None = None
    source_published_at_status: str = "missing"
    source_published_at_review_reason: str | None = None
    warnings: tuple[str, ...] = ()


def extract_realworks_property_facts_from_html(
    *,
    html: str,
    source_id: str,
    source_domain: str,
    canonical_url: str,
    address_raw: str | None = None,
    city: str | None = None,
    status: str | None = None,
    fetched_at: datetime,
    ttl_days: int = 14,
    listing_fallbacks: Mapping[str, object] | None = None,
) -> RealworksFactsExtractionResult:
    label_values = _extract_kenmerk_label_values(html)
    location = _extract_location_from_detail_html(html, label_values)
    published_at = _extract_source_published_at(html, label_values)
    warnings: list[str] = []
    facts: list[PropertyFactValue] = []
    seen_fields: set[str] = set()

    for label, value in label_values:
        field = _LABEL_TO_FIELD.get(label)
        if field is None:
            continue
        if field == "postcode":
            continue
        fact = _fact_from_kenmerk(field=field, label=label, value=value)
        facts.append(fact)
        seen_fields.add(field)
        warnings.extend(fact.warnings)

    fallback_facts = _listing_fallback_facts(
        listing_fallbacks or {},
        seen_fields={fact.field for fact in facts if fact.status == FACT_STATUS_USABLE},
    )
    facts.extend(fallback_facts)
    seen_fields.update(fact.field for fact in fallback_facts)

    if "description_length_bucket" not in seen_fields:
        description_bucket = _description_length_bucket(html, label_values)
        facts.append(
            build_property_fact_value(
                field="description_length_bucket",
                value=description_bucket,
                normalized_value=normalize_description_length_bucket(description_bucket),
                source=REALWORKS_FACT_SOURCE,
                confidence=0.70,
                status=FACT_STATUS_USABLE if description_bucket != "none" else FACT_STATUS_MISSING,
                evidence_preview=description_bucket,
            )
        )
        seen_fields.add("description_length_bucket")
        if description_bucket != "none":
            warnings.append("description_not_stored")

    for field in REALWORKS_TRACKED_FIELDS:
        if field in seen_fields:
            continue
        facts.append(_missing_fact(field))

    fetched = _datetime_to_utc_iso(fetched_at)
    expires_at = _datetime_to_utc_iso(fetched_at + timedelta(days=ttl_days)) if ttl_days > 0 else None
    raw_warnings = tuple(warnings)
    record = build_property_facts_record(
        source_id=source_id,
        source_domain=source_domain,
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        status=status,
        facts=facts,
        extraction_status="complete" if any(fact.status == FACT_STATUS_USABLE for fact in facts) else "partial",
        fetched_at=fetched,
        expires_at=expires_at,
        warnings=raw_warnings,
    )
    all_warnings = _dedupe((*raw_warnings, *record.warnings, *(warning for fact in record.facts for warning in fact.warnings)))
    return RealworksFactsExtractionResult(
        record=record,
        fields_usable=tuple(fact.field for fact in record.facts if fact.status == FACT_STATUS_USABLE),
        fields_review=tuple(fact.field for fact in record.facts if fact.status == FACT_STATUS_REVIEW),
        fields_missing=tuple(fact.field for fact in record.facts if fact.status == FACT_STATUS_MISSING),
        warning_counts=_counter_pairs(all_warnings),
        address_raw=location.address_raw or address_raw,
        postcode=location.postcode,
        city=location.city or city,
        postcode_status=location.postcode_status,
        postcode_source=location.postcode_source,
        postcode_review_reason=location.postcode_review_reason,
        source_published_at=published_at.source_published_at,
        source_published_at_raw=published_at.source_published_at_raw,
        source_published_at_source=published_at.source_published_at_source,
        source_published_at_status=published_at.source_published_at_status,
        source_published_at_review_reason=published_at.source_published_at_review_reason,
        warnings=all_warnings,
    )


def extract_realworks_property_facts_for_listing(
    *,
    html: str,
    listing: ParsedListing,
    fetched_at: datetime,
    ttl_days: int = 14,
) -> RealworksFactsExtractionResult:
    return extract_realworks_property_facts_from_html(
        html=html,
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        canonical_url=listing.canonical_url,
        address_raw=listing.address_raw or None,
        city=listing.city or None,
        status=listing.status or None,
        fetched_at=fetched_at,
        ttl_days=ttl_days,
        listing_fallbacks={
            "asking_price": listing.asking_price_eur,
            "status": listing.status,
        },
    )


def realworks_field_completion_counts(
    records: Iterable[PropertyFactsRecord],
    fields: Iterable[str],
) -> tuple[tuple[str, int, int, int], ...]:
    rows: list[tuple[str, int, int, int]] = []
    for requested_field in fields:
        field = REPORT_FIELD_ALIASES.get(requested_field, requested_field)
        statuses = Counter(
            fact.status
            for record in records
            for fact in record.facts
            if fact.field == field
        )
        rows.append(
            (
                requested_field,
                statuses[FACT_STATUS_USABLE],
                statuses[FACT_STATUS_REVIEW],
                statuses[FACT_STATUS_MISSING],
            )
        )
    return tuple(rows)


def _extract_kenmerk_label_values(html: str) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for match in _KENMERK_PAIR_PATTERN.finditer(html or ""):
        label = _normalize_label(_strip_tags(match.group("label")))
        value = _clean_evidence(_strip_tags(match.group("value")))
        if label and value:
            pairs.append((label, value))
    return tuple(_dedupe_pairs(pairs))


@dataclass(frozen=True, slots=True)
class _ExtractedLocation:
    address_raw: str | None
    postcode: str | None
    city: str | None
    postcode_status: str
    postcode_source: str
    postcode_review_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _ExtractedSourcePublishedAt:
    source_published_at: datetime | None
    source_published_at_raw: str | None
    source_published_at_source: str | None
    source_published_at_status: str
    source_published_at_review_reason: str | None = None


def _extract_source_published_at(
    html: str,
    label_values: tuple[tuple[str, str], ...],
) -> _ExtractedSourcePublishedAt:
    strong_candidates: list[_ExtractedSourcePublishedAt] = []
    review_candidates: list[_ExtractedSourcePublishedAt] = []

    for match in _JSON_LD_PATTERN.finditer(html or ""):
        try:
            payload = json.loads(unescape(match.group("body")).strip())
        except Exception:
            continue
        for item in _walk_json(payload):
            if not isinstance(item, dict):
                continue
            for key, source in (("datePosted", "json_ld_datePosted"), ("datePublished", "json_ld_datePublished")):
                parsed = _source_published_candidate(item.get(key), source=source, status="usable")
                if parsed:
                    strong_candidates.append(parsed)
            parsed_modified = _source_published_candidate(
                item.get("dateModified"),
                source="json_ld_dateModified",
                status="review",
                review_reason="date_modified_not_publication_date",
            )
            if parsed_modified:
                review_candidates.append(parsed_modified)

    for label, value in label_values:
        if label not in _SOURCE_PUBLISHED_LABELS:
            continue
        parsed = _source_published_candidate(value, source=f"realworks_kenmerk_{label.replace(' ', '_')}", status="usable")
        if parsed:
            strong_candidates.append(parsed)

    for parsed in _extract_embedded_state_dates(html):
        if parsed.source_published_at_status == "usable":
            strong_candidates.append(parsed)
        else:
            review_candidates.append(parsed)

    return _select_source_published_candidate(strong_candidates, review_candidates)


def _extract_embedded_state_dates(html: str) -> tuple[_ExtractedSourcePublishedAt, ...]:
    candidates: list[_ExtractedSourcePublishedAt] = []
    source_names = {
        "publishedAt": ("embedded_state_publishedAt", "usable", None),
        "createdAt": ("embedded_state_createdAt", "usable", None),
        "datePublished": ("embedded_state_datePublished", "usable", None),
        "datePosted": ("embedded_state_datePosted", "usable", None),
        "availableFrom": ("embedded_state_availableFrom", "usable", None),
        "updatedAt": ("embedded_state_updatedAt", "review", "updated_at_not_publication_date"),
        "statusChangedAt": ("embedded_state_statusChangedAt", "review", "status_changed_at_not_publication_date"),
    }
    for field, (source, status, reason) in source_names.items():
        pattern = re.compile(rf'["\']{re.escape(field)}["\']\s*:\s*["\'](?P<value>[^"\']+)["\']', re.IGNORECASE)
        for match in pattern.finditer(html or ""):
            parsed = _source_published_candidate(
                match.group("value"),
                source=source,
                status=status,
                review_reason=reason,
            )
            if parsed:
                candidates.append(parsed)
    return tuple(candidates)


def _select_source_published_candidate(
    strong_candidates: list[_ExtractedSourcePublishedAt],
    review_candidates: list[_ExtractedSourcePublishedAt],
) -> _ExtractedSourcePublishedAt:
    strong = _unique_source_date_candidates(strong_candidates)
    if len({candidate.source_published_at.date() for candidate in strong if candidate.source_published_at}) > 1:
        raw = "; ".join(candidate.source_published_at_raw or "" for candidate in strong if candidate.source_published_at_raw)
        return _ExtractedSourcePublishedAt(
            source_published_at=None,
            source_published_at_raw=raw or None,
            source_published_at_source="conflicting_source_published_at_candidates",
            source_published_at_status="review",
            source_published_at_review_reason="source_published_at_conflict",
        )
    if strong:
        return strong[0]
    if review_candidates:
        return review_candidates[0]
    return _ExtractedSourcePublishedAt(None, None, None, "missing", None)


def _unique_source_date_candidates(
    candidates: list[_ExtractedSourcePublishedAt],
) -> list[_ExtractedSourcePublishedAt]:
    seen: set[tuple[datetime | None, str | None, str | None]] = set()
    result: list[_ExtractedSourcePublishedAt] = []
    for candidate in candidates:
        key = (candidate.source_published_at, candidate.source_published_at_raw, candidate.source_published_at_source)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _source_published_candidate(
    value: object,
    *,
    source: str,
    status: str,
    review_reason: str | None = None,
) -> _ExtractedSourcePublishedAt | None:
    raw = _optional_text(value)
    if not raw:
        return None
    parsed = _parse_publication_date(raw)
    if parsed is None:
        return _ExtractedSourcePublishedAt(
            source_published_at=None,
            source_published_at_raw=raw,
            source_published_at_source=source,
            source_published_at_status="review",
            source_published_at_review_reason="source_published_at_unparseable",
        )
    return _ExtractedSourcePublishedAt(
        source_published_at=parsed,
        source_published_at_raw=raw,
        source_published_at_source=source,
        source_published_at_status=status,
        source_published_at_review_reason=review_reason,
    )


def _parse_publication_date(value: str) -> datetime | None:
    text = _clean_evidence(value)
    token_match = _DATE_TOKEN_PATTERN.search(text)
    if token_match:
        text = token_match.group(0)
    iso_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        pass
    numeric_match = re.fullmatch(r"(?P<day>\d{1,2})[-/.](?P<month>\d{1,2})[-/.](?P<year>20\d{2})", text)
    if numeric_match:
        return _date_parts_to_datetime(
            int(numeric_match.group("year")),
            int(numeric_match.group("month")),
            int(numeric_match.group("day")),
        )
    textual_match = re.fullmatch(r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>20\d{2})", text, re.IGNORECASE)
    if textual_match:
        month = _DUTCH_MONTHS.get(textual_match.group("month").casefold())
        if month is None:
            return None
        return _date_parts_to_datetime(int(textual_match.group("year")), month, int(textual_match.group("day")))
    return None


def _date_parts_to_datetime(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _extract_location_from_detail_html(
    html: str,
    label_values: tuple[tuple[str, str], ...],
) -> _ExtractedLocation:
    json_location = _extract_json_ld_location(html)
    header_location = _extract_header_location(html)
    label_location = _extract_label_postcode_location(label_values)
    visible_location = _extract_visible_postcode_location(html)

    if json_location.postcode and header_location.postcode and json_location.postcode != header_location.postcode:
        return _ExtractedLocation(
            address_raw=json_location.address_raw or header_location.address_raw,
            postcode=json_location.postcode,
            city=json_location.city or header_location.city,
            postcode_status="review",
            postcode_source="json_ld_conflict",
            postcode_review_reason="postcode_conflict_json_ld_visible_header",
        )
    for candidate in (json_location, header_location, visible_location, label_location):
        if candidate.postcode:
            return candidate
    return _ExtractedLocation(None, None, None, "missing", "missing_not_extracted", "postcode_not_found")


def _extract_json_ld_location(html: str) -> _ExtractedLocation:
    for match in _JSON_LD_PATTERN.finditer(html or ""):
        try:
            payload = json.loads(unescape(match.group("body")).strip())
        except Exception:
            continue
        for item in _walk_json(payload):
            if not isinstance(item, dict):
                continue
            address = item.get("address")
            if not isinstance(address, dict):
                continue
            postcode = _normalize_postcode(address.get("postalCode"))
            if not postcode:
                continue
            return _ExtractedLocation(
                address_raw=_optional_text(address.get("streetAddress")),
                postcode=postcode,
                city=_optional_text(address.get("addressLocality")),
                postcode_status="usable",
                postcode_source="json_ld",
            )
    return _ExtractedLocation(None, None, None, "missing", "missing_not_extracted")


def _walk_json(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _extract_header_location(html: str) -> _ExtractedLocation:
    text = _normalize_visible_text(unescape(_TAG_PATTERN.sub(" ", html or "")))
    match = re.search(
        rf"(?P<address>[^|]{{2,120}}?)\s*\|\s*(?P<postcode>[1-9][0-9]{{3}}\s?[A-Z]{{2}})\s+(?P<city>[A-Za-zÀ-ÿ' -]{{2,80}})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return _ExtractedLocation(None, None, None, "missing", "missing_not_extracted")
    return _ExtractedLocation(
        address_raw=_optional_text(match.group("address")),
        postcode=_normalize_postcode(match.group("postcode")),
        city=_optional_text(match.group("city")),
        postcode_status="usable",
        postcode_source="realworks_detail_header",
    )


def _extract_visible_postcode_location(html: str) -> _ExtractedLocation:
    text = _normalize_visible_text(unescape(_TAG_PATTERN.sub(" ", html or "")))
    match = _POSTCODE_PATTERN.search(text)
    if not match:
        return _ExtractedLocation(None, None, None, "missing", "missing_not_extracted")
    city_match = re.match(r"\s*(?P<city>[A-Za-zÀ-ÿ' -]{2,80})", text[match.end() :])
    return _ExtractedLocation(
        address_raw=None,
        postcode=_normalize_postcode(match.group(0)),
        city=_optional_text(city_match.group("city")) if city_match else None,
        postcode_status="usable",
        postcode_source="visible_postcode_regex",
    )


def _extract_label_postcode_location(label_values: tuple[tuple[str, str], ...]) -> _ExtractedLocation:
    for label, value in label_values:
        if label != "postcode":
            continue
        postcode = _normalize_postcode(value)
        if postcode:
            return _ExtractedLocation(
                address_raw=None,
                postcode=postcode,
                city=None,
                postcode_status="usable",
                postcode_source="realworks_kenmerk_postcode",
            )
    return _ExtractedLocation(None, None, None, "missing", "missing_not_extracted")


def _normalize_postcode(value: object) -> str | None:
    match = _POSTCODE_PATTERN.search(str(value or "").upper())
    if not match:
        return None
    return f"{match.group('postcode')} {match.group('letters').upper()}"


def _optional_text(value: object) -> str | None:
    text = _normalize_visible_text(str(value or ""))
    return text or None


def _fact_from_kenmerk(*, field: str, label: str, value: str) -> PropertyFactValue:
    normalized: str | int | bool | None
    status = FACT_STATUS_USABLE
    warnings: list[str] = []
    unit: str | None = None

    if field == "asking_price":
        normalized = normalize_price(value)
        unit = "EUR"
    elif field in {"living_area_m2", "plot_area_m2"}:
        normalized = normalize_area_m2(value)
        unit = "m2"
    elif field == "volume_m3":
        normalized = normalize_count(value)
        unit = "m3"
    elif field == "rooms":
        normalized = normalize_count(value)
    elif field == "bedrooms":
        normalized = normalize_small_count(value, minimum=0, maximum=8)
    elif field == "bathrooms":
        normalized = normalize_small_count(value, minimum=0, maximum=10)
    elif field == "bouwjaar":
        normalized = _normalize_bouwjaar(value)
    elif field == "energy_label":
        normalized = _normalize_explicit_energy_label(value)
        if normalized is None:
            status = FACT_STATUS_REVIEW
            warnings.append("energy_label_not_explicit")
    elif field == "property_type":
        normalized, property_warnings = _normalize_realworks_property_type(value)
        warnings.extend(property_warnings)
        if property_warnings:
            status = FACT_STATUS_REVIEW
    elif field == "eigendomssituatie":
        normalized = normalize_eigendomssituatie(value)
        if normalized == "unknown":
            status = FACT_STATUS_REVIEW
            warnings.append("ownership_ambiguous")
    elif field == "heating_type":
        normalized = normalize_heating_system(value) or _preview(value)
        if normalize_heating_system(value) is None:
            status = FACT_STATUS_REVIEW
            warnings.append("heating_not_normalized")
    elif field == "hot_water":
        normalized = normalize_heating_system(value) or _preview(value)
        if normalize_heating_system(value) is None:
            status = FACT_STATUS_REVIEW
            warnings.append("hot_water_not_normalized")
    elif field == "cv_ketel_present":
        normalized = "cv" in _normalize_text(value)
        warnings.append("cv_ketel_ownership_not_clear")
    elif field == "cv_ketel_ownership":
        normalized = None
        status = FACT_STATUS_MISSING
    elif field in {"parking", "garage"}:
        normalized = _normalize_open_text_value(value)
        if _is_ambiguous_parking_or_garage(value):
            status = FACT_STATUS_REVIEW
            warnings.append(f"{field}_ambiguous")
    elif field == "garden":
        normalized = _normalize_open_text_value(value)
    elif field in {"insulation", "availability_date"}:
        normalized = _preview(value)
    elif field == "vve_monthly_cost":
        normalized = normalize_price(value)
        if normalized is None:
            status = FACT_STATUS_REVIEW
            warnings.append("vve_present_without_monthly_cost")
    elif field == "vve_active":
        normalized = True
    else:
        normalized = _preview(value)

    if normalized is None and status == FACT_STATUS_USABLE:
        status = FACT_STATUS_REVIEW
        warnings.append("normalization_failed")

    return build_property_fact_value(
        field=field,
        value=_preview(value),
        normalized_value=normalized,
        unit=unit,
        source=REALWORKS_FACT_SOURCE,
        confidence=0.90 if status == FACT_STATUS_USABLE else 0.65,
        status=status,
        evidence_preview=value,
        warnings=warnings,
    )


def _listing_fallback_facts(
    fallbacks: Mapping[str, object],
    *,
    seen_fields: set[str],
) -> tuple[PropertyFactValue, ...]:
    facts: list[PropertyFactValue] = []
    price = fallbacks.get("asking_price")
    if "asking_price" not in seen_fields and price not in (None, ""):
        facts.append(
            build_property_fact_value(
                field="asking_price",
                value=price if isinstance(price, (str, int, float)) else str(price),
                normalized_value=normalize_price(price),
                unit="EUR",
                source=LISTING_FALLBACK_SOURCE,
                confidence=0.80,
                status=FACT_STATUS_USABLE if normalize_price(price) is not None else FACT_STATUS_REVIEW,
                evidence_preview=str(price),
            )
        )
    status = fallbacks.get("status")
    if "availability_date" not in seen_fields and status not in (None, ""):
        facts.append(
            build_property_fact_value(
                field="availability_date",
                value=str(status),
                normalized_value=str(status),
                source=LISTING_FALLBACK_SOURCE,
                confidence=0.75,
                status=FACT_STATUS_USABLE,
                evidence_preview=str(status),
            )
        )
    return tuple(facts)


def _missing_fact(field: str) -> PropertyFactValue:
    return build_property_fact_value(
        field=field,
        value=None,
        normalized_value=None,
        source=REALWORKS_FACT_SOURCE,
        confidence=0.0,
        status=FACT_STATUS_MISSING,
        evidence_preview="",
    )


def _normalize_realworks_property_type(value: str) -> tuple[str | None, tuple[str, ...]]:
    text = _normalize_text(value)
    if text == "overigog":
        return "unknown", ("unsupported_property_type_overigog", "non_residential_property_type")
    if _is_non_residential_text(text):
        normalized = normalize_property_type(value)
        return normalized or "unknown", ("non_residential_property_type",)
    normalized = normalize_property_type(value)
    if normalized in {None, "unknown"}:
        return normalized, ("property_type_not_supported",)
    return normalized, ()


def _normalize_explicit_energy_label(value: str) -> str | None:
    text = _normalize_text(value).upper().replace(" ", "")
    text = text.replace("ENERGIEKLASSE", "").replace("ENERGIELABEL", "")
    if not text:
        return None
    return normalize_energy_label(text)


def _normalize_bouwjaar(value: str) -> int | None:
    match = _YEAR_PATTERN.search(value or "")
    return int(match.group(1)) if match else None


def _normalize_open_text_value(value: str) -> str:
    text = _preview(value)
    normalized = _normalize_text(text)
    if fieldless := {
        "geen garage": "geen_garage",
        "geen tuin": "geen_tuin",
    }.get(normalized):
        return fieldless
    return text


def _is_ambiguous_parking_or_garage(value: str) -> bool:
    text = _normalize_text(value)
    return text in {"n.v.t.", "nvt", "onbekend", "diverse", "nader te bepalen"} or "mogelijk" in text


def _is_non_residential_text(text: str) -> bool:
    terms = (
        "garage",
        "garages",
        "parkeerplaats",
        "parkeerplaatsen",
        "berging",
        "schuur",
        "opslag",
        "box",
        "bedrijfsruimte",
        "kantoor",
        "winkelruimte",
    )
    return any(term in text for term in terms)


def _description_length_bucket(html: str, label_values: tuple[tuple[str, str], ...]) -> str:
    text = _description_text(html, label_values)
    length = len(_normalize_visible_text(text))
    if length <= 0:
        return "none"
    if length < 250:
        return "short"
    if length < 1000:
        return "medium"
    return "long"


def _description_text(html: str, label_values: tuple[tuple[str, str], ...]) -> str:
    match = _META_DESCRIPTION_PATTERN.search(html or "")
    if match:
        return _clean_evidence(unescape(match.group("content")))
    for label, value in label_values:
        if label in _DESCRIPTION_PAIR_LABELS:
            return value
    return ""


def _strip_tags(value: str) -> str:
    return _normalize_visible_text(unescape(_TAG_PATTERN.sub(" ", value or "")))


def _normalize_visible_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip()


def _normalize_label(value: str) -> str:
    return _normalize_text(value).strip(":")


def _normalize_text(value: str) -> str:
    return _normalize_visible_text(value).casefold()


def _clean_evidence(value: str) -> str:
    return _normalize_visible_text(value)


def _preview(value: object) -> str:
    text = _normalize_visible_text(str(value or ""))
    if len(text) <= REALWORKS_EVIDENCE_PREVIEW_LIMIT:
        return text
    return text[:REALWORKS_EVIDENCE_PREVIEW_LIMIT].rstrip()


def _dedupe_pairs(values: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for value in values:
        if value[0] and value[1] and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _counter_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(value for value in values if value).items()))


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
