from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlsplit

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
    re.compile(r"/(?:huis|appartement|woning)-[^/]+$"),
)
_REALWORKS_HOUSE_SLUG_PATTERN = re.compile(
    r"/aanbod/woningaanbod/(?P<city>[^/]+)/koop/(?P<slug>huis-\d+-.+)$",
    flags=re.IGNORECASE,
)
_LOWERCASE_PARTICLES = {"aan", "de", "den", "der", "het", "in", "of", "op", "te", "ten", "ter", "van"}


def _normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/")


def _path_segments(url: str) -> list[str]:
    return [segment.lower() for segment in urlsplit(url).path.split("/") if segment.strip()]


def _base_website_url(source: PropertySource) -> str:
    website = (source.website or "").strip()
    if website:
        return website.rstrip("/")
    root_domain = (source.root_domain or "").strip()
    if root_domain.startswith(("http://", "https://")):
        return root_domain.rstrip("/")
    return f"https://{root_domain}".rstrip("/")


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
            for candidate_url in listing_candidates:
                response = fetcher.fetch(candidate_url)
                if not response.ok:
                    continue
                detail_urls = self.extract_detail_urls(response.url or candidate_url, response.text, root_domain=source.root_domain)
                if detail_urls:
                    selected_listing_url = response.url or candidate_url
                    selected_detail_urls = detail_urls
                    break

            if not selected_detail_urls:
                raise RuntimeError("realworks parser found no property detail urls")

            candidates: list[PropertyCandidate] = []
            for detail_url in selected_detail_urls[:max_properties_per_source]:
                detail_response = fetcher.fetch(detail_url)
                candidate = PropertyCandidate(
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
                        address_raw=slug_address,
                        city_raw=slug_city,
                        detail_error=detail_response.error or "detail page fetch failed",
                    )

                if not candidate.address_raw:
                    slug_address, slug_city = parse_realworks_address_city_from_url(candidate.property_url)
                    if not slug_address:
                        slug_address, slug_city = derive_address_from_slug(candidate.property_url)
                    if slug_address:
                        candidate = replace(candidate, address_raw=slug_address, city_raw=candidate.city_raw or slug_city)

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
