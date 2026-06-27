from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.parsers import ParserFamilyRunner
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.parsers.source_config import (
    ParserSourceConfig,
    build_paginated_api_url,
    build_parser_input_from_api_json,
    load_parser_source_config,
)
from domek_wonen.pilots.live_fetch import controlled_http_fetch_html
from domek_wonen.pilots.ogonline_xhr_live_fetch import controlled_http_fetch_json
from domek_wonen.qa import ParserFamilyQAResult, qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

if TYPE_CHECKING:
    from domek_wonen.facts.models import PropertyFactsRecord
    from domek_wonen.facts.summary import ClientReadyPropertySummary


MAX_KIN_READINESS_API_PAGES = 25
MAX_KIN_READINESS_DETAILS = 300
MAX_SAMPLE_ROWS = 5
_KEY_FIELDS = (
    "asking_price",
    "property_type",
    "living_area_m2",
    "bedrooms",
    "energy_label",
    "eigendomssituatie",
)
_FIELD_COMPLETION_FIELDS = (
    "asking_price",
    "property_type",
    "living_area_m2",
    "plot_area_m2",
    "rooms",
    "bedrooms",
    "bathrooms",
    "energy_label",
    "eigendomssituatie",
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
)


@dataclass(frozen=True, slots=True)
class PropertyLocationReadiness:
    address_raw: str | None
    postcode: str | None
    city: str | None
    gemeente: str | None
    province: str | None
    latitude: float | None
    longitude: float | None
    location_status: str
    location_source: str
    location_confidence: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KINPropertyReadinessRow:
    source_id: str
    source_domain: str
    canonical_url: str
    listing_status: str | None
    address_raw: str | None
    postcode: str | None
    city: str | None
    gemeente: str | None
    province: str | None
    latitude: float | None
    longitude: float | None
    location_status: str
    facts_record: PropertyFactsRecord
    summary: ClientReadyPropertySummary
    export_readiness: str
    quality_status: str
    missing_key_fields: tuple[str, ...]
    attention_points: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KINFullPropertyReadinessResult:
    source_id: str
    source_domain: str
    listings_seen: int
    qa_clean_count: int
    rows_built: int
    summaries_built: int
    active_count: int
    inactive_count: int
    review_count: int
    cache_hits: int
    cache_misses: int
    detail_fetch_attempted: int
    detail_fetch_succeeded: int
    detail_fetch_failed: int
    records_written: int
    location_usable_count: int
    location_review_count: int
    location_missing_count: int
    export_ready_count: int
    export_review_count: int
    export_blocked_count: int
    field_completion_counts: tuple[tuple[str, int], ...]
    missing_key_field_counts: tuple[tuple[str, int], ...]
    attention_point_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    sample_rows: tuple[KINPropertyReadinessRow, ...]
    rows: tuple[KINPropertyReadinessRow, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ListingFetchResult:
    listings_seen: int
    qa_result: ParserFamilyQAResult
    warnings: tuple[str, ...] = ()


def build_location_readiness_from_listing(listing: ParsedListing) -> PropertyLocationReadiness:
    address_raw = _optional_text(listing.address_raw)
    postcode = _normalize_postcode(listing.postcode)
    city = _optional_text(listing.city)
    latitude = _optional_float(getattr(listing, "latitude", None))
    longitude = _optional_float(getattr(listing, "longitude", None))
    warnings: list[str] = []

    if address_raw and postcode and city:
        status = "usable"
        confidence = 0.85
    elif address_raw and city:
        status = "review"
        confidence = 0.65
        warnings.append("missing_postcode")
    elif city:
        status = "review"
        confidence = 0.45
        warnings.append("partial_location")
    else:
        status = "missing"
        confidence = 0.0
        warnings.append("missing_location")

    if latitude is not None and longitude is not None:
        confidence = min(1.0, round(confidence + 0.10, 2))
    else:
        warnings.append("missing_coordinates")

    return PropertyLocationReadiness(
        address_raw=address_raw,
        postcode=postcode,
        city=city,
        gemeente=None,
        province=None,
        latitude=latitude,
        longitude=longitude,
        location_status=status,
        location_source="parsed_listing",
        location_confidence=confidence,
        warnings=_dedupe(warnings),
    )


def classify_export_readiness(row: KINPropertyReadinessRow) -> str:
    if not row.canonical_url or row.location_status == "missing":
        return "export_blocked"
    if row.facts_record is None or row.summary is None:
        return "export_blocked"
    if "canonical_url" in row.missing_key_fields or "city" in row.missing_key_fields:
        return "export_blocked"
    if "asking_price" in row.missing_key_fields:
        return "export_blocked"
    if row.missing_key_fields or row.attention_points:
        return "export_review"
    return "export_ready"


def run_kin_full_property_readiness(
    *,
    config_path: Path,
    cache_path: Path | None = None,
    max_api_pages: int = MAX_KIN_READINESS_API_PAGES,
    max_details: int = MAX_KIN_READINESS_DETAILS,
    max_runtime_seconds: float | None = None,
    force_refresh: bool = False,
) -> KINFullPropertyReadinessResult:
    config = load_parser_source_config(config_path)
    return run_kin_full_property_readiness_config(
        config,
        cache_path=cache_path,
        max_api_pages=max_api_pages,
        max_details=max_details,
        max_runtime_seconds=max_runtime_seconds,
        force_refresh=force_refresh,
        fetch_json=controlled_http_fetch_json,
        fetch_html=controlled_http_fetch_html,
    )


def run_kin_full_property_readiness_config(
    config: ParserSourceConfig,
    *,
    cache_path: Path | None = None,
    max_api_pages: int = MAX_KIN_READINESS_API_PAGES,
    max_details: int = MAX_KIN_READINESS_DETAILS,
    max_runtime_seconds: float | None = None,
    force_refresh: bool = False,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    now: datetime | None = None,
) -> KINFullPropertyReadinessResult:
    _validate_kin_config(config)
    fetched_at = now or datetime.now(UTC)
    started_at = time.monotonic()
    deadline = _deadline(started_at, max_runtime_seconds)
    warnings: list[str] = []
    api_limit = _cap_positive(max_api_pages, MAX_KIN_READINESS_API_PAGES, "max_api_pages_capped_at_25", warnings)
    detail_limit = _cap_positive(max_details, MAX_KIN_READINESS_DETAILS, "max_details_capped_at_300", warnings)
    from domek_wonen.facts.cache import PropertyFactsCache
    from domek_wonen.facts.ogonline_extractor import extract_ogonline_property_facts_from_html

    cache = PropertyFactsCache(cache_path) if cache_path is not None else None
    if cache is None:
        warnings.append("no_cache_path_no_write")

    fetch_result = _fetch_qa_clean_listings(
        _config_with_page_limit(config, api_limit),
        fetch_json=fetch_json,
        page_limit=api_limit,
        deadline=deadline,
    )
    warnings.extend(fetch_result.warnings)
    if _deadline_exhausted(deadline):
        warnings.append("kin_readiness_runtime_budget_exhausted")

    clean_listings = tuple(qa_listing.listing for qa_listing in fetch_result.qa_result.clean_listings)
    selected = _select_listings(clean_listings, max_details=detail_limit)
    status_counts = _status_bucket_counts(clean_listings)

    rows: list[KINPropertyReadinessRow] = []
    records_to_write: list[PropertyFactsRecord] = []
    cache_hits = 0
    cache_misses = 0
    detail_fetch_attempted = 0
    detail_fetch_succeeded = 0
    detail_fetch_failed = 0

    for listing in selected:
        if _deadline_exhausted(deadline):
            warnings.append("kin_readiness_runtime_budget_exhausted")
            break
        location = build_location_readiness_from_listing(listing)
        record: PropertyFactsRecord | None = None
        cached = cache.get(listing.canonical_url, listing.source_domain) if cache is not None else None
        if cached is not None and not force_refresh and not cache.is_stale(cached, fetched_at):
            cache_hits += 1
            warnings.append("cache_hit")
            record = cached
        else:
            cache_misses += 1
            if cached is not None and cache is not None and cache.is_stale(cached, fetched_at):
                warnings.append("cache_stale")
            elif cache is None:
                warnings.append("cache_disabled")
            else:
                warnings.append("cache_miss")

            can_fetch, robot_warnings = _robots_check_url(listing.canonical_url)
            if not can_fetch:
                detail_fetch_failed += 1
                warnings.extend((*robot_warnings, "blocked_by_robots"))
            else:
                detail_fetch_attempted += 1
                try:
                    html = fetch_html(listing.canonical_url)
                except Exception:
                    detail_fetch_failed += 1
                    warnings.append("detail_fetch_exception")
                else:
                    detail_fetch_succeeded += 1
                    extraction = extract_ogonline_property_facts_from_html(
                        html=html,
                        source_id=listing.source_id,
                        source_domain=listing.source_domain,
                        canonical_url=listing.canonical_url,
                        address_raw=listing.address_raw or None,
                        city=listing.city or None,
                        status=listing.status or None,
                        fetched_at=fetched_at,
                        listing_fallbacks=_fallbacks_from_listing(listing),
                    )
                    record = _sanitize_record_for_readiness(extraction.record)
                    warnings.extend(extraction.warnings)
                    if cache is not None:
                        records_to_write.append(record)

        if record is None:
            continue
        row = build_kin_property_readiness_row(listing, record, location)
        rows.append(row)
        warnings.extend(row.warnings)

    if cache is not None and records_to_write:
        cache.upsert_many(records_to_write)

    return _result_from_rows(
        config=config,
        listings_seen=fetch_result.listings_seen,
        qa_clean_count=len(clean_listings),
        rows=tuple(rows),
        active_count=status_counts["active"],
        inactive_count=status_counts["inactive"],
        review_count=status_counts["review"],
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        detail_fetch_attempted=detail_fetch_attempted,
        detail_fetch_succeeded=detail_fetch_succeeded,
        detail_fetch_failed=detail_fetch_failed,
        records_written=len(records_to_write),
        warnings=_dedupe(warnings),
    )


def build_kin_property_readiness_row(
    listing: ParsedListing,
    facts_record: PropertyFactsRecord,
    location: PropertyLocationReadiness | None = None,
) -> KINPropertyReadinessRow:
    from domek_wonen.facts.summary import build_client_ready_property_summary

    location = location or build_location_readiness_from_listing(listing)
    summary = build_client_ready_property_summary(facts_record)
    missing_key_fields = _missing_key_fields(listing, summary, location)
    attention_points = summary.attention_points
    row_warnings = _dedupe((*location.warnings, *facts_record.warnings, *summary.warnings))
    row = KINPropertyReadinessRow(
        source_id=listing.source_id,
        source_domain=listing.source_domain,
        canonical_url=listing.canonical_url,
        listing_status=listing.status or None,
        address_raw=location.address_raw,
        postcode=location.postcode,
        city=location.city,
        gemeente=location.gemeente,
        province=location.province,
        latitude=location.latitude,
        longitude=location.longitude,
        location_status=location.location_status,
        facts_record=facts_record,
        summary=summary,
        export_readiness="export_blocked",
        quality_status="insufficient_facts",
        missing_key_fields=missing_key_fields,
        attention_points=attention_points,
        warnings=row_warnings,
    )
    export_readiness = classify_export_readiness(row)
    return replace(row, export_readiness=export_readiness, quality_status=_quality_status(row, export_readiness))


def _sanitize_record_for_readiness(record: PropertyFactsRecord) -> PropertyFactsRecord:
    from domek_wonen.facts.models import PropertyFactValue, PropertyFactsRecord

    return PropertyFactsRecord(
        schema_version=record.schema_version,
        source_id=record.source_id,
        source_domain=record.source_domain,
        canonical_url=record.canonical_url,
        address_raw=_safe_fact_text(record.address_raw),
        city=_safe_fact_text(record.city),
        status=record.status,
        facts=tuple(
            PropertyFactValue(
                field=fact.field,
                value=_safe_fact_value(fact.value),
                normalized_value=_safe_fact_value(fact.normalized_value),
                unit=fact.unit,
                source=fact.source,
                confidence=fact.confidence,
                status=fact.status,
                evidence_preview=_safe_fact_text(fact.evidence_preview) or "",
                warnings=fact.warnings,
            )
            for fact in record.facts
        ),
        extraction_status=record.extraction_status,
        fetched_at=record.fetched_at,
        expires_at=record.expires_at,
        warnings=record.warnings,
    )


def _fetch_qa_clean_listings(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    page_limit: int,
    deadline: float | None,
) -> _ListingFetchResult:
    warnings: list[str] = []
    qa_results: list[ParserFamilyQAResult] = []
    listings_seen = 0
    api = config.api
    if api is None:
        return _ListingFetchResult(0, _empty_qa_result(config), ("missing_paginated_api_config",))
    for page in range(api.start_page, api.start_page + page_limit):
        if _deadline_exhausted(deadline):
            warnings.append("kin_readiness_runtime_budget_exhausted")
            break
        try:
            api_url = build_paginated_api_url(config, page)
        except Exception:
            warnings.append("api_url_build_failed")
            continue
        can_fetch, robot_warnings = _robots_check_url(api_url)
        if not can_fetch:
            warnings.extend((*robot_warnings, "api_blocked_by_robots"))
            continue
        try:
            json_content = fetch_json(api_url)
            parser_input = build_parser_input_from_api_json(config, json_content, page=page)
            parser_result = ParserFamilyRunner().run(_fingerprint_for_config(config), parser_input)
            qa_result = qa_parser_family_result(parser_result)
        except Exception:
            warnings.append("api_fetch_or_parse_exception")
            continue
        listings_seen += len(parser_result.listings)
        qa_results.append(qa_result)
        warnings.extend((*parser_result.warnings, *qa_result.warnings))
    return _ListingFetchResult(
        listings_seen=listings_seen,
        qa_result=_combine_qa_results(config, qa_results),
        warnings=_dedupe(warnings),
    )


def _combine_qa_results(config: ParserSourceConfig, qa_results: Iterable[ParserFamilyQAResult]) -> ParserFamilyQAResult:
    clean = []
    review = []
    rejected = []
    warnings = []
    for qa_result in qa_results:
        clean.extend(qa_result.clean_listings)
        review.extend(qa_result.review_listings)
        rejected.extend(qa_result.rejected_listings)
        warnings.extend(qa_result.warnings)
    return ParserFamilyQAResult(
        parser_family=config.parser_family,
        source_id=config.source_id,
        source_domain=config.source_domain,
        clean_listings=tuple(clean),
        review_listings=tuple(review),
        rejected_listings=tuple(rejected),
        total_count=len(clean) + len(review) + len(rejected),
        clean_count=len(clean),
        review_count=len(review),
        rejected_count=len(rejected),
        warnings=_dedupe(warnings),
    )


def _empty_qa_result(config: ParserSourceConfig) -> ParserFamilyQAResult:
    return ParserFamilyQAResult(
        parser_family=config.parser_family,
        source_id=config.source_id,
        source_domain=config.source_domain,
        clean_listings=(),
        review_listings=(),
        rejected_listings=(),
        total_count=0,
        clean_count=0,
        review_count=0,
        rejected_count=0,
        warnings=(),
    )


def _result_from_rows(
    *,
    config: ParserSourceConfig,
    listings_seen: int,
    qa_clean_count: int,
    rows: tuple[KINPropertyReadinessRow, ...],
    active_count: int,
    inactive_count: int,
    review_count: int,
    cache_hits: int,
    cache_misses: int,
    detail_fetch_attempted: int,
    detail_fetch_succeeded: int,
    detail_fetch_failed: int,
    records_written: int,
    warnings: tuple[str, ...],
) -> KINFullPropertyReadinessResult:
    row_warnings = tuple(warning for row in rows for warning in row.warnings)
    all_warnings = _dedupe((*warnings, *row_warnings))
    return KINFullPropertyReadinessResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        listings_seen=listings_seen,
        qa_clean_count=qa_clean_count,
        rows_built=len(rows),
        summaries_built=sum(1 for row in rows if row.summary is not None),
        active_count=active_count,
        inactive_count=inactive_count,
        review_count=review_count,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        detail_fetch_attempted=detail_fetch_attempted,
        detail_fetch_succeeded=detail_fetch_succeeded,
        detail_fetch_failed=detail_fetch_failed,
        records_written=records_written,
        location_usable_count=sum(1 for row in rows if row.location_status == "usable"),
        location_review_count=sum(1 for row in rows if row.location_status == "review"),
        location_missing_count=sum(1 for row in rows if row.location_status == "missing"),
        export_ready_count=sum(1 for row in rows if row.export_readiness == "export_ready"),
        export_review_count=sum(1 for row in rows if row.export_readiness == "export_review"),
        export_blocked_count=sum(1 for row in rows if row.export_readiness == "export_blocked"),
        field_completion_counts=_field_completion_counts(rows),
        missing_key_field_counts=_counter_pairs(field for row in rows for field in row.missing_key_fields),
        attention_point_counts=_counter_pairs(point for row in rows for point in row.attention_points),
        warning_counts=_counter_pairs(all_warnings),
        sample_rows=tuple(rows[:MAX_SAMPLE_ROWS]),
        rows=rows,
        warnings=all_warnings,
    )


