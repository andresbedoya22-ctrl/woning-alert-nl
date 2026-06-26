from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from domek_wonen.compliance import robots_gate
from domek_wonen.inventory import (
    build_active_inventory_qa_result,
    build_inventory_snapshot_from_qa,
    evaluate_inventory_eligibility,
)
from domek_wonen.parsers import ParserFamilyRunner
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.parsers.source_config import (
    ParserSourceConfig,
    build_paginated_api_url,
    build_parser_input_from_api_json,
    load_parser_source_config,
)
from domek_wonen.qa import ParserFamilyQAResult, qa_parser_family_result
from domek_wonen.qa.parser_output_gate import ParserListingQAResult
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .live_fetch import controlled_http_fetch_html
from .ogonline_detail_property_type_enrichment import (
    DetailPropertyTypeEnrichmentResult,
    enrich_listings_with_detail_property_type,
)
from .ogonline_xhr_live_fetch import controlled_http_fetch_json


MAX_KIN_OGONLINE_ACTIVE_INVENTORY_PAGES = 2


@dataclass(frozen=True, slots=True)
class ActiveInventoryPilotResult:
    source_id: str
    source_domain: str
    pages_attempted: int
    pages_succeeded: int
    parser_listing_count: int
    qa_clean_count: int
    qa_review_count: int
    qa_rejected_count: int
    active_inventory_count: int
    inactive_status_count: int
    unsupported_transaction_type_count: int
    unsupported_property_type_count: int
    eligibility_review_count: int
    snapshot_listing_count: int
    detail_enrichment_attempted_count: int = 0
    detail_enrichment_succeeded_count: int = 0
    detail_enriched_count: int = 0
    detail_enrichment_warnings: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _PageQAResult:
    page: int
    succeeded: bool
    parser_listing_count: int = 0
    qa_result: ParserFamilyQAResult | None = None
    warnings: tuple[str, ...] = ()


def run_kin_ogonline_active_inventory_pilot(
    *,
    config_path,
    max_pages: int = MAX_KIN_OGONLINE_ACTIVE_INVENTORY_PAGES,
    enrich_detail_property_type: bool = False,
    max_detail_enrichment: int = 5,
) -> ActiveInventoryPilotResult:
    config = load_parser_source_config(config_path)
    return _run_kin_ogonline_active_inventory_config(
        config,
        fetch_json=controlled_http_fetch_json,
        fetch_html=controlled_http_fetch_html,
        max_pages=max_pages,
        enrich_detail_property_type=enrich_detail_property_type,
        max_detail_enrichment=max_detail_enrichment,
    )


