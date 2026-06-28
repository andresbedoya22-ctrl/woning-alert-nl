from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
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
from domek_wonen.pilots.ogonline_detail_facts_probe import extract_detail_fact_candidates
from domek_wonen.pilots.ogonline_xhr_live_fetch import controlled_http_fetch_json
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .cache import PropertyFactsCache
from .models import (
    FACT_STATUS_REVIEW,
    FACT_STATUS_USABLE,
    PROPERTY_FACT_FIELDS,
    PropertyFactValue,
    PropertyFactsRecord,
    build_property_fact_value,
    build_property_facts_record,
)
from .normalization import (
    normalize_area_m2,
    normalize_boolean_signal,
    normalize_count,
    normalize_cv_ketel_ownership,
    normalize_description_length_bucket,
    normalize_eigendomssituatie,
    normalize_energy_label,
    normalize_heating_system,
    normalize_price,
    normalize_property_type,
    normalize_small_count,
    normalize_vve_monthly_cost,
)


MAX_FACTS_API_PAGES = 25
MAX_FACTS_DETAILS = 300
DEFAULT_FACTS_API_PAGES = 5
DEFAULT_FACTS_DETAILS = 50
MAX_SAMPLE_RECORDS = 5

_SUMMARY_CANDIDATE_FIELDS = frozenset(
    {
        "short_description_summary_candidate",
        "key_selling_points_candidate",
        "attention_points_candidate",
    }
)
_EXTRACTABLE_FIELDS = tuple(field for field in PROPERTY_FACT_FIELDS if field not in _SUMMARY_CANDIDATE_FIELDS)
_FIELD_ALIASES = {
    "short_description_source_available": "short_description_summary_candidate",
    "possible_key_selling_points_source": "key_selling_points_candidate",
    "possible_attention_points_source": "attention_points_candidate",
}
_LISTING_FALLBACK_FIELDS = {
    "asking_price": ("asking_price", "asking_price_eur", "price"),
    "living_area_m2": ("living_area_m2", "living_area"),
    "rooms": ("rooms", "rooms_count"),
    "bedrooms": ("bedrooms", "bedrooms_count"),
    "property_type": ("property_type",),
}
_NORMALIZERS = {
    "asking_price": normalize_price,
    "living_area_m2": normalize_area_m2,
    "plot_area_m2": normalize_area_m2,
    "rooms": normalize_count,
    "bedrooms": lambda value: normalize_small_count(value, minimum=0, maximum=8),
    "bathrooms": lambda value: normalize_small_count(value, minimum=0, maximum=10),
    "floors": lambda value: normalize_small_count(value, minimum=1, maximum=10),
    "volume_m3": normalize_count,
    "energy_label": normalize_energy_label,
    "property_type": normalize_property_type,
    "vve_monthly_cost": normalize_vve_monthly_cost,
    "vve_active": normalize_boolean_signal,
    "heating_type": normalize_heating_system,
    "hot_water": normalize_heating_system,
    "cv_ketel_present": normalize_boolean_signal,
    "cv_ketel_ownership": normalize_cv_ketel_ownership,
    "eigendomssituatie": normalize_eigendomssituatie,
    "description_length_bucket": normalize_description_length_bucket,
    "main_garden_area_m2": normalize_area_m2,
    "garage_count": lambda value: normalize_small_count(value, minimum=0, maximum=10),
}
_UNITS = {
    "asking_price": "EUR",
    "living_area_m2": "m2",
    "plot_area_m2": "m2",
    "volume_m3": "m3",
    "main_garden_area_m2": "m2",
    "vve_monthly_cost": "EUR_month",
}
_SOURCE_CONFIDENCE = {
    "json_ld": 0.90,
    "embedded_state": 0.90,
    "metadata": 0.85,
    "listing_fallback": 0.85,
    "html_text_signal": 0.65,
}
_AMBIGUOUS_FACT_WARNING = "ambiguous_fact_candidate"


@dataclass(frozen=True, slots=True)
class OGonlineFactsExtractionResult:
    record: PropertyFactsRecord
    fields_extracted: tuple[str, ...]
    fields_review: tuple[str, ...]
    fields_missing: tuple[str, ...]
    warning_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OGonlineFactsBatchResult:
    source_id: str
    source_domain: str
    listings_seen: int
    details_requested: int
    cache_hits: int
    cache_misses: int
    detail_fetch_attempted: int
    detail_fetch_succeeded: int
    detail_fetch_failed: int
    records_built: int
    records_written: int
    skipped_stale_or_invalid: int
    field_completion_counts: tuple[tuple[str, int], ...]
    review_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    sample_records: tuple[PropertyFactsRecord, ...]
    warnings: tuple[str, ...] = ()


