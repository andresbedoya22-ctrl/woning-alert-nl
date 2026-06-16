from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import replace
from html import unescape
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from domek_wonen.discovery.website_fetcher import WebsiteFetcher

from ..address_quality import classify_address_quality, derive_address_from_slug
from ..detail_page_extractor import DetailPageExtractor
from ..models import PropertyCandidate, PropertySource
from ..property_url_classifier import PropertyUrlClassifier

_LISTING_PATH_SUFFIXES = (
    "/aanbod/woningaanbod",
    "/woningaanbod",
    "/aanbod/koop",
    "/aanbod/woningaanbod/koop",
    "/aanbod/woningen",
    "/wonen",
    "/aanbod/wonen/te-koop",
)
_EXCLUDED_SEGMENTS = {
    "aankoop",
    "aankoop_verwerving",
    "bouwperiode",
    "verkoopadvies",
    "gratis-verkoopadvies",
    "contact",
    "over-ons",
    "provincie",
    "taxatie",
}
_EXCLUDED_DETAIL_SLUG_PREFIXES = (
    "bouwperiode-",
    "provincie-",
    "plaats-",
    "woonplaats-",
    "prijs-",
    "woonoppervlakte-",
    "perceeloppervlakte-",
    "kamers-",
)
_DETAIL_INDEX_SEGMENTS = {"aanbod", "woningaanbod", "koop", "woningen", "wonen"}
_DETAIL_PATH_PATTERNS = (
    re.compile(r"/aanbod/woningaanbod/.+"),
    re.compile(r"/woningaanbod/.+"),
    re.compile(r"/koop/.+"),
    re.compile(r"/woningen/[^/]+$"),
    re.compile(r"/aanbod/wonen/[^/]+/[^/]+/[a-z0-9]+$", flags=re.IGNORECASE),
    re.compile(r"/(?:huis|appartement|woning)-[^/]+$"),
)
_OGONLINE_DETAIL_PATH_PATTERN = re.compile(r"/aanbod/wonen/[^/]+/[^/]+/[a-z0-9]+$", flags=re.IGNORECASE)
_OGONLINE_DETAIL_LINK_PATTERN = re.compile(
    r"(?:https?://[^\"'\s>]+)?(/aanbod/wonen/[^\"'\s>]+/[a-z0-9]+)",
    flags=re.IGNORECASE,
)
_OGONLINE_CARD_PATTERN = re.compile(
    r"<a[^>]+href=[\"'](?P<href>/aanbod/wonen/[^\"'#]+/[a-z0-9]+)[\"'][^>]*>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_OGONLINE_LISTINGS_API_URL_PATTERN = re.compile(
    r"https://cpl01\.ogonline\.nl/api/listings\?[^\"'\s<]+",
    flags=re.IGNORECASE,
)
_REALWORKS_HOUSE_SLUG_PATTERN = re.compile(
    r"/aanbod/woningaanbod/(?P<city>[^/]+)/koop/(?P<slug>huis-\d+-.+)$",
    flags=re.IGNORECASE,
)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>", flags=re.IGNORECASE)
_HTML_SVG_PATTERN = re.compile(r"<svg[^>]*>.*?</svg>", flags=re.IGNORECASE | re.DOTALL)
_HTML_WHITESPACE_PATTERN = re.compile(r"\s+")
_PRICE_PATTERN = re.compile(r"(?:€|eur)\s?[\d\.\,]+(?:\s*[a-z.]+)?", flags=re.IGNORECASE)
_LIVING_AREA_PATTERN = re.compile(r"\d+\s?m[²2]", flags=re.IGNORECASE)
_ROOMS_PATTERN = re.compile(r"\d+\s*kamers?", flags=re.IGNORECASE)
_ENERGY_LABEL_PATTERN = re.compile(r"(?:energielabel|energy label)\s*[:\-]?\s*([a-g]\+{0,3})", flags=re.IGNORECASE)
_STATUS_TEXT_PATTERN = re.compile(
    r"\b(verkocht onder voorbehoud|verkocht o\.v\.|onder bod|verkocht|nieuw!?|beschikbaar|te koop)\b",
    flags=re.IGNORECASE,
)
_LOWERCASE_PARTICLES = {"aan", "de", "den", "der", "het", "in", "of", "op", "te", "ten", "ter", "van"}
_KIN_HTTP_PREFIX = "http://www.kinmakelaars.nl/"
_KIN_HTTPS_PREFIX = "https://www.kinmakelaars.nl/"
_OGONLINE_CITY_FROM_URL_PATTERN = re.compile(
    r"/aanbod/wonen/(?P<city>[^/]+)/[^/]+/[a-z0-9]+$",
    flags=re.IGNORECASE,
)
_OGONLINE_TYPE_IN_CITY_PATTERN = re.compile(
    r"(?P<kind>galerijflat|appartement|portiekflat|flat|studio|woonhuis|maisonnette|penthouse)\s+in\s+(?P<city>[A-Za-zÀ-ÿ' -]+)",
    flags=re.IGNORECASE,
)