def _run_kin_ogonline_active_inventory_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str] | None = None,
    max_pages: int = MAX_KIN_OGONLINE_ACTIVE_INVENTORY_PAGES,
    enrich_detail_property_type: bool = False,
    max_detail_enrichment: int = 5,
) -> ActiveInventoryPilotResult:
    _validate_ogonline_config(config)
    if max_pages <= 0:
        return ActiveInventoryPilotResult(
            source_id=config.source_id,
            source_domain=config.source_domain,
            pages_attempted=0,
            pages_succeeded=0,
            parser_listing_count=0,
            qa_clean_count=0,
            qa_review_count=0,
            qa_rejected_count=0,
            active_inventory_count=0,
            inactive_status_count=0,
            unsupported_transaction_type_count=0,
            unsupported_property_type_count=0,
            eligibility_review_count=0,
            snapshot_listing_count=0,
            detail_enrichment_attempted_count=0,
            detail_enrichment_succeeded_count=0,
            detail_enriched_count=0,
            detail_enrichment_warnings=(),
            warnings=("max_pages_must_be_positive",),
        )

    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_ogonline_config
        raise ValueError("missing_paginated_api_config")

    configured_page_count = max(0, api.max_pages - api.start_page + 1)
    page_count = min(configured_page_count, max_pages, MAX_KIN_OGONLINE_ACTIVE_INVENTORY_PAGES)
    pages = range(api.start_page, api.start_page + page_count)
    page_results = tuple(_run_page(config, page, fetch_json) for page in pages)

    qa_result = _combine_qa_results(
        config,
        (qa_result for qa_result in (result.qa_result for result in page_results) if qa_result is not None),
    )
    enrichment_result: DetailPropertyTypeEnrichmentResult | None = None
    if enrich_detail_property_type:
        if fetch_html is None:
            fetch_html = controlled_http_fetch_html
        enrichment_result = enrich_listings_with_detail_property_type(
            (qa_listing.listing for qa_listing in qa_result.clean_listings),
            fetch_html=fetch_html,
            max_details=max_detail_enrichment,
        )
        qa_result = _qa_result_with_enriched_clean_listings(qa_result, enrichment_result.enriched_listings)

    eligibility_result = evaluate_inventory_eligibility(qa_result)
    active_qa_result = build_active_inventory_qa_result(qa_result)
    capture_status = _capture_status(page_results)
    detail_enrichment_warnings = () if enrichment_result is None else enrichment_result.warnings
    snapshot = build_inventory_snapshot_from_qa(
        active_qa_result,
        _utc_timestamp(),
        capture_status=capture_status,
        safe_to_compare_removals=capture_status == "success",
    )

    return ActiveInventoryPilotResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        pages_attempted=len(page_results),
        pages_succeeded=sum(1 for result in page_results if result.succeeded),
        parser_listing_count=sum(result.parser_listing_count for result in page_results),
        qa_clean_count=qa_result.clean_count,
        qa_review_count=qa_result.review_count,
        qa_rejected_count=qa_result.rejected_count,
        active_inventory_count=eligibility_result.active_count,
        inactive_status_count=eligibility_result.inactive_status_count,
        unsupported_transaction_type_count=eligibility_result.unsupported_transaction_type_count,
        unsupported_property_type_count=eligibility_result.unsupported_property_type_count,
        eligibility_review_count=eligibility_result.review_count,
        snapshot_listing_count=len(snapshot.listings),
        detail_enrichment_attempted_count=0 if enrichment_result is None else enrichment_result.attempted_count,
        detail_enrichment_succeeded_count=0 if enrichment_result is None else enrichment_result.succeeded_count,
        detail_enriched_count=0 if enrichment_result is None else enrichment_result.enriched_count,
        detail_enrichment_warnings=detail_enrichment_warnings,
        warnings=_dedupe_warnings(
            (
                *qa_result.warnings,
                *detail_enrichment_warnings,
                *snapshot.warnings,
                *(warning for result in page_results for warning in result.warnings),
                *(() if max_pages <= MAX_KIN_OGONLINE_ACTIVE_INVENTORY_PAGES else ("max_pages_capped_at_2",)),
            )
        ),
    )


def _qa_result_with_enriched_clean_listings(
    qa_result: ParserFamilyQAResult,
    enriched_listings: tuple[ParsedListing, ...],
) -> ParserFamilyQAResult:
    enriched_clean = tuple(
        ParserListingQAResult(
            listing=enriched_listing,
            qa_status=qa_listing.qa_status,
            issues=qa_listing.issues,
            normalized_key=qa_listing.normalized_key,
        )
        for qa_listing, enriched_listing in zip(qa_result.clean_listings, enriched_listings, strict=True)
    )
    return ParserFamilyQAResult(
        parser_family=qa_result.parser_family,
        source_id=qa_result.source_id,
        source_domain=qa_result.source_domain,
        clean_listings=enriched_clean,
        review_listings=qa_result.review_listings,
        rejected_listings=qa_result.rejected_listings,
        total_count=qa_result.total_count,
        clean_count=qa_result.clean_count,
        review_count=qa_result.review_count,
        rejected_count=qa_result.rejected_count,
        warnings=qa_result.warnings,
    )