def extract_ogonline_property_facts_from_html(
    *,
    html: str,
    source_id: str,
    source_domain: str,
    canonical_url: str,
    address_raw: str | None,
    city: str | None,
    status: str | None,
    fetched_at: datetime,
    ttl_days: int = 14,
    listing_fallbacks: Mapping[str, object] | None = None,
) -> OGonlineFactsExtractionResult:
    warnings: list[str] = []
    facts: list[PropertyFactValue] = []
    fallback_fields = _listing_fallback_fields(listing_fallbacks or {})

    for candidate in extract_detail_fact_candidates(html):
        field = _FIELD_ALIASES.get(candidate.field, candidate.field)
        if field in _SUMMARY_CANDIDATE_FIELDS:
            warnings.append("description_not_stored")
            continue
        if field not in _EXTRACTABLE_FIELDS:
            continue
        fact = _fact_from_candidate(
            field=field,
            value=candidate.preview,
            source=candidate.source,
            warning=candidate.warning,
        )
        if fact is not None:
            facts.append(fact)

    existing_usable_fields = {fact.field for fact in facts if fact.status == FACT_STATUS_USABLE}
    for field, value in fallback_fields:
        if field in existing_usable_fields:
            continue
        fact = _fact_from_candidate(field=field, value=value, source="listing_fallback", warning="")
        if fact is not None:
            facts.append(fact)

    fetched = _datetime_to_utc_iso(fetched_at)
    expires_at = _datetime_to_utc_iso(fetched_at + timedelta(days=ttl_days)) if ttl_days > 0 else None
    record = build_property_facts_record(
        source_id=source_id,
        source_domain=source_domain,
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        status=status,
        facts=facts,
        extraction_status="complete" if facts else "partial",
        fetched_at=fetched,
        expires_at=expires_at,
        warnings=warnings,
    )
    fields_extracted = tuple(fact.field for fact in record.facts if fact.status == FACT_STATUS_USABLE)
    fields_review = tuple(fact.field for fact in record.facts if fact.status == FACT_STATUS_REVIEW)
    fields_missing = tuple(field for field in _EXTRACTABLE_FIELDS if field not in {*fields_extracted, *fields_review})
    raw_warnings = (*warnings, *record.warnings, *(warning for fact in record.facts for warning in fact.warnings))
    return OGonlineFactsExtractionResult(
        record=record,
        fields_extracted=fields_extracted,
        fields_review=fields_review,
        fields_missing=fields_missing,
        warning_counts=_counter_pairs(raw_warnings),
        warnings=_dedupe(raw_warnings),
    )


def run_kin_ogonline_normalized_facts_extraction_batch(
    *,
    config_path: Path,
    cache_path: Path | None = None,
    max_api_pages: int = DEFAULT_FACTS_API_PAGES,
    max_details: int = DEFAULT_FACTS_DETAILS,
    max_runtime_seconds: float | None = None,
    force_refresh: bool = False,
    fetch_json: Callable[[str], str] = controlled_http_fetch_json,
    fetch_html: Callable[[str], str] = controlled_http_fetch_html,
    now: datetime | None = None,
) -> OGonlineFactsBatchResult:
    config = load_parser_source_config(config_path)
    return run_kin_ogonline_normalized_facts_extraction_batch_config(
        config,
        cache_path=cache_path,
        max_api_pages=max_api_pages,
        max_details=max_details,
        max_runtime_seconds=max_runtime_seconds,
        force_refresh=force_refresh,
        fetch_json=fetch_json,
        fetch_html=fetch_html,
        now=now,
    )