def _field_completion_counts(rows: Iterable[KINPropertyReadinessRow]) -> tuple[tuple[str, int], ...]:
    counts: Counter[str] = Counter()
    for row in rows:
        usable = {fact.field for fact in row.facts_record.facts if fact.status == "usable"}
        for field in _FIELD_COMPLETION_FIELDS:
            if field in usable:
                counts[field] += 1
    return tuple(sorted(counts.items()))


def _missing_key_fields(
    listing: ParsedListing,
    summary: ClientReadyPropertySummary,
    location: PropertyLocationReadiness,
) -> tuple[str, ...]:
    missing = list(summary.missing_key_fields)
    if not listing.canonical_url:
        missing.append("canonical_url")
    if not (listing.source_domain or "").strip():
        missing.append("source_domain")
    if not location.city:
        missing.append("city")
    return _dedupe(missing)


def _quality_status(row: KINPropertyReadinessRow, export_readiness: str) -> str:
    if row.location_status == "missing":
        return "insufficient_location"
    if export_readiness == "export_blocked":
        return "insufficient_facts"
    critical_attention = any("conflicterende" in point.casefold() for point in row.attention_points)
    if export_readiness == "export_ready" and not critical_attention:
        return "client_ready"
    return "advisor_review"


def _select_listings(listings: Iterable[ParsedListing], *, max_details: int) -> tuple[ParsedListing, ...]:
    if max_details <= 0:
        return ()
    return tuple(listing for listing in listings if listing.canonical_url)[:max_details]