def _normalize_url(url: str) -> str:
    normalized = url.split("#", 1)[0].rstrip("/")
    if normalized.lower().startswith(_KIN_HTTP_PREFIX):
        return f"{_KIN_HTTPS_PREFIX}{normalized[len(_KIN_HTTP_PREFIX):]}"
    return normalized


def _path_segments(url: str) -> list[str]:
    return [segment.lower() for segment in urlsplit(url).path.split("/") if segment.strip()]


def _base_website_url(source: PropertySource) -> str:
    website = (source.website or "").strip()
    if website:
        return _normalize_url(website)
    root_domain = (source.root_domain or "").strip()
    if root_domain.startswith(("http://", "https://")):
        return _normalize_url(root_domain)
    return _normalize_url(f"https://{root_domain}")


def _looks_like_listing_url(url: str) -> bool:
    if not url.strip():
        return False
    normalized = _normalize_url(url).lower()
    segments = _path_segments(normalized)
    if any(segment in _EXCLUDED_SEGMENTS for segment in segments):
        return False
    return any(
        normalized.endswith(suffix) or f"{suffix}/" in normalized
        for suffix in _LISTING_PATH_SUFFIXES
    )


def _listing_candidates(source: PropertySource) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    def add(url: str) -> None:
        normalized = _normalize_url(url.strip())
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    if _looks_like_listing_url(source.aanbod_url):
        add(source.aanbod_url)

    base_url = _base_website_url(source)
    for suffix in _LISTING_PATH_SUFFIXES:
        add(f"{base_url}{suffix}")
    return candidates


def _is_realworks_detail_url(url: str, *, root_domain: str, classifier: PropertyUrlClassifier) -> bool:
    parsed = urlsplit(url)
    hostname = (parsed.netloc or "").lower()
    normalized_root = (root_domain or "").strip().lower()
    if normalized_root and hostname != normalized_root and not hostname.endswith(f".{normalized_root}"):
        return False

    path = parsed.path.rstrip("/").lower()
    segments = _path_segments(url)
    if not path or any(segment in _EXCLUDED_SEGMENTS for segment in segments):
        return False
    if not segments or segments[-1] in _DETAIL_INDEX_SEGMENTS:
        return False
    if any(segments[-1].startswith(prefix) for prefix in _EXCLUDED_DETAIL_SLUG_PREFIXES):
        return False
    if _OGONLINE_DETAIL_PATH_PATTERN.search(path):
        return True
    if not any(pattern.search(path) for pattern in _DETAIL_PATH_PATTERNS):
        return False
    return classifier.classify(url, root_domain).classification == "property_detail_candidate"


def _confidence(candidate: PropertyCandidate) -> float:
    score = 0.6
    if candidate.address_raw:
        score += 0.15
    if candidate.price_raw:
        score += 0.1
    if candidate.status_raw:
        score += 0.05
    if candidate.living_area_raw:
        score += 0.05
    if candidate.rooms_raw:
        score += 0.03
    if candidate.energy_label:
        score += 0.02
    return min(score, 0.95)


def _collapse_whitespace(value: str) -> str:
    return _HTML_WHITESPACE_PATTERN.sub(" ", value or "").strip()


