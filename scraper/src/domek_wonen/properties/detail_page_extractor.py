from __future__ import annotations

import json
import re
from dataclasses import replace
from html import unescape
from html.parser import HTMLParser

from .address_quality import derive_address_from_slug as derive_address_from_slug_fallback
from .models import PropertyCandidate

STATUS_PATTERNS = (
    "verkocht onder voorbehoud",
    "verkocht o.v.",
    "onder bod",
    "verkocht",
    "beschikbaar",
    "te koop",
)
PRICE_PATTERN = r"(?:€|eur)\s?[\d\.\,]+(?:\s*[a-z.]+)?"
LIVING_AREA_PATTERN = r"\d+\s?m[²2]\s*(?:woonoppervlakte|wonen|living)?"
PLOT_AREA_PATTERN = r"\d+\s?m[²2]\s*(?:perceel|plot|kavel)"
ROOMS_PATTERN = r"\d+\s*(?:kamers?|rooms?)"
ENERGY_LABEL_PATTERN = r"(?:energielabel|energy label)\s*[:\-]?\s*([a-g]\+{0,3})"
BEDROOMS_PATTERNS = (
    re.compile(r"\b(\d+)\s*(?:slaapkamers?|bedrooms?)\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:aantal\s+)?(?:slaapkamers?|bedrooms?)\s*[:\-]?\s*(\d+)\b", flags=re.IGNORECASE),
)
ROOMS_COUNT_PATTERNS = (
    re.compile(r"\b(\d+)\s*(?:kamers?|rooms?)\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:aantal\s+)?(?:kamers?|rooms?)\s*[:\-]?\s*(\d+)\b", flags=re.IGNORECASE),
)
LIVING_AREA_M2_PATTERNS = (
    re.compile(r"\b(\d+)\s*m[²2]\s*(?:woonoppervlakte|wonen|living)?\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:woonoppervlakte|living area)\s*[:\-]?\s*(\d+)\s*m[²2]\b", flags=re.IGNORECASE),
)
GARDEN_TRUE_PATTERNS = (
    re.compile(r"\b(?:tuin|garden)\b", flags=re.IGNORECASE),
)
GARDEN_FALSE_PATTERNS = (
    re.compile(r"\b(?:geen|zonder|no)\s+(?:tuin|garden)\b", flags=re.IGNORECASE),
)
BALCONY_TRUE_PATTERNS = (
    re.compile(r"\b(?:balkon|balcony)\b", flags=re.IGNORECASE),
)
BALCONY_FALSE_PATTERNS = (
    re.compile(r"\b(?:geen|zonder|no)\s+(?:balkon|balcony)\b", flags=re.IGNORECASE),
)
ADDRESS_PATTERN = re.compile(
    r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ'()./\- ]+\d+[A-Za-z0-9/\-]*)(?:,\s*|\s+)([A-ZÀ-ÿ][A-Za-zÀ-ÿ'().\- ]+)",
    flags=re.IGNORECASE,
)
JSON_LD_PATTERN = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<body>.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
META_PATTERN = re.compile(
    r"<meta[^>]+(?:property|name)=[\"'](?P<key>[^\"']+)[\"'][^>]+content=[\"'](?P<value>[^\"']+)[\"'][^>]*>",
    flags=re.IGNORECASE,
)


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.parts.append(unescape(data))


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html or "")
    return _collapse_whitespace(" ".join(parser.parts))


def _first_tag_text(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(?P<body>.*?)</{tag}>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group("body"))
    return _collapse_whitespace(unescape(text))


def _find_line(text: str, pattern: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE)
    return _collapse_whitespace(match.group(0)) if match else ""


def _extract_address_from_text(text: str) -> tuple[str, str]:
    match = ADDRESS_PATTERN.search(text or "")
    if match:
        return _collapse_whitespace(match.group(1)), _collapse_whitespace(match.group(2))
    return "", ""


def _extract_status(text: str) -> str:
    lowered = (text or "").lower()
    for pattern in STATUS_PATTERNS:
        if pattern in lowered:
            return pattern
    return ""


