from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from html import unescape
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
from domek_wonen.qa import qa_parser_family_result
from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .live_fetch import controlled_http_fetch_html
from .ogonline_xhr_live_fetch import controlled_http_fetch_json


MAX_DETAIL_FACTS_SAMPLES = 20
DEFAULT_DETAIL_FACTS_SAMPLES = 10
MAX_DETAIL_FACTS_API_PAGES = 5
DEFAULT_DETAIL_FACTS_API_PAGES = 2
DESCRIPTION_PREVIEW_LIMIT = 120

FACT_FIELDS = (
    "property_type",
    "asking_price",
    "living_area_m2",
    "plot_area_m2",
    "rooms",
    "bedrooms",
    "bathrooms",
    "energy_label",
    "eigendomssituatie",
    "erfpacht_details",
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
    "short_description_source_available",
    "description_length_bucket",
    "possible_key_selling_points_source",
    "possible_attention_points_source",
)

PROPERTY_TYPE_CANDIDATES = (
    "Vrijstaande woning",
    "Tussenwoning",
    "Hoekwoning",
    "Twee-onder-een-kap",
    "Herenhuis",
    "Benedenwoning",
    "Bovenwoning",
    "Maisonette",
    "Appartement",
    "Woonhuis",
    "Bouwgrond",
)

