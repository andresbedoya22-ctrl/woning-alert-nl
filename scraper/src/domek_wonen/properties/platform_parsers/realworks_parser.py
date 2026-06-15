from __future__ import annotations

import re
from dataclasses import replace
from html import unescape
from urllib.parse import urljoin, urlsplit

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
    r"<a[^>]+href=\"(?P<href>/aanbod/wonen/[^\"#]+/[a-z0-9]+)\"[^>]*>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
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
                if detail_urls:
                    selected_listing_url = response.url or candidate_url
                    selected_detail_urls = detail_urls
                    seed_candidates = self.extract_listing_seed_candidates(
                        selected_listing_url,
                        response.text,
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
