from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.facts.models import FACT_STATUS_REVIEW, FACT_STATUS_USABLE, PropertyFactsRecord
from domek_wonen.facts.realworks_extractor import (
    REALWORKS_TRACKED_FIELDS,
    extract_realworks_property_facts_for_listing,
    realworks_field_completion_counts,
)
from domek_wonen.facts.summary import ClientReadyPropertySummary, build_client_ready_property_summary
from domek_wonen.parsers import ParserFamilyRunner, ParserInput
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.pilots.kin_full_property_readiness import (
    PropertyLocationReadiness,
    build_location_readiness_from_listing,
)
from domek_wonen.pilots.live_fetch import controlled_http_fetch_html
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult


MAX_REALWORKS_READINESS_DETAILS = 9
MAX_SAMPLE_ROWS = 5
MAX_PROBLEM_ROWS = 10
REALWORKS_READINESS_FIELDS = (
    "property_type",
    "asking_price",
    "availability",
    "rooms",
    "bedrooms",
    "bathrooms",
    "living_area_m2",
    "plot_area_m2",
    "volume_m3",
    "energy_label",
    "bouwjaar",
    "heating",
    "garden",
    "parking",
    "garage",
    "ownership_or_erfpacht",
    "description_length_bucket",
)
NON_RESIDENTIAL_TERMS = (
    "overigog",
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
_ROW_FACT_FIELDS = {
    "asking_price": "asking_price",
    "property_type": "property_type",
    "availability": "availability_date",
    "rooms": "rooms",
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    "living_area_m2": "living_area_m2",
    "plot_area_m2": "plot_area_m2",
    "volume_m3": "volume_m3",
    "energy_label": "energy_label",
    "bouwjaar": "bouwjaar",
    "heating": "heating_type",
    "garden": "garden",
    "parking": "parking",
    "garage": "garage",
    "ownership_or_erfpacht": "eigendomssituatie",
    "description_length_bucket": "description_length_bucket",
    "vve_active": "vve_active",
    "vve_monthly_cost": "vve_monthly_cost",
}
_SUMMARY_KEY_FIELDS = (
    "asking_price",
    "property_type",
    "living_area_m2",
    "bedrooms",
    "energy_label",
    "eigendomssituatie",
)
_ROW_REVIEW_FIELDS = (
    "property_type",
    "energy_label",
    "heating_type",
    "hot_water",
    "parking",
    "garage",
    "eigendomssituatie",
)
_NONCRITICAL_MISSING_REVIEW_FIELDS = (
    "postcode",
    "bedrooms",
    "bathrooms",
    "bouwjaar",
    "energy_label",
    "heating_type",
    "parking",
)
_CRITICAL_REVIEW_WARNINGS = frozenset(
    {
        "unsupported_property_type_definitely_non_residential",
        "conflicting_fact_values",
    }
)


@dataclass(frozen=True, slots=True)
class RealworksPropertyReadinessRow:
    source_id: str
    source_domain: str
    canonical_url: str
    property_link: str
    address: str | None
    postcode: str | None
    city: str | None
    source_status: str | None
    status_bucket: str
    active_inventory_eligible: bool
    db_persistence_action: str
    asking_price: int | None
    property_type: str | None
    status: str | None
    availability: str | int | None
    rooms: int | None
    bedrooms: int | None
    bathrooms: int | None
    living_area_m2: int | None
    plot_area_m2: int | None
    volume_m3: int | None
    energy_label: str | None
    bouwjaar: int | None
    heating: str | None
    garden: str | None
    parking: str | None
    garage: str | None
    ownership_or_erfpacht: str | None
    description_length_bucket: str | None
    residential_classification: str
    postcode_status: str
    postcode_source: str
    postcode_review_reason: str | None
    vve_active: bool | None
    vve_monthly_cost: int | None
    vve_status: str
    vve_review_reason: str | None
    vve_missing_reason: str | None
    energy_label_status: str
    energy_label_raw: str | None
    energy_label_review_reason: str | None
    client_summary: ClientReadyPropertySummary
    location_readiness: PropertyLocationReadiness
    export_readiness: str
    quality_status: str
    missing_key_fields: tuple[str, ...]
    review_fields: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    facts_record: PropertyFactsRecord | None = None


@dataclass(frozen=True, slots=True)
class RealworksCompactRow:
    canonical_url: str
    address: str | None
    postcode: str | None
    city: str | None
    asking_price: int | None
    property_type: str | None
    quality_status: str
    export_readiness: str
    missing_key_fields: tuple[str, ...]
    review_fields: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RealworksPropertyReadinessResult:
    source_id: str
    source_domain: str
    listing_parser_total: int
    listing_qa_clean: int
    listing_qa_review: int
    listing_qa_rejected: int
    detail_attempted: int
    detail_succeeded: int
    detail_failed: int
    facts_records_built: int
    readiness_rows_built: int
    quality_status_counts: tuple[tuple[str, int], ...]
    export_readiness_counts: tuple[tuple[str, int], ...]
    field_completion_counts: tuple[tuple[str, int, int, int], ...]
    missing_key_fields_counts: tuple[tuple[str, int], ...]
    review_fields_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    sample_rows_compact: tuple[RealworksCompactRow, ...]
    problem_rows_compact: tuple[RealworksCompactRow, ...]
    excel_validation_ready: bool
    rows: tuple[RealworksPropertyReadinessRow, ...] = ()
    warnings: tuple[str, ...] = ()


def build_realworks_property_readiness_row(
    listing: ParsedListing,
    facts_record: PropertyFactsRecord,
    location: PropertyLocationReadiness | None = None,
    postcode_status: str | None = None,
    postcode_source: str | None = None,
    postcode_review_reason: str | None = None,
) -> RealworksPropertyReadinessRow:
    location = location or build_location_readiness_from_listing(listing)
    summary = build_client_ready_property_summary(facts_record)
    fact_map = {fact.field: fact for fact in facts_record.facts}
    missing_key_fields = _missing_key_fields(listing, facts_record, summary, location)
    review_fields = _review_fields(facts_record)
    residential_classification = _residential_classification(listing, facts_record)
    derived_postcode_status, derived_postcode_source, derived_postcode_review_reason = _postcode_status(location)
    postcode_status = postcode_status or derived_postcode_status
    postcode_source = postcode_source or derived_postcode_source
    postcode_review_reason = postcode_review_reason or derived_postcode_review_reason
    vve_active, vve_monthly_cost, vve_status, vve_review_reason, vve_missing_reason = _vve_status(facts_record)
    energy_label_status, energy_label_raw, energy_label_review_reason = _energy_label_status(facts_record)
    if vve_status == "missing" and "vve_active" not in missing_key_fields:
        missing_key_fields = (*missing_key_fields, "vve_active")
    if residential_classification.startswith("non_residential") and "property_type" not in review_fields:
        review_fields = (*review_fields, "property_type")
    row_warnings = _row_warnings(
        location,
        facts_record,
        summary,
        residential_classification=residential_classification,
        vve_status=vve_status,
    )
    quality_status = _quality_status(
        listing=listing,
        facts_record=facts_record,
        location=location,
        missing_key_fields=missing_key_fields,
        review_fields=review_fields,
        warnings=row_warnings,
    )
    source_status = listing.status or facts_record.status
    status_bucket = _status_bucket(source_status, _value(fact_map, "availability_date"))
    active_inventory_eligible = _active_inventory_eligible(
        quality_status=quality_status,
        residential_classification=residential_classification,
        status_bucket=status_bucket,
    )
    db_persistence_action = _db_persistence_action(
        residential_classification=residential_classification,
        status_bucket=status_bucket,
    )
    row = RealworksPropertyReadinessRow(
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        canonical_url=listing.canonical_url,
        property_link=listing.canonical_url,
        address=location.address_raw,
        postcode=location.postcode,
        city=location.city,
        source_status=source_status,
        status_bucket=status_bucket,
        active_inventory_eligible=active_inventory_eligible,
        db_persistence_action=db_persistence_action,
        asking_price=_int_fact(fact_map, "asking_price"),
        property_type=_str_fact(fact_map, "property_type"),
        status=listing.status or facts_record.status,
        availability=_value(fact_map, "availability_date"),
        rooms=_int_fact(fact_map, "rooms"),
        bedrooms=_int_fact(fact_map, "bedrooms"),
        bathrooms=_int_fact(fact_map, "bathrooms"),
        living_area_m2=_int_fact(fact_map, "living_area_m2"),
        plot_area_m2=_int_fact(fact_map, "plot_area_m2"),
        volume_m3=_int_fact(fact_map, "volume_m3"),
        energy_label=_usable_str_fact(fact_map, "energy_label"),
        bouwjaar=_int_fact(fact_map, "bouwjaar"),
        heating=_str_fact(fact_map, "heating_type"),
        garden=_str_fact(fact_map, "garden"),
        parking=_str_fact(fact_map, "parking"),
        garage=_str_fact(fact_map, "garage"),
        ownership_or_erfpacht=_str_fact(fact_map, "eigendomssituatie"),
        description_length_bucket=_str_fact(fact_map, "description_length_bucket"),
        residential_classification=residential_classification,
        postcode_status=postcode_status,
        postcode_source=postcode_source,
        postcode_review_reason=postcode_review_reason,
        vve_active=vve_active,
        vve_monthly_cost=vve_monthly_cost,
        vve_status=vve_status,
        vve_review_reason=vve_review_reason,
        vve_missing_reason=vve_missing_reason,
        energy_label_status=energy_label_status,
        energy_label_raw=energy_label_raw,
        energy_label_review_reason=energy_label_review_reason,
        client_summary=summary,
        location_readiness=location,
        export_readiness="export_blocked",
        quality_status=quality_status,
        missing_key_fields=missing_key_fields,
        review_fields=review_fields,
        warnings=row_warnings,
        facts_record=facts_record,
    )
    return replace(row, export_readiness=classify_realworks_export_readiness(row))


def classify_realworks_export_readiness(row: RealworksPropertyReadinessRow) -> str:
    if row.quality_status == "blocked":
        return "export_blocked"
    if row.quality_status == "advisor_review":
        return "export_review"
    return "export_ready"


def run_realworks_property_readiness(
    *,
    source_id: str,
    source_domain: str,
    listing_url: str,
    max_listing_fetches: int = 1,
    max_detail_fetches: int = MAX_REALWORKS_READINESS_DETAILS,
    timeout_seconds: float = 15.0,
    fetch_html: Callable[[str], str] | None = None,
    now: datetime | None = None,
) -> RealworksPropertyReadinessResult:
    fetched_at = now or datetime.now(UTC)
    fetch = fetch_html or (lambda url: controlled_http_fetch_html(url, timeout_seconds=timeout_seconds))
    warnings: list[str] = []
    rows: list[RealworksPropertyReadinessRow] = []
    records: list[PropertyFactsRecord] = []
    listing_parser_total = 0
    listing_qa_clean = 0
    listing_qa_review = 0
    listing_qa_rejected = 0
    detail_attempted = 0
    detail_succeeded = 0
    detail_failed = 0

    if max_listing_fetches <= 0:
        warnings.append("max_listing_fetches_zero")
        return _result(
            source_id=source_id,
            source_domain=source_domain,
            listing_parser_total=0,
            listing_qa_clean=0,
            listing_qa_review=0,
            listing_qa_rejected=0,
            detail_attempted=0,
            detail_succeeded=0,
            detail_failed=0,
            records=(),
            rows=(),
            warnings=warnings,
        )

    can_fetch_listing, listing_robot_warnings = _robots_check_url(listing_url)
    warnings.extend(listing_robot_warnings)
    if not can_fetch_listing:
        warnings.append("listing_blocked_by_robots")
        return _result(
            source_id=source_id,
            source_domain=source_domain,
            listing_parser_total=0,
            listing_qa_clean=0,
            listing_qa_review=0,
            listing_qa_rejected=0,
            detail_attempted=0,
            detail_succeeded=0,
            detail_failed=0,
            records=(),
            rows=(),
            warnings=warnings,
        )

    try:
        listing_html = fetch(listing_url)
        parser_result = ParserFamilyRunner().run(
            _fingerprint(source_id=source_id, source_domain=source_domain),
            ParserInput(
                source_id=source_id,
                source_domain=source_domain,
                source_url=listing_url,
                content=listing_html,
                content_type="html",
            ),
        )
        qa_result = qa_parser_family_result(parser_result)
    except Exception:
        warnings.append("listing_fetch_parse_or_qa_exception")
        return _result(
            source_id=source_id,
            source_domain=source_domain,
            listing_parser_total=0,
            listing_qa_clean=0,
            listing_qa_review=0,
            listing_qa_rejected=0,
            detail_attempted=0,
            detail_succeeded=0,
            detail_failed=0,
            records=(),
            rows=(),
            warnings=warnings,
        )

    listing_parser_total = len(parser_result.listings)
    listing_qa_clean = qa_result.clean_count
    listing_qa_review = qa_result.review_count
    listing_qa_rejected = qa_result.rejected_count
    warnings.extend((*parser_result.warnings, *qa_result.warnings))

    clean_listings = tuple(item.listing for item in qa_result.clean_listings if item.listing.canonical_url)
    for listing in clean_listings[: max(0, max_detail_fetches)]:
        detail_attempted += 1
        can_fetch_detail, detail_robot_warnings = _robots_check_url(listing.canonical_url)
        warnings.extend(detail_robot_warnings)
        if not can_fetch_detail:
            detail_failed += 1
            warnings.append("detail_blocked_by_robots")
            continue
        try:
            detail_html = fetch(listing.canonical_url)
            extraction = extract_realworks_property_facts_for_listing(
                html=detail_html,
                listing=listing,
                fetched_at=fetched_at,
            )
        except Exception:
            detail_failed += 1
            warnings.append("detail_fetch_or_extract_exception")
            continue
        detail_succeeded += 1
        records.append(extraction.record)
        warnings.extend(extraction.warnings)
        row = build_realworks_property_readiness_row(
            listing,
            extraction.record,
            _location_with_extracted_detail(listing, extraction),
            postcode_status=extraction.postcode_status,
            postcode_source=extraction.postcode_source,
            postcode_review_reason=extraction.postcode_review_reason,
        )
        rows.append(row)

    return _result(
        source_id=source_id,
        source_domain=source_domain,
        listing_parser_total=listing_parser_total,
        listing_qa_clean=listing_qa_clean,
        listing_qa_review=listing_qa_review,
        listing_qa_rejected=listing_qa_rejected,
        detail_attempted=detail_attempted,
        detail_succeeded=detail_succeeded,
        detail_failed=detail_failed,
        records=tuple(records),
        rows=tuple(rows),
        warnings=warnings,
    )


def _result(
    *,
    source_id: str,
    source_domain: str,
    listing_parser_total: int,
    listing_qa_clean: int,
    listing_qa_review: int,
    listing_qa_rejected: int,
    detail_attempted: int,
    detail_succeeded: int,
    detail_failed: int,
    records: tuple[PropertyFactsRecord, ...],
    rows: tuple[RealworksPropertyReadinessRow, ...],
    warnings: Iterable[str],
) -> RealworksPropertyReadinessResult:
    row_warning_sequence = tuple(warning for row in rows for warning in row.warnings)
    all_warnings = _dedupe((*warnings, *row_warning_sequence))
    quality_counts = _counter_pairs(row.quality_status for row in rows)
    export_counts = _counter_pairs(row.export_readiness for row in rows)
    return RealworksPropertyReadinessResult(
        source_id=source_id,
        source_domain=source_domain,
        listing_parser_total=listing_parser_total,
        listing_qa_clean=listing_qa_clean,
        listing_qa_review=listing_qa_review,
        listing_qa_rejected=listing_qa_rejected,
        detail_attempted=detail_attempted,
        detail_succeeded=detail_succeeded,
        detail_failed=detail_failed,
        facts_records_built=len(records),
        readiness_rows_built=len(rows),
        quality_status_counts=quality_counts,
        export_readiness_counts=export_counts,
        field_completion_counts=realworks_field_completion_counts(records, REALWORKS_READINESS_FIELDS),
        missing_key_fields_counts=_counter_pairs(field for row in rows for field in row.missing_key_fields),
        review_fields_counts=_counter_pairs(field for row in rows for field in row.review_fields),
        warning_counts=_counter_pairs(row_warning_sequence if rows else warnings),
        sample_rows_compact=tuple(_compact_row(row) for row in rows[:MAX_SAMPLE_ROWS]),
        problem_rows_compact=_problem_rows(rows),
        excel_validation_ready=(
            bool(rows)
            and len(rows) == listing_qa_clean
            and detail_failed == 0
            and not any(row.quality_status == "blocked" for row in rows)
        ),
        rows=rows,
        warnings=all_warnings,
    )


def _missing_key_fields(
    listing: ParsedListing,
    facts_record: PropertyFactsRecord,
    summary: ClientReadyPropertySummary,
    location: PropertyLocationReadiness,
) -> tuple[str, ...]:
    fact_map = {fact.field: fact for fact in facts_record.facts}
    missing = list(summary.missing_key_fields)
    if not (listing.canonical_url or "").strip():
        missing.append("canonical_url")
    if not (location.address_raw or "").strip():
        missing.append("address")
    if not (location.city or "").strip():
        missing.append("city")
    if not (location.postcode or "").strip():
        missing.append("postcode")
    if not (_usable(fact_map, "living_area_m2") or _usable(fact_map, "plot_area_m2")):
        missing.append("area_or_size_signal")
    for field in _NONCRITICAL_MISSING_REVIEW_FIELDS:
        fact_field = _ROW_FACT_FIELDS.get(field, field)
        if field == "postcode":
            continue
        if fact_map.get(fact_field) is None or fact_map[fact_field].status not in {FACT_STATUS_USABLE, FACT_STATUS_REVIEW}:
            missing.append(field)
    return _dedupe(missing)


def _review_fields(facts_record: PropertyFactsRecord) -> tuple[str, ...]:
    fields = [
        report_field
        for report_field, fact_field in _ROW_FACT_FIELDS.items()
        if fact_field in _ROW_REVIEW_FIELDS and _fact_status(facts_record, fact_field) == FACT_STATUS_REVIEW
    ]
    return _dedupe(fields)


def _quality_status(
    *,
    listing: ParsedListing,
    facts_record: PropertyFactsRecord,
    location: PropertyLocationReadiness,
    missing_key_fields: tuple[str, ...],
    review_fields: tuple[str, ...],
    warnings: tuple[str, ...],
) -> str:
    fact_map = {fact.field: fact for fact in facts_record.facts}
    residential_classification = _residential_classification(listing, facts_record)
    if not (listing.canonical_url or "").strip():
        return "blocked"
    if not (location.address_raw or "").strip():
        return "blocked"
    if not (location.city or "").strip():
        return "blocked"
    if not _usable(fact_map, "asking_price"):
        return "blocked"
    if residential_classification == "non_residential_blocked":
        return "blocked"
    if residential_classification == "non_residential_review":
        return "blocked"
    if not _usable(fact_map, "property_type"):
        return "blocked"
    if _str_fact(fact_map, "property_type") in {"garage", "bouwgrond"}:
        return "blocked"
    if not (_usable(fact_map, "living_area_m2") or _usable(fact_map, "plot_area_m2")):
        return "blocked"
    if any(warning in _CRITICAL_REVIEW_WARNINGS for warning in warnings):
        return "blocked"
    if not (location.postcode or "").strip():
        return "advisor_review"
    if missing_key_fields or review_fields or location.location_status != "usable":
        return "advisor_review"
    return "client_ready"


def _row_warnings(
    location: PropertyLocationReadiness,
    facts_record: PropertyFactsRecord,
    summary: ClientReadyPropertySummary,
    *,
    residential_classification: str,
    vve_status: str,
) -> tuple[str, ...]:
    warnings = [*location.warnings, *facts_record.warnings, *summary.warnings]
    if residential_classification.startswith("non_residential"):
        warnings.append("non_residential_property_type")
    if vve_status == "missing":
        warnings.append("missing_vve_for_apartment")
    return _dedupe(warnings)


def _compact_row(row: RealworksPropertyReadinessRow) -> RealworksCompactRow:
    return RealworksCompactRow(
        canonical_url=row.canonical_url,
        address=row.address,
        postcode=row.postcode,
        city=row.city,
        asking_price=row.asking_price,
        property_type=row.property_type,
        quality_status=row.quality_status,
        export_readiness=row.export_readiness,
        missing_key_fields=row.missing_key_fields,
        review_fields=row.review_fields,
        warnings=row.warnings,
    )


def _problem_rows(rows: tuple[RealworksPropertyReadinessRow, ...]) -> tuple[RealworksCompactRow, ...]:
    ranked = sorted(rows, key=_problem_rank, reverse=True)
    return tuple(_compact_row(row) for row in ranked if _problem_rank(row) > 0)[:MAX_PROBLEM_ROWS]


def _problem_rank(row: RealworksPropertyReadinessRow) -> int:
    score = 0
    if row.quality_status == "blocked":
        score += 6
    if row.export_readiness == "export_blocked":
        score += 4
    if row.quality_status == "advisor_review":
        score += 2
    score += min(5, len(row.missing_key_fields))
    score += min(4, len(row.review_fields))
    if "unsupported_property_type_overigog" in row.warnings:
        score += 3
    if "non_residential_property_type" in row.warnings:
        score += 5
    if "missing_vve_for_apartment" in row.warnings:
        score += 2
    return score


def _postcode_status(location: PropertyLocationReadiness) -> tuple[str, str, str | None]:
    if (location.postcode or "").strip():
        return "usable", "parsed_listing", None
    return "missing", "missing_not_extracted", "postcode_missing_no_detail_or_listing_extraction"


def _location_with_extracted_detail(listing: ParsedListing, extraction: object) -> PropertyLocationReadiness:
    base = build_location_readiness_from_listing(listing)
    postcode = getattr(extraction, "postcode", None) or base.postcode
    city = getattr(extraction, "city", None) or base.city
    address_raw = getattr(extraction, "address_raw", None) or base.address_raw
    if postcode and address_raw and city:
        status = "usable"
        confidence = max(base.location_confidence, 0.88)
        warnings = tuple(warning for warning in base.warnings if warning not in {"missing_postcode", "partial_location"})
    else:
        status = base.location_status
        confidence = base.location_confidence
        warnings = base.warnings
    return replace(
        base,
        address_raw=address_raw,
        postcode=postcode,
        city=city,
        location_status=status,
        location_confidence=confidence,
        warnings=warnings,
    )


def _vve_status(facts_record: PropertyFactsRecord) -> tuple[bool | None, int | None, str, str | None, str | None]:
    fact_map = {fact.field: fact for fact in facts_record.facts}
    property_type = _str_fact(fact_map, "property_type")
    active_fact = fact_map.get("vve_active")
    monthly_fact = fact_map.get("vve_monthly_cost")
    active = _bool_fact(fact_map, "vve_active")
    monthly = _int_fact(fact_map, "vve_monthly_cost")
    if active_fact is not None and active_fact.status == FACT_STATUS_USABLE:
        return active, monthly, "usable", None, None
    if monthly_fact is not None and monthly_fact.status == FACT_STATUS_USABLE:
        return active, monthly, "usable", None, None
    if property_type == "appartement":
        return None, None, "missing", "apartment_without_vve_evidence", "missing_vve_for_apartment"
    if property_type in {"woonhuis", "tussenwoning", "hoekwoning", "vrijstaande_woning", "twee_onder_een_kap"}:
        return None, None, "not_applicable", None, None
    return None, None, "not_applicable", None, None


def _energy_label_status(facts_record: PropertyFactsRecord) -> tuple[str, str | None, str | None]:
    fact = next((candidate for candidate in facts_record.facts if candidate.field == "energy_label"), None)
    if fact is None:
        return "missing", None, "energy_label_missing"
    raw = str(fact.value) if fact.value not in (None, "") else None
    if fact.status == FACT_STATUS_USABLE and fact.normalized_value not in (None, ""):
        return "usable", raw, None
    if fact.status == FACT_STATUS_REVIEW:
        return "review", raw, "energy_label_not_explicit"
    return "missing", raw, "energy_label_missing"


def _residential_classification(listing: ParsedListing, facts_record: PropertyFactsRecord) -> str:
    fact_map = {fact.field: fact for fact in facts_record.facts}
    property_type_fact = fact_map.get("property_type")
    property_type = _str_fact(fact_map, "property_type")
    evidence = " ".join(
        str(value or "")
        for value in (
            property_type_fact.value if property_type_fact else "",
            property_type_fact.normalized_value if property_type_fact else "",
            listing.property_type,
            listing.address_raw,
            listing.canonical_url,
        )
    ).casefold()
    if "unsupported_property_type_overigog" in (property_type_fact.warnings if property_type_fact else ()):
        return "non_residential_blocked"
    if any(term in evidence for term in NON_RESIDENTIAL_TERMS):
        return "non_residential_blocked"
    if property_type in {"appartement", "woonhuis", "tussenwoning", "hoekwoning", "vrijstaande_woning", "twee_onder_een_kap", "herenhuis", "benedenwoning", "bovenwoning", "maisonette", "bungalow", "studio"}:
        return "residential"
    if property_type in {"garage", "bouwgrond"}:
        return "non_residential_blocked"
    return "residential_review"


def _status_bucket(source_status: object, availability: object) -> str:
    text = " ".join(str(value or "") for value in (source_status, availability)).casefold().replace("_", " ")
    if "verkocht onder voorbehoud" in text:
        return "inactive_under_contract"
    if "verkocht" in text:
        return "inactive_sold"
    if "onder bod" in text or "onder optie" in text:
        return "inactive_under_offer"
    if "verhuurd" in text:
        return "inactive_rented"
    if "beschikbaar" in text or "te koop" in text:
        return "active_available"
    return "status_review"


def _active_inventory_eligible(
    *,
    quality_status: str,
    residential_classification: str,
    status_bucket: str,
) -> bool:
    return (
        quality_status == "client_ready"
        and residential_classification == "residential"
        and status_bucket == "active_available"
    )


def _db_persistence_action(*, residential_classification: str, status_bucket: str) -> str:
    if residential_classification.startswith("non_residential"):
        return "store_excluded_non_residential"
    if status_bucket in {
        "inactive_under_contract",
        "inactive_sold",
        "inactive_under_offer",
        "inactive_rented",
    }:
        return "store_status_history"
    return "store_active_candidate"


def _fingerprint(*, source_id: str, source_domain: str) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=source_id,
        source_domain=source_domain,
        access_status="allowed",
        delivery_mode="realworks_public",
        parser_family_candidate="realworks_public",
        confidence=0.86,
        evidence_signals=("realworks", "property_readiness"),
        blocking_signals=(),
        recommended_action="realworks_property_readiness",
        can_proceed_to_parser_family=True,
        reason="realworks_property_readiness",
    )


