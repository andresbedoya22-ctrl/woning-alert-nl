from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any

from domek_wonen.compliance import robots_gate
from domek_wonen.parsers import ParserFamilyRunner
from domek_wonen.parsers.models import ParsedListing
from domek_wonen.parsers.source_config import (
    ParserSourceConfig,
    build_paginated_api_url,
    build_parser_input_from_api_json,
    load_parser_source_config,
)
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .live_fetch import controlled_http_fetch_html
from .ogonline_xhr_live_fetch import controlled_http_fetch_json


MAX_DETAIL_PROPERTY_TYPE_SAMPLES = 5
MAX_DETAIL_PROPERTY_TYPE_API_PAGES = 2

PROPERTY_TYPE_CANDIDATES = (
    "Woonhuis",
    "Appartement",
    "Bouwgrond",
    "Vrijstaande woning",
    "Tussenwoning",
    "Hoekwoning",
    "Twee-onder-een-kap",
    "Herenhuis",
    "Benedenwoning",
    "Bovenwoning",
    "Maisonette",
    "Garage",
    "Parkeerplaats",
    "Kantoor",
    "Bedrijfspand",
)

BADGE_CANDIDATES = (
    "Beschikbaar",
    "Onder bod",
    "Verkocht",
    "Verkocht onder voorbehoud",
    "Open huis",
    "Open Huis",
    "open_huis",
    "openHouse",
)

