from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from domek_wonen.compliance import robots_gate
from domek_wonen.parsers import ParserFamilyRunner
from domek_wonen.parsers.source_config import (
    ParserSourceConfig,
    build_paginated_api_url,
    build_parser_input_from_api_json,
)
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult


PAGINATED_STATUS_SUCCESS = "success"
PAGINATED_STATUS_BLOCKED_BY_ROBOTS = "blocked_by_robots"
PAGINATED_STATUS_FETCH_FAILED = "fetch_failed"
PAGINATED_STATUS_PARSER_FAILED = "parser_failed"
PAGINATED_STATUS_QA_FAILED = "qa_failed"
PAGINATED_STATUS_SKIPPED = "skipped"

ALLOWED_PAGINATED_STATUSES = frozenset(
    {
        PAGINATED_STATUS_SUCCESS,
        PAGINATED_STATUS_BLOCKED_BY_ROBOTS,
        PAGINATED_STATUS_FETCH_FAILED,
        PAGINATED_STATUS_PARSER_FAILED,
        PAGINATED_STATUS_QA_FAILED,
        PAGINATED_STATUS_SKIPPED,
    }
)


@dataclass(frozen=True, slots=True)
class PaginatedPageResult:
    page: int
    api_url: str
    can_fetch: bool
    fetch_status: str
    parser_listing_count: int = 0
    clean_count: int = 0
    review_count: int = 0
    rejected_count: int = 0
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.fetch_status not in ALLOWED_PAGINATED_STATUSES:
            raise ValueError(f"Unsupported fetch_status: {self.fetch_status}")


@dataclass(frozen=True, slots=True)
class PaginatedRunResult:
    source_id: str
    source_domain: str
    pages_attempted: int
    pages_succeeded: int
    total_parser_listings: int
    total_clean: int
    total_review: int
    total_rejected: int
    page_results: tuple[PaginatedPageResult, ...]
    warnings: tuple[str, ...] = ()


def run_ogonline_xhr_paginated_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    max_pages: int | None = None,
) -> PaginatedRunResult:
    _validate_ogonline_config(config)
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_ogonline_config
        raise ValueError("missing_paginated_api_config")

    if max_pages is not None and max_pages <= 0:
        return PaginatedRunResult(
            source_id=config.source_id,
            source_domain=config.source_domain,
            pages_attempted=0,
            pages_succeeded=0,
            total_parser_listings=0,
            total_clean=0,
            total_review=0,
            total_rejected=0,
            page_results=(),
            warnings=("max_pages_must_be_positive",),
        )

    configured_page_count = max(0, api.max_pages - api.start_page + 1)
    page_count = configured_page_count if max_pages is None else min(configured_page_count, max_pages)
    pages = range(api.start_page, api.start_page + page_count)
    page_results = tuple(_run_page(config, page, fetch_json) for page in pages)

    return PaginatedRunResult(
        source_id=config.source_id,
        source_domain=config.source_domain,
        pages_attempted=len(page_results),
        pages_succeeded=sum(1 for result in page_results if result.fetch_status == PAGINATED_STATUS_SUCCESS),
        total_parser_listings=sum(result.parser_listing_count for result in page_results),
        total_clean=sum(result.clean_count for result in page_results),
        total_review=sum(result.review_count for result in page_results),
        total_rejected=sum(result.rejected_count for result in page_results),
        page_results=page_results,
        warnings=_dedupe_warnings(warning for result in page_results for warning in result.warnings),
    )


def _run_page(
    config: ParserSourceConfig,
    page: int,
    fetch_json: Callable[[str], str],
) -> PaginatedPageResult:
    try:
        api_url = build_paginated_api_url(config, page)
    except Exception:
        return PaginatedPageResult(
            page=page,
            api_url="",
            can_fetch=False,
            fetch_status=PAGINATED_STATUS_SKIPPED,
            warnings=("api_url_build_failed",),
        )

    can_fetch, robots_warnings = _robots_check_api_url(api_url)
    if not can_fetch:
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=False,
            fetch_status=PAGINATED_STATUS_BLOCKED_BY_ROBOTS,
            warnings=_dedupe_warnings((*robots_warnings, "robots_gate_blocked")),
        )

    try:
        json_content = fetch_json(api_url)
    except Exception:
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=True,
            fetch_status=PAGINATED_STATUS_FETCH_FAILED,
            warnings=("fetch_json_exception",),
        )

    if not (json_content or "").strip():
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=True,
            fetch_status=PAGINATED_STATUS_FETCH_FAILED,
            warnings=("empty_json",),
        )

    try:
        parser_input = build_parser_input_from_api_json(config, json_content, page=page)
        parser_result = ParserFamilyRunner().run(_fingerprint_for_config(config), parser_input)
    except Exception:
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=True,
            fetch_status=PAGINATED_STATUS_PARSER_FAILED,
            warnings=("parser_exception",),
        )

    parser_listing_count = len(parser_result.listings)
    if parser_listing_count == 0:
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=True,
            fetch_status=PAGINATED_STATUS_PARSER_FAILED,
            warnings=_dedupe_warnings(("parser_no_listings", *parser_result.warnings)),
        )

    try:
        qa_result = qa_parser_family_result(parser_result)
    except Exception:
        return PaginatedPageResult(
            page=page,
            api_url=api_url,
            can_fetch=True,
            fetch_status=PAGINATED_STATUS_QA_FAILED,
            parser_listing_count=parser_listing_count,
            warnings=("qa_exception",),
        )

    return PaginatedPageResult(
        page=page,
        api_url=api_url,
        can_fetch=True,
        fetch_status=PAGINATED_STATUS_SUCCESS,
        parser_listing_count=parser_listing_count,
        clean_count=qa_result.clean_count,
        review_count=qa_result.review_count,
        rejected_count=qa_result.rejected_count,
        warnings=_dedupe_warnings((*parser_result.warnings, *qa_result.warnings)),
    )


def _can_fetch_api_url(api_url: str) -> bool:
    parsed = _parse_api_url(api_url)
    if parsed is None:
        return False

    domain, path = parsed
    try:
        return robots_gate.can_fetch(domain, path) is True
    except Exception:
        return False


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
        evidence_signals=("ogonline", "paginated_config_runner"),
        blocking_signals=(),
        recommended_action="build_source_config",
        can_proceed_to_parser_family=True,
        reason="ogonline_paginated_config_runner",
    )


def _dedupe_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.add(warning)
            result.append(warning)
    return tuple(result)
