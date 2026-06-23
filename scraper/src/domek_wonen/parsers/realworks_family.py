from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit

from domek_wonen.sources.delivery_fingerprint import DeliveryFingerprintResult

from .models import ParsedListing, ParserFamilyResult, ParserInput


_ANCHOR_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)\bhref\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG_PATTERN = re.compile(r"<[^>]+>", flags=re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_PRICE_PATTERN = re.compile(r"(?:\u20ac|eur)\s*([\d][\d\.,]*)", flags=re.IGNORECASE)
_LIVING_AREA_PATTERN = re.compile(r"\b(\d{2,4})\s*m(?:2|\^2|\u00b2)\b", flags=re.IGNORECASE)
_PLOT_AREA_PATTERN = re.compile(r"\b(?:perceel|plot|kavel)\D{0,20}(\d{2,6})\s*m(?:2|\^2|\u00b2)\b", flags=re.IGNORECASE)
_ROOMS_PATTERN = re.compile(r"\b(\d{1,2})\s*kamers?\b", flags=re.IGNORECASE)
_BEDROOMS_PATTERN = re.compile(r"\b(\d{1,2})\s*slaapkamers?\b", flags=re.IGNORECASE)
_POSTCODE_PATTERN = re.compile(r"\b(\d{4}\s?[A-Z]{2})\b", flags=re.IGNORECASE)
_HOUSE_NUMBER_PATTERN = re.compile(r"^(?P<street>.+?)\s+(?P<number>\d+[A-Za-z0-9\-/]*)$")
_FIELD_CLASS_PATTERN = (
    r"<(?P<tag>[a-z0-9]+)\b[^>]*class\s*=\s*[\"'][^\"']*(?P<class>{class_name})[^\"']*[\"'][^>]*>"
    r"(?P<body>.*?)</(?P=tag)>"
)
_DETAIL_PATH_PATTERNS = (
    re.compile(r"/aanbod/woningaanbod/.+", flags=re.IGNORECASE),
    re.compile(r"/woningaanbod/.+", flags=re.IGNORECASE),
    re.compile(r"/aanbod/wonen/[^/]+/[^/]+/[a-z0-9]+$", flags=re.IGNORECASE),
    re.compile(r"/woningen/[^/]+$", flags=re.IGNORECASE),
    re.compile(r"/(?:huis|appartement|woning)-[^/]+$", flags=re.IGNORECASE),
)
_EXCLUDED_SEGMENTS = {
    "aankoop",
    "contact",
    "over-ons",
    "provincie",
    "taxatie",
    "verkoopadvies",
}
_EXCLUDED_DETAIL_SLUG_PREFIXES = (
    "bouwperiode-",
    "kamers-",
    "pagina-",
    "plaats-",
    "prijs-",
    "provincie-",
    "street-",
    "woonoppervlakte-",
    "woonplaats-",
)


class RealworksParserFamily:
    parser_family = "realworks_public"

    def parse_listing_page(self, parser_input: ParserInput) -> ParserFamilyResult:
        warnings: list[str] = []
        if (parser_input.content_type or "").lower() != "html":
            warnings.append(f"unsupported_content_type:{parser_input.content_type}")

        listings: list[ParsedListing] = []
        seen_urls: set[str] = set()
        rejected_count = 0

        for match in _ANCHOR_PATTERN.finditer(parser_input.content or ""):
            href = unescape(match.group("href")).strip()
            canonical_url = _canonical_url(parser_input.source_url, href)
            if not canonical_url or canonical_url in seen_urls:
                continue
            if not _looks_like_realworks_detail_url(canonical_url, parser_input.source_domain):
                rejected_count += 1
                continue

            listing = _parse_card(
                parser_input=parser_input,
                canonical_url=canonical_url,
                card_html=match.group("body"),
            )
            seen_urls.add(canonical_url)
            listings.append(listing)

        if not listings:
            warnings.append("no_realworks_detail_urls_found")

        return ParserFamilyResult(
            parser_family=self.parser_family,
            source_id=parser_input.source_id,
            source_domain=parser_input.source_domain,
            listings=tuple(listings),
            rejected_count=rejected_count,
            warning_count=len(warnings),
            warnings=tuple(warnings),
        )


def parse_realworks_listing_page(parser_input: ParserInput) -> ParserFamilyResult:
    return RealworksParserFamily().parse_listing_page(parser_input)


def can_parse_realworks_source(fingerprint_result: DeliveryFingerprintResult) -> bool:
    return (
        fingerprint_result.delivery_mode == "realworks_public"
        and fingerprint_result.parser_family_candidate == "realworks_public"
        and fingerprint_result.can_proceed_to_parser_family is True
    )


def _parse_card(*, parser_input: ParserInput, canonical_url: str, card_html: str) -> ParsedListing:
    text = _visible_text(card_html)
    address_raw = (
        _extract_field(card_html, ("address", "title", "street-address"))
        or _extract_first_tag(card_html, ("h1", "h2", "h3", "h4"))
    )
    city = _extract_field(card_html, ("city", "locality", "plaats"))
    price_raw = _extract_field(card_html, ("price", "asking-price", "vraagprijs")) or _extract_price_raw(text)
    status_raw = _extract_field(card_html, ("status", "label", "badge"))
    living_area_m2 = _extract_int(text, _LIVING_AREA_PATTERN)
    plot_area_m2 = _extract_int(text, _PLOT_AREA_PATTERN)
    rooms_count = _extract_int(text, _ROOMS_PATTERN)
    bedrooms_count = _extract_int(text, _BEDROOMS_PATTERN)
    property_type = _extract_property_type(text)
    energy_label = _extract_energy_label(text)
    asking_price_eur = _parse_price_eur(price_raw or text)
    transaction_type = _classify_transaction_type(" ".join((text, price_raw)))
    status = _classify_status(" ".join((text, status_raw, price_raw)))
    street, house_number, postcode = _split_address(address_raw)
    needs_review, review_reason = _review_state(address_raw, asking_price_eur)
    evidence = _evidence(
        canonical_url=canonical_url,
        address_raw=address_raw,
        city=city,
        asking_price_eur=asking_price_eur,
        status=status,
        living_area_m2=living_area_m2,
        rooms_count=rooms_count,
    )

    return ParsedListing(
        source_id=parser_input.source_id,
        source_domain=parser_input.source_domain,
        canonical_url=canonical_url,
        address_raw=address_raw,
        street=street,
        house_number=house_number,
        postcode=postcode,
        city=city,
        asking_price_eur=asking_price_eur,
        transaction_type=transaction_type,
        status=status,
        living_area_m2=living_area_m2,
        plot_area_m2=plot_area_m2,
        rooms_count=rooms_count,
        bedrooms_count=bedrooms_count,
        property_type=property_type,
        energy_label=energy_label,
        evidence=evidence,
        confidence_score=_confidence_score(
            canonical_url=canonical_url,
            address_raw=address_raw,
            city=city,
            asking_price_eur=asking_price_eur,
            status=status,
            living_area_m2=living_area_m2,
            rooms_count=rooms_count,
        ),
        needs_review=needs_review,
        review_reason=review_reason,
    )


def _canonical_url(base_url: str, href: str) -> str:
    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
        return ""
    absolute = urljoin(base_url, href)
    parts = urlsplit(absolute)
    if not parts.scheme or not parts.netloc:
        return ""
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _looks_like_realworks_detail_url(url: str, source_domain: str) -> bool:
    parts = urlsplit(url)
    hostname = (parts.netloc or "").lower()
    domain = (source_domain or "").lower()
    if domain and hostname != domain and not hostname.endswith(f".{domain}"):
        return False
    segments = [segment.lower() for segment in parts.path.split("/") if segment]
    if not segments or any(segment in _EXCLUDED_SEGMENTS for segment in segments):
        return False
    if any(segments[-1].startswith(prefix) for prefix in _EXCLUDED_DETAIL_SLUG_PREFIXES):
        return False
    return any(pattern.search(parts.path) for pattern in _DETAIL_PATH_PATTERNS)


def _visible_text(html: str) -> str:
    return _collapse_whitespace(unescape(_TAG_PATTERN.sub(" ", html or "")))


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value or "").strip()


