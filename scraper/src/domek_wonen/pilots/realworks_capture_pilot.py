from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.inventory import build_inventory_snapshot_from_qa
from domek_wonen.parsers import ParserFamilyRunner, ParserInput
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult


CAPTURE_STATUS_SUCCESS = "success"
CAPTURE_STATUS_BLOCKED_BY_ROBOTS = "blocked_by_robots"
CAPTURE_STATUS_FETCH_FAILED = "fetch_failed"
CAPTURE_STATUS_PARSER_FAILED = "parser_failed"
CAPTURE_STATUS_QA_FAILED = "qa_failed"
CAPTURE_STATUS_INVENTORY_FAILED = "inventory_failed"
CAPTURE_STATUS_SKIPPED = "skipped"

ALLOWED_CAPTURE_STATUSES = frozenset(
    {
        CAPTURE_STATUS_SUCCESS,
        CAPTURE_STATUS_BLOCKED_BY_ROBOTS,
        CAPTURE_STATUS_FETCH_FAILED,
        CAPTURE_STATUS_PARSER_FAILED,
        CAPTURE_STATUS_QA_FAILED,
        CAPTURE_STATUS_INVENTORY_FAILED,
        CAPTURE_STATUS_SKIPPED,
    }
)


@dataclass(frozen=True, slots=True)
class CapturePilotSource:
    source_id: str
    source_domain: str
    listing_url: str
    parser_family_candidate: str = "realworks_public"
    delivery_mode: str = "realworks_public"


@dataclass(frozen=True, slots=True)
class CapturePilotResult:
    source: CapturePilotSource
    capture_status: str
    can_fetch: bool
    parser_listing_count: int = 0
    clean_count: int = 0
    review_count: int = 0
    rejected_count: int = 0
    inventory_count: int = 0
    safe_to_compare_removals: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.capture_status not in ALLOWED_CAPTURE_STATUSES:
            raise ValueError(f"Unsupported capture_status: {self.capture_status}")
        if self.capture_status != CAPTURE_STATUS_SUCCESS and self.safe_to_compare_removals:
            object.__setattr__(self, "safe_to_compare_removals", False)


def can_capture_source(source: CapturePilotSource) -> bool:
    parsed = _parse_listing_url(source.listing_url)
    if parsed is None:
        return False

    domain, path = parsed
    try:
        return robots_gate.can_fetch(domain, path) is True
    except Exception:
        return False


def run_realworks_capture_pilot_for_source(
    source: CapturePilotSource,
    fetch_html: Callable[[str], str],
    captured_at: str,
) -> CapturePilotResult:
    can_fetch = can_capture_source(source)
    if not can_fetch:
        warning = "invalid_listing_url" if _parse_listing_url(source.listing_url) is None else "robots_gate_blocked"
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_BLOCKED_BY_ROBOTS,
            can_fetch=False,
            safe_to_compare_removals=False,
            warnings=(warning,),
        )

    try:
        html = fetch_html(source.listing_url)
    except Exception:
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_FETCH_FAILED,
            can_fetch=True,
            safe_to_compare_removals=False,
            warnings=("fetch_html_exception",),
        )

    if not (html or "").strip():
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_FETCH_FAILED,
            can_fetch=True,
            safe_to_compare_removals=False,
            warnings=("empty_html",),
        )

    try:
        parser_result = ParserFamilyRunner().run(
            _fingerprint_for_source(source),
            ParserInput(
                source_id=source.source_id,
                source_domain=source.source_domain,
                source_url=source.listing_url,
                content=html,
                content_type="html",
                metadata={"captured_at": captured_at},
            ),
        )
    except Exception:
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_PARSER_FAILED,
            can_fetch=True,
            safe_to_compare_removals=False,
            warnings=("parser_exception",),
        )

    parser_listing_count = len(parser_result.listings)
    if parser_listing_count == 0:
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_PARSER_FAILED,
            can_fetch=True,
            safe_to_compare_removals=False,
            warnings=_dedupe_warnings(("parser_no_listings", *parser_result.warnings)),
        )

    try:
        qa_result = qa_parser_family_result(parser_result)
    except Exception:
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_QA_FAILED,
            can_fetch=True,
            parser_listing_count=parser_listing_count,
            safe_to_compare_removals=False,
            warnings=("qa_exception",),
        )

    try:
        inventory_snapshot = build_inventory_snapshot_from_qa(
            qa_result,
            captured_at,
            capture_status="success",
            safe_to_compare_removals=True,
        )
    except Exception:
        return CapturePilotResult(
            source=source,
            capture_status=CAPTURE_STATUS_INVENTORY_FAILED,
            can_fetch=True,
            parser_listing_count=parser_listing_count,
            clean_count=qa_result.clean_count,
            review_count=qa_result.review_count,
            rejected_count=qa_result.rejected_count,
            safe_to_compare_removals=False,
            warnings=("inventory_exception",),
        )

    return CapturePilotResult(
        source=source,
        capture_status=CAPTURE_STATUS_SUCCESS,
        can_fetch=True,
        parser_listing_count=parser_listing_count,
        clean_count=qa_result.clean_count,
        review_count=qa_result.review_count,
        rejected_count=qa_result.rejected_count,
        inventory_count=len(inventory_snapshot.listings),
        safe_to_compare_removals=inventory_snapshot.safe_to_compare_removals,
        warnings=_dedupe_warnings((*parser_result.warnings, *qa_result.warnings, *inventory_snapshot.warnings)),
    )


def run_realworks_capture_pilot(
    sources: Iterable[CapturePilotSource],
    fetch_html: Callable[[str], str],
    captured_at: str,
    max_sources: int = 5,
) -> list[CapturePilotResult]:
    results: list[CapturePilotResult] = []
    if max_sources <= 0:
        return results

    for index, source in enumerate(sources):
        if index >= max_sources:
            break
        results.append(
            run_realworks_capture_pilot_for_source(
                source=source,
                fetch_html=fetch_html,
                captured_at=captured_at,
            )
        )
    return results


def _fingerprint_for_source(source: CapturePilotSource) -> DeliveryFingerprintResult:
    return DeliveryFingerprintResult(
        source_id=source.source_id,
        source_domain=source.source_domain,
        access_status="allowed",
        delivery_mode=source.delivery_mode,
        parser_family_candidate=source.parser_family_candidate,
        confidence=0.86,
        evidence_signals=("realworks", "controlled_capture_pilot"),
        blocking_signals=(),
        recommended_action="build_source_config",
        can_proceed_to_parser_family=True,
        reason="controlled_realworks_capture_pilot",
    )


def _parse_listing_url(listing_url: str) -> tuple[str, str] | None:
    parts = urlsplit((listing_url or "").strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None

    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return parts.netloc.lower(), path


def _dedupe_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.add(warning)
            result.append(warning)
    return tuple(result)
