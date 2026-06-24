from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from domek_wonen.parsers.models import ParsedListing, ParserFamilyResult


QA_STATUS_CLEAN = "clean"
QA_STATUS_NEEDS_REVIEW = "needs_review"
QA_STATUS_REJECTED = "rejected"

_ALLOWED_TRANSACTION_TYPES = frozenset({"koop", "huur", "unknown"})
_ALLOWED_STATUSES = frozenset({"beschikbaar", "onder_bod", "verkocht", "unknown"})
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ParserListingQAResult:
    listing: ParsedListing
    qa_status: str
    issues: tuple[str, ...] = ()
    normalized_key: str = ""


@dataclass(frozen=True, slots=True)
class ParserFamilyQAResult:
    parser_family: str
    source_id: str
    source_domain: str
    clean_listings: tuple[ParserListingQAResult, ...]
    review_listings: tuple[ParserListingQAResult, ...]
    rejected_listings: tuple[ParserListingQAResult, ...]
    total_count: int
    clean_count: int
    review_count: int
    rejected_count: int
    warnings: tuple[str, ...] = ()


def qa_parser_family_result(result: ParserFamilyResult) -> ParserFamilyQAResult:
    clean_listings: list[ParserListingQAResult] = []
    review_listings: list[ParserListingQAResult] = []
    rejected_listings: list[ParserListingQAResult] = []

    for listing in result.listings:
        qa_result = _qa_listing(listing)
        if qa_result.qa_status == QA_STATUS_REJECTED:
            rejected_listings.append(qa_result)
        elif qa_result.qa_status == QA_STATUS_NEEDS_REVIEW:
            review_listings.append(qa_result)
        else:
            clean_listings.append(qa_result)

    return ParserFamilyQAResult(
        parser_family=result.parser_family,
        source_id=result.source_id,
        source_domain=result.source_domain,
        clean_listings=tuple(clean_listings),
        review_listings=tuple(review_listings),
        rejected_listings=tuple(rejected_listings),
        total_count=len(result.listings),
        clean_count=len(clean_listings),
        review_count=len(review_listings),
        rejected_count=len(rejected_listings),
        warnings=result.warnings,
    )


def qa_parser_results(results: Iterable[ParserFamilyResult]) -> list[ParserFamilyQAResult]:
    return [qa_parser_family_result(result) for result in results]


def build_listing_normalized_key(listing: ParsedListing) -> str:
    source_domain = _normalize_text(listing.source_domain)

    canonical_url = _normalize_url(listing.canonical_url)
    if canonical_url:
        return "|".join((source_domain, canonical_url))

    postcode = _normalize_text(listing.postcode).replace(" ", "")
    house_number = _normalize_text(listing.house_number)
    if postcode and house_number:
        return "|".join((source_domain, postcode, house_number))

    address_raw = _normalize_text(listing.address_raw)
    city = _normalize_text(listing.city)
    return "|".join((source_domain, address_raw, city))


def _qa_listing(listing: ParsedListing) -> ParserListingQAResult:
    reject_issues = _reject_issues(listing)
    review_issues = _review_issues(listing)
    normalized_key = build_listing_normalized_key(listing)

    if reject_issues:
        return ParserListingQAResult(
            listing=listing,
            qa_status=QA_STATUS_REJECTED,
            issues=reject_issues,
            normalized_key=normalized_key,
        )

    if review_issues:
        return ParserListingQAResult(
            listing=listing,
            qa_status=QA_STATUS_NEEDS_REVIEW,
            issues=review_issues,
            normalized_key=normalized_key,
        )

    return ParserListingQAResult(
        listing=listing,
        qa_status=QA_STATUS_CLEAN,
        normalized_key=normalized_key,
    )


def _reject_issues(listing: ParsedListing) -> tuple[str, ...]:
    issues: list[str] = []
    canonical_url = (listing.canonical_url or "").strip()

    if not canonical_url:
        issues.append("missing_canonical_url")
    elif not _is_http_url(canonical_url):
        issues.append("invalid_canonical_url")

    if listing.transaction_type not in _ALLOWED_TRANSACTION_TYPES:
        issues.append("invalid_transaction_type")
    if listing.status not in _ALLOWED_STATUSES:
        issues.append("invalid_status")

    return tuple(issues)


def _review_issues(listing: ParsedListing) -> tuple[str, ...]:
    issues: list[str] = []

    if listing.needs_review:
        issues.append("listing_marked_needs_review")
    if not (listing.address_raw or "").strip() and not (listing.street or "").strip():
        issues.append("missing_address")
    if listing.asking_price_eur is None:
        issues.append("missing_price")
    if not (listing.city or "").strip():
        issues.append("missing_city")
    if listing.confidence_score < 0.50:
        issues.append("low_confidence")
    if listing.transaction_type == "unknown":
        issues.append("unknown_transaction_type")
    if listing.status == "unknown":
        issues.append("unknown_status")

    return tuple(issues)


def _is_http_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _normalize_url(value: str) -> str:
    cleaned = _collapse_whitespace(value).strip()
    if not cleaned:
        return ""

    parts = urlsplit(cleaned)
    if not parts.scheme or not parts.netloc:
        return _normalize_text(cleaned)

    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",
        )
    ).casefold()


def _normalize_text(value: str) -> str:
    return _collapse_whitespace(value).casefold()


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value or "").strip()
