from __future__ import annotations

import re
from urllib.parse import urlparse

AddressQuality = str

_NAVIGATION_SIGNALS = (
    "aanbod",
    "aankopen",
    "verkopen",
    "taxeren",
    "contact",
    "over ons",
    "diensten",
    "veelgestelde vragen",
    "snel naar",
)
_HOUSE_NUMBER_PATTERN = re.compile(r"\b\d+[A-Za-z0-9/\-]*\b")
_STREET_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ0-9'()./\- ]+$")


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _contains_navigation_signal(value: str) -> bool:
    lowered = (value or "").casefold()
    return any(signal in lowered for signal in _NAVIGATION_SIGNALS)


def derive_address_from_slug(property_url: str) -> tuple[str, str]:
    path = (urlparse(property_url).path or "").strip("/").lower()
    if not path:
        return "", ""
    slug = path.split("/")[-1]
    slug = re.sub(r"\.(html|htm|php)$", "", slug)
    slug = re.sub(r"-\d{4}[a-z]{2}$", "", slug)
    slug = re.sub(
        r"-(?:te-koop|koopwoning|woning|huis|appartement|vrijstaand|tussenwoning|hoekwoning|villa|woonhuis)$",
        "",
        slug,
    )
    parts = [part for part in slug.split("-") if part]
    if len(parts) < 3:
        return "", ""

    number_index = -1
    for index, part in enumerate(parts):
        if any(character.isdigit() for character in part):
            number_index = index
            break
    if number_index <= 0 or number_index >= len(parts) - 1:
        return "", ""

    address_parts = parts[: number_index + 1]
    city_parts = parts[number_index + 1 :]
    address_raw = " ".join(address_parts).title()
    city_raw = "-".join(city_parts).title() if len(city_parts) > 1 else city_parts[0].title()
    return address_raw, city_raw


def classify_address_quality(address_raw: str, property_url: str) -> AddressQuality:
    value = _collapse_whitespace(address_raw)
    if not value:
        return "invalid"
    if len(value) > 120:
        return "invalid"
    if value.casefold().startswith("k.k."):
        return "invalid"
    if _contains_navigation_signal(value):
        return "invalid"
    if not _HOUSE_NUMBER_PATTERN.search(value):
        return "invalid"

    before_number = _HOUSE_NUMBER_PATTERN.split(value, maxsplit=1)[0].strip(" ,-/")
    street_tokens = [token for token in re.split(r"\s+", before_number) if token]
    looks_like_street = (
        bool(before_number)
        and len(before_number) >= 4
        and len(street_tokens) >= 1
        and any(any(character.isalpha() for character in token) for token in street_tokens)
        and _STREET_PATTERN.match(value) is not None
    )
    if not looks_like_street:
        return "weak"

    slug_address, _ = derive_address_from_slug(property_url)
    if slug_address and slug_address.casefold() == value.casefold():
        return "valid"
    if len(value) < 8:
        return "weak"
    return "valid"