def _extract_energy_label(text: str) -> str:
    match = re.search(ENERGY_LABEL_PATTERN, text or "", flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _extract_first_count(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    for pattern in patterns:
        match = pattern.search(text or "")
        if match:
            return match.group(1)
    return ""


def _extract_boolean_signal(
    text: str,
    *,
    true_patterns: tuple[re.Pattern[str], ...],
    false_patterns: tuple[re.Pattern[str], ...],
) -> str:
    for pattern in false_patterns:
        if pattern.search(text or ""):
            return "false"
    for pattern in true_patterns:
        if pattern.search(text or ""):
            return "true"
    return ""


def _iter_json_ld_records(html: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for match in JSON_LD_PATTERN.finditer(html or ""):
        body = _collapse_whitespace(match.group("body"))
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
        elif isinstance(payload, list):
            records.extend(item for item in payload if isinstance(item, dict))
    return records


class DetailPageExtractor:
    def enrich(self, candidate: PropertyCandidate, html: str, final_url: str) -> PropertyCandidate:
        h1_text = _first_tag_text(html, "h1")
        title_text = _collapse_whitespace(unescape(TITLE_PATTERN.search(html or "")["body"])) if TITLE_PATTERN.search(html or "") else ""
        visible_text = _visible_text(html)
        meta_values = [_collapse_whitespace(unescape(match.group("value"))) for match in META_PATTERN.finditer(html or "")]
        json_ld_records = _iter_json_ld_records(html)

        address_raw = candidate.address_raw
        city_raw = candidate.city_raw
        extraction_source = candidate.extraction_source

        for text in [h1_text, title_text, *meta_values, visible_text]:
            extracted_address, extracted_city = _extract_address_from_text(text)
            if extracted_address and not address_raw:
                address_raw = extracted_address
                extraction_source = "detail_page"
            if extracted_city and not city_raw:
                city_raw = extracted_city

        for record in json_ld_records:
            address = record.get("address")
            if isinstance(address, dict):
                street = _collapse_whitespace(str(address.get("streetAddress") or ""))
                locality = _collapse_whitespace(str(address.get("addressLocality") or ""))
                if street and not address_raw:
                    address_raw = street
                    extraction_source = "detail_page"
                if locality and not city_raw:
                    city_raw = locality
            offers = record.get("offers")
            if isinstance(offers, dict) and not candidate.price_raw:
                price = _collapse_whitespace(str(offers.get("price") or ""))
                currency = _collapse_whitespace(str(offers.get("priceCurrency") or ""))
                if price:
                    candidate = replace(candidate, price_raw=_collapse_whitespace(f"{currency} {price}".strip()))
            name = _collapse_whitespace(str(record.get("name") or ""))
            if name and not candidate.title:
                candidate = replace(candidate, title=name)

        if not address_raw:
            slug_address, slug_city = derive_address_from_slug_fallback(final_url or candidate.property_url)
            if slug_address:
                address_raw = slug_address
                city_raw = city_raw or slug_city
                extraction_source = "url_slug"

        price_raw = candidate.price_raw
        status_raw = candidate.status_raw
        living_area_raw = candidate.living_area_raw
        plot_area_raw = candidate.plot_area_raw
        rooms_raw = candidate.rooms_raw
        rooms_count = candidate.rooms_count
        bedrooms_count = candidate.bedrooms_count
        living_area_m2 = candidate.living_area_m2
        energy_label = candidate.energy_label
        has_garden = candidate.has_garden
        has_balcony = candidate.has_balcony

        detail_texts = [h1_text, title_text, *meta_values, visible_text]
        for text in detail_texts:
            if not price_raw:
                price_raw = _find_line(text, PRICE_PATTERN)
            if not status_raw:
                status_raw = _extract_status(text)
            if not living_area_raw:
                living_area_raw = _find_line(text, LIVING_AREA_PATTERN)
            if not plot_area_raw:
                plot_area_raw = _find_line(text, PLOT_AREA_PATTERN)
            if not rooms_raw:
                rooms_raw = _find_line(text, ROOMS_PATTERN)
            if not rooms_count:
                rooms_count = _extract_first_count(text, ROOMS_COUNT_PATTERNS)
            if not bedrooms_count:
                bedrooms_count = _extract_first_count(text, BEDROOMS_PATTERNS)
            if not living_area_m2:
                living_area_m2 = _extract_first_count(text, LIVING_AREA_M2_PATTERNS)
            if not energy_label:
                energy_label = _extract_energy_label(text)
            if not has_garden:
                has_garden = _extract_boolean_signal(
                    text,
                    true_patterns=GARDEN_TRUE_PATTERNS,
                    false_patterns=GARDEN_FALSE_PATTERNS,
                )
            if not has_balcony:
                has_balcony = _extract_boolean_signal(
                    text,
                    true_patterns=BALCONY_TRUE_PATTERNS,
                    false_patterns=BALCONY_FALSE_PATTERNS,
                )

        detail_succeeded = any(
            [
                extraction_source in {"detail_page", "url_slug"} and address_raw,
                price_raw != candidate.price_raw and bool(price_raw),
                status_raw != candidate.status_raw and bool(status_raw),
                living_area_raw != candidate.living_area_raw and bool(living_area_raw),
                rooms_raw != candidate.rooms_raw and bool(rooms_raw),
                rooms_count != candidate.rooms_count and bool(rooms_count),
                bedrooms_count != candidate.bedrooms_count and bool(bedrooms_count),
                living_area_m2 != candidate.living_area_m2 and bool(living_area_m2),
                energy_label != candidate.energy_label and bool(energy_label),
                has_garden != candidate.has_garden and bool(has_garden),
                has_balcony != candidate.has_balcony and bool(has_balcony),
            ]
        )

        return replace(
            candidate,
            property_url=final_url or candidate.property_url,
            address_raw=address_raw,
            city_raw=city_raw,
            price_raw=price_raw,
            status_raw=status_raw,
            living_area_raw=living_area_raw,
            plot_area_raw=plot_area_raw,
            rooms_raw=rooms_raw,
            rooms_count=rooms_count,
            bedrooms_count=bedrooms_count,
            living_area_m2=living_area_m2,
            energy_label=energy_label,
            has_garden=has_garden,
            has_balcony=has_balcony,
            extraction_source=extraction_source,
            detail_extraction_status="succeeded" if detail_succeeded else "failed",
            detail_error="" if detail_succeeded else "detail page missing usable signals",
        )


def derive_address_from_slug(property_url: str) -> tuple[str, str]:
    return derive_address_from_slug_fallback(property_url)
