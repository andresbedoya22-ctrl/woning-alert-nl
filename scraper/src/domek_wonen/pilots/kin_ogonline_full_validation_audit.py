from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from domek_wonen.inventory import (
    build_active_inventory_qa_result,
    build_inventory_snapshot_from_qa,
    evaluate_inventory_eligibility,
)
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.parsers.source_config import (
    ParserSourceConfig,
    build_paginated_api_url,
    build_parser_input_from_api_json,
    load_parser_source_config,
)
from domek_wonen.qa import ParserFamilyQAResult

from .kin_ogonline_active_inventory_pilot import (
    _capture_status,
    _combine_qa_results,
    _dedupe_warnings,
    _fingerprint_for_config,
    _qa_result_with_enriched_clean_listings,
    _robots_check_api_url,
    _utc_timestamp,
    _validate_ogonline_config,
)
from .live_fetch import controlled_http_fetch_html
from .ogonline_detail_property_type_enrichment import (
    DetailPropertyTypeEnrichmentResult,
    _eligible_listing_indexes,
    _enrich_listing,
)
from .ogonline_xhr_live_fetch import controlled_http_fetch_json


MAX_FULL_KIN_API_PAGES = 25
MAX_FULL_KIN_DETAIL_ENRICHMENT = 300


@dataclass(frozen=True, slots=True)
class KINOGonlineFullValidationAuditResult:
    source_id: str
    source_domain: str
    total_pages_reported: int | None
    total_docs_reported: int | None
    pages_requested: int
    pages_attempted: int
    pages_succeeded: int
    pages_failed: int
    parser_listing_count: int
    qa_clean_count: int
    qa_review_count: int
    qa_rejected_count: int
    detail_enrichment_attempted_count: int
    detail_enrichment_succeeded_count: int
    detail_enrichment_failed_count: int
    detail_enriched_count: int
    active_inventory_count: int
    inactive_status_count: int
    unsupported_transaction_type_count: int
    unsupported_property_type_count: int
    eligibility_review_count: int
    snapshot_listing_count: int
    parser_status_counts: tuple[tuple[str, int], ...]
    eligibility_decision_counts: tuple[tuple[str, int], ...]
    property_type_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    page_result_counts: tuple[tuple[int, int, int, int], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _FullPageResult:
    page: int
    succeeded: bool
    parser_listing_count: int = 0
    qa_result: ParserFamilyQAResult | None = None
    total_pages_reported: int | None = None
    total_docs_reported: int | None = None
    has_next_page: bool | None = None
    warnings: tuple[str, ...] = ()


def run_kin_ogonline_full_validation_audit(
    *,
    config_path: Path,
    max_api_pages: int = MAX_FULL_KIN_API_PAGES,
    max_detail_enrichment: int = MAX_FULL_KIN_DETAIL_ENRICHMENT,
    max_runtime_seconds: float | None = None,
    max_detail_runtime_seconds: float | None = None,
) -> KINOGonlineFullValidationAuditResult:
    config = load_parser_source_config(config_path)
    return run_kin_ogonline_full_validation_audit_config(
        config,
        fetch_json=controlled_http_fetch_json,
        fetch_html=controlled_http_fetch_html,
        max_api_pages=max_api_pages,
        max_detail_enrichment=max_detail_enrichment,
        max_runtime_seconds=max_runtime_seconds,
        max_detail_runtime_seconds=max_detail_runtime_seconds,
    )


def run_kin_ogonline_full_validation_audit_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    max_api_pages: int = MAX_FULL_KIN_API_PAGES,
    max_detail_enrichment: int = MAX_FULL_KIN_DETAIL_ENRICHMENT,
    max_runtime_seconds: float | None = None,
    max_detail_runtime_seconds: float | None = None,
) -> KINOGonlineFullValidationAuditResult:
    _validate_full_kin_config(config)
    if max_api_pages <= 0:
        return _empty_result(config, pages_requested=0, warnings=("max_api_pages_must_be_positive",))

    started_at = time.monotonic()
    runtime_deadline = _deadline(started_at, max_runtime_seconds)
    api_page_limit = min(max_api_pages, MAX_FULL_KIN_API_PAGES)
    warnings = [] if max_api_pages <= MAX_FULL_KIN_API_PAGES else ["full_audit_api_pages_capped"]
    audit_config = _config_with_full_page_limit(config, api_page_limit)

    page_results = _run_full_pages(
        audit_config,
        fetch_json=fetch_json,
        page_limit=api_page_limit,
        runtime_deadline=runtime_deadline,
    )
    if _deadline_exhausted(runtime_deadline):
        _append_warning(warnings, "full_audit_runtime_budget_exhausted")
    total_pages_reported = _first_int(result.total_pages_reported for result in page_results)
    total_docs_reported = _first_int(result.total_docs_reported for result in page_results)
    if total_pages_reported is not None and total_pages_reported > api_page_limit:
        warnings.append("full_audit_api_pages_capped")

    qa_result = _combine_qa_results(
        audit_config,
        (qa_result for qa_result in (result.qa_result for result in page_results) if qa_result is not None),
    )
    parser_status_counts = _parser_status_counts(qa_result)

    detail_limit, detail_limit_warnings = _detail_enrichment_limit(qa_result.clean_count, max_detail_enrichment)
    _extend_warnings(warnings, detail_limit_warnings)
    detail_deadline = _deadline(time.monotonic(), max_detail_runtime_seconds)
    enrichment_result, enrichment_runtime_warnings = _enrich_listings_with_runtime_budget(
        (qa_listing.listing for qa_listing in qa_result.clean_listings),
        fetch_html=fetch_html,
        max_details=detail_limit,
        detail_deadline=detail_deadline,
        runtime_deadline=runtime_deadline,
    )
    _extend_warnings(warnings, enrichment_runtime_warnings)
    qa_result = _qa_result_with_enriched_clean_listings(qa_result, enrichment_result.enriched_listings)

    eligibility_result = evaluate_inventory_eligibility(qa_result)
    active_qa_result = build_active_inventory_qa_result(qa_result)
    capture_status = _capture_status(_page_results_for_capture(page_results))
    snapshot = build_inventory_snapshot_from_qa(
        active_qa_result,
        _utc_timestamp(),
        capture_status=capture_status,
        safe_to_compare_removals=capture_status == "success",
    )
    if len(snapshot.listings) != eligibility_result.active_count:
        _append_warning(warnings, "snapshot_active_inventory_count_mismatch")

    raw_warnings = (
        *warnings,
        *qa_result.warnings,
        *_enrichment_warning_events(enrichment_result),
        *snapshot.warnings,
        *(warning for result in page_results for warning in result.warnings),
    )

    return KINOGonlineFullValidationAuditResult(
        source_id=audit_config.source_id,
        source_domain=audit_config.source_domain,
        total_pages_reported=total_pages_reported,
        total_docs_reported=total_docs_reported,
        pages_requested=_pages_requested(total_pages_reported, page_results, api_page_limit),
        pages_attempted=len(page_results),
        pages_succeeded=sum(1 for result in page_results if result.succeeded),
        pages_failed=sum(1 for result in page_results if not result.succeeded),
        parser_listing_count=sum(result.parser_listing_count for result in page_results),
        qa_clean_count=qa_result.clean_count,
        qa_review_count=qa_result.review_count,
        qa_rejected_count=qa_result.rejected_count,
        detail_enrichment_attempted_count=enrichment_result.attempted_count,
        detail_enrichment_succeeded_count=enrichment_result.succeeded_count,
        detail_enrichment_failed_count=enrichment_result.attempted_count - enrichment_result.succeeded_count,
        detail_enriched_count=enrichment_result.enriched_count,
        active_inventory_count=eligibility_result.active_count,
        inactive_status_count=eligibility_result.inactive_status_count,
        unsupported_transaction_type_count=eligibility_result.unsupported_transaction_type_count,
        unsupported_property_type_count=eligibility_result.unsupported_property_type_count,
        eligibility_review_count=eligibility_result.review_count,
        snapshot_listing_count=len(snapshot.listings),
        parser_status_counts=parser_status_counts,
        eligibility_decision_counts=(
            ("active_inventory", eligibility_result.active_count),
            ("inactive_status", eligibility_result.inactive_status_count),
            ("unsupported_transaction_type", eligibility_result.unsupported_transaction_type_count),
            ("unsupported_property_type", eligibility_result.unsupported_property_type_count),
            ("review", eligibility_result.review_count),
        ),
        property_type_counts=_property_type_counts(enrichment_result.enriched_listings),
        warning_counts=_counter_pairs(raw_warnings),
        page_result_counts=tuple(
            (
                result.page,
                result.parser_listing_count,
                0 if result.qa_result is None else result.qa_result.clean_count,
                0 if result.qa_result is None else result.qa_result.review_count,
            )
            for result in page_results
        ),
        warnings=_dedupe_warnings(raw_warnings),
    )