def _extract_field(html: str, class_names: tuple[str, ...]) -> str:
    for class_name in class_names:
        pattern = re.compile(
            _FIELD_CLASS_PATTERN.format(class_name=re.escape(class_name)),
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(html or "")
        if match:
            return _visible_text(match.group("body"))
    return ""


def _extract_first_tag(html: str, tags: tuple[str, ...]) -> str:
    for tag in tags:
        match = re.search(rf"<{tag}\b[^>]*>(?P<body>.*?)</{tag}>", html or "", flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _visible_text(match.group("body"))
    return ""


def _extract_price_raw(text: str) -> str:
    match = _PRICE_PATTERN.search(text or "")
    return _collapse_whitespace(match.group(0)) if match else ""


def _parse_price_eur(text: str) -> int | None:
    match = _PRICE_PATTERN.search(text or "")
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(1))
    return int(digits) if digits else None


def _extract_int(text: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.search(text or "")
    if not match:
        return None
    return int(match.group(1))


def _classify_transaction_type(text: str) -> str:
    normalized = (text or "").casefold()
    if any(signal in normalized for signal in ("te huur", "per maand", "p/m")):
        return "huur"
    if any(signal in normalized for signal in ("te koop", "vraagprijs", "k.k.")):
        return "koop"
    return "unknown"


def _classify_status(text: str) -> str:
    normalized = (text or "").casefold()
    if any(signal in normalized for signal in ("onder bod", "onder optie")):
        return "onder_bod"
    if "verkocht" in normalized:
        return "verkocht"
    if any(signal in normalized for signal in ("beschikbaar", "te koop", "vraagprijs", "k.k.")):
        return "beschikbaar"
    return "unknown"


def _split_address(address_raw: str) -> tuple[str, str, str]:
    postcode_match = _POSTCODE_PATTERN.search(address_raw or "")
    postcode = postcode_match.group(1).upper().replace(" ", "") if postcode_match else ""
    without_postcode = _POSTCODE_PATTERN.sub("", address_raw or "")
    match = _HOUSE_NUMBER_PATTERN.match(_collapse_whitespace(without_postcode))
    if not match:
        return "", "", postcode
    return _collapse_whitespace(match.group("street")), _collapse_whitespace(match.group("number")), postcode


def _extract_property_type(text: str) -> str:
    normalized = (text or "").casefold()
    if "appartement" in normalized:
        return "apartment"
    if "studio" in normalized:
        return "studio"
    if "woonhuis" in normalized or "huis" in normalized:
        return "house"
    return ""


def _extract_energy_label(text: str) -> str:
    match = re.search(r"\benergielabel\s*[:\-]?\s*([a-g]\+{0,3})\b", text or "", flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _review_state(address_raw: str, asking_price_eur: int | None) -> tuple[bool, str]:
    reasons: list[str] = []
    if not address_raw:
        reasons.append("missing_address")
    if asking_price_eur is None:
        reasons.append("missing_price")
    return bool(reasons), ",".join(reasons)


def _evidence(
    *,
    canonical_url: str,
    address_raw: str,
    city: str,
    asking_price_eur: int | None,
    status: str,
    living_area_m2: int | None,
    rooms_count: int | None,
) -> tuple[str, ...]:
    signals = ["detail_url"] if canonical_url else []
    if address_raw:
        signals.append("address")
    if city:
        signals.append("city")
    if asking_price_eur is not None:
        signals.append("price")
    if status != "unknown":
        signals.append(f"status:{status}")
    if living_area_m2 is not None:
        signals.append("living_area")
    if rooms_count is not None:
        signals.append("rooms")
    return tuple(signals)


def _confidence_score(
    *,
    canonical_url: str,
    address_raw: str,
    city: str,
    asking_price_eur: int | None,
    status: str,
    living_area_m2: int | None,
    rooms_count: int | None,
) -> float:
    score = 0.0
    if canonical_url:
        score += 0.35
    if address_raw:
        score += 0.20
    if asking_price_eur is not None:
        score += 0.15
    if city:
        score += 0.10
    if status != "unknown":
        score += 0.10
    if living_area_m2 is not None:
        score += 0.05
    if rooms_count is not None:
        score += 0.05
    return round(max(0.0, min(score, 1.0)), 2)
