from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlsplit

from domek_wonen.compliance import robots_gate
from domek_wonen.parsers.models import ParsedListing

from .live_fetch import controlled_http_fetch_html


FIELD_STATUS_AVAILABLE = "available"
FIELD_STATUS_REVIEW = "review"
FIELD_STATUS_MISSING = "missing"
FIELD_STATUSES = frozenset({FIELD_STATUS_AVAILABLE, FIELD_STATUS_REVIEW, FIELD_STATUS_MISSING})

EVIDENCE_PREVIEW_LIMIT = 120

PROBE_FIELDS = (
    "property_type",
    "asking_price",
    "availability",
    "rooms",
    "bedrooms",
    "bathrooms",
    "living_area_m2",
    "plot_area_m2",
    "volume_m3",
    "energy_label",
    "bouwjaar",
    "heating",
    "insulation",
    "garden",
    "parking",
    "garage",
    "vve",
    "ownership_or_erfpacht",
    "description_length_bucket",
)

_TAG_PATTERN = re.compile(r"<[^>]+>")
_SCRIPT_PATTERN = re.compile(r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
_H1_PATTERN = re.compile(r"<h1\b[^>]*>(?P<body>.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TITLE_PATTERN = re.compile(r"<title\b[^>]*>(?P<body>.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESCRIPTION_PATTERN = re.compile(
    r"<meta\b(?=[^>]*(?:name|property)\s*=\s*['\"](?:description|og:description)['\"])(?=[^>]*content\s*=\s*['\"](?P<content>[^'\"]*)['\"])[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_DL_PAIR_PATTERN = re.compile(
    r"<dt[^>]*>(?P<label>.*?)</dt>\s*<dd[^>]*>(?P<value>.*?)</dd>",
    re.IGNORECASE | re.DOTALL,
)
_TABLE_PAIR_PATTERN = re.compile(
    r"<tr[^>]*>\s*<t[hd][^>]*>(?P<label>.*?)</t[hd]>\s*<t[hd][^>]*>(?P<value>.*?)</t[hd]>",
    re.IGNORECASE | re.DOTALL,
)
_KENMERK_PAIR_PATTERN = re.compile(
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*kenmerkName[^'\"]*['\"][^>]*>(?P<label>.*?)</span>\s*"
    r"<span\b[^>]*class\s*=\s*['\"][^'\"]*kenmerkValue[^'\"]*['\"][^>]*>(?P<value>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
_CLASS_LABEL_VALUE_PATTERN = re.compile(
    r"<(?P<tag>div|li|p|span)\b[^>]*class\s*=\s*['\"][^'\"]*(?:kenmerk|feature|fact|specificatie|property)[^'\"]*['\"][^>]*>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_IMAGE_PATTERN = re.compile(r"<img\b", re.IGNORECASE)
_JSON_LD_PATTERN = re.compile(r"<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>", re.IGNORECASE)
_EMBEDDED_STATE_MARKER_PATTERN = re.compile(
    r"(__NEXT_DATA__|window\.__|window\[[\"']__|dataLayer|objectId|realworks)",
    re.IGNORECASE,
)
_REALWORKS_MARKER_PATTERN = re.compile(
    r"(realworks\.nl|static\.realworks\.nl|images\.realworks\.nl|aanbodEntry|data-paginatable|objectId)",
    re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_NUMBER_PATTERN = re.compile(r"\d[\d\., ]*")
_ENERGY_VALUE_PATTERN = re.compile(r"^(?:energielabel\s*)?(A(?:\s*\+){0,4}|[B-G])$", re.IGNORECASE)

_LABEL_TO_FIELD: Mapping[str, str] = {
    "aanvaarding": "availability",
    "aantal badkamers": "bathrooms",
    "aantal garages": "garage",
    "aantal kamers": "rooms",
    "aantal slaapkamers": "bedrooms",
    "badkamers": "bathrooms",
    "bouwjaar": "bouwjaar",
    "cv ketel": "heating",
    "cv-ketel": "heating",
    "c.v.-ketel": "heating",
    "eigendomssituatie": "ownership_or_erfpacht",
    "energielabel": "energy_label",
    "energieklasse": "energy_label",
    "erfpacht": "ownership_or_erfpacht",
    "garage": "garage",
    "garagetypes": "garage",
    "hoofdtype": "property_type",
    "inhoud": "volume_m3",
    "isolatie": "insulation",
    "kamers": "rooms",
    "koopprijs": "asking_price",
    "parkeertypes": "parking",
    "parkeren": "parking",
    "parkeerfaciliteiten": "parking",
    "perceel": "plot_area_m2",
    "perceeloppervlakte": "plot_area_m2",
    "slaapkamers": "bedrooms",
    "status": "availability",
    "soort object": "property_type",
    "tuin": "garden",
    "tuintypes": "garden",
    "verwarming": "heating",
    "vraagprijs": "asking_price",
    "vve": "vve",
    "vve bijdrage": "vve",
    "woonoppervlakte": "living_area_m2",
    "woningtype": "property_type",
}

_FIELD_VALUE_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "asking_price": re.compile(r"(?:eur|euro|€)\s*([\d][\d\., ]*)", re.IGNORECASE),
    "living_area_m2": re.compile(r"(\d{2,4})\s*(?:m2|m\^2|m²)", re.IGNORECASE),
    "plot_area_m2": re.compile(r"(\d{1,6})\s*(?:m2|m\^2|m²)", re.IGNORECASE),
    "volume_m3": re.compile(r"(\d{2,6})\s*(?:m3|m\^3|m³)", re.IGNORECASE),
    "rooms": re.compile(r"(\d{1,2})", re.IGNORECASE),
    "bedrooms": re.compile(r"(\d{1,2})", re.IGNORECASE),
    "bathrooms": re.compile(r"(\d{1,2})", re.IGNORECASE),
    "bouwjaar": re.compile(r"\b(1[89]\d{2}|20\d{2})\b"),
}


@dataclass(frozen=True, slots=True)
class RealworksDetailFieldProbe:
    field: str
    status: str
    label: str = ""
    normalized_value: str | int | None = None
    evidence_preview: str = ""
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.field not in PROBE_FIELDS:
            raise ValueError(f"Unsupported Realworks detail probe field: {self.field}")
        if self.status not in FIELD_STATUSES:
            raise ValueError(f"Unsupported Realworks detail probe status: {self.status}")
        object.__setattr__(self, "evidence_preview", _cap_preview(self.evidence_preview))
        object.__setattr__(self, "warnings", _dedupe(self.warnings))


@dataclass(frozen=True, slots=True)
class RealworksDetailFactsProbeSample:
    canonical_url: str
    http_status: int | None
    content_type: str
    robots_allowed: bool
    detail_fetch_status: str
    page_title_or_h1_preview: str
    has_fact_table: bool
    has_definition_list: bool
    has_realworks_markers: bool
    has_json_ld: bool
    has_embedded_state: bool
    has_description: bool
    description_length_bucket: str
    has_images: bool
    image_count: int
    labels_found: tuple[str, ...]
    fields: tuple[RealworksDetailFieldProbe, ...]
    address_raw: str = ""
    asking_price_eur: int | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RealworksDetailFactsProbeResult:
    source_id: str
    source_domain: str
    detail_pages_attempted: int
    detail_pages_succeeded: int
    detail_pages_failed: int
    robots_allowed_count: int
    robots_blocked_count: int
    field_availability_counts: tuple[tuple[str, int, int, int], ...]
    warning_counts: tuple[tuple[str, int], ...]
    samples: tuple[RealworksDetailFactsProbeSample, ...]
    warnings: tuple[str, ...] = ()


def build_realworks_detail_facts_probe_sample(
    *,
    canonical_url: str,
    html: str,
    http_status: int | None = None,
    content_type: str = "",
    robots_allowed: bool = True,
    detail_fetch_status: str = "success",
    address_raw: str = "",
    asking_price_eur: int | None = None,
) -> RealworksDetailFactsProbeSample:
    label_values = _extract_label_values(html)
    labels_found = _dedupe(label for label, _value in label_values)
    description_text = _description_text(html)
    description_bucket = _description_length_bucket(description_text)
    fields = list(_fields_from_label_values(label_values))
    fields.append(
        RealworksDetailFieldProbe(
            field="description_length_bucket",
            status=FIELD_STATUS_AVAILABLE if description_bucket != "none" else FIELD_STATUS_MISSING,
            normalized_value=description_bucket,
            evidence_preview=description_bucket,
        )
    )
    by_field = {field.field: field for field in fields}
    complete_fields = tuple(by_field.get(field) or _missing_field(field) for field in PROBE_FIELDS)
    return RealworksDetailFactsProbeSample(
        canonical_url=canonical_url,
        http_status=http_status,
        content_type=content_type,
        robots_allowed=robots_allowed,
        detail_fetch_status=detail_fetch_status,
        page_title_or_h1_preview=_page_title_or_h1(html),
        has_fact_table=bool(_TABLE_PAIR_PATTERN.search(html or "") or _KENMERK_PAIR_PATTERN.search(html or "")),
        has_definition_list=bool(_DL_PAIR_PATTERN.search(html or "")),
        has_realworks_markers=bool(_REALWORKS_MARKER_PATTERN.search(html or "")),
        has_json_ld=bool(_JSON_LD_PATTERN.search(html or "")),
        has_embedded_state=bool(_EMBEDDED_STATE_MARKER_PATTERN.search(html or "")),
        has_description=description_bucket != "none",
        description_length_bucket=description_bucket,
        has_images=bool(_IMAGE_PATTERN.search(html or "")),
        image_count=len(_IMAGE_PATTERN.findall(html or "")),
        labels_found=labels_found,
        fields=complete_fields,
        address_raw=address_raw,
        asking_price_eur=asking_price_eur,
        warnings=_sample_warnings(complete_fields),
    )


def run_realworks_detail_facts_probe(
    *,
    listings: Iterable[ParsedListing],
    source_id: str,
    source_domain: str,
    max_detail_fetches: int = 9,
    fetch_html: Callable[[str], str] = controlled_http_fetch_html,
) -> RealworksDetailFactsProbeResult:
    samples: list[RealworksDetailFactsProbeSample] = []
    warnings: list[str] = []
    selected = tuple(listing for listing in listings if listing.canonical_url)[: max(0, max_detail_fetches)]
    for listing in selected:
        can_fetch, robots_warnings = _robots_check_url(listing.canonical_url)
        warnings.extend(robots_warnings)
        if not can_fetch:
            samples.append(_failed_sample(listing, "blocked_by_robots", False, (*robots_warnings, "blocked_by_robots")))
            continue
        try:
            html = fetch_html(listing.canonical_url)
        except Exception:
            samples.append(_failed_sample(listing, "fetch_failed", True, ("detail_fetch_exception",)))
            warnings.append("detail_fetch_exception")
            continue
        samples.append(
            build_realworks_detail_facts_probe_sample(
                canonical_url=listing.canonical_url,
                html=html,
                http_status=200,
                content_type="text/html",
                robots_allowed=True,
                address_raw=listing.address_raw,
                asking_price_eur=listing.asking_price_eur,
            )
        )

    return _result(source_id=source_id, source_domain=source_domain, samples=samples, warnings=warnings)


def _extract_label_values(html: str) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for pattern in (_DL_PAIR_PATTERN, _TABLE_PAIR_PATTERN, _KENMERK_PAIR_PATTERN):
        for match in pattern.finditer(html or ""):
            label = _normalize_label(_strip_tags(match.group("label")))
            value = _normalize_text(_strip_tags(match.group("value")))
            if label and value:
                pairs.append((label, value))
    for match in _CLASS_LABEL_VALUE_PATTERN.finditer(html or ""):
        body = match.group("body")
        texts = _split_compact_lines(_strip_tags(body))
        if len(texts) >= 2:
            label = _normalize_label(texts[0])
            value = _normalize_text(" ".join(texts[1:]))
            if label and value:
                pairs.append((label, value))
    return tuple(_dedupe_pairs(pairs))


def _fields_from_label_values(label_values: Iterable[tuple[str, str]]) -> tuple[RealworksDetailFieldProbe, ...]:
    fields: dict[str, RealworksDetailFieldProbe] = {}
    for label, value in label_values:
        field = _LABEL_TO_FIELD.get(label)
        if not field:
            continue
        probe = _field_probe(field=field, label=label, value=value)
        existing = fields.get(field)
        if existing is None or _field_rank(probe) > _field_rank(existing):
            fields[field] = probe
    return tuple(fields.values())


def _field_probe(*, field: str, label: str, value: str) -> RealworksDetailFieldProbe:
    warnings: list[str] = []
    normalized: str | int | None
    status = FIELD_STATUS_AVAILABLE
    if field in _FIELD_VALUE_PATTERNS:
        normalized = _extract_number_or_year(field, value)
        if normalized is None:
            status = FIELD_STATUS_REVIEW
            warnings.append("normalization_failed")
    elif field == "energy_label":
        normalized = _normalize_energy_label(value)
        if normalized is None:
            status = FIELD_STATUS_REVIEW
            warnings.append("energy_label_not_explicit")
    elif field == "ownership_or_erfpacht":
        normalized = _ownership_value(label, value)
        if normalized is None:
            status = FIELD_STATUS_MISSING
            warnings.append("no_affirmative_ownership_or_erfpacht")
    elif field == "vve":
        normalized = _cap_preview(value)
    else:
        normalized = _cap_preview(value)
    return RealworksDetailFieldProbe(
        field=field,
        status=status,
        label=label,
        normalized_value=normalized,
        evidence_preview=value,
        warnings=warnings,
    )


def _extract_number_or_year(field: str, value: str) -> int | None:
    pattern = _FIELD_VALUE_PATTERNS[field]
    match = pattern.search(value or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def _normalize_energy_label(value: str) -> str | None:
    match = _ENERGY_VALUE_PATTERN.match(_normalize_text(value))
    if not match:
        return None
    return match.group(1).upper().replace(" ", "")


def _ownership_value(label: str, value: str) -> str | None:
    text = _normalize_text(value)
    if label == "erfpacht" and ("geen erfpacht" in text or text in {"geen", "nee", "niet van toepassing"}):
        return None
    if "erfpacht" in text:
        return "erfpacht"
    if "volle eigendom" in text:
        return "volle_eigendom"
    if "eigen grond" in text:
        return "eigen_grond"
    return None


def _failed_sample(
    listing: ParsedListing,
    status: str,
    robots_allowed: bool,
    warnings: tuple[str, ...],
) -> RealworksDetailFactsProbeSample:
    return RealworksDetailFactsProbeSample(
        canonical_url=listing.canonical_url,
        http_status=None,
        content_type="",
        robots_allowed=robots_allowed,
        detail_fetch_status=status,
        page_title_or_h1_preview="",
        has_fact_table=False,
        has_definition_list=False,
        has_realworks_markers=False,
        has_json_ld=False,
        has_embedded_state=False,
        has_description=False,
        description_length_bucket="none",
        has_images=False,
        image_count=0,
        labels_found=(),
        fields=tuple(_missing_field(field) for field in PROBE_FIELDS),
        address_raw=listing.address_raw,
        asking_price_eur=listing.asking_price_eur,
        warnings=_dedupe(warnings),
    )


def _result(
    *,
    source_id: str,
    source_domain: str,
    samples: list[RealworksDetailFactsProbeSample],
    warnings: Iterable[str],
) -> RealworksDetailFactsProbeResult:
    detail_pages_succeeded = sum(1 for sample in samples if sample.detail_fetch_status == "success")
    field_counts: list[tuple[str, int, int, int]] = []
    for field in PROBE_FIELDS:
        statuses = Counter(
            probe.status
            for sample in samples
            for probe in sample.fields
            if probe.field == field
        )
        field_counts.append(
            (
                field,
                statuses[FIELD_STATUS_AVAILABLE],
                statuses[FIELD_STATUS_REVIEW],
                statuses[FIELD_STATUS_MISSING],
            )
        )
    raw_warnings = tuple(warnings) + tuple(warning for sample in samples for warning in sample.warnings)
    return RealworksDetailFactsProbeResult(
        source_id=source_id,
        source_domain=source_domain,
        detail_pages_attempted=len(samples),
        detail_pages_succeeded=detail_pages_succeeded,
        detail_pages_failed=len(samples) - detail_pages_succeeded,
        robots_allowed_count=sum(1 for sample in samples if sample.robots_allowed),
        robots_blocked_count=sum(1 for sample in samples if not sample.robots_allowed),
        field_availability_counts=tuple(field_counts),
        warning_counts=tuple(sorted(Counter(raw_warnings).items())),
        samples=tuple(samples),
        warnings=_dedupe(raw_warnings),
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


def _sample_warnings(fields: tuple[RealworksDetailFieldProbe, ...]) -> tuple[str, ...]:
    warnings = [warning for field in fields for warning in field.warnings]
    if any(field.status == FIELD_STATUS_MISSING for field in fields):
        warnings.append("missing_fact_source")
    if any(field.status == FIELD_STATUS_REVIEW for field in fields):
        warnings.append("review_fact_source")
    return _dedupe(warnings)


def _missing_field(field: str) -> RealworksDetailFieldProbe:
    return RealworksDetailFieldProbe(field=field, status=FIELD_STATUS_MISSING)


def _field_rank(probe: RealworksDetailFieldProbe) -> int:
    return {FIELD_STATUS_AVAILABLE: 2, FIELD_STATUS_REVIEW: 1, FIELD_STATUS_MISSING: 0}[probe.status]


def _page_title_or_h1(html: str) -> str:
    for pattern in (_H1_PATTERN, _TITLE_PATTERN):
        match = pattern.search(html or "")
        if match:
            return _cap_preview(_strip_tags(match.group("body")))
    return ""


def _description_text(html: str) -> str:
    match = _META_DESCRIPTION_PATTERN.search(html or "")
    if match:
        return _normalize_text(unescape(match.group("content")))
    label_values = _extract_label_values(html)
    for label, value in label_values:
        if label in {"omschrijving", "description", "beschrijving"}:
            return value
    return ""


def _description_length_bucket(text: str) -> str:
    length = len(_normalize_text(text))
    if length <= 0:
        return "none"
    if length < 250:
        return "short"
    if length < 1000:
        return "medium"
    return "long"


def _strip_tags(value: str) -> str:
    return _normalize_text(unescape(_TAG_PATTERN.sub(" ", value or "")))


def _normalize_label(value: str) -> str:
    text = _normalize_text(value).strip(":")
    text = text.replace("cv-ketel", "cv ketel")
    return text


def _normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip().casefold()


def _cap_preview(value: object) -> str:
    text = _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip()
    if len(text) <= EVIDENCE_PREVIEW_LIMIT:
        return text
    return text[:EVIDENCE_PREVIEW_LIMIT].rstrip()


def _preview(value: object) -> str:
    return _cap_preview(value)


def _split_compact_lines(value: str) -> tuple[str, ...]:
    return tuple(part for part in (_normalize_text(value).split("  ")) if part)


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
    for value in values:
        if value[0] and value[1] and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