def run_kin_ogonline_normalized_facts_extraction_batch_config(
    config: ParserSourceConfig,
    *,
    cache_path: Path | None = None,
    max_api_pages: int = DEFAULT_FACTS_API_PAGES,
    max_details: int = DEFAULT_FACTS_DETAILS,
    max_runtime_seconds: float | None = None,
    force_refresh: bool = False,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    now: datetime | None = None,
) -> OGonlineFactsBatchResult:
    _validate_kin_config(config)
    fetched_at = now or datetime.now(UTC)
    started_at = time.monotonic()
    deadline = _deadline(started_at, max_runtime_seconds)
    warnings: list[str] = []
    api_limit = _cap_positive(max_api_pages, MAX_FACTS_API_PAGES, "max_api_pages_capped_at_25", warnings)
    detail_limit = _cap_positive(max_details, MAX_FACTS_DETAILS, "max_details_capped_at_300", warnings)
    cache = PropertyFactsCache(cache_path) if cache_path is not None else None
    if cache is None:
        warnings.append("no_cache_path_no_write")

    listings, listing_warnings = _fetch_clean_listings(
        _config_with_page_limit(config, api_limit),
        fetch_json=fetch_json,
        page_limit=api_limit,
        deadline=deadline,
    )
    warnings.extend(listing_warnings)
    selected = _select_fact_listings(listings, max_details=detail_limit)

    records: list[PropertyFactsRecord] = []
    records_to_write: list[PropertyFactsRecord] = []
    records_written = 0
    cache_hits = 0
    cache_misses = 0
    details_requested = 0
    detail_fetch_attempted = 0
    detail_fetch_succeeded = 0
    detail_fetch_failed = 0
    skipped_stale_or_invalid = 0

    for listing in selected:
        if _deadline_exhausted(deadline):
            warnings.append("facts_batch_runtime_budget_exhausted")
            break
        details_requested += 1
        cached = cache.get(listing.canonical_url, listing.source_domain) if cache is not None else None
        if cached is not None and not force_refresh:
            if cache and cache.is_stale(cached, fetched_at):
                cache_misses += 1
                skipped_stale_or_invalid += 1
                warnings.append("cache_stale")
            else:
                cache_hits += 1
                warnings.append("cache_hit")
                records.append(cached)
                continue
        else:
            cache_misses += 1
            warnings.append("cache_miss")

        can_fetch, robot_warnings = _robots_check_url(listing.canonical_url)
        if not can_fetch:
            detail_fetch_failed += 1
            warnings.extend((*robot_warnings, "blocked_by_robots"))
            continue

        detail_fetch_attempted += 1
        try:
            html = fetch_html(listing.canonical_url)
        except Exception:
            detail_fetch_failed += 1
            warnings.append("detail_fetch_exception")
            continue

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
        records.append(extraction.record)
        warnings.extend(extraction.warnings)
        if cache is not None:
            records_to_write.append(extraction.record)
            records_written += 1

    if cache is not None and records_to_write:
        cache.upsert_many(records_to_write)

    raw_warnings = tuple(warnings)
    return OGonlineFactsBatchResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        listings_seen=len(listings),
        details_requested=details_requested,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        detail_fetch_attempted=detail_fetch_attempted,
        detail_fetch_succeeded=detail_fetch_succeeded,
        detail_fetch_failed=detail_fetch_failed,
        records_built=len(records),
        records_written=records_written,
        skipped_stale_or_invalid=skipped_stale_or_invalid,
        field_completion_counts=_counter_pairs(
            fact.field for record in records for fact in record.facts if fact.status == FACT_STATUS_USABLE
        ),
        review_counts=_counter_pairs(
            fact.field for record in records for fact in record.facts if fact.status == FACT_STATUS_REVIEW
        ),
        warning_counts=_counter_pairs(raw_warnings),
        sample_records=tuple(records[:MAX_SAMPLE_RECORDS]),
        warnings=_dedupe(raw_warnings),
    )


def _fact_from_candidate(
    *,
    field: str,
    value: object,
    source: str,
    warning: str,
) -> PropertyFactValue | None:
    normalized = _normalize(field, value)
    confidence = _SOURCE_CONFIDENCE.get(source, 0.40)
    warning_forces_review = bool(warning and warning != _AMBIGUOUS_FACT_WARNING)
    status = FACT_STATUS_USABLE if normalized is not None and confidence >= 0.65 and not warning_forces_review else FACT_STATUS_REVIEW
    fact_warnings = (warning,) if warning and warning != _AMBIGUOUS_FACT_WARNING else ()
    raw_count = normalize_count(value) if field in {"rooms", "bedrooms", "bathrooms", "floors", "garage_count"} else None
    if normalized is None and raw_count is not None and _is_implausible_count(field, raw_count):
        normalized = raw_count
        status = FACT_STATUS_REVIEW
        fact_warnings = _dedupe((*fact_warnings, "implausible_count"))
    if normalized is None:
        if field in {
            "erfpacht_details",
            "insulation",
            "outdoor_space",
            "garden",
            "balcony",
            "storage",
            "garage",
            "parking",
            "availability_date",
            "open_huis_badge_or_event",
            "cv_ketel_brand",
        }:
            normalized = str(value)
        elif field in {"heating_type", "hot_water"} and _is_rawish_value(value):
            normalized = None
            status = FACT_STATUS_REVIEW
            fact_warnings = _dedupe((*fact_warnings, "rawish_value_suppressed", "normalization_failed"))
        else:
            status = FACT_STATUS_REVIEW
            fact_warnings = _dedupe((*fact_warnings, "normalization_failed"))
    if _is_implausible_count(field, normalized):
        if source == "html_text_signal":
            return None
        status = FACT_STATUS_REVIEW
        fact_warnings = _dedupe((*fact_warnings, "implausible_count"))
    if _is_implausible_area(field, normalized):
        if source == "html_text_signal":
            return None
        status = FACT_STATUS_REVIEW
        fact_warnings = _dedupe((*fact_warnings, "implausible_area"))
    if warning == _AMBIGUOUS_FACT_WARNING and status == FACT_STATUS_REVIEW:
        fact_warnings = _dedupe((*fact_warnings, warning))
    return build_property_fact_value(
        field=field,
        value=value if isinstance(value, (str, int, float, bool)) else str(value),
        normalized_value=normalized,
        unit=_UNITS.get(field),
        source=source,
        confidence=confidence,
        status=status,
        evidence_preview=str(value),
        warnings=fact_warnings,
    )