_TAG_PATTERN = re.compile(r"<[^>]+>")
_SCRIPT_PATTERN = re.compile(r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
_META_PATTERN = re.compile(r"<meta\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_KEY_PATTERN = re.compile(r"(description|omschrijving|aanbiedingstekst|intro|summary)", re.IGNORECASE)
_PRICE_PATTERN = re.compile(r"(?:vraagprijs|koopprijs|askingPrice|salesPrice|price)[^0-9]{0,40}([0-9][0-9\., ]{4,})", re.IGNORECASE)
_INT_FIELD_PATTERNS: Mapping[str, tuple[re.Pattern[str], ...]] = {
    "living_area_m2": (
        re.compile(r"(?:woonoppervlakte|gebruiksoppervlakte wonen|\bwonen\b)[^0-9]{0,40}([0-9]{2,4})\s*(?:m2|m²)", re.IGNORECASE),
    ),
    "plot_area_m2": (
        re.compile(r"(?:perceeloppervlakte|\bperceel\b)[^0-9]{0,40}([0-9]{2,6})\s*(?:m2|m²)", re.IGNORECASE),
    ),
    "rooms": (
        re.compile(r"(?:aantal kamers|\bkamers\b)[^0-9]{0,30}([0-9]{1,2})", re.IGNORECASE),
    ),
    "bedrooms": (
        re.compile(r"(?:slaapkamers|aantal slaapkamers)[^0-9]{0,30}([0-9]{1,2})", re.IGNORECASE),
        re.compile(r"([0-9]{1,2})\s+slaapkamers", re.IGNORECASE),
    ),
    "bathrooms": (
        re.compile(r"(?:badkamers|aantal badkamers)[^0-9]{0,30}([0-9]{1,2})", re.IGNORECASE),
    ),
}
_ENERGY_LABEL_PATTERN = re.compile(r"(?:energielabel|energyLabel)[^A-G]{0,40}(A\+{0,4}|[B-G])", re.IGNORECASE)
_VVE_COST_PATTERN = re.compile(r"(?:vve|vereniging van eigenaars|servicekosten|bijdrage)[^0-9]{0,50}([0-9][0-9\., ]*)", re.IGNORECASE)
_AVAILABILITY_PATTERN = re.compile(r"(?:aanvaarding|beschikbaar(?:heid)?|availability)[^0-9a-z]{0,30}([0-9]{1,2}[-/ ][0-9]{1,2}[-/ ][0-9]{2,4}|in overleg|per direct)", re.IGNORECASE)
_HEATING_PATTERN = re.compile(r"(?:verwarming|heating)[^.;,\n]{0,80}", re.IGNORECASE)
_CV_PATTERN = re.compile(r"cv[-\s]?ketel[^.;,\n]{0,80}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class OGonlineDetailFactsProbeSample:
    canonical_url: str
    address_raw: str | None
    city: str | None
    fields_present: tuple[str, ...]
    field_values_preview: tuple[tuple[str, str], ...]
    extraction_sources: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OGonlineDetailFactsProbeResult:
    source_id: str
    source_domain: str
    samples_requested: int
    samples_attempted: int
    samples_succeeded: int
    samples_failed: int
    field_presence_counts: tuple[tuple[str, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    samples: tuple[OGonlineDetailFactsProbeSample, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _FactCandidate:
    field: str
    preview: str
    source: str
    warning: str = ""


@dataclass(frozen=True, slots=True)
class _DetailSource:
    canonical_url: str
    address_raw: str | None = None
    city: str | None = None
    status: str = ""
    property_type: str = ""
    asking_price_eur: int | None = None
    living_area_m2: int | None = None
    rooms_count: int | None = None
    bedrooms_count: int | None = None


def run_ogonline_detail_facts_probe(
    *,
    detail_urls: tuple[str, ...],
    source_id: str,
    source_domain: str,
    max_samples: int = DEFAULT_DETAIL_FACTS_SAMPLES,
    fetch_html: Callable[[str], str] = controlled_http_fetch_html,
) -> OGonlineDetailFactsProbeResult:
    requested, cap_warnings = _sample_limit(max_samples)
    sources = tuple(_DetailSource(canonical_url=url) for url in detail_urls[:requested] if url)
    samples, run_warnings = _probe_detail_sources(sources, fetch_html=fetch_html)
    return _result(
        source_id=source_id,
        source_domain=source_domain,
        samples_requested=requested,
        samples=samples,
        warnings=(*cap_warnings, *run_warnings),
    )


def run_kin_ogonline_detail_facts_probe(
    *,
    config_path: Path,
    max_api_pages: int = DEFAULT_DETAIL_FACTS_API_PAGES,
    max_samples: int = DEFAULT_DETAIL_FACTS_SAMPLES,
    fetch_json: Callable[[str], str] = controlled_http_fetch_json,
    fetch_html: Callable[[str], str] = controlled_http_fetch_html,
) -> OGonlineDetailFactsProbeResult:
    config = load_parser_source_config(config_path)
    return run_kin_ogonline_detail_facts_probe_config(
        config,
        fetch_json=fetch_json,
        fetch_html=fetch_html,
        max_api_pages=max_api_pages,
        max_samples=max_samples,
    )


def run_kin_ogonline_detail_facts_probe_config(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    fetch_html: Callable[[str], str],
    max_api_pages: int = DEFAULT_DETAIL_FACTS_API_PAGES,
    max_samples: int = DEFAULT_DETAIL_FACTS_SAMPLES,
) -> OGonlineDetailFactsProbeResult:
    _validate_config(config)
    requested, sample_warnings = _sample_limit(max_samples)
    page_limit, page_warnings = _api_page_limit(max_api_pages)
    if page_limit <= 0 or requested <= 0:
        return _result(
            source_id=config.source_id,
            source_domain=config.source_domain,
            samples_requested=max(0, requested),
            samples=(),
            warnings=_dedupe((*sample_warnings, *page_warnings, "max_api_pages_or_samples_not_positive")),
        )

    api_config = _config_with_page_limit(config, page_limit)
    listings, listing_warnings = _fetch_qa_clean_listings(api_config, fetch_json=fetch_json, max_api_pages=page_limit)
    selected = select_detail_fact_probe_listings(listings, max_samples=requested)
    sources = tuple(_source_from_listing(listing) for listing in selected)
    samples, detail_warnings = _probe_detail_sources(sources, fetch_html=fetch_html)
    return _result(
        source_id=config.source_id,
        source_domain=config.source_domain,
        samples_requested=requested,
        samples=samples,
        warnings=_dedupe((*sample_warnings, *page_warnings, *listing_warnings, *detail_warnings)),
    )


def select_detail_fact_probe_listings(
    listings: Iterable[ParsedListing],
    *,
    max_samples: int = DEFAULT_DETAIL_FACTS_SAMPLES,
) -> tuple[ParsedListing, ...]:
    if max_samples <= 0:
        return ()
    limit = min(max_samples, MAX_DETAIL_FACTS_SAMPLES)
    eligible = tuple(listing for listing in listings if listing.canonical_url)
    selected: list[ParsedListing] = []

    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: item.status == "beschikbaar", limit=3)
    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: item.status == "onder_bod", limit=2)
    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: item.status == "unknown", limit=1)
    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: item.property_type == "appartement", limit=2)
    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: item.property_type in {"woonhuis", "tussenwoning", "vrijstaande_woning"}, limit=2)
    _extend_selected(
        selected,
        sorted(eligible, key=lambda item: (item.asking_price_eur is not None, item.asking_price_eur or 0), reverse=True),
        max_samples=limit,
        predicate=lambda item: True,
        limit=2,
    )
    _extend_selected(selected, eligible, max_samples=limit, predicate=lambda item: True, limit=limit)
    return tuple(selected[:limit])


def extract_detail_fact_candidates(html: str) -> tuple[_FactCandidate, ...]:
    sections = _html_sections(html)
    candidates: list[_FactCandidate] = []

    for source, text in sections:
        _append_text_candidates(candidates, source, text)

    embedded_values = _embedded_state_values(html)
    for source, payload in embedded_values:
        _append_mapping_candidates(candidates, source, payload)

    return tuple(_dedupe_candidates(candidates))


def build_detail_facts_probe_sample(
    *,
    canonical_url: str,
    html: str,
    address_raw: str | None = None,
    city: str | None = None,
) -> OGonlineDetailFactsProbeSample:
    candidates = extract_detail_fact_candidates(html)
    fields = _dedupe(candidate.field for candidate in candidates)
    previews = _safe_previews(candidates)
    sources = _dedupe_pairs((candidate.field, candidate.source) for candidate in candidates)
    warnings = _dedupe(candidate.warning for candidate in candidates if candidate.warning)
    missing = tuple(field for field in FACT_FIELDS if field not in fields)
    if missing:
        warnings = _dedupe((*warnings, "missing_fact_source"))

    return OGonlineDetailFactsProbeSample(
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        fields_present=fields,
        field_values_preview=previews,
        extraction_sources=sources,
        warnings=warnings,
    )


def _probe_detail_sources(
    sources: Iterable[_DetailSource],
    *,
    fetch_html: Callable[[str], str],
) -> tuple[tuple[OGonlineDetailFactsProbeSample, ...], tuple[str, ...]]:
    samples: list[OGonlineDetailFactsProbeSample] = []
    for source in sources:
        can_fetch, robots_warnings = _robots_check_url(source.canonical_url)
        if not can_fetch:
            sample_warnings = _dedupe((*robots_warnings, "blocked_by_robots"))
            samples.append(_failed_sample(source, sample_warnings))
            continue
        try:
            html = fetch_html(source.canonical_url)
        except Exception:
            samples.append(_failed_sample(source, ("fetch_exception",)))
            continue

        sample = build_detail_facts_probe_sample(
            canonical_url=source.canonical_url,
            html=html,
            address_raw=source.address_raw,
            city=source.city,
        )
        samples.append(_sample_with_listing_fallbacks(sample, source))
    return tuple(samples), ()


def _fetch_qa_clean_listings(
    config: ParserSourceConfig,
    *,
    fetch_json: Callable[[str], str],
    max_api_pages: int,
) -> tuple[tuple[ParsedListing, ...], tuple[str, ...]]:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_config
        raise ValueError("missing_paginated_api_config")

    listings: list[ParsedListing] = []
    warnings: list[str] = []
    page_count = min(max_api_pages, max(0, api.max_pages - api.start_page + 1))
    for page in range(api.start_page, api.start_page + page_count):
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
            qa_result = qa_parser_family_result(parser_result)
        except Exception:
            warnings.append("api_fetch_or_parse_exception")
            continue
        listings.extend(qa_listing.listing for qa_listing in qa_result.clean_listings)
        warnings.extend((*parser_result.warnings, *qa_result.warnings))
    return tuple(listings), _dedupe(warnings)


def _append_text_candidates(candidates: list[_FactCandidate], source: str, text: str) -> None:
    normalized = _normalize_text(text)
    if not normalized:
        return

    for property_type in PROPERTY_TYPE_CANDIDATES:
        if _contains_phrase(normalized, property_type):
            candidates.append(_FactCandidate("property_type", property_type, source))

    price = _first_pattern_value(_PRICE_PATTERN, normalized)
    if price:
        candidates.append(_FactCandidate("asking_price", _preview_number(price), source))

    for field, patterns in _INT_FIELD_PATTERNS.items():
        for pattern in patterns:
            value = _first_pattern_value(pattern, normalized)
            if value:
                candidates.append(_FactCandidate(field, _preview_number(value), source))
                break

    energy_label = _first_pattern_value(_ENERGY_LABEL_PATTERN, normalized)
    if energy_label:
        candidates.append(_FactCandidate("energy_label", energy_label.upper(), source))

    if _contains_any(normalized, ("volle eigendom", "eigen grond", "erfpacht")):
        candidates.append(_FactCandidate("eigendomssituatie", _context_preview(normalized, ("volle eigendom", "eigen grond", "erfpacht")), source))
    if _contains_any(normalized, ("erfpacht", "canon")):
        candidates.append(_FactCandidate("erfpacht_details", "source_available", source))

    vve_cost = _first_pattern_value(_VVE_COST_PATTERN, normalized)
    if vve_cost:
        candidates.append(_FactCandidate("vve_monthly_cost", _preview_number(vve_cost), source))
    if _contains_any(normalized, ("vve", "vereniging van eigenaars")):
        candidates.append(_FactCandidate("vve_active", "source_available", source))

    heating = _first_match_text(_HEATING_PATTERN, normalized)
    if heating:
        candidates.append(_FactCandidate("heating_type", _cap_preview(heating), source))
    cv = _first_match_text(_CV_PATTERN, normalized)
    if cv:
        candidates.append(_FactCandidate("cv_ketel_present", "true", source))
        if _contains_any(cv, ("huur", "gehuurd", "lease")):
            candidates.append(_FactCandidate("cv_ketel_ownership", "huur", source))
        elif _contains_any(cv, ("eigendom", "owned")):
            candidates.append(_FactCandidate("cv_ketel_ownership", "eigendom", source))

    for field, phrases in (
        ("outdoor_space", ("buitenruimte", "terras", "tuin", "balkon", "dakterras")),
        ("garden", ("tuin", "achtertuin", "voortuin")),
        ("balcony", ("balkon",)),
        ("storage", ("berging", "schuur", "opslag")),
        ("garage", ("garage",)),
        ("parking", ("parkeerplaats", "parkeren", "eigen oprit")),
        ("open_huis_badge_or_event", ("open huis", "openhouse")),
        ("possible_key_selling_points_source", ("highlights", "pluspunten", "kenmerken", "bijzonderheden")),
        ("possible_attention_points_source", ("aandachtspunt", "let op", "kluswoning", "asbest", "fundering")),
    ):
        if _contains_any(normalized, phrases):
            candidates.append(_FactCandidate(field, "source_available", source))

    availability = _first_pattern_value(_AVAILABILITY_PATTERN, normalized)
    if availability:
        candidates.append(_FactCandidate("availability_date", _cap_preview(availability), source))

    description = _description_from_text(source, normalized)
    if description:
        bucket = _description_bucket(description)
        candidates.append(_FactCandidate("short_description_source_available", "true", source))
        candidates.append(_FactCandidate("description_length_bucket", bucket, source))
        if len(description) > DESCRIPTION_PREVIEW_LIMIT:
            candidates.append(
                _FactCandidate(
                    "short_description_source_available",
                    _cap_preview(description),
                    source,
                    "description_preview_capped",
                )
            )


def _append_mapping_candidates(candidates: list[_FactCandidate], source: str, payload: Mapping[str, Any]) -> None:
    flat = tuple(_flatten_mapping(payload))
    for path, value in flat:
        path_text = ".".join(path).casefold()
        text = _value_text(value)
        if not text:
            continue

        field = _field_from_path(path_text)
        if field:
            preview = _preview_for_field(field, text)
            candidates.append(_FactCandidate(field, preview, source))
            continue

        lower_text = text.casefold()
        if _contains_any(lower_text, ("energielabel", "woonoppervlakte", "perceeloppervlakte", "vve", "cv-ketel")):
            _append_text_candidates(candidates, source, f"{path_text} {text}")


def _field_from_path(path_text: str) -> str:
    checks = (
        ("property_type", ("subtype", "propertytype", "woningtype", "objecttype", "housetype")),
        ("asking_price", ("askingprice", "salesprice", "purchaseprice", "vraagprijs", "price.amount", "price.value")),
        ("living_area_m2", ("livingarea", "living_area", "woonoppervlakte", "area_living")),
        ("plot_area_m2", ("plotarea", "plot_area", "perceeloppervlakte")),
        ("rooms", ("rooms", "aantalkamers", "numberofrooms")),
        ("bedrooms", ("bedrooms", "slaapkamers", "numberofbedrooms")),
        ("bathrooms", ("bathrooms", "badkamers", "numberofbathrooms")),
        ("energy_label", ("energylabel", "energielabel")),
        ("eigendomssituatie", ("eigendom", "ownership")),
        ("erfpacht_details", ("erfpacht", "leasehold")),
        ("vve_monthly_cost", ("vvecost", "servicekosten", "servicecost")),
        ("vve_active", ("vve",)),
        ("heating_type", ("heating", "verwarming")),
        ("cv_ketel_present", ("cvketel", "cv_ketel")),
        ("outdoor_space", ("outdoorspace", "buitenruimte", "terrace")),
        ("garden", ("garden", "tuin")),
        ("balcony", ("balcony", "balkon")),
        ("storage", ("storage", "berging")),
        ("garage", ("garage",)),
        ("parking", ("parking", "parkeren")),
        ("availability_date", ("availability", "aanvaarding")),
        ("open_huis_badge_or_event", ("openhouse", "open_huis", "viewing")),
        ("short_description_source_available", ("description", "omschrijving", "summary")),
    )
    compact = path_text.replace("_", "").replace("-", "")
    for field, tokens in checks:
        if any(token.replace("_", "").replace("-", "") in compact for token in tokens):
            return field
    return ""


def _preview_for_field(field: str, value: str) -> str:
    if field == "short_description_source_available":
        return "true"
    if field in {"possible_key_selling_points_source", "possible_attention_points_source"}:
        return "source_available"
    return _cap_preview(value)


def _html_sections(html: str) -> tuple[tuple[str, str], ...]:
    cleaned = html or ""
    sections: list[tuple[str, str]] = []
    for match in _SCRIPT_PATTERN.finditer(cleaned):
        attrs = match.group("attrs")
        body = match.group("body")
        if "application/ld+json" in attrs.casefold():
            sections.append(("json_ld", _json_text(body)))
        else:
            sections.append(("embedded_state", _normalize_text(body)))
    for match in _META_PATTERN.finditer(cleaned):
        attrs = _normalize_text(match.group("attrs"))
        if attrs:
            sections.append(("metadata", attrs))
    html_text = _strip_tags(cleaned)
    if html_text:
        sections.append(("html_text_signal", html_text))
    return tuple(sections)


def _embedded_state_values(html: str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    values: list[tuple[str, Mapping[str, Any]]] = []
    for match in _SCRIPT_PATTERN.finditer(html or ""):
        attrs = match.group("attrs")
        body = match.group("body").strip()
        source = "json_ld" if "application/ld+json" in attrs.casefold() else "embedded_state"
        for json_text in _json_object_strings(body):
            try:
                loaded = json.loads(json_text)
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, Mapping):
                values.append((source, loaded))
    return tuple(values)


def _json_object_strings(text: str) -> tuple[str, ...]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return (stripped,)
    results: list[str] = []
    for match in re.finditer(r"\{", stripped):
        depth = 0
        for index in range(match.start(), len(stripped)):
            char = stripped[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    results.append(stripped[match.start() : index + 1])
                    break
    return tuple(results)


def _flatten_mapping(payload: Mapping[str, Any], path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    for key, value in payload.items():
        next_path = (*path, str(key))
        if isinstance(value, Mapping):
            yield from _flatten_mapping(value, next_path)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, item in enumerate(value[:10]):
                item_path = (*next_path, str(index))
                if isinstance(item, Mapping):
                    yield from _flatten_mapping(item, item_path)
                else:
                    yield item_path, item
        else:
            yield next_path, value


def _safe_previews(candidates: Iterable[_FactCandidate]) -> tuple[tuple[str, str], ...]:
    previews: list[tuple[str, str]] = []
    seen_fields: set[str] = set()
    for candidate in candidates:
        if candidate.field in seen_fields:
            continue
        preview = _cap_preview(candidate.preview)
        if preview:
            previews.append((candidate.field, preview))
            seen_fields.add(candidate.field)
    return tuple(previews)


def _failed_sample(source: _DetailSource, warnings: tuple[str, ...]) -> OGonlineDetailFactsProbeSample:
    return OGonlineDetailFactsProbeSample(
        canonical_url=source.canonical_url,
        address_raw=source.address_raw,
        city=source.city,
        fields_present=(),
        field_values_preview=(),
        extraction_sources=(),
        warnings=warnings,
    )


def _sample_with_listing_fallbacks(
    sample: OGonlineDetailFactsProbeSample,
    source: _DetailSource,
) -> OGonlineDetailFactsProbeSample:
    fallback_candidates: list[_FactCandidate] = []
    if source.property_type:
        fallback_candidates.append(_FactCandidate("property_type", source.property_type, "metadata"))
    if source.asking_price_eur is not None:
        fallback_candidates.append(_FactCandidate("asking_price", str(source.asking_price_eur), "metadata"))
    if source.living_area_m2 is not None:
        fallback_candidates.append(_FactCandidate("living_area_m2", str(source.living_area_m2), "metadata"))
    if source.rooms_count is not None:
        fallback_candidates.append(_FactCandidate("rooms", str(source.rooms_count), "metadata"))
    if source.bedrooms_count is not None:
        fallback_candidates.append(_FactCandidate("bedrooms", str(source.bedrooms_count), "metadata"))
    if not fallback_candidates:
        return sample
    fields = _dedupe((*sample.fields_present, *(candidate.field for candidate in fallback_candidates)))
    previews = _dedupe_pairs((*sample.field_values_preview, *_safe_previews(fallback_candidates)))
    sources = _dedupe_pairs((*sample.extraction_sources, *((candidate.field, candidate.source) for candidate in fallback_candidates)))
    return OGonlineDetailFactsProbeSample(
        canonical_url=sample.canonical_url,
        address_raw=sample.address_raw,
        city=sample.city,
        fields_present=fields,
        field_values_preview=previews,
        extraction_sources=sources,
        warnings=sample.warnings,
    )


def _result(
    *,
    source_id: str,
    source_domain: str,
    samples_requested: int,
    samples: tuple[OGonlineDetailFactsProbeSample, ...],
    warnings: tuple[str, ...],
) -> OGonlineDetailFactsProbeResult:
    raw_warnings = (*warnings, *(warning for sample in samples for warning in sample.warnings))
    return OGonlineDetailFactsProbeResult(
        source_id=source_id,
        source_domain=source_domain,
        samples_requested=samples_requested,
        samples_attempted=len(samples),
        samples_succeeded=sum(1 for sample in samples if sample.fields_present),
        samples_failed=sum(1 for sample in samples if not sample.fields_present),
        field_presence_counts=_counter_pairs(field for sample in samples for field in sample.fields_present),
        warning_counts=_counter_pairs(raw_warnings),
        samples=samples,
        warnings=_dedupe(raw_warnings),
    )


def _sample_limit(max_samples: int) -> tuple[int, tuple[str, ...]]:
    if max_samples <= 0:
        return 0, ("max_samples_must_be_positive",)
    if max_samples > MAX_DETAIL_FACTS_SAMPLES:
        return MAX_DETAIL_FACTS_SAMPLES, ("max_samples_capped_at_20",)
    return max_samples, ()


def _api_page_limit(max_api_pages: int) -> tuple[int, tuple[str, ...]]:
    if max_api_pages <= 0:
        return 0, ("max_api_pages_must_be_positive",)
    if max_api_pages > MAX_DETAIL_FACTS_API_PAGES:
        return MAX_DETAIL_FACTS_API_PAGES, ("max_api_pages_capped_at_5",)
    return max_api_pages, ()


def _source_from_listing(listing: ParsedListing) -> _DetailSource:
    return _DetailSource(
        canonical_url=listing.canonical_url,
        address_raw=listing.address_raw or None,
        city=listing.city or None,
        status=listing.status,
        property_type=listing.property_type,
        asking_price_eur=listing.asking_price_eur,
        living_area_m2=listing.living_area_m2,
        rooms_count=listing.rooms_count,
        bedrooms_count=listing.bedrooms_count,
    )


def _config_with_page_limit(config: ParserSourceConfig, pages: int) -> ParserSourceConfig:
    api = config.api
    if api is None:  # pragma: no cover - guarded by _validate_config
        raise ValueError("missing_paginated_api_config")
    required_max_page = api.start_page + pages - 1
    return replace(config, api=replace(api, max_pages=max(api.max_pages, required_max_page)))


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
        evidence_signals=("ogonline", "detail_facts_probe"),
        blocking_signals=(),
        recommended_action="diagnostic_probe",
        can_proceed_to_parser_family=True,
        reason="ogonline_detail_facts_probe",
    )


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


def _value_text(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, float)):
        return _normalize_text(str(value))
    return ""


def _contains_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    lowered = text.casefold()
    return any(phrase.casefold() in lowered for phrase in phrases)


def _first_pattern_value(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return _normalize_text(match.group(1)) if match else ""


def _first_match_text(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return _normalize_text(match.group(0)) if match else ""


def _preview_number(value: str) -> str:
    return re.sub(r"[^\d]", "", value) or _cap_preview(value)


def _context_preview(text: str, phrases: Iterable[str]) -> str:
    lowered = text.casefold()
    for phrase in phrases:
        index = lowered.find(phrase.casefold())
        if index >= 0:
            return _cap_preview(text[index : index + 80])
    return "source_available"


def _description_from_text(source: str, text: str) -> str:
    if source == "metadata" and not _DESCRIPTION_KEY_PATTERN.search(text):
        return ""
    if _DESCRIPTION_KEY_PATTERN.search(text) or len(text) >= 80:
        return text
    return ""


def _description_bucket(description: str) -> str:
    length = len(description)
    if length < 250:
        return "short"
    if length < 1000:
        return "medium"
    return "long"


def _cap_preview(value: str) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= DESCRIPTION_PREVIEW_LIMIT:
        return normalized
    return normalized[:DESCRIPTION_PREVIEW_LIMIT].rstrip()


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _dedupe_pairs(values: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for left, right in values:
        pair = (left, right)
        if left and right and pair not in seen:
            seen.add(pair)
            result.append(pair)
    return tuple(result)


def _dedupe_candidates(candidates: Iterable[_FactCandidate]) -> tuple[_FactCandidate, ...]:
    seen: set[tuple[str, str, str]] = set()
    result: list[_FactCandidate] = []
    for candidate in candidates:
        key = (candidate.field, candidate.preview, candidate.source)
        if candidate.field and candidate.preview and key not in seen:
            seen.add(key)
            result.append(candidate)
    field_sources: dict[str, set[str]] = {}
    for candidate in result:
        field_sources.setdefault(candidate.field, set()).add(candidate.preview.casefold())
    ambiguous_fields = {field for field, previews in field_sources.items() if len(previews) > 1 and field not in {"short_description_source_available"}}
    if not ambiguous_fields:
        return tuple(result)
    return tuple(
        _FactCandidate(candidate.field, candidate.preview, candidate.source, "ambiguous_fact_candidate")
        if candidate.field in ambiguous_fields and not candidate.warning
        else candidate
        for candidate in result
    )


def _counter_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(value for value in values if value).items()))