def _run_page(
    config: ParserSourceConfig,
    page: int,
    fetch_json: Callable[[str], str],
) -> _PageQAResult:
    try:
        api_url = build_paginated_api_url(config, page)
    except Exception:
        return _PageQAResult(page=page, succeeded=False, warnings=("api_url_build_failed",))

    can_fetch, robots_warnings = _robots_check_api_url(api_url)
    if not can_fetch:
        return _PageQAResult(
            page=page,
            succeeded=False,
            warnings=_dedupe_warnings((*robots_warnings, "robots_gate_blocked")),
        )

    try:
        json_content = fetch_json(api_url)
    except Exception:
        return _PageQAResult(page=page, succeeded=False, warnings=("fetch_json_exception",))

    if not (json_content or "").strip():
        return _PageQAResult(page=page, succeeded=False, warnings=("empty_json",))

    try:
        parser_input = build_parser_input_from_api_json(config, json_content, page=page)
        parser_result = ParserFamilyRunner().run(_fingerprint_for_config(config), parser_input)
    except Exception:
        return _PageQAResult(page=page, succeeded=False, warnings=("parser_exception",))

    parser_listing_count = len(parser_result.listings)
    if parser_listing_count == 0:
        return _PageQAResult(
            page=page,
            succeeded=False,
            warnings=_dedupe_warnings(("parser_no_listings", *parser_result.warnings)),
        )

    try:
        qa_result = qa_parser_family_result(parser_result)
    except Exception:
        return _PageQAResult(
            page=page,
            succeeded=False,
            parser_listing_count=parser_listing_count,
            warnings=("qa_exception",),
        )

    return _PageQAResult(
        page=page,
        succeeded=True,
        parser_listing_count=parser_listing_count,
        qa_result=qa_result,
        warnings=_dedupe_warnings((*parser_result.warnings, *qa_result.warnings)),
    )


def _combine_qa_results(
    config: ParserSourceConfig,
    qa_results: Iterable[ParserFamilyQAResult],
) -> ParserFamilyQAResult:
    clean = []
    review = []
    rejected = []
    warnings = []

    for qa_result in qa_results:
        clean.extend(qa_result.clean_listings)
        review.extend(qa_result.review_listings)
        rejected.extend(qa_result.rejected_listings)
        warnings.extend(qa_result.warnings)

    total_count = len(clean) + len(review) + len(rejected)
    return ParserFamilyQAResult(
        parser_family=config.parser_family,
        source_id=config.source_id,
        source_domain=config.source_domain,
        clean_listings=tuple(clean),
        review_listings=tuple(review),
        rejected_listings=tuple(rejected),
        total_count=total_count,
        clean_count=len(clean),
        review_count=len(review),
        rejected_count=len(rejected),
        warnings=_dedupe_warnings(warnings),
    )


def _capture_status(page_results: tuple[_PageQAResult, ...]) -> str:
    if not page_results:
        return "failed"
    if all(result.succeeded for result in page_results):
        return "success"
    if any(result.succeeded for result in page_results):
        return "partial"
    return "failed"


def _robots_check_api_url(api_url: str) -> tuple[bool, tuple[str, ...]]:
    parsed = _parse_api_url(api_url)
    if parsed is None:
        return False, ("invalid_api_url",)

    domain, path = parsed
    try:
        return robots_gate.can_fetch(domain, path) is True, ()
    except Exception:
        return False, ("robots_gate_exception",)


def _parse_api_url(api_url: str) -> tuple[str, str] | None:
    cleaned = (api_url or "").strip()
    scheme_separator = cleaned.find("://")
    if scheme_separator <= 0:
        return None

    scheme = cleaned[:scheme_separator].lower()
    if scheme not in {"http", "https"}:
        return None

    remainder = cleaned[scheme_separator + 3 :]
    if not remainder:
        return None

    slash_index = remainder.find("/")
    if slash_index < 0:
        domain = remainder
        path = "/"
    else:
        domain = remainder[:slash_index]
        path = remainder[slash_index:] or "/"

    domain = domain.strip().lower()
    if not domain or any(separator in domain for separator in ("/", "?", "#")):
        return None

    fragment_index = path.find("#")
    if fragment_index >= 0:
        path = path[:fragment_index] or "/"
    return domain, path


def _validate_ogonline_config(config: ParserSourceConfig) -> None:
    if config.parser_family != "ogonline_xhr":
        raise ValueError("unsupported_parser_family")
    if config.delivery_mode != "ogonline_xhr":
        raise ValueError("unsupported_delivery_mode")
    if config.api is None:
        raise ValueError("missing_paginated_api_config")


def _fingerprint_for_config(config: ParserSourceConfig) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        access_status="allowed",
        delivery_mode=config.delivery_mode,
        parser_family_candidate=config.parser_family,
        confidence=0.84,
        evidence_signals=("ogonline", "active_inventory_pilot"),
        blocking_signals=(),
        recommended_action="build_source_config",
        can_proceed_to_parser_family=True,
        reason="kin_ogonline_active_inventory_pilot",
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dedupe_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.add(warning)
            result.append(warning)
    return tuple(result)