def _run_full_pages(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    page_limit: int,
    runtime_deadline: float | None,
) -> tuple[_FullPageResult, ...]:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_full_kin_config
        raise ValueError("missing_paginated_api_config")

    page_results: list[_FullPageResult] = []
    page = api.start_page
    while len(page_results) < page_limit:
        if _deadline_exhausted(runtime_deadline):
            break
        result = _run_full_page(config, page, fetch_json)
        page_results.append(result)

        if len(page_results) >= page_limit:
            break
        if page_results[0].total_pages_reported is not None:
            if len(page_results) >= min(page_results[0].total_pages_reported or 0, page_limit):
                break
        elif result.has_next_page is False:
            break
        page += 1

    return tuple(page_results)


def _enrich_listings_with_runtime_budget(
    listings: Iterable[ParsedListing],
    *,
    fetch_html: Callable[[str], str],
    max_details: int,
    detail_deadline: float | None,
    runtime_deadline: float | None,
) -> tuple[DetailPropertyTypeEnrichmentResult, tuple[str, ...]]:
    original_listings = tuple(listings)
    if max_details <= 0:
        return (
            DetailPropertyTypeEnrichmentResult(
                enriched_listings=original_listings,
                items=(),
                attempted_count=0,
                succeeded_count=0,
                enriched_count=0,
                unchanged_count=0,
                blocked_count=0,
                failed_count=0,
                warnings=("max_details_must_be_positive",),
            ),
            (),
        )

    warnings: list[str] = []
    enriched_by_index: dict[int, ParsedListing] = {}
    items = []
    for index in _eligible_listing_indexes(original_listings)[:max_details]:
        if _deadline_exhausted(runtime_deadline):
            warnings.append("full_audit_runtime_budget_exhausted")
            break
        if _deadline_exhausted(detail_deadline):
            warnings.append("full_audit_detail_runtime_budget_exhausted")
            break

        listing = original_listings[index]
        item = _enrich_listing(listing, fetch_html=fetch_html)
        items.append(item)
        if item.enriched_listing is not listing:
            enriched_by_index[index] = item.enriched_listing

    if len(items) < min(max_details, len(_eligible_listing_indexes(original_listings))):
        if _deadline_exhausted(runtime_deadline) and "full_audit_runtime_budget_exhausted" not in warnings:
            warnings.append("full_audit_runtime_budget_exhausted")
        elif _deadline_exhausted(detail_deadline) and "full_audit_detail_runtime_budget_exhausted" not in warnings:
            warnings.append("full_audit_detail_runtime_budget_exhausted")

    enriched_listings = tuple(enriched_by_index.get(index, listing) for index, listing in enumerate(original_listings))
    succeeded_count = sum(1 for item in items if item.fetch_status == "success")
    enriched_count = sum(1 for item in items if item.mapped_property_type)
    blocked_count = sum(1 for item in items if item.fetch_status == "blocked_by_robots")
    failed_count = sum(1 for item in items if item.fetch_status == "fetch_exception")
    item_warnings = tuple(warning for item in items for warning in item.warnings)

    return (
        DetailPropertyTypeEnrichmentResult(
            enriched_listings=enriched_listings,
            items=tuple(items),
            attempted_count=len(items),
            succeeded_count=succeeded_count,
            enriched_count=enriched_count,
            unchanged_count=len(items) - enriched_count,
            blocked_count=blocked_count,
            failed_count=failed_count,
            warnings=_dedupe_warnings((*item_warnings, *warnings)),
        ),
        tuple(warnings),
    )


