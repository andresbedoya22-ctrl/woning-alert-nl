from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit, urlunsplit

import httpx
from selectolax.parser import HTMLParser

from ..compliance import robots_gate
from ..runtime_settings import load_runtime_settings


logger = logging.getLogger(__name__)

_LISTING_PATTERNS = (
    "/aanbod/wonen/",
    "/woning/",
    "/aanbod/",
    "/koop/",
    "/te-koop/",
    "/huis/",
)
_LISTING_HINTS = ("woning", "aanbod", "koop", "te-koop", "huis", "appartement", "villa")
_LISTING_PATHS_BY_FINGERPRINT = {
    "ogonline": ("/woningaanbod", "/aanbod", "/woningen"),
    "sumedia": ("/aanbod", "/woningen", "/koopwoningen"),
    "silverstripe": ("/aanbod", "/woningen", "/aanbod/wonen"),
    "wordpress": ("/aanbod", "/woningen", "/aanbod/wonen"),
    "realworks": ("/aanbod", "/woningen", "/aanbod/wonen"),
    "kolibri": ("/aanbod", "/woningen", "/koopwoningen"),
    "unknown": ("/aanbod", "/woningen", "/aanbod/wonen"),
}
_EXTRACTABLE_FIELDS_ORDER = ("url", "price", "address", "city", "area")
_CONTENT_BUDGET = 8
_SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap/sitemap-index.xml",
)
_CHALLENGE_MARKERS = (
    "cf-chl-",
    "challenge-platform",
    "checking your browser",
    "attention required",
    "g-recaptcha",
    "grecaptcha",
    "hcaptcha",
    "cf-turnstile",
    "/captcha/",
)


class DiscoveryStrategy(str, Enum):
    sitemap_with_listings = "sitemap_with_listings"
    wp_json = "wp_json"
    listing_html = "listing_html"
    listing_js = "listing_js"
    iframe_only = "iframe_only"
    blocked = "blocked"
    robots_disallow = "robots_disallow"
    no_signal = "no_signal"


@dataclass(slots=True)
class DomainClassification:
    domain: str
    robots_status: str
    robots_crawl_delay: float
    discovery_strategy: DiscoveryStrategy
    cms_fingerprint_guess: str
    sitemap_found: bool
    sitemap_has_listing_urls: bool
    wp_json_listings_found: bool
    structured_channel_open: bool
    html_blocked_but_structured_open: bool
    listing_url_pattern: str | None
    card_fields_extractable: list[str] = field(default_factory=list)
    needs_js: bool = False
    requests_used: int = 0
    recommended_action: str = "manual_review"
    blocker_reason: str | None = None


@dataclass(slots=True)
class _FetchedResponse:
    url: str
    status_code: int
    text: str
    headers: dict[str, str]


def _build_url(domain: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return urlunsplit(("https", domain, normalized_path, "", ""))


def _normalize_known_aanbod_url(known_aanbod_url: str | None) -> str | None:
    if known_aanbod_url is None:
        return None
    normalized = known_aanbod_url.strip()
    return normalized or None


def _is_portal_aanbod_url(known_aanbod_url: str) -> bool:
    hostname = (urlsplit(known_aanbod_url).hostname or "").lower()
    return hostname in {"funda.nl", "www.funda.nl", "pararius.nl", "www.pararius.nl"}


def _path_with_query(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        return f"{path}?{parts.query}"
    return path


def _normalize_response(response: object, url: str) -> _FetchedResponse:
    if isinstance(response, _FetchedResponse):
        return response
    if isinstance(response, httpx.Response):
        return _FetchedResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            headers={key.lower(): value for key, value in response.headers.items()},
        )
    status_code = int(getattr(response, "status_code", getattr(response, "status", 200)))
    text = getattr(response, "text", None)
    if text is None:
        content = getattr(response, "content", b"")
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="ignore")
        else:
            text = str(content)
    raw_headers = getattr(response, "headers", {}) or {}
    headers = {str(key).lower(): str(value) for key, value in raw_headers.items()}
    return _FetchedResponse(url=url, status_code=status_code, text=text, headers=headers)


def _default_fetcher(url: str, headers: dict[str, str], timeout: float) -> _FetchedResponse:
    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    return _normalize_response(response, url)