_TAG_PATTERN = re.compile(r"<[^>]+>")
_SCRIPT_PATTERN = re.compile(r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
_META_PATTERN = re.compile(r"<meta\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_BREADCRUMB_PATTERN = re.compile(r"breadcrumb|broodkruimel|BreadcrumbList", re.IGNORECASE)
_LABEL_PATTERN = re.compile(r"(Woningtype|Type woning|Soort woning)", re.IGNORECASE)
_HEADING_PATTERN = re.compile(r"<h[1-3]\b[^>]*>(?P<body>.*?)</h[1-3]>", re.IGNORECASE | re.DOTALL)
_DEFINITION_PATTERN = re.compile(r"<d[td]\b[^>]*>(?P<body>.*?)</d[td]>", re.IGNORECASE | re.DOTALL)
_BADGE_ELEMENT_PATTERN = re.compile(
    r"<(?P<tag>[a-z0-9]+)\b(?P<attrs>[^>]*(?:badge|status|label)[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class DetailPropertyTypeProbeSample:
    canonical_url: str
    address_raw: str
    status: str
    transaction_type: str
    parser_property_type: str
    can_fetch: bool
    fetch_status: str
    extracted_property_type_candidates: tuple[str, ...]
    extracted_badge_candidates: tuple[str, ...]
    evidence_signals: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DetailPropertyTypeProbeResult:
    samples_attempted: int
    samples_succeeded: int
    candidate_counts: dict[str, int]
    badge_counts: dict[str, int]
    samples: tuple[DetailPropertyTypeProbeSample, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ExtractionResult:
    property_type_candidates: tuple[str, ...]
    badge_candidates: tuple[str, ...]
    evidence_signals: tuple[str, ...]


def run_kin_ogonline_detail_property_type_probe(
    *,
    config_path: Path,
    max_pages: int = MAX_DETAIL_PROPERTY_TYPE_API_PAGES,
    max_samples: int = MAX_DETAIL_PROPERTY_TYPE_SAMPLES,
) -> DetailPropertyTypeProbeResult:
    config = load_parser_source_config(config_path)
    return run_ogonline_detail_property_type_probe_config(
        config,
        fetch_json=controlled_http_fetch_json,
        fetch_html=controlled_http_fetch_html,
        max_pages=max_pages,
        max_samples=max_samples,
    )


def run_ogonline_detail_property_type_probe_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    max_pages: int = MAX_DETAIL_PROPERTY_TYPE_API_PAGES,
    max_samples: int = MAX_DETAIL_PROPERTY_TYPE_SAMPLES,
) -> DetailPropertyTypeProbeResult:
    _validate_config(config)
    if max_pages <= 0 or max_samples <= 0:
        return DetailPropertyTypeProbeResult(
            samples_attempted=0,
            samples_succeeded=0,
            candidate_counts={},
            badge_counts={},
            samples=(),
            warnings=("max_pages_and_max_samples_must_be_positive",),
        )

    listings, listing_warnings = _fetch_parser_listings(config, fetch_json=fetch_json, max_pages=max_pages)
    selected_listings = select_detail_probe_listings(listings, max_samples=max_samples)
    samples = tuple(_probe_detail_listing(listing, fetch_html=fetch_html) for listing in selected_listings)
    succeeded = tuple(sample for sample in samples if sample.fetch_status == "success")

    return DetailPropertyTypeProbeResult(
        samples_attempted=len(samples),
        samples_succeeded=len(succeeded),
        candidate_counts=dict(
            Counter(candidate for sample in succeeded for candidate in sample.extracted_property_type_candidates)
        ),
        badge_counts=dict(Counter(candidate for sample in succeeded for candidate in sample.extracted_badge_candidates)),
        samples=samples,
        warnings=_dedupe_warnings(listing_warnings),
    )


def select_detail_probe_listings(
    listings: Iterable[ParsedListing],
    *,
    max_samples: int = MAX_DETAIL_PROPERTY_TYPE_SAMPLES,
) -> tuple[ParsedListing, ...]:
    if max_samples <= 0:
        return ()

    eligible = tuple(listing for listing in listings if listing.canonical_url)
    selected: list[ParsedListing] = []

    _extend_selected(
        selected,
        eligible,
        max_samples=max_samples,
        predicate=lambda listing: listing.status == "beschikbaar" and not listing.property_type,
        limit=2,
    )
    _extend_selected(
        selected,
        eligible,
        max_samples=max_samples,
        predicate=lambda listing: listing.status == "onder_bod",
        limit=1,
    )
    _extend_selected(
        selected,
        eligible,
        max_samples=max_samples,
        predicate=lambda listing: listing.status in {"unknown", "verkocht"},
        limit=1,
    )
    _extend_selected(
        selected,
        sorted(
            eligible,
            key=lambda listing: (
                listing.asking_price_eur is not None,
                listing.asking_price_eur or 0,
                listing.city,
            ),
            reverse=True,
        ),
        max_samples=max_samples,
        predicate=lambda listing: listing.status == "beschikbaar",
        limit=1,
    )
    _extend_selected(selected, eligible, max_samples=max_samples, predicate=lambda listing: True, limit=max_samples)

    return tuple(selected[:max_samples])


def extract_detail_property_type_candidates(html: str) -> tuple[str, ...]:
    return extract_detail_candidates(html).property_type_candidates


def extract_detail_badge_candidates(html: str) -> tuple[str, ...]:
    return extract_detail_candidates(html).badge_candidates


def extract_detail_candidates(html: str) -> _ExtractionResult:
    sections = _html_sections(html)
    property_candidates: list[str] = []
    badge_candidates: list[str] = []
    evidence: list[str] = []

    for source_name, text in sections:
        for candidate in PROPERTY_TYPE_CANDIDATES:
            if _contains_candidate(text, candidate):
                property_candidates.append(candidate)
                evidence.append(f"{source_name}:property_type:{candidate}")
        for candidate in BADGE_CANDIDATES:
            if source_name == "embedded_state" and candidate not in {"Open huis", "Open Huis", "open_huis", "openHouse"}:
                continue
            if source_name == "embedded_state" and candidate in {"Open huis", "Open Huis", "open_huis", "openHouse"}:
                lowered_text = text.casefold()
                if "false" in lowered_text or "openhouse\":[]" in lowered_text or "openhouse\\\":[]" in lowered_text:
                    continue
            if _contains_candidate(text, candidate):
                badge_candidates.append(candidate)
                evidence.append(f"{source_name}:badge:{candidate}")

    return _ExtractionResult(
        property_type_candidates=_dedupe_warnings(property_candidates),
        badge_candidates=_dedupe_warnings(badge_candidates),
        evidence_signals=_dedupe_warnings(evidence),
    )


def _fetch_parser_listings(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    max_pages: int,
) -> tuple[tuple[ParsedListing, ...], tuple[str, ...]]:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_config
        raise ValueError("missing_paginated_api_config")

    page_limit = min(max_pages, MAX_DETAIL_PROPERTY_TYPE_API_PAGES, max(0, api.max_pages - api.start_page + 1))
    listings: list[ParsedListing] = []
    warnings: list[str] = []
    for page in range(api.start_page, api.start_page + page_limit):
        try:
            api_url = build_paginated_api_url(config, page)
        except Exception:
            warnings.append("api_url_build_failed")
            continue

        can_fetch, robots_warnings = _robots_check_url(api_url)
        if not can_fetch:
            warnings.extend((*robots_warnings, "api_blocked_by_robots"))
            continue

        try:
            json_content = fetch_json(api_url)
            parser_input = build_parser_input_from_api_json(config, json_content, page=page)
            parser_result = ParserFamilyRunner().run(_fingerprint_for_config(config), parser_input)
        except Exception:
            warnings.append("api_fetch_or_parse_exception")
            continue

        listings.extend(parser_result.listings)
        warnings.extend(parser_result.warnings)

    return tuple(listings), _dedupe_warnings(warnings)


def _probe_detail_listing(
    listing: ParsedListing,
    *,
    fetch_html: Callable[[str], str],
) -> DetailPropertyTypeProbeSample:
    can_fetch, robots_warnings = _robots_check_url(listing.canonical_url)
    if not can_fetch:
        return _sample_from_listing(
            listing,
            can_fetch=False,
            fetch_status="blocked_by_robots",
            extraction=_ExtractionResult((), (), ()),
            warnings=robots_warnings,
        )

    try:
        html = fetch_html(listing.canonical_url)
    except Exception:
        return _sample_from_listing(
            listing,
            can_fetch=True,
            fetch_status="fetch_exception",
            extraction=_ExtractionResult((), (), ()),
        )

    extraction = extract_detail_candidates(html)
    warnings = ()
    if not extraction.property_type_candidates:
        warnings = ("no_property_type_candidates",)
    return _sample_from_listing(
        listing,
        can_fetch=True,
        fetch_status="success",
        extraction=extraction,
        warnings=warnings,
    )


def _sample_from_listing(
    listing: ParsedListing,
    *,
    can_fetch: bool,
    fetch_status: str,
    extraction: _ExtractionResult,
    warnings: tuple[str, ...] = (),
) -> DetailPropertyTypeProbeSample:
    return DetailPropertyTypeProbeSample(
        canonical_url=listing.canonical_url,
        address_raw=listing.address_raw,
        status=listing.status,
        transaction_type=listing.transaction_type,
        parser_property_type=listing.property_type,
        can_fetch=can_fetch,
        fetch_status=fetch_status,
        extracted_property_type_candidates=extraction.property_type_candidates,
        extracted_badge_candidates=extraction.badge_candidates,
        evidence_signals=extraction.evidence_signals,
        warnings=warnings,
    )


def _extend_selected(
    selected: list[ParsedListing],
    listings: Iterable[ParsedListing],
    *,
    max_samples: int,
    predicate: Callable[[ParsedListing], bool],
    limit: int,
) -> None:
    selected_urls = {listing.canonical_url for listing in selected}
    added = 0
    for listing in listings:
        if len(selected) >= max_samples or added >= limit:
            return
        if listing.canonical_url in selected_urls or not predicate(listing):
            continue
        selected.append(listing)
        selected_urls.add(listing.canonical_url)
        added += 1


def _html_sections(html: str) -> tuple[tuple[str, str], ...]:
    cleaned_html = html or ""
    sections: list[tuple[str, str]] = []

    for source_name, pattern in (("json_ld", _SCRIPT_PATTERN),):
        for match in pattern.finditer(cleaned_html):
            attrs = match.group("attrs")
            body = _normalize_text(match.group("body"))
            lowered_attrs = attrs.casefold()
            lowered_body = body.casefold()
            if "application/ld+json" in lowered_attrs:
                sections.append((source_name, _json_text(body)))
            else:
                sections.extend(_candidate_context_sections("embedded_state", body, window=160))

    for match in _META_PATTERN.finditer(cleaned_html):
        attrs = _normalize_text(match.group("attrs"))
        if attrs:
            sections.append(("meta", attrs))

    for marker_name, marker_pattern in (("breadcrumb", _BREADCRUMB_PATTERN), ("label_context", _LABEL_PATTERN)):
        for match in marker_pattern.finditer(cleaned_html):
            start = max(0, match.start() - 240)
            end = min(len(cleaned_html), match.end() + 240)
            sections.append((marker_name, _strip_tags(cleaned_html[start:end])))

    for match in _HEADING_PATTERN.finditer(cleaned_html):
        text = _strip_tags(match.group("body"))
        if any(_contains_candidate(text, candidate) for candidate in PROPERTY_TYPE_CANDIDATES):
            sections.append(("heading", text))

    for match in _BADGE_ELEMENT_PATTERN.finditer(cleaned_html):
        text = _strip_tags(match.group("body"))
        if any(_contains_candidate(text, candidate) for candidate in BADGE_CANDIDATES):
            sections.append(("badge_element", text))

    definition_cells = tuple(_strip_tags(match.group("body")) for match in _DEFINITION_PATTERN.finditer(cleaned_html))
    for index, text in enumerate(definition_cells):
        if _LABEL_PATTERN.search(text):
            context = " ".join(definition_cells[index : index + 2])
            sections.append(("definition_label", context))

    return tuple(sections)


def _candidate_context_sections(source_name: str, text: str, *, window: int) -> tuple[tuple[str, str], ...]:
    contexts: list[tuple[str, str]] = []
    for candidate in (*PROPERTY_TYPE_CANDIDATES, *BADGE_CANDIDATES):
        match = re.search(re.escape(candidate), text, re.IGNORECASE)
        if not match:
            continue
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        context = _normalize_text(text[start:end])
        normalized_context = context.casefold()
        if (
            _LABEL_PATTERN.search(context)
            or _BREADCRUMB_PATTERN.search(context)
            or "consumer.house.subtype" in normalized_context
            or "subtype" in normalized_context
            or "detailtype" in normalized_context
            or "status" in normalized_context
        ):
            contexts.append((source_name, context))
    return tuple(contexts)


def _json_text(value: str) -> str:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return _normalize_text(value)
    return _normalize_text(json.dumps(loaded, ensure_ascii=False))


def _strip_tags(value: str) -> str:
    return _normalize_text(_TAG_PATTERN.sub(" ", value))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _contains_candidate(text: str, candidate: str) -> bool:
    if not text:
        return False
    escaped = re.escape(candidate).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None


def _robots_check_url(url: str) -> tuple[bool, tuple[str, ...]]:
    parsed = _parse_http_url(url)
    if parsed is None:
        return False, ("invalid_url",)
    domain, path = parsed
    try:
        return robots_gate.can_fetch(domain, path) is True, ()
    except Exception:
        return False, ("robots_gate_exception",)


def _parse_http_url(url: str) -> tuple[str, str] | None:
    cleaned = (url or "").strip()
    scheme_separator = cleaned.find("://")
    if scheme_separator <= 0:
        return None
    scheme = cleaned[:scheme_separator].lower()
    if scheme not in {"http", "https"}:
        return None
    remainder = cleaned[scheme_separator + 3 :]
    slash_index = remainder.find("/")
    domain = remainder if slash_index < 0 else remainder[:slash_index]
    path = "/" if slash_index < 0 else remainder[slash_index:] or "/"
    if not domain or any(separator in domain for separator in ("/", "?", "#")):
        return None
    fragment_index = path.find("#")
    if fragment_index >= 0:
        path = path[:fragment_index] or "/"
    return domain.lower(), path


def _validate_config(config: ParserSourceConfig) -> None:
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
        evidence_signals=("ogonline", "detail_property_type_probe"),
        blocking_signals=(),
        recommended_action="diagnostic_probe",
        can_proceed_to_parser_family=True,
        reason="ogonline_detail_property_type_probe",
    )


def _dedupe_warnings(warnings: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.add(warning)
            result.append(warning)
    return tuple(result)