def _status_bucket_counts(listings: Iterable[ParsedListing]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for listing in listings:
        status = (listing.status or "").strip()
        if status == "beschikbaar":
            counts["active"] += 1
        elif status in {"onder_bod", "verkocht", "verhuurd"}:
            counts["inactive"] += 1
        else:
            counts["review"] += 1
    return counts


def _fallbacks_from_listing(listing: ParsedListing) -> Mapping[str, object]:
    return {
        "asking_price_eur": listing.asking_price_eur,
        "living_area_m2": listing.living_area_m2,
        "rooms_count": listing.rooms_count,
        "bedrooms_count": listing.bedrooms_count,
        "property_type": listing.property_type,
    }


def _validate_kin_config(config: ParserSourceConfig) -> None:
    if config.parser_family != "ogonline_xhr":
        raise ValueError("unsupported_parser_family")
    if config.delivery_mode != "ogonline_xhr":
        raise ValueError("unsupported_delivery_mode")
    if config.api is None:
        raise ValueError("missing_paginated_api_config")
    if config.source_domain != "kinmakelaars.nl" or not config.source_id.startswith("kinmakelaars.nl__"):
        raise ValueError("unsupported_kin_source")


def _config_with_page_limit(config: ParserSourceConfig, pages: int) -> ParserSourceConfig:
    api = config.api
    if api is None:
        raise ValueError("missing_paginated_api_config")
    required_max_page = api.start_page + max(pages, 1) - 1
    return replace(config, api=replace(api, max_pages=max(api.max_pages, required_max_page)))


def _fingerprint_for_config(config: ParserSourceConfig) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        access_status="allowed",
        delivery_mode=config.delivery_mode,
        parser_family_candidate=config.parser_family,
        confidence=0.84,
        evidence_signals=("ogonline", "kin_full_property_readiness"),
        blocking_signals=(),
        recommended_action="kin_full_property_readiness",
        can_proceed_to_parser_family=True,
        reason="kin_full_property_readiness",
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


def _cap_positive(value: int, cap: int, warning: str, warnings: list[str]) -> int:
    if value <= 0:
        return 0
    if value > cap:
        warnings.append(warning)
        return cap
    return value


def _deadline(started_at: float, budget_seconds: float | None) -> float | None:
    if budget_seconds is None:
        return None
    if budget_seconds <= 0:
        return started_at
    return started_at + budget_seconds


def _deadline_exhausted(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


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


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_postcode(value: object) -> str | None:
    text = str(value or "").replace(" ", "").upper().strip()
    if len(text) == 6 and text[:4].isdigit() and text[4:].isalpha():
        return f"{text[:4]} {text[4:]}"
    return text or None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_fact_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_fact_text(value)
    return value


def _safe_fact_text(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    if any(marker in lowered for marker in ("<html", "<script", "</", '{"', "{'", '"docs"', "window.__")):
        return None
    return text