def _blocked_reason(response: _FetchedResponse) -> str | None:
    if _looks_like_challenge_page(response):
        if response.status_code in {200, 403, 503}:
            return "captcha"
    if response.status_code == 429:
        return "http_429"
    if response.status_code == 403:
        return "http_403"
    haystack = " ".join(
        (
            response.text.lower(),
            response.headers.get("location", "").lower(),
            response.headers.get("server", "").lower(),
        )
    )
    if "login" in haystack or "sign in" in haystack or "inloggen" in haystack:
        return "login_wall"
    return None


def _looks_like_challenge_page(response: _FetchedResponse) -> bool:
    haystack = " ".join(
        (
            response.text.lower(),
            response.headers.get("location", "").lower(),
            response.headers.get("server", "").lower(),
        )
    )
    return any(marker in haystack for marker in _CHALLENGE_MARKERS)


def _fingerprint_homepage(html: str) -> str:
    lowered = html.lower()
    if "ogonline" in lowered or "website door ogonline" in lowered:
        return "ogonline"
    if "sumedia" in lowered:
        return "sumedia"
    if "/_resources/themes/" in lowered:
        return "silverstripe"
    if "/wp-content/uploads/realworks/" in lowered:
        return "wordpress"
    if "elementor" in lowered or "wordpress" in lowered or "/wp-content/" in lowered:
        return "wordpress"
    if "kolibri" in lowered:
        return "kolibri"
    return "unknown"


def _listing_pattern_from_urls(urls: list[str]) -> str | None:
    for url in urls:
        path = urlsplit(url).path.lower()
        for pattern in _LISTING_PATTERNS:
            if pattern in path:
                return pattern
    return None


def _extract_sitemap_urls(text: str) -> list[str]:
    return re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", text, flags=re.IGNORECASE)