def _run_full_page(
    config: ParserSourceConfig,
    page: int,
    fetch_json: Callable[[str], str],
) -> _FullPageResult:
    try:
        api_url = build_paginated_api_url(config, page)
    except Exception:
        return _FullPageResult(page=page, succeeded=False, warnings=("api_url_build_failed",))

    can_fetch, robots_warnings = _robots_check_api_url(api_url)
    if not can_fetch:
        return _FullPageResult(
            page=page,
            succeeded=False,
            warnings=_dedupe_warnings((*robots_warnings, "robots_gate_blocked")),
        )

    try:
        json_content = fetch_json(api_url)
    except Exception:
        return _FullPageResult(page=page, succeeded=False, warnings=("fetch_exception",))

    if not (json_content or "").strip():
        return _FullPageResult(page=page, succeeded=False, warnings=("empty_json",))

    payload, metadata_warnings = _load_payload(json_content)
    total_pages = _metadata_int(payload, config.api.total_pages_path if config.api else "")
    total_docs = _metadata_int(payload, config.api.total_count_path if config.api else "")
    has_next = _metadata_bool(payload, config.api.has_next_path if config.api else "")

    try:
        parser_input = build_parser_input_from_api_json(config, json_content, page=page)
        from domek_wonen.parsers import ParserFamilyRunner

        parser_result = ParserFamilyRunner().run(_fingerprint_for_config(config), parser_input)
    except Exception:
        return _FullPageResult(
            page=page,
            succeeded=False,
            total_pages_reported=total_pages,
            total_docs_reported=total_docs,
            has_next_page=has_next,
            warnings=_dedupe_warnings((*metadata_warnings, "parser_exception")),
        )

    parser_listing_count = len(parser_result.listings)
    if parser_listing_count == 0:
        return _FullPageResult(
            page=page,
            succeeded=False,
            total_pages_reported=total_pages,
            total_docs_reported=total_docs,
            has_next_page=has_next,
            warnings=_dedupe_warnings((*metadata_warnings, "parser_no_listings", *parser_result.warnings)),
        )

    try:
        from domek_wonen.qa import qa_parser_family_result

        qa_result = qa_parser_family_result(parser_result)
    except Exception:
        return _FullPageResult(
            page=page,
            succeeded=False,
            parser_listing_count=parser_listing_count,
            total_pages_reported=total_pages,
            total_docs_reported=total_docs,
            has_next_page=has_next,
            warnings=_dedupe_warnings((*metadata_warnings, "qa_exception")),
        )

    return _FullPageResult(
        page=page,
        succeeded=True,
        parser_listing_count=parser_listing_count,
        qa_result=qa_result,
        total_pages_reported=total_pages,
        total_docs_reported=total_docs,
        has_next_page=has_next,
        warnings=_dedupe_warnings((*metadata_warnings, *parser_result.warnings, *qa_result.warnings)),
    )