def _robots_check_url(url: str) -> tuple[bool, tuple[str, ...]]:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return False, ("invalid_url",)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    try:
        return robots_gate.can_fetch(parts.netloc.lower(), path) is True, ()
    except Exception:
        return False, ("robots_gate_exception",)


def _fact_status(record: PropertyFactsRecord, field: str) -> str | None:
    for fact in record.facts:
        if fact.field == field:
            return fact.status
    return None


def _usable(facts: dict[str, Any], field: str) -> bool:
    fact = facts.get(field)
    return fact is not None and fact.status == FACT_STATUS_USABLE and _value(facts, field) not in (None, "")


def _value(facts: dict[str, Any], field: str) -> object | None:
    fact = facts.get(field)
    if fact is None:
        return None
    return fact.normalized_value if fact.normalized_value is not None else fact.value


def _int_fact(facts: dict[str, Any], field: str) -> int | None:
    value = _value(facts, field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _bool_fact(facts: dict[str, Any], field: str) -> bool | None:
    value = _value(facts, field)
    if isinstance(value, bool):
        return value
    return None


def _str_fact(facts: dict[str, Any], field: str) -> str | None:
    value = _value(facts, field)
    if value is None or isinstance(value, bool):
        return None
    return str(value)


def _usable_str_fact(facts: dict[str, Any], field: str) -> str | None:
    fact = facts.get(field)
    if fact is None or fact.status != FACT_STATUS_USABLE:
        return None
    value = fact.normalized_value if fact.normalized_value is not None else fact.value
    if value is None or isinstance(value, bool):
        return None
    return str(value)


def _counter_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(value for value in values if value).items()))


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