def _has_listing_type(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if value.get("public") is False:
            continue
        haystack = " ".join(
            str(value.get(field, ""))
            for field in ("slug", "name", "description", "rest_base")
        ).lower()
        if key.lower() in _LISTING_HINTS or any(hint in haystack for hint in _LISTING_HINTS):
            return True
    return False


def _parse_wp_json_payload(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    if _has_listing_type(payload):
        return True
    if isinstance(payload, dict):
        namespaces = payload.get("namespaces")
        routes = payload.get("routes")
        if isinstance(namespaces, list) and any("wp/v2" in str(item) for item in namespaces):
            if _has_listing_type(routes):
                return True
    return False


def _extract_listing_rest_bases(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []

    candidates: list[str] = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if value.get("public") is False:
            continue
        rest_base = str(value.get("rest_base") or key).strip("/")
        haystack = " ".join(
            str(value.get(field, ""))
            for field in ("slug", "name", "description", "rest_base")
        ).lower()
        if key.lower() in _LISTING_HINTS or any(hint in haystack for hint in _LISTING_HINTS):
            if rest_base and rest_base not in candidates:
                candidates.append(rest_base)
    return candidates


def _extract_card_fields(html: str) -> tuple[list[str], str | None, bool, bool]:
    tree = HTMLParser(html)
    text = tree.body.text(separator=" ", strip=True) if tree.body else tree.text(separator=" ", strip=True)
    lowered = text.lower()

    iframes = [node.attributes.get("src", "") for node in tree.css("iframe")]
    if any(src and urlsplit(src).netloc for src in iframes):
        return [], None, False, True

    anchor_urls: list[str] = []
    for node in tree.css("a[href]"):
        href = node.attributes.get("href", "")
        if not href:
            continue
        lowered_href = href.lower()
        if any(pattern in lowered_href for pattern in _LISTING_PATTERNS) or any(hint in lowered_href for hint in _LISTING_HINTS):
            anchor_urls.append(href)

    has_cards = bool(anchor_urls)
    fields: list[str] = []
    if has_cards:
        fields.append("url")
    if "€" in text or "eur" in lowered:
        fields.append("price")
    if "m²" in text or re.search(r"\bm2\b", lowered):
        fields.append("area")
    if tree.css('[class*="address"], [data-testid*="address"]'):
        fields.append("address")
    if tree.css('[class*="city"], [data-testid*="city"]'):
        fields.append("city")

    normalized_fields = [field_name for field_name in _EXTRACTABLE_FIELDS_ORDER if field_name in fields]
    listing_pattern = _listing_pattern_from_urls(anchor_urls)
    script_count = len(tree.css("script"))
    text_is_thin = len(re.sub(r"\s+", " ", text).strip()) < 80
    needs_js = not has_cards and not iframes and script_count > 0 and text_is_thin
    return normalized_fields, listing_pattern, needs_js, False


def _recommended_action(strategy: DiscoveryStrategy, *, structured_channel_open: bool = False) -> str:
    if structured_channel_open:
        return "build_discovery"
    if strategy in {
        DiscoveryStrategy.sitemap_with_listings,
        DiscoveryStrategy.wp_json,
        DiscoveryStrategy.listing_html,
    }:
        return "build_discovery"
    if strategy is DiscoveryStrategy.listing_js:
        return "needs_js_playwright"
    if strategy is DiscoveryStrategy.iframe_only:
        return "commercial_only"
    if strategy in {DiscoveryStrategy.blocked, DiscoveryStrategy.robots_disallow}:
        return "skip_blocked"
    return "manual_review"


class _RequestManager:
    def __init__(
        self,
        domain: str,
        fetcher,
        timeout_seconds: float,
        user_agent: str,
        crawl_delay_seconds: float,
        sleep_between_requests: bool,
    ) -> None:
        self.domain = domain
        self.fetcher = fetcher
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.crawl_delay_seconds = crawl_delay_seconds
        self.sleep_between_requests = sleep_between_requests
        self.requests_used = 0

    def fetch(self, path: str) -> _FetchedResponse | None:
        normalized_path = path if path.startswith("/") else f"/{path}"
        if self.requests_used >= _CONTENT_BUDGET:
            return None
        if not robots_gate.can_fetch(self.domain, normalized_path):
            logger.info("Skipping disallowed path %s for domain %s", normalized_path, self.domain)
            return None
        if self.sleep_between_requests and self.requests_used > 0 and self.crawl_delay_seconds > 0:
            time.sleep(self.crawl_delay_seconds)
        url = _build_url(self.domain, normalized_path)
        response = self.fetcher(
            url,
            {"User-Agent": self.user_agent},
            self.timeout_seconds,
        )
        self.requests_used += 1
        return _normalize_response(response, url)

    def fetch_url(self, url: str) -> _FetchedResponse | None:
        if self.requests_used >= _CONTENT_BUDGET:
            return None
        parsed = urlsplit(url)
        request_domain = (parsed.hostname or self.domain).lower()
        gate_path = parsed.path or "/"
        if not robots_gate.can_fetch(request_domain, gate_path):
            logger.info("Skipping disallowed path %s for domain %s", _path_with_query(url), request_domain)
            return None
        if self.sleep_between_requests and self.requests_used > 0 and self.crawl_delay_seconds > 0:
            time.sleep(self.crawl_delay_seconds)
        response = self.fetcher(
            url,
            {"User-Agent": self.user_agent},
            self.timeout_seconds,
        )
        self.requests_used += 1
        return _normalize_response(response, url)


def _apply_listing_response(classification: DomainClassification, response: _FetchedResponse) -> bool:
    fields, listing_pattern, needs_js, iframe_only = _extract_card_fields(response.text)
    if listing_pattern and classification.listing_url_pattern is None:
        classification.listing_url_pattern = listing_pattern
    if fields:
        classification.card_fields_extractable = fields
        classification.discovery_strategy = DiscoveryStrategy.listing_html
        classification.recommended_action = _recommended_action(classification.discovery_strategy)
        return True
    if needs_js:
        classification.needs_js = True
        classification.discovery_strategy = DiscoveryStrategy.listing_js
        classification.recommended_action = _recommended_action(classification.discovery_strategy)
        return True
    if iframe_only:
        classification.discovery_strategy = DiscoveryStrategy.iframe_only
        classification.recommended_action = _recommended_action(classification.discovery_strategy)
        return True
    return False


def _classification_defaults(domain: str, robots_status_value: str, crawl_delay_value: float) -> DomainClassification:
    return DomainClassification(
        domain=domain,
        robots_status=robots_status_value,
        robots_crawl_delay=crawl_delay_value,
        discovery_strategy=DiscoveryStrategy.no_signal,
        cms_fingerprint_guess="unknown",
        sitemap_found=False,
        sitemap_has_listing_urls=False,
        wp_json_listings_found=False,
        structured_channel_open=False,
        html_blocked_but_structured_open=False,
        listing_url_pattern=None,
        card_fields_extractable=[],
        needs_js=False,
        requests_used=0,
        recommended_action="manual_review",
        blocker_reason=None,
    )


def _pick_blocker_reason(reasons: list[str]) -> str | None:
    for candidate in ("captcha", "login_wall", "http_429", "http_403"):
        if candidate in reasons:
            return candidate
    return reasons[0] if reasons else None


def _record_blocked_reason(reasons: list[str], response: _FetchedResponse | None) -> str | None:
    if response is None:
        return None
    reason = _blocked_reason(response)
    if reason is not None:
        reasons.append(reason)
    return reason


def _apply_structured_channel_open(classification: DomainClassification, *, html_blocked: bool = False) -> None:
    classification.structured_channel_open = True
    if html_blocked:
        classification.html_blocked_but_structured_open = True
    classification.recommended_action = _recommended_action(
        classification.discovery_strategy,
        structured_channel_open=classification.structured_channel_open,
    )


def _apply_blocked_if_needed(classification: DomainClassification, blocked_reasons: list[str]) -> None:
    if classification.discovery_strategy is not DiscoveryStrategy.no_signal or not blocked_reasons:
        classification.recommended_action = _recommended_action(
            classification.discovery_strategy,
            structured_channel_open=classification.structured_channel_open,
        )
        return
    classification.discovery_strategy = DiscoveryStrategy.blocked
    classification.blocker_reason = _pick_blocker_reason(blocked_reasons)
    classification.recommended_action = _recommended_action(DiscoveryStrategy.blocked)


def _probe_sitemaps(
    classification: DomainClassification,
    request_manager: _RequestManager,
    blocked_reasons: list[str],
    *,
    html_blocked: bool = False,
) -> bool:
    nested_candidate: str | None = None
    for sitemap_path in _SITEMAP_PATHS:
        sitemap_response = request_manager.fetch(sitemap_path)
        classification.requests_used = request_manager.requests_used
        _record_blocked_reason(blocked_reasons, sitemap_response)
        if sitemap_response is None or sitemap_response.status_code != 200:
            continue
        classification.sitemap_found = True
        sitemap_urls = _extract_sitemap_urls(sitemap_response.text)
        listing_pattern = _listing_pattern_from_urls(sitemap_urls)
        if listing_pattern is not None:
            classification.sitemap_has_listing_urls = True
            classification.listing_url_pattern = listing_pattern
            classification.discovery_strategy = DiscoveryStrategy.sitemap_with_listings
            _apply_structured_channel_open(classification, html_blocked=html_blocked)
            return True
        if nested_candidate is None:
            for sitemap_url in sitemap_urls:
                lowered = urlsplit(sitemap_url).path.lower()
                if lowered.endswith(".xml") and any(hint in lowered for hint in _LISTING_HINTS):
                    nested_candidate = sitemap_url
                    break
        if classification.sitemap_found:
            break

    if nested_candidate is None:
        return False

    nested_response = request_manager.fetch_url(nested_candidate)
    classification.requests_used = request_manager.requests_used
    _record_blocked_reason(blocked_reasons, nested_response)
    if nested_response is None or nested_response.status_code != 200:
        return False
    nested_urls = _extract_sitemap_urls(nested_response.text)
    listing_pattern = _listing_pattern_from_urls(nested_urls)
    if listing_pattern is None:
        return False
    classification.sitemap_has_listing_urls = True
    classification.listing_url_pattern = listing_pattern
    classification.discovery_strategy = DiscoveryStrategy.sitemap_with_listings
    _apply_structured_channel_open(classification, html_blocked=html_blocked)
    return True


def _probe_wp_json(
    classification: DomainClassification,
    request_manager: _RequestManager,
    blocked_reasons: list[str],
    *,
    html_blocked: bool = False,
) -> bool:
    types_response = request_manager.fetch("/wp-json/wp/v2/types")
    classification.requests_used = request_manager.requests_used
    _record_blocked_reason(blocked_reasons, types_response)
    if types_response is None or types_response.status_code != 200:
        return False

    rest_bases = _extract_listing_rest_bases(types_response.text)
    for rest_base in rest_bases:
        collection_response = request_manager.fetch(f"/wp-json/wp/v2/{rest_base}?per_page=1")
        classification.requests_used = request_manager.requests_used
        _record_blocked_reason(blocked_reasons, collection_response)
        if collection_response is None or collection_response.status_code != 200:
            continue
        try:
            payload = json.loads(collection_response.text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list) and payload:
            classification.wp_json_listings_found = True
            classification.discovery_strategy = DiscoveryStrategy.wp_json
            _apply_structured_channel_open(classification, html_blocked=html_blocked)
            return True
    return False


def classify_domain(domain: str, fetcher=None, known_aanbod_url: str | None = None) -> DomainClassification:
    normalized_domain = domain.strip().lower()
    root_allowed = robots_gate.can_fetch(normalized_domain, "/")
    robots_status_value = robots_gate.robots_status(normalized_domain)
    crawl_delay_value = robots_gate.crawl_delay(normalized_domain)

    if not root_allowed:
        return DomainClassification(
            domain=normalized_domain,
            robots_status="disallow",
            robots_crawl_delay=crawl_delay_value,
            discovery_strategy=DiscoveryStrategy.robots_disallow,
            cms_fingerprint_guess="unknown",
            sitemap_found=False,
            sitemap_has_listing_urls=False,
            wp_json_listings_found=False,
            structured_channel_open=False,
            html_blocked_but_structured_open=False,
            listing_url_pattern=None,
            card_fields_extractable=[],
            needs_js=False,
            requests_used=0,
            recommended_action=_recommended_action(DiscoveryStrategy.robots_disallow),
            blocker_reason=None,
        )

    normalized_aanbod_url = _normalize_known_aanbod_url(known_aanbod_url)
    if normalized_aanbod_url is not None and _is_portal_aanbod_url(normalized_aanbod_url):
        return DomainClassification(
            domain=normalized_domain,
            robots_status=robots_status_value,
            robots_crawl_delay=crawl_delay_value,
            discovery_strategy=DiscoveryStrategy.blocked,
            cms_fingerprint_guess="unknown",
            sitemap_found=False,
            sitemap_has_listing_urls=False,
            wp_json_listings_found=False,
            structured_channel_open=False,
            html_blocked_but_structured_open=False,
            listing_url_pattern=None,
            card_fields_extractable=[],
            needs_js=False,
            requests_used=0,
            recommended_action="commercial_only",
            blocker_reason="aanbod_on_funda_pararius",
        )

    settings = load_runtime_settings(load_dotenv_file=False)
    request_manager = _RequestManager(
        domain=normalized_domain,
        fetcher=fetcher or _default_fetcher,
        timeout_seconds=float(settings.request_timeout_seconds),
        user_agent=settings.user_agent,
        crawl_delay_seconds=crawl_delay_value,
        sleep_between_requests=fetcher is None,
    )
    classification = _classification_defaults(normalized_domain, robots_status_value, crawl_delay_value)
    blocked_reasons: list[str] = []

    home_response = request_manager.fetch("/")
    classification.requests_used = request_manager.requests_used
    home_block_reason = _record_blocked_reason(blocked_reasons, home_response)
    if home_block_reason is not None:
        classification.blocker_reason = home_block_reason
    if home_response is not None:
        classification.cms_fingerprint_guess = _fingerprint_homepage(home_response.text)

    if _probe_sitemaps(classification, request_manager, blocked_reasons, html_blocked=home_block_reason is not None):
        classification.requests_used = request_manager.requests_used
        return classification

    if _probe_wp_json(classification, request_manager, blocked_reasons, html_blocked=home_block_reason is not None):
        classification.requests_used = request_manager.requests_used
        return classification

    if normalized_aanbod_url is not None:
        known_listing_response = request_manager.fetch_url(normalized_aanbod_url)
        classification.requests_used = request_manager.requests_used
        _record_blocked_reason(blocked_reasons, known_listing_response)
        if known_listing_response is not None and known_listing_response.status_code == 200:
            if _apply_listing_response(classification, known_listing_response):
                classification.requests_used = request_manager.requests_used
                return classification

    listing_candidates = _LISTING_PATHS_BY_FINGERPRINT.get(
        classification.cms_fingerprint_guess,
        _LISTING_PATHS_BY_FINGERPRINT["unknown"],
    )
    for listing_path in listing_candidates:
        listing_response = request_manager.fetch(listing_path)
        classification.requests_used = request_manager.requests_used
        _record_blocked_reason(blocked_reasons, listing_response)
        if listing_response is None or listing_response.status_code != 200:
            continue
        if _apply_listing_response(classification, listing_response):
            classification.requests_used = request_manager.requests_used
            return classification

    classification.requests_used = request_manager.requests_used
    _apply_blocked_if_needed(classification, blocked_reasons)
    return classification