def _normalize(field: str, value: object) -> str | int | float | bool | None:
    normalizer = _NORMALIZERS.get(field)
    if normalizer is None:
        return value if isinstance(value, (str, int, float, bool)) else None
    return normalizer(value)


def _is_implausible_count(field: str, value: object) -> bool:
    if not isinstance(value, int):
        return False
    if field == "bedrooms":
        return value < 0 or value > 8
    if field == "bathrooms":
        return value < 0 or value > 10
    if field == "rooms":
        return value < 1 or value > 30
    if field == "floors":
        return value < 1 or value > 10
    if field == "garage_count":
        return value < 0 or value > 10
    return False


def _is_implausible_area(field: str, value: object) -> bool:
    if not isinstance(value, int):
        return False
    if field == "living_area_m2":
        return value < 10 or value > 1000
    if field == "plot_area_m2":
        return value < 0 or value > 100000
    if field == "main_garden_area_m2":
        return value < 0 or value > 10000
    if field == "volume_m3":
        return value < 10 or value > 10000
    return False


def _is_rawish_value(value: object) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in ('{"', "{'", '":', "\\\"", "[{", "}]"))


def _listing_fallback_fields(fallbacks: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    values: list[tuple[str, object]] = []
    for field, keys in _LISTING_FALLBACK_FIELDS.items():
        for key in keys:
            value = fallbacks.get(key)
            if value not in (None, ""):
                values.append((field, value))
                break
    return tuple(values)


def _fallbacks_from_listing(listing: ParsedListing) -> Mapping[str, object]:
    return {
        "asking_price_eur": listing.asking_price_eur,
        "living_area_m2": listing.living_area_m2,
        "rooms_count": listing.rooms_count,
        "bedrooms_count": listing.bedrooms_count,
        "property_type": listing.property_type,
    }


def _fetch_clean_listings(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    page_limit: int,
    deadline: float | None,
) -> tuple[tuple[ParsedListing, ...], tuple[str, ...]]:
    listings: list[ParsedListing] = []
    warnings: list[str] = []
    api = config.api
    if api is None:
        return (), ("missing_paginated_api_config",)
    for page in range(api.start_page, api.start_page + page_limit):
        if _deadline_exhausted(deadline):
            warnings.append("facts_batch_runtime_budget_exhausted")
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
        listings.extend(qa_listing.listing for qa_listing in qa_result.clean_listings)
        warnings.extend((*parser_result.warnings, *qa_result.warnings))
    return tuple(listings), _dedupe(warnings)


def _select_fact_listings(listings: Iterable[ParsedListing], *, max_details: int) -> tuple[ParsedListing, ...]:
    if max_details <= 0:
        return ()
    eligible = tuple(listing for listing in listings if listing.canonical_url)
    selected: list[ParsedListing] = []
    _extend_selected(selected, eligible, max_details=max_details, predicate=lambda item: item.status == "beschikbaar")
    _extend_selected(selected, eligible, max_details=max_details, predicate=lambda item: item.property_type == "appartement")
    _extend_selected(
        selected,
        sorted(eligible, key=lambda item: (item.city or "", item.asking_price_eur or 0, item.canonical_url)),
        max_details=max_details,
        predicate=lambda item: True,
    )
    return tuple(selected[:max_details])


def _extend_selected(
    selected: list[ParsedListing],
    listings: Iterable[ParsedListing],
    *,
    max_details: int,
    predicate: Callable[[ParsedListing], bool],
) -> None:
    seen = {listing.canonical_url for listing in selected}
    for listing in listings:
        if len(selected) >= max_details:
            return
        if listing.canonical_url in seen or not predicate(listing):
            continue
        selected.append(listing)
        seen.add(listing.canonical_url)


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
    required_max_page = api.start_page + pages - 1
    return replace(config, api=replace(api, max_pages=max(api.max_pages, required_max_page)))


def _fingerprint_for_config(config: ParserSourceConfig) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        access_status="allowed",
        delivery_mode=config.delivery_mode,
        parser_family_candidate=config.parser_family,
        confidence=0.84,
        evidence_signals=("ogonline", "normalized_facts_extractor"),
        blocking_signals=(),
        recommended_action="facts_extraction",
        can_proceed_to_parser_family=True,
        reason="ogonline_normalized_facts_extractor",
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


def _datetime_to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