def _empty_result(
    config: ParserSourceConfig,
    *,
    pages_requested: int,
    warnings: tuple[str, ...],
) -> KINOGonlineFullValidationAuditResult:
    return KINOGonlineFullValidationAuditResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        total_pages_reported=None,
        total_docs_reported=None,
        pages_requested=pages_requested,
        pages_attempted=0,
        pages_succeeded=0,
        pages_failed=0,
        parser_listing_count=0,
        qa_clean_count=0,
        qa_review_count=0,
        qa_rejected_count=0,
        detail_enrichment_attempted_count=0,
        detail_enrichment_succeeded_count=0,
        detail_enrichment_failed_count=0,
        detail_enriched_count=0,
        active_inventory_count=0,
        inactive_status_count=0,
        unsupported_transaction_type_count=0,
        unsupported_property_type_count=0,
        eligibility_review_count=0,
        snapshot_listing_count=0,
        parser_status_counts=(),
        eligibility_decision_counts=(),
        property_type_counts=(),
        warning_counts=_counter_pairs(warnings),
        page_result_counts=(),
        warnings=warnings,
    )


def _validate_full_kin_config(config: ParserSourceConfig) -> None:
    _validate_ogonline_config(config)
    if config.source_domain != "kinmakelaars.nl" or not config.source_id.startswith("kinmakelaars.nl__"):
        raise ValueError("unsupported_full_audit_source")


