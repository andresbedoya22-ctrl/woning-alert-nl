from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.facts.models import PropertyFactsRecord
from domek_wonen.facts.realworks_extractor import (
    extract_realworks_property_facts_for_listing,
    realworks_field_completion_counts,
)
from domek_wonen.parsers import ParserFamilyRunner, ParserInput
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.pilots.live_fetch import controlled_http_fetch_html
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult


REALWORKS_VALIDATION_FIELDS = (
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


@dataclass(frozen=True, slots=True)
class RealworksFactsValidationResult:
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
    field_completion: tuple[tuple[str, int, int, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    sample_records_compact: tuple[tuple[str, str | int | None, str | int | None, str | int | None, str | int | None, str | int | None], ...]
    records: tuple[PropertyFactsRecord, ...] = ()
    warnings: tuple[str, ...] = ()


def run_realworks_property_facts_validation(
    *,
    source_id: str,
    source_domain: str,
    listing_url: str,
    max_detail_fetches: int = 9,
    timeout_seconds: float = 15.0,
    fetch_html: Callable[[str], str] | None = None,
    now: datetime | None = None,
) -> RealworksFactsValidationResult:
    fetched_at = now or datetime.now(UTC)
    fetch = fetch_html or (lambda url: controlled_http_fetch_html(url, timeout_seconds=timeout_seconds))
    warnings: list[str] = []
    listing_parser_total = 0
    listing_qa_clean = 0
    listing_qa_review = 0
    listing_qa_rejected = 0
    records: list[PropertyFactsRecord] = []
    detail_attempted = 0
    detail_succeeded = 0
    detail_failed = 0

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
    warnings: Iterable[str],
) -> RealworksFactsValidationResult:
    warning_tuple = tuple(warnings)
    raw_warnings = _dedupe(warning_tuple)
    return RealworksFactsValidationResult(
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
        field_completion=realworks_field_completion_counts(records, REALWORKS_VALIDATION_FIELDS),
        warning_counts=tuple(sorted(Counter(warning for warning in warning_tuple if warning).items())),
        sample_records_compact=tuple(_sample_record(record) for record in records[:3]),
        records=records,
        warnings=raw_warnings,
    )


def _sample_record(record: PropertyFactsRecord) -> tuple[str, str | int | None, str | int | None, str | int | None, str | int | None, str | int | None]:
    facts = {fact.field: fact for fact in record.facts}
    return (
        record.canonical_url,
        record.address_raw,
        _fact_value(facts, "asking_price"),
        _fact_value(facts, "property_type"),
        _fact_value(facts, "living_area_m2"),
        _fact_value(facts, "energy_label"),
    )


def _fact_value(facts: dict[str, object], field: str) -> str | int | None:
    fact = facts.get(field)
    if fact is None:
        return None
    value = getattr(fact, "normalized_value", None)
    if value is None:
        value = getattr(fact, "value", None)
    return value if isinstance(value, (str, int)) else None


def _fingerprint(*, source_id: str, source_domain: str) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=source_id,
        source_domain=source_domain,
        access_status="allowed",
        delivery_mode="realworks_public",
        parser_family_candidate="realworks_public",
        confidence=0.86,
        evidence_signals=("realworks", "property_facts_validation"),
        blocking_signals=(),
        recommended_action="facts_extraction_validation",
        can_proceed_to_parser_family=True,
        reason="realworks_property_facts_validation",
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


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
