from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from domek_wonen.inventory import (
    build_active_inventory_qa_result,
    build_inventory_snapshot_from_qa,
    evaluate_inventory_eligibility,
)
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.parsers.source_config import ParserSourceConfig, load_parser_source_config
from domek_wonen.qa import ParserFamilyQAResult

from .kin_ogonline_active_inventory_pilot import (
    _capture_status,
    _combine_qa_results,
    _dedupe_warnings,
    _qa_result_with_enriched_clean_listings,
    _run_page,
    _utc_timestamp,
    _validate_ogonline_config,
)
from .live_fetch import controlled_http_fetch_html
from .ogonline_detail_property_type_enrichment import (
    enrich_listings_with_detail_property_type,
)
from .ogonline_xhr_live_fetch import controlled_http_fetch_json


MAX_KIN_OGONLINE_VALIDATION_AUDIT_PAGES = 5
MAX_KIN_OGONLINE_VALIDATION_AUDIT_DETAILS = 120


@dataclass(frozen=True, slots=True)
class KINOGonlineValidationAuditResult:
    source_id: str
    source_domain: str
    pages_requested: int
    pages_attempted: int
    pages_succeeded: int
    parser_listing_count: int
    qa_clean_count: int
    qa_review_count: int
    qa_rejected_count: int
    detail_enrichment_attempted_count: int
    detail_enrichment_succeeded_count: int
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
    warnings: tuple[str, ...] = ()


def run_kin_ogonline_5_page_validation_audit(
    *,
    config_path: Path,
    pages: int = MAX_KIN_OGONLINE_VALIDATION_AUDIT_PAGES,
    max_detail_enrichment: int | None = None,
) -> KINOGonlineValidationAuditResult:
    config = load_parser_source_config(config_path)
    return run_kin_ogonline_validation_audit_config(
        config,
        fetch_json=controlled_http_fetch_json,
        fetch_html=controlled_http_fetch_html,
        pages=pages,
        max_detail_enrichment=max_detail_enrichment,
    )


def run_kin_ogonline_validation_audit_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    pages: int = MAX_KIN_OGONLINE_VALIDATION_AUDIT_PAGES,
    max_detail_enrichment: int | None = None,
) -> KINOGonlineValidationAuditResult:
    _validate_ogonline_config(config)
    if pages <= 0:
        return _empty_result(config, pages_requested=0, warnings=("pages_must_be_positive",))

    capped_pages = min(pages, MAX_KIN_OGONLINE_VALIDATION_AUDIT_PAGES)
    warnings = [] if pages <= MAX_KIN_OGONLINE_VALIDATION_AUDIT_PAGES else ["pages_capped_at_5"]
    audit_config = _config_with_audit_page_limit(config, capped_pages)
    api = audit_config.api
    if api is None:  # pragma: no cover - guarded by _validate_ogonline_config
        raise ValueError("missing_paginated_api_config")

    configured_page_count = max(0, api.max_pages - api.start_page + 1)
    page_count = min(configured_page_count, capped_pages)
    page_results = tuple(
        _run_page(audit_config, page, fetch_json)
        for page in range(api.start_page, api.start_page + page_count)
    )
    qa_result = _combine_qa_results(
        audit_config,
        (qa_result for qa_result in (result.qa_result for result in page_results) if qa_result is not None),
    )
    parser_status_counts = _parser_status_counts(qa_result)

    detail_limit, detail_limit_warnings = _detail_enrichment_limit(qa_result.clean_count, max_detail_enrichment)
    enrichment_result = enrich_listings_with_detail_property_type(
        (qa_listing.listing for qa_listing in qa_result.clean_listings),
        fetch_html=fetch_html,
        max_details=detail_limit,
    )
    qa_result = _qa_result_with_enriched_clean_listings(qa_result, enrichment_result.enriched_listings)

    eligibility_result = evaluate_inventory_eligibility(qa_result)
    active_qa_result = build_active_inventory_qa_result(qa_result)
    capture_status = _capture_status(page_results)
    snapshot = build_inventory_snapshot_from_qa(
        active_qa_result,
        _utc_timestamp(),
        capture_status=capture_status,
        safe_to_compare_removals=capture_status == "success",
    )

    return KINOGonlineValidationAuditResult(
        source_id=audit_config.source_id,
        source_domain=audit_config.source_domain,
        pages_requested=capped_pages,
        pages_attempted=len(page_results),
        pages_succeeded=sum(1 for result in page_results if result.succeeded),
        parser_listing_count=sum(result.parser_listing_count for result in page_results),
        qa_clean_count=qa_result.clean_count,
        qa_review_count=qa_result.review_count,
        qa_rejected_count=qa_result.rejected_count,
        detail_enrichment_attempted_count=enrichment_result.attempted_count,
        detail_enrichment_succeeded_count=enrichment_result.succeeded_count,
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
        warnings=_dedupe_warnings(
            (
                *warnings,
                *qa_result.warnings,
                *detail_limit_warnings,
                *enrichment_result.warnings,
                *snapshot.warnings,
                *(warning for result in page_results for warning in result.warnings),
            )
        ),
    )


def _empty_result(
    config: ParserSourceConfig,
    *,
    pages_requested: int,
    warnings: tuple[str, ...],
) -> KINOGonlineValidationAuditResult:
    return KINOGonlineValidationAuditResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        pages_requested=pages_requested,
        pages_attempted=0,
        pages_succeeded=0,
        parser_listing_count=0,
        qa_clean_count=0,
        qa_review_count=0,
        qa_rejected_count=0,
        detail_enrichment_attempted_count=0,
        detail_enrichment_succeeded_count=0,
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
        warnings=warnings,
    )


def _config_with_audit_page_limit(config: ParserSourceConfig, pages: int) -> ParserSourceConfig:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_ogonline_config
        raise ValueError("missing_paginated_api_config")
    required_max_page = api.start_page + pages - 1
    return replace(config, api=replace(api, max_pages=max(api.max_pages, required_max_page)))


def _detail_enrichment_limit(
    clean_count: int,
    max_detail_enrichment: int | None,
) -> tuple[int, tuple[str, ...]]:
    if max_detail_enrichment is None:
        return min(clean_count, MAX_KIN_OGONLINE_VALIDATION_AUDIT_DETAILS), ()
    if max_detail_enrichment > MAX_KIN_OGONLINE_VALIDATION_AUDIT_DETAILS:
        return MAX_KIN_OGONLINE_VALIDATION_AUDIT_DETAILS, ("max_detail_enrichment_capped_at_120",)
    return max_detail_enrichment, ()


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
