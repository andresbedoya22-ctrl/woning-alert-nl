from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

LISTING_HINTS = (
    "woning",
    "woningen",
    "aanbod",
    "object",
    "huis",
    "huizen",
    "appartement",
    "koop",
    "te-koop",
    "wonen",
)
STATUS_PATTERNS = (
    ("verkocht onder voorbehoud", "sold"),
    ("verkocht o.v.", "sold"),
    ("verkocht", "sold"),
    ("onder bod", "under_offer"),
    ("beschikbaar", "available"),
    ("te koop", "available"),
    ("te huur", "available"),
)
PRICE_PATTERN = re.compile(
    r"(?P<amount>(?:EUR|\u20ac)\s?[\d\.\,]+(?:\s*[-,/]?\s*(?P<qualifier>k\.k\.|v\.o\.n\.|p/m))?)",
    flags=re.IGNORECASE,
)
PRICE_ON_REQUEST_PATTERN = re.compile(r"\b(?:prijs op aanvraag|op aanvraag|n\.o\.t\.k\.)\b", flags=re.IGNORECASE)
AREA_PATTERN = re.compile(r"\b(?P<area>\d+\s?m(?:2|\u00b2|Â²))\b", flags=re.IGNORECASE)
ROOMS_PATTERN = re.compile(r"\b(?P<rooms>\d+)\s*(?:kamers?|rooms?)\b", flags=re.IGNORECASE)
POSTCODE_PATTERN = re.compile(r"\b(?P<postcode>\d{4}\s?[A-Z]{2})\b", flags=re.IGNORECASE)
ENERGY_LABEL_PATTERN = re.compile(r"energielabel\s*:\s*(?P<label>[A-G](?:\+{1,3})?)", flags=re.IGNORECASE)
ADDRESS_WITH_POSTCODE_PATTERN = re.compile(
    r"(?P<address>[A-Z][A-Za-z0-9'()./\- ]+?\d+[A-Za-z0-9/\-]*)"
    r"(?:,\s*|\s+)"
    r"(?P<postcode>\d{4}\s?[A-Z]{2})\s+"
    r"(?P<city>[A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+){0,3})"
    r"(?=\s+(?:verkocht|onder bod|beschikbaar|te koop|te huur|EUR|\u20ac|prijs op aanvraag|op aanvraag|n\.o\.t\.k\.|energielabel|$)|$)",
    flags=re.IGNORECASE,
)
ADDRESS_COMMA_CITY_PATTERN = re.compile(
    r"(?P<address>[A-Z][A-Za-z0-9'()./\- ]+?\d+[A-Za-z0-9/\-]*)\s*,\s*"
    r"(?P<city>[A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+){0,3})"
    r"(?=\s+(?:verkocht|onder bod|beschikbaar|te koop|te huur|EUR|\u20ac|prijs op aanvraag|op aanvraag|n\.o\.t\.k\.|energielabel|$)|$)",
    flags=re.IGNORECASE,
)
CITY_ADDRESS_PATTERN = re.compile(
    r"\b(?P<city>[A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+)*)\s+"
    r"(?P<address>[A-Z][A-Za-z0-9'()./\- ]+?\d+[A-Za-z0-9/\-]*)"
    r"(?=\s+(?:verkocht|onder bod|beschikbaar|te koop|te huur|EUR|\u20ac|prijs op aanvraag|op aanvraag|n\.o\.t\.k\.|energielabel|$)|$)"
)


@dataclass(slots=True)
class Listing:
    source_url: str
    title: str = ""
    price: str = ""
    price_on_request: bool = False
    price_qualifier: str = ""
    area: str = ""
    rooms: str = ""
    postcode: str = ""
    city: str = ""
    address: str = ""
    energy_label: str = ""
    status: str = "unknown"
    location_confidence: float = 0.0
    needs_location_resolution: bool = False
    confidence: float = 0.0


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _normalize_url(url: str, base_url: str = "") -> str:
    resolved = urljoin(base_url, url)
    parts = urlsplit(resolved)
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def _normalize_price(value: str) -> str:
    return _collapse_whitespace(value.replace("EUR", "\u20ac").replace("eur", "\u20ac"))


def _dedupe_repeated_phrase(value: str) -> str:
    parts = value.split()
    half = len(parts) // 2
    if len(parts) % 2 == 0 and parts[:half] == parts[half:]:
        return " ".join(parts[:half])
    return value


def _trim_trailing_location_noise(value: str) -> str:
    cleaned = re.split(
        r"\s+(?:verkocht(?:\s+o\.v\.)?|onder\s+bod|beschikbaar|te\s+koop|te\s+huur|EUR|\u20ac|prijs\s+op\s+aanvraag|op\s+aanvraag|n\.o\.t\.k\.|energielabel)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return _collapse_whitespace(cleaned)


def _finalize_city(value: str) -> str:
    cleaned = _trim_trailing_location_noise(value)
    if cleaned.upper() in {"EUR", "ENERGIELABEL"}:
        return ""
    return cleaned


def _trim_address(value: str) -> str:
    cleaned = _dedupe_repeated_phrase(_collapse_whitespace(value))
    if " in " in cleaned:
        cleaned = cleaned.rsplit(" in ", 1)[-1]
    suffix_match = re.search(
        r"([A-Z][A-Za-z0-9'()./\-]*(?:\s+(?:[a-z]+|[A-Z][A-Za-z0-9'()./\-]*))*\s+\d+[A-Za-z0-9/\-]*)$",
        cleaned,
    )
    if suffix_match:
        return _collapse_whitespace(suffix_match.group(1))
    return cleaned


def _extract_price(text: str) -> tuple[str, bool, str]:
    on_request = bool(PRICE_ON_REQUEST_PATTERN.search(text))
    match = PRICE_PATTERN.search(text)
    if not match:
        return ("Prijs op aanvraag" if on_request else "", on_request, "")
    qualifier = _collapse_whitespace(match.group("qualifier") or "")
    return (_normalize_price(match.group("amount")), on_request, qualifier.lower())


def _extract_area(text: str) -> str:
    for match in AREA_PATTERN.finditer(text):
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 24)
        context = text[start:end].lower()
        if "perceel" in context or "kavel" in context or "plot" in context:
            continue
        return _collapse_whitespace(match.group("area"))
    return ""


