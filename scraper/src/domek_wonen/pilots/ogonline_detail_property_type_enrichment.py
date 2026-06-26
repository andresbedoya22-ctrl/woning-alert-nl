from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.parsers.models import ParsedListing

from .ogonline_detail_property_type_probe import extract_detail_candidates


UNKNOWN_PROPERTY_TYPE_TOKENS = frozenset({"", "unknown", "onbekend", "nvt", "n/a", "none", "null"})

_PROPERTY_TYPE_MAPPING = {
    "woonhuis": "woonhuis",
    "vrijstaande woning": "vrijstaande_woning",
    "tussenwoning": "tussenwoning",
    "hoekwoning": "hoekwoning",
    "twee-onder-een-kap": "twee_onder_een_kap",
    "herenhuis": "herenhuis",
    "appartement": "appartement",
    "benedenwoning": "benedenwoning",
    "bovenwoning": "bovenwoning",
    "maisonette": "maisonette",
    "bouwgrond": "bouwgrond",
    "garage": "garage",
    "parkeerplaats": "parkeerplaats",
    "kantoor": "kantoor",
    "bedrijfspand": "bedrijfspand",
}


@dataclass(frozen=True, slots=True)
class DetailPropertyTypeEnrichmentItem:
    original_listing: ParsedListing
    enriched_listing: ParsedListing
    fetch_status: str
    raw_candidates: tuple[str, ...]
    mapped_property_type: str
    evidence_signals: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DetailPropertyTypeEnrichmentResult:
    enriched_listings: tuple[ParsedListing, ...]
    items: tuple[DetailPropertyTypeEnrichmentItem, ...]
    attempted_count: int
    succeeded_count: int
    enriched_count: int
    unchanged_count: int
    blocked_count: int
    failed_count: int
    warnings: tuple[str, ...] = ()


def map_ogonline_detail_property_type(candidate: str) -> str:
    normalized = _normalize_candidate(candidate)
    return _PROPERTY_TYPE_MAPPING.get(normalized, "")


def enrich_listings_with_detail_property_type(
    listings: Iterable[ParsedListing],
    *,
    fetch_html: Callable[[str], str],
    max_details: int = 5,
) -> DetailPropertyTypeEnrichmentResult:
    original_listings = tuple(listings)
    if max_details <= 0:
        return DetailPropertyTypeEnrichmentResult(
            enriched_listings=original_listings,
            items=(),
            attempted_count=0,
            succeeded_count=0,
            enriched_count=0,
            unchanged_count=0,
            blocked_count=0,
            failed_count=0,
            warnings=("max_details_must_be_positive",),
        )

    enriched_by_index: dict[int, ParsedListing] = {}
    items: list[DetailPropertyTypeEnrichmentItem] = []
    for index in _eligible_listing_indexes(original_listings)[:max_details]:
        listing = original_listings[index]
        item = _enrich_listing(listing, fetch_html=fetch_html)
        items.append(item)
        if item.enriched_listing is not listing:
            enriched_by_index[index] = item.enriched_listing

    enriched_listings = tuple(enriched_by_index.get(index, listing) for index, listing in enumerate(original_listings))
    succeeded_count = sum(1 for item in items if item.fetch_status == "success")
    enriched_count = sum(1 for item in items if item.mapped_property_type)
    blocked_count = sum(1 for item in items if item.fetch_status == "blocked_by_robots")
    failed_count = sum(1 for item in items if item.fetch_status == "fetch_exception")

    return DetailPropertyTypeEnrichmentResult(
        enriched_listings=enriched_listings,
        items=tuple(items),
        attempted_count=len(items),
        succeeded_count=succeeded_count,
        enriched_count=enriched_count,
        unchanged_count=len(items) - enriched_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        warnings=_dedupe_warnings(warning for item in items for warning in item.warnings),
    )


def _enrich_listing(
    listing: ParsedListing,
    *,
    fetch_html: Callable[[str], str],
) -> DetailPropertyTypeEnrichmentItem:
    can_fetch, robots_warnings = _robots_check_url(listing.canonical_url)
    if not can_fetch:
        warnings = _dedupe_warnings((*robots_warnings, "blocked_by_robots"))
        return _item(
            listing,
            fetch_status="blocked_by_robots",
            raw_candidates=(),
            mapped_property_type="",
            evidence_signals=(),
            warnings=warnings,
        )

    try:
        html = fetch_html(listing.canonical_url)
    except Exception:
        return _item(
            listing,
            fetch_status="fetch_exception",
            raw_candidates=(),
            mapped_property_type="",
            evidence_signals=(),
            warnings=("fetch_exception",),
        )

    extraction = extract_detail_candidates(html)
    mapped = tuple(
        mapped
        for mapped in (map_ogonline_detail_property_type(candidate) for candidate in extraction.property_type_candidates)
        if mapped
    )
    unique_mapped = _dedupe_warnings(mapped)
    if len(unique_mapped) == 1:
        mapped_property_type = unique_mapped[0]
        return DetailPropertyTypeEnrichmentItem(
            original_listing=listing,
            enriched_listing=replace(listing, property_type=mapped_property_type),
            fetch_status="success",
            raw_candidates=extraction.property_type_candidates,
            mapped_property_type=mapped_property_type,
            evidence_signals=extraction.evidence_signals,
        )
    if len(unique_mapped) > 1:
        return _item(
            listing,
            fetch_status="success",
            raw_candidates=extraction.property_type_candidates,
            mapped_property_type="",
            evidence_signals=extraction.evidence_signals,
            warnings=("ambiguous_property_type_candidates",),
        )
    return _item(
        listing,
        fetch_status="success",
        raw_candidates=extraction.property_type_candidates,
        mapped_property_type="",
        evidence_signals=extraction.evidence_signals,
        warnings=("no_mapped_property_type",),
    )


def _item(
    listing: ParsedListing,
    *,
    fetch_status: str,
    raw_candidates: tuple[str, ...],
    mapped_property_type: str,
    evidence_signals: tuple[str, ...],
    warnings: tuple[str, ...],
) -> DetailPropertyTypeEnrichmentItem:
    return DetailPropertyTypeEnrichmentItem(
        original_listing=listing,
        enriched_listing=listing,
        fetch_status=fetch_status,
        raw_candidates=raw_candidates,
        mapped_property_type=mapped_property_type,
        evidence_signals=evidence_signals,
        warnings=warnings,
    )


def _eligible_listing_indexes(listings: tuple[ParsedListing, ...]) -> tuple[int, ...]:
    eligible = tuple(
        index
        for index, listing in enumerate(listings)
        if listing.canonical_url
        and _is_unknown_property_type(listing.property_type)
        and (listing.transaction_type or "").strip().casefold() == "koop"
    )
    return tuple(
        sorted(
            eligible,
            key=lambda index: (0 if listings[index].status == "beschikbaar" else 1, index),
        )
    )


def _is_unknown_property_type(value: str) -> bool:
    return _normalize_candidate(value) in UNKNOWN_PROPERTY_TYPE_TOKENS


def _normalize_candidate(candidate: str) -> str:
    return " ".join((candidate or "").strip().casefold().replace("_", " ").split())


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


def _dedupe_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.add(warning)
            result.append(warning)
    return tuple(result)