def _config_with_full_page_limit(config: ParserSourceConfig, pages: int) -> ParserSourceConfig:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_full_kin_config
        raise ValueError("missing_paginated_api_config")
    required_max_page = api.start_page + pages - 1
    return replace(config, api=replace(api, max_pages=max(api.max_pages, required_max_page)))


def _detail_enrichment_limit(clean_count: int, max_detail_enrichment: int) -> tuple[int, tuple[str, ...]]:
    if max_detail_enrichment <= 0:
        return 0, ("max_detail_enrichment_disabled",)
    if max_detail_enrichment > MAX_FULL_KIN_DETAIL_ENRICHMENT:
        return min(clean_count, MAX_FULL_KIN_DETAIL_ENRICHMENT), ("full_audit_detail_enrichment_capped",)
    if clean_count > max_detail_enrichment:
        return max_detail_enrichment, ("full_audit_detail_enrichment_capped",)
    return min(clean_count, max_detail_enrichment), ()


def _load_payload(json_content: str) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    try:
        payload = json.loads(json_content)
    except json.JSONDecodeError:
        return {}, ("invalid_json",)
    if not isinstance(payload, Mapping):
        return {}, ("payload_not_object",)
    return payload, ()


def _metadata_int(payload: Mapping[str, Any], path: str) -> int | None:
    value = _path_value(payload, path)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _metadata_bool(payload: Mapping[str, Any], path: str) -> bool | None:
    value = _path_value(payload, path)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _path_value(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for key in (part for part in (path or "").split(".") if part):
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _pages_requested(
    total_pages_reported: int | None,
    page_results: tuple[_FullPageResult, ...],
    page_limit: int,
) -> int:
    if total_pages_reported is not None:
        return min(total_pages_reported, page_limit)
    return len(page_results)


def _page_results_for_capture(page_results: tuple[_FullPageResult, ...]) -> tuple[object, ...]:
    return tuple(result for result in page_results)


def _first_int(values: Iterable[int | None]) -> int | None:
    for value in values:
        if value is not None:
            return value
    return None


def _deadline(started_at: float, budget_seconds: float | None) -> float | None:
    if budget_seconds is None:
        return None
    if budget_seconds <= 0:
        return started_at
    return started_at + budget_seconds


def _deadline_exhausted(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _extend_warnings(warnings: list[str], new_warnings: Iterable[str]) -> None:
    for warning in new_warnings:
        _append_warning(warnings, warning)


def _append_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def _enrichment_warning_events(enrichment_result: DetailPropertyTypeEnrichmentResult) -> tuple[str, ...]:
    budget_warnings = {
        "full_audit_runtime_budget_exhausted",
        "full_audit_detail_runtime_budget_exhausted",
    }
    item_warnings = tuple(
        warning
        for item in enrichment_result.items
        for warning in item.warnings
    )
    item_warning_types = set(item_warnings)
    result_only_warnings = tuple(
        warning
        for warning in enrichment_result.warnings
        if warning not in item_warning_types and warning not in budget_warnings
    )
    return (*item_warnings, *result_only_warnings)


def _parser_status_counts(qa_result: ParserFamilyQAResult) -> tuple[tuple[str, int], ...]:
    listings = tuple(_all_qa_listings(qa_result))
    return _counter_pairs((listing.status or "unknown" for listing in listings))


def _property_type_counts(listings: Iterable[ParsedListing]) -> tuple[tuple[str, int], ...]:
    return _counter_pairs((_normalized_count_value(listing.property_type) for listing in listings))


def _all_qa_listings(qa_result: ParserFamilyQAResult) -> tuple[ParsedListing, ...]:
    return tuple(
        qa_listing.listing
        for bucket in (qa_result.clean_listings, qa_result.review_listings, qa_result.rejected_listings)
        for qa_listing in bucket
    )


def _counter_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counts = Counter(values)
    return tuple(sorted(counts.items()))


def _normalized_count_value(value: str) -> str:
    normalized = (value or "").strip()
    return normalized if normalized else "unknown"