def _visible_card_text(html: str) -> str:
    without_svg = _HTML_SVG_PATTERN.sub(" ", html or "")
    without_tags = _HTML_TAG_PATTERN.sub(" ", without_svg)
    return _collapse_whitespace(unescape(without_tags))


def _extract_card_text(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(?P<body>.*?)</{tag}>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _collapse_whitespace(unescape(_HTML_TAG_PATTERN.sub(" ", match.group("body"))))


def _extract_card_city(html: str) -> str:
    match = re.search(r"<p[^>]*>(?P<city>.*?)</p>\s*<h3", html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _collapse_whitespace(unescape(_HTML_TAG_PATTERN.sub(" ", match.group("city"))))


def _extract_card_match(text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(text or "")
    return _collapse_whitespace(match.group(0)) if match else ""


def _extract_card_energy_label(text: str) -> str:
    match = _ENERGY_LABEL_PATTERN.search(text or "")
    return match.group(1).upper() if match else ""


def _extract_card_status(text: str) -> str:
    match = _STATUS_TEXT_PATTERN.search(text or "")
    return _collapse_whitespace(match.group(1)) if match else ""


def normalize_kin_city_from_url(property_url: str) -> str:
    match = _OGONLINE_CITY_FROM_URL_PATTERN.search(urlsplit(property_url).path.rstrip("/"))
    if not match:
        return ""
    return _format_slug_value(match.group("city"), lowercase_particles=_LOWERCASE_PARTICLES)


def _extract_ogonline_type_and_city(text: str) -> tuple[str, str]:
    match = _OGONLINE_TYPE_IN_CITY_PATTERN.search(_collapse_whitespace(text))
    if not match:
        return "", ""
    normalized_property_type = {
        "galerijflat": "apartment",
        "appartement": "apartment",
        "portiekflat": "apartment",
        "flat": "apartment",
        "studio": "studio",
        "woonhuis": "house",
        "maisonnette": "maisonette",
        "penthouse": "penthouse",
    }.get(match.group("kind").strip().casefold(), "")
    return normalized_property_type, _collapse_whitespace(match.group("city"))


def _extract_first_count(text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(text or "")
    if not match:
        return ""
    return re.sub(r"[^\d]", "", match.group(0))


def _to_absolute_url(base_url: str, maybe_relative_url: str) -> str:
    return _normalize_url(urljoin(f"{_normalize_url(base_url).rstrip('/')}/", maybe_relative_url))


def _build_listing_seed_candidate(
    source: PropertySource,
    *,
    source_url: str,
    property_url: str,
    card_html: str,
) -> PropertyCandidate:
    text = _visible_card_text(card_html)
    image_match = re.search(r"<img[^>]+src=\"(?P<src>[^\"]+)\"", card_html or "", flags=re.IGNORECASE)
    address_raw = _extract_card_text(card_html, "h3")
    property_type, title_city = _extract_ogonline_type_and_city(text)
    city_raw = normalize_kin_city_from_url(property_url) or title_city or _extract_card_city(card_html)
    living_area_raw = _extract_card_match(text, _LIVING_AREA_PATTERN)
    rooms_raw = _extract_card_match(text, _ROOMS_PATTERN)
    return PropertyCandidate(
        source_id=source.source_id,
        source_url=source_url,
        root_domain=source.root_domain,
        gemeente=source.gemeente,
        property_url=property_url,
        candidate_type="platform_parser_detail_url",
        extraction_method="realworks_listing_detail_fetch",
        is_property_like=True,
        property_url_classification="property_detail_candidate",
        title=address_raw,
        address_raw=address_raw,
        city_raw=city_raw,
        price_raw=_extract_card_match(text, _PRICE_PATTERN),
        status_raw=_extract_card_status(text),
        living_area_raw=living_area_raw,
        rooms_raw=rooms_raw,
        rooms_count=_extract_first_count(rooms_raw, _ROOMS_PATTERN),
        living_area_m2=_extract_first_count(living_area_raw, _LIVING_AREA_PATTERN),
        property_type=property_type,
        energy_label=_extract_card_energy_label(text),
        image_url=_normalize_url(image_match.group("src")) if image_match else "",
        extraction_source="realworks_parser",
        detail_extraction_status="failed",
        detail_error="detail page fetch failed",
    )


def _coerce_int(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return ""


def _normalize_location_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def _slugify_path_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    return slug


def _extract_ogonline_listings_api_url(html: str) -> str:
    match = _OGONLINE_LISTINGS_API_URL_PATTERN.search(unescape(html or ""))
    if not match:
        return ""
    return _normalize_url(match.group(0))


def _set_query_page(url: str, page: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _format_ogonline_price(doc: dict[str, object]) -> str:
    sales_price = doc.get("salesPrice")
    if not isinstance(sales_price, dict):
        return ""
    amount = sales_price.get("amount")
    if isinstance(amount, bool) or amount in (None, ""):
        return ""
    try:
        amount_value = int(amount)
    except (TypeError, ValueError):
        return ""
    amount_text = f"{amount_value:,}".replace(",", ".")
    condition = sales_price.get("condition")
    suffix = ""
    if isinstance(condition, dict):
        suffix = _collapse_whitespace(str(condition.get("title") or ""))
    return _collapse_whitespace(f"EUR {amount_text} {suffix}".strip())


def _format_ogonline_status(status: object) -> str:
    normalized = _collapse_whitespace(str(status or "")).casefold()
    mapping = {
        "available": "beschikbaar",
        "new": "Nieuw",
        "sold_ur": "verkocht onder voorbehoud",
        "sold": "verkocht",
        "under_offer": "onder bod",
    }
    return mapping.get(normalized, _collapse_whitespace(str(status or "")).replace("_", " "))


def _extract_ogonline_property_type(doc: dict[str, object]) -> str:
    consumer = doc.get("consumer")
    if not isinstance(consumer, dict):
        return ""
    if consumer.get("isApartment"):
        return "apartment"
    if consumer.get("isHouse"):
        return "house"
    return ""


def _extract_ogonline_image_url(doc: dict[str, object]) -> str:
    photos = doc.get("photos")
    if not isinstance(photos, list) or not photos:
        return ""
    first = photos[0]
    if not isinstance(first, dict):
        return ""
    imported = first.get("import")
    if isinstance(imported, dict) and imported.get("url"):
        return _normalize_url(str(imported["url"]))
    return ""


def _build_ogonline_api_seed_candidate(
    source: PropertySource,
    *,
    source_url: str,
    doc: dict[str, object],
) -> PropertyCandidate | None:
    property_id = _collapse_whitespace(str(doc.get("id") or ""))
    title = _collapse_whitespace(str(doc.get("title") or ""))
    address = doc.get("address")
    address_line = ""
    city_raw = ""
    if isinstance(address, dict):
        street = _collapse_whitespace(str(address.get("street") or ""))
        house_number = _collapse_whitespace(str(address.get("houseNumber") or ""))
        house_number_extension = _collapse_whitespace(str(address.get("houseNumberExtension") or ""))
        address_line = _collapse_whitespace(f"{street} {house_number}{house_number_extension}".strip())
        city_raw = _collapse_whitespace(str(address.get("settlement") or ""))
    address_raw = address_line or title
    city_raw = city_raw or source.gemeente
    if not property_id or not address_raw or not city_raw:
        return None

    city_slug = _slugify_path_value(city_raw)
    address_slug = _slugify_path_value(address_raw)
    if not city_slug or not address_slug:
        return None

    detail_url = _to_absolute_url(source_url, f"/aanbod/wonen/{city_slug}/{address_slug}/{property_id}")
    consumer = doc.get("consumer") if isinstance(doc.get("consumer"), dict) else {}
    consumer_details = consumer.get("details") if isinstance(consumer, dict) and isinstance(consumer.get("details"), dict) else {}
    energy_details = doc.get("energyDetails") if isinstance(doc.get("energyDetails"), dict) else {}
    rooms_count = _coerce_int(consumer_details.get("rooms"))
    bedrooms_count = _coerce_int(consumer_details.get("bedrooms"))
    living_area_m2 = _coerce_int(consumer_details.get("livingSurface"))
    living_area_raw = f"{living_area_m2} m2" if living_area_m2 else ""
    rooms_raw = f"{rooms_count} kamers" if rooms_count else ""
    return PropertyCandidate(
        source_id=source.source_id,
        source_url=source_url,
        root_domain=source.root_domain,
        gemeente=source.gemeente,
        property_url=detail_url,
        candidate_type="platform_parser_detail_url",
        extraction_method="realworks_listing_api",
        is_property_like=True,
        property_url_classification="property_detail_candidate",
        title=title or address_raw,
        address_raw=address_raw,
        city_raw=city_raw,
        price_raw=_format_ogonline_price(doc),
        status_raw=_format_ogonline_status(doc.get("status")),
        living_area_raw=living_area_raw,
        rooms_raw=rooms_raw,
        rooms_count=rooms_count,
        bedrooms_count=bedrooms_count,
        living_area_m2=living_area_m2,
        property_type=_extract_ogonline_property_type(doc),
        energy_label=_collapse_whitespace(str(energy_details.get("energyLabel") or "")).upper(),
        has_garden="true" if doc.get("hasGarden") else "false" if doc.get("hasGarden") is False else "",
        has_balcony="true" if doc.get("hasBalcony") else "false" if doc.get("hasBalcony") is False else "",
        image_url=_extract_ogonline_image_url(doc),
        extraction_source="realworks_parser",
        detail_extraction_status="failed",
        detail_error="detail page fetch failed",
    )


def _format_slug_token(token: str, *, lowercase_particles: set[str]) -> str:
    lowered = token.casefold()
    if lowered in lowercase_particles:
        return lowered
    if lowered == "'s":
        return "'s"
    if token.endswith(".") and len(token) > 1:
        core = token[:-1]
        return f"{core[:1].upper()}{core[1:].lower()}."
    return token[:1].upper() + token[1:].lower()


def _format_slug_value(value: str, *, lowercase_particles: set[str]) -> str:
    parts = [part for part in value.split("-") if part]
    if not parts:
        return ""
    return " ".join(_format_slug_token(part, lowercase_particles=lowercase_particles) for part in parts)


def parse_realworks_address_city_from_url(property_url: str) -> tuple[str, str]:
    path = urlsplit(property_url).path.rstrip("/")
    match = _REALWORKS_HOUSE_SLUG_PATTERN.search(path)
    if not match:
        return "", ""
    city_slug = match.group("city")
    address_slug = re.sub(r"^huis-\d+-", "", match.group("slug"), flags=re.IGNORECASE)
    address_raw = _format_slug_value(address_slug, lowercase_particles=_LOWERCASE_PARTICLES)
    city_raw = _format_slug_value(
        city_slug,
        lowercase_particles={"aan", "de", "den", "der", "het", "op", "te", "ten", "ter", "van"},
    )
    return address_raw, city_raw


class RealworksParser:
    def __init__(self) -> None:
        self._detail_extractor = DetailPageExtractor()
        self._url_classifier = PropertyUrlClassifier()

    def build_listing_candidates(self, source: PropertySource) -> list[str]:
        return _listing_candidates(source)

    def extract_detail_urls(self, listing_url: str, html: str, *, root_domain: str) -> list[str]:
        fetcher = WebsiteFetcher(timeout_seconds=1, delay_seconds=0)
        try:
            links = fetcher.extract_internal_links(listing_url, html)
        finally:
            fetcher.close()

        for match in _OGONLINE_DETAIL_LINK_PATTERN.finditer(html or ""):
            links.append(_to_absolute_url(listing_url, match.group(1)))

        detail_urls: list[str] = []
        seen: set[str] = set()
        for link in links:
            normalized = _normalize_url(link)
            if normalized in seen:
                continue
            seen.add(normalized)
            if _is_realworks_detail_url(normalized, root_domain=root_domain, classifier=self._url_classifier):
                detail_urls.append(normalized)
        return detail_urls

    def extract_listing_seed_candidates(
        self,
        listing_url: str,
        html: str,
        *,
        source: PropertySource,
    ) -> dict[str, PropertyCandidate]:
        seed_candidates: dict[str, PropertyCandidate] = {}
        base_url = _normalize_url(listing_url)
        for match in _OGONLINE_CARD_PATTERN.finditer(html or ""):
            detail_url = _to_absolute_url(base_url, match.group("href"))
            if not _is_realworks_detail_url(detail_url, root_domain=source.root_domain, classifier=self._url_classifier):
                continue
            if detail_url in seed_candidates:
                continue
            seed_candidates[detail_url] = _build_listing_seed_candidate(
                source,
                source_url=base_url,
                property_url=detail_url,
                card_html=match.group("body"),
            )
        return seed_candidates

    def extract_ogonline_api_seed_candidates(
        self,
        listing_url: str,
        html: str,
        *,
        source: PropertySource,
        fetcher: WebsiteFetcher,
        max_properties_per_source: int,
    ) -> dict[str, PropertyCandidate]:
        api_url = _extract_ogonline_listings_api_url(html)
        if not api_url:
            return {}

        seed_candidates: dict[str, PropertyCandidate] = {}
        fallback_candidates: dict[str, PropertyCandidate] = {}
        source_city_key = _normalize_location_key(source.gemeente)
        page_url = api_url
        while page_url:
            response = fetcher.fetch(page_url)
            if not response.ok:
                break
            try:
                payload = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                break
            docs = payload.get("docs")
            if not isinstance(docs, list):
                break
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                candidate = _build_ogonline_api_seed_candidate(
                    source,
                    source_url=listing_url,
                    doc=doc,
                )
                if candidate is None or candidate.property_url in seed_candidates or candidate.property_url in fallback_candidates:
                    continue
                if not _is_realworks_detail_url(candidate.property_url, root_domain=source.root_domain, classifier=self._url_classifier):
                    continue
                candidate_city_key = _normalize_location_key(candidate.city_raw)
                target = seed_candidates if source_city_key and candidate_city_key == source_city_key else fallback_candidates
                if not source_city_key:
                    target = seed_candidates
                target[candidate.property_url] = candidate
                if source_city_key and len(seed_candidates) >= max_properties_per_source:
                    break
                if not source_city_key and len(seed_candidates) >= max_properties_per_source:
                    break
            if source_city_key and len(seed_candidates) >= max_properties_per_source:
                break
            if not source_city_key and len(seed_candidates) >= max_properties_per_source:
                break
            if not payload.get("hasNextPage"):
                break
            next_page = payload.get("nextPage")
            if isinstance(next_page, int):
                page_url = _set_query_page(api_url, next_page)
            else:
                break
        if source_city_key and len(seed_candidates) < max_properties_per_source:
            for property_url, candidate in fallback_candidates.items():
                if property_url in seed_candidates:
                    continue
                seed_candidates[property_url] = candidate
                if len(seed_candidates) >= max_properties_per_source:
                    break
        return seed_candidates

    def prioritize_detail_urls(
        self,
        detail_urls: list[str],
        *,
        seed_candidates: dict[str, PropertyCandidate],
        source: PropertySource,
    ) -> list[str]:
        source_city_key = _normalize_location_key(source.gemeente)
        if not source_city_key:
            return detail_urls

        prioritized: list[str] = []
        deferred: list[str] = []
        for detail_url in detail_urls:
            candidate = seed_candidates.get(detail_url)
            candidate_city = candidate.city_raw if candidate is not None else normalize_kin_city_from_url(detail_url)
            if _normalize_location_key(candidate_city) == source_city_key:
                prioritized.append(detail_url)
            else:
                deferred.append(detail_url)
        return prioritized + deferred

    def parse(
        self,
        source: PropertySource,
        *,
        max_properties_per_source: int,
        page_timeout_seconds: int,
    ) -> list[PropertyCandidate]:
        listing_candidates = self.build_listing_candidates(source)
        if not listing_candidates:
            raise RuntimeError("no realworks listing candidates available")

        fetcher = WebsiteFetcher(timeout_seconds=max(1.0, min(float(page_timeout_seconds), 8.0)), delay_seconds=0)
        try:
            selected_listing_url = ""
            selected_detail_urls: list[str] = []
            seed_candidates: dict[str, PropertyCandidate] = {}
            for candidate_url in listing_candidates:
                response = fetcher.fetch(candidate_url)
                if not response.ok:
                    continue
                detail_urls = self.extract_detail_urls(response.url or candidate_url, response.text, root_domain=source.root_domain)
                api_seed_candidates = self.extract_ogonline_api_seed_candidates(
                    response.url or candidate_url,
                    response.text,
                    source=source,
                    fetcher=fetcher,
                    max_properties_per_source=max_properties_per_source,
                )
                for detail_url in api_seed_candidates:
                    if detail_url not in detail_urls:
                        detail_urls.append(detail_url)
                if detail_urls:
                    selected_listing_url = response.url or candidate_url
                    selected_detail_urls = detail_urls
                    seed_candidates = self.extract_listing_seed_candidates(
                        selected_listing_url,
                        response.text,
                        source=source,
                    )
                    seed_candidates.update(
                        {
                            property_url: candidate
                            for property_url, candidate in api_seed_candidates.items()
                            if property_url not in seed_candidates
                        }
                    )
                    selected_detail_urls = self.prioritize_detail_urls(
                        selected_detail_urls,
                        seed_candidates=seed_candidates,
                        source=source,
                    )
                    break

            if not selected_detail_urls:
                raise RuntimeError("realworks parser found no property detail urls")

            candidates: list[PropertyCandidate] = []
            for detail_url in selected_detail_urls[:max_properties_per_source]:
                detail_response = fetcher.fetch(detail_url)
                candidate = seed_candidates.get(detail_url) or PropertyCandidate(
                    source_id=source.source_id,
                    source_url=selected_listing_url or source.aanbod_url or _base_website_url(source),
                    root_domain=source.root_domain,
                    gemeente=source.gemeente,
                    property_url=detail_url,
                    candidate_type="platform_parser_detail_url",
                    extraction_method="realworks_listing_detail_fetch",
                    is_property_like=True,
                    property_url_classification="property_detail_candidate",
                    extraction_source="realworks_parser",
                    detail_extraction_status="failed",
                    detail_error="detail page fetch failed",
                )
                if detail_response.ok:
                    candidate = self._detail_extractor.enrich(candidate, detail_response.text, detail_response.url or detail_url)
                    candidate = replace(candidate, extraction_source="realworks_parser")
                else:
                    slug_address, slug_city = parse_realworks_address_city_from_url(detail_url)
                    if not slug_address:
                        slug_address, slug_city = derive_address_from_slug(detail_url)
                    candidate = replace(
                        candidate,
                        address_raw=candidate.address_raw or slug_address,
                        city_raw=candidate.city_raw or slug_city,
                        detail_error=detail_response.error or "detail page fetch failed",
                    )

                if not candidate.address_raw:
                    slug_address, slug_city = parse_realworks_address_city_from_url(candidate.property_url)
                    if not slug_address:
                        slug_address, slug_city = derive_address_from_slug(candidate.property_url)
                    if slug_address:
                        candidate = replace(candidate, address_raw=slug_address, city_raw=candidate.city_raw or slug_city)

                kin_city = normalize_kin_city_from_url(candidate.property_url)
                inferred_property_type, inferred_city = _extract_ogonline_type_and_city(candidate.city_raw)
                if kin_city:
                    candidate = replace(
                        candidate,
                        city_raw=kin_city,
                        property_type=candidate.property_type or inferred_property_type,
                    )
                elif inferred_city:
                    candidate = replace(
                        candidate,
                        city_raw=inferred_city,
                        property_type=candidate.property_type or inferred_property_type,
                    )

                candidates.append(
                    replace(
                        candidate,
                        address_quality=classify_address_quality(candidate.address_raw, candidate.property_url),
                        extraction_confidence=_confidence(candidate),
                    )
                )
            return candidates
        finally:
            fetcher.close()