def _extract_location(text: str) -> tuple[str, str, str, float, bool]:
    postcode_match = POSTCODE_PATTERN.search(text)
    postcode = _collapse_whitespace(postcode_match.group("postcode")) if postcode_match else ""

    match = ADDRESS_WITH_POSTCODE_PATTERN.search(text)
    if match:
        return (
            _trim_address(match.group("address")),
            _finalize_city(match.group("city")),
            _collapse_whitespace(match.group("postcode")),
            1.0,
            False,
        )

    match = ADDRESS_COMMA_CITY_PATTERN.search(text)
    if match:
        return (
            _trim_address(match.group("address")),
            _finalize_city(match.group("city")),
            postcode,
            0.75,
            False,
        )

    match = CITY_ADDRESS_PATTERN.search(text)
    if match:
        city = _finalize_city(match.group("city"))
        address = _trim_address(match.group("address"))
        if city and address.lower().startswith(f"{city.lower()} "):
            address = _collapse_whitespace(address[len(city) :])
        return (
            address,
            city,
            postcode,
            0.75,
            False,
        )

    if postcode:
        tail = text[postcode_match.end() :]
        city_match = re.search(
            r"\s+(?P<city>[A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+){0,3})"
            r"(?=\s+(?:\d|verkocht|onder bod|beschikbaar|te koop|te huur|EUR|\u20ac|prijs op aanvraag|op aanvraag|n\.o\.t\.k\.|energielabel|$)|$)",
            tail,
        )
        city = _finalize_city(city_match.group("city")) if city_match else ""
        return ("", city, postcode, 0.5 if city else 0.25, not bool(city))

    city_match = re.search(r"\b(?P<city>[A-Z][A-Za-z'().\-]+(?:\s+[A-Z][A-Za-z'().\-]+)*)\b", text)
    city = _finalize_city(city_match.group("city")) if city_match else ""
    return ("", city, "", 0.25 if city else 0.0, False)


def _extract_status(text: str) -> str:
    lowered = text.lower()
    for needle, status in STATUS_PATTERNS:
        if needle in lowered:
            return status
    return "unknown"


def _extract_title(container) -> str:
    heading = container.css_first("h1, h2, h3, h4")
    if heading:
        return _collapse_whitespace(heading.text(separator=" ", strip=True))
    return ""


def _container_text(node) -> str:
    return _collapse_whitespace(node.text(separator=" ", strip=True))


def _anchor_score(url: str, text: str) -> int:
    lowered_url = url.lower()
    lowered_text = text.lower()
    score = 0
    if any(hint in lowered_url for hint in LISTING_HINTS):
        score += 3
    if PRICE_PATTERN.search(text) or PRICE_ON_REQUEST_PATTERN.search(text):
        score += 2
    if AREA_PATTERN.search(text):
        score += 1
    if ROOMS_PATTERN.search(text):
        score += 1
    if any(marker in lowered_text for marker, _ in STATUS_PATTERNS):
        score += 1
    if POSTCODE_PATTERN.search(text):
        score += 1
    return score


def _confidence(listing: Listing) -> float:
    parts = (
        bool(listing.price or listing.price_on_request),
        listing.location_confidence > 0.0,
        bool(listing.area),
        bool(listing.address),
    )
    return sum(1 for item in parts if item) / 4


def parse_card(url: str, text: str) -> Listing:
    normalized_text = _collapse_whitespace(text)
    price, price_on_request, qualifier = _extract_price(normalized_text)
    address, city, postcode, location_confidence, needs_location_resolution = _extract_location(normalized_text)
    rooms_match = ROOMS_PATTERN.search(normalized_text)
    energy_match = ENERGY_LABEL_PATTERN.search(normalized_text)
    listing = Listing(
        source_url=_normalize_url(url),
        price=price,
        price_on_request=price_on_request,
        price_qualifier=qualifier,
        area=_extract_area(normalized_text),
        rooms=_collapse_whitespace(rooms_match.group("rooms")) if rooms_match else "",
        postcode=postcode,
        city=city,
        address=address,
        energy_label=_collapse_whitespace(energy_match.group("label")) if energy_match else "",
        status=_extract_status(normalized_text),
        location_confidence=location_confidence,
        needs_location_resolution=needs_location_resolution,
    )
    listing.confidence = _confidence(listing)
    return listing


def harvest(html: str, base_url: str = "") -> list[Listing]:
    tree = HTMLParser(html or "")
    listings: list[Listing] = []
    seen_urls: set[str] = set()
    normalized_base_url = _normalize_url(base_url) if base_url else ""

    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if not href:
            continue

        resolved_url = _normalize_url(href, base_url)
        if normalized_base_url and resolved_url == normalized_base_url:
            continue
        container = anchor
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            if container.tag in {"article", "li", "div", "a"}:
                break

        text = _container_text(container)
        if _anchor_score(resolved_url, text) < 4:
            continue
        if resolved_url in seen_urls:
            continue

        listing = parse_card(resolved_url, text)
        listing.title = _extract_title(container) or _collapse_whitespace(anchor.text(separator=" ", strip=True))
        seen_urls.add(resolved_url)
        listings.append(listing)

    return listings
