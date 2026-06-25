from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.discovery.website_fetcher import FetchResponse, WebsiteFetcher, dedupe_urls


DEFAULT_OUTPUT_BASE_DIR = Path("data/diagnostics/delivery_mode_evidence")
DEFAULT_PLATFORM_FINGERPRINT_PATH = Path("data/discovery/platform_fingerprint/platform_fingerprint_results.csv")
DEFAULT_DELIVERY_MODE_FINGERPRINT_BASE_DIR = Path("data/diagnostics/delivery_mode_fingerprint")
INVENTORY_FILENAME = "delivery_mode_evidence_inventory.csv"
REPORT_FILENAME = "delivery_mode_evidence_report.md"
TARGET_PLATFORM_GUESSES = {"custom", "unknown", "unsupported"}
PRIORITY_DOMAINS = [
    "hoomz.nl",
    "vandenboschmakelaars.com",
    "tivoliwoningmakelaars.nl",
    "hj-makelaars.nl",
    "vandewatergroep.nl",
    "brabantstadmakelaardij.nl",
    "architectuurmakelaar.nl",
]
CSV_FIELDNAMES = [
    "source_domain",
    "source_id",
    "source_name",
    "website_url",
    "current_aanbod_url",
    "current_platform_guess",
    "current_delivery_mode",
    "homepage_status",
    "aanbod_url_candidates",
    "selected_aanbod_url",
    "listing_page_status",
    "wordpress_signals",
    "wp_json_status",
    "json_ld_found",
    "card_count_estimate",
    "card_selector_candidates",
    "detail_url_pattern",
    "card_fields_visible",
    "xhr_or_api_candidates",
    "iframe_funda_detected",
    "requires_js_likely",
    "commercial_only_signal",
    "detected_delivery_mode_enriched",
    "confidence",
    "recommended_next_action",
    "evidence",
]
LISTING_PATH_HINTS = [
    "/aanbod",
    "/woningaanbod",
    "/wonen",
    "/woningen",
    "/te-koop",
    "/koop",
    "/object",
]
DETAIL_PATH_HINTS = [
    "/woning/",
    "/woningen/",
    "/aanbod/",
    "/object/",
    "/huis/",
    "/te-koop/",
]
EXCLUDED_LISTING_HINTS = [
    "/diensten",
    "/service",
    "/nieuws",
    "/blog",
    "/vacature",
    "/contact",
]
WORDPRESS_SIGNALS = ["wp-content", "wp-json", "wp-includes", "wordpress", "elementor", "api.w.org"]
XHR_API_HINTS = ["fetch(", "xmlhttprequest", "axios", "/api/", "/graphql", "admin-ajax.php", "wp-json", "__next_data__"]
COMMERCIAL_HINTS = [
    "bedrijfsmakelaar",
    "bedrijfsmakelaardij",
    "bedrijfsruimte",
    "bedrijfsobject",
    "kantoorruimte",
    "beleggingspand",
    "commercieel vastgoed",
    "nieuwbouwproject",
    "units beschikbaar",
]
RESIDENTIAL_HINTS = [
    "woning",
    "woningen",
    "woonhuis",
    "appartement",
    "eengezinswoning",
    "slaapkamer",
    "woonoppervlakte",
    "tussenwoning",
    "hoekwoning",
    "vrijstaand",
]
STATUS_HINTS = ["onder bod", "verkocht", "sold", "beschikbaar", "nieuw", "under offer"]
CITY_PATTERN = re.compile(r"\b\d{4}\s?[a-z]{2}\b", re.IGNORECASE)
LIVING_AREA_PATTERN = re.compile(r"\b\d{2,4}\s?(m2|m²)\b", re.IGNORECASE)
ROOMS_PATTERN = re.compile(r"\b\d+\s+(kamers?|rooms?)\b", re.IGNORECASE)
ADDRESS_PATTERN = re.compile(
    r"\b[a-z][a-z0-9' -]{2,}(straat|laan|weg|plein|dreef|ring|pad|steeg|singel|hof)\s+\d+[a-z]?\b",
    re.IGNORECASE,
)
JSON_LD_PROPERTY_HINTS = ['"offer"', '"residence"', '"singlefamilyresidence"', '"apartment"', '"postaladdress"', '"product"']


class FetcherProtocol(Protocol):
    def fetch(self, url: str) -> FetchResponse: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DeliveryModeEvidenceResult:
    run_id: str
    run_dir: Path
    report_path: Path
    inventory_path: Path
    inventory_rows: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class PageSignals:
    wordpress_signals: list[str]
    wp_json_status: str
    json_ld_found: bool
    card_count_estimate: int
    card_selector_candidates: list[str]
    detail_url_pattern: str
    card_fields_visible: list[str]
    xhr_or_api_candidates: list[str]
    iframe_funda_detected: bool
    requires_js_likely: bool
    commercial_only_signal: bool
    detected_delivery_mode_enriched: str
    confidence: float
    recommended_next_action: str
    evidence: list[str]


class _EvidenceHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchor_hrefs: list[str] = []
        self.class_tokens: list[str] = []
        self.script_sources: list[str] = []
        self.script_types: list[str] = []
        self.iframe_sources: list[str] = []
        self.link_hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        lower_tag = tag.lower()
        if lower_tag == "a" and attr_map.get("href"):
            self.anchor_hrefs.append(attr_map["href"])
        if lower_tag == "script":
            if attr_map.get("src"):
                self.script_sources.append(attr_map["src"])
            if attr_map.get("type"):
                self.script_types.append(attr_map["type"].lower())
        if lower_tag == "iframe" and attr_map.get("src"):
            self.iframe_sources.append(attr_map["src"])
        if lower_tag == "link" and attr_map.get("href"):
            self.link_hrefs.append(attr_map["href"])
        if attr_map.get("class"):
            self.class_tokens.extend(token.lower() for token in attr_map["class"].split())


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_if_exists(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    return _read_csv(path)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _extract_domain(*values: str) -> str:
    for value in values:
        raw = (value or "").strip()
        if not raw:
            continue
        parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
        hostname = (parsed.netloc or parsed.path).lower().strip().strip("/")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname:
            return hostname
    return ""


def _read_first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _resolve_platform_fingerprint_path(path: Path | None) -> Path | None:
    candidate = path or DEFAULT_PLATFORM_FINGERPRINT_PATH
    return candidate if candidate.exists() else None


def _resolve_delivery_mode_inventory_path(path: Path | None) -> Path | None:
    if path is not None:
        return path if path.exists() else None
    if not DEFAULT_DELIVERY_MODE_FINGERPRINT_BASE_DIR.exists():
        return None
    run_dirs = sorted(
        [candidate for candidate in DEFAULT_DELIVERY_MODE_FINGERPRINT_BASE_DIR.iterdir() if candidate.is_dir()],
        key=lambda item: item.name,
        reverse=True,
    )
    for run_dir in run_dirs:
        candidate = run_dir / "delivery_mode_inventory.csv"
        if candidate.exists():
            return candidate
    return None


def _parse_html(html_text: str) -> _EvidenceHtmlParser:
    parser = _EvidenceHtmlParser()
    try:
        parser.feed(html_text or "")
    except Exception:
        return parser
    return parser


def _status_from_response(response: FetchResponse | None, *, missing_label: str) -> str:
    if response is None:
        return missing_label
    if response.ok:
        return "ok"
    if response.error:
        return "blocked"
    return f"http_{response.status_code}"


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _score_listing_candidate(url: str, *, root_domain: str, seeded: bool) -> int:
    lowered = (url or "").lower()
    if not lowered:
        return -999
    score = 0
    if _extract_domain(url) == root_domain:
        score += 20
    for hint in LISTING_PATH_HINTS:
        if hint in lowered:
            score += 15
    for hint in EXCLUDED_LISTING_HINTS:
        if hint in lowered:
            score -= 25
    if "funda.nl" in lowered or "pararius.nl" in lowered:
        score -= 100
    if seeded:
        score += 10
    return score


def _collect_listing_candidates(
    row: dict[str, str],
    homepage_response: FetchResponse | None,
    fetcher: FetcherProtocol,
) -> list[str]:
    website_url = _read_first(row, "website_url", "website")
    root_domain = _extract_domain(_read_first(row, "root_domain"), website_url)
    seeded_candidates = []
    current_aanbod_url = _read_first(row, "aanbod_url")
    if current_aanbod_url:
        seeded_candidates.append(current_aanbod_url)
    homepage_candidates: list[str] = []
    if homepage_response and homepage_response.ok and website_url:
        homepage_candidates.extend(fetcher.extract_internal_links(homepage_response.url or website_url, homepage_response.text))
    scored: list[tuple[int, str]] = []
    for candidate in dedupe_urls([*seeded_candidates, *homepage_candidates]):
        score = _score_listing_candidate(candidate, root_domain=root_domain, seeded=candidate in seeded_candidates)
        if score <= 0:
            continue
        scored.append((score, candidate.rstrip("/")))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _score, candidate in scored[:6]]


def _detail_link_score(url: str, *, listing_url: str, root_domain: str) -> int:
    lowered = (url or "").lower()
    score = 0
    if _extract_domain(url) != root_domain:
        return -999
    if lowered.rstrip("/") == listing_url.rstrip("/").lower():
        return -999
    if "funda.nl" in lowered or "pararius.nl" in lowered:
        return -999
    if any(hint in lowered for hint in DETAIL_PATH_HINTS):
        score += 15
    path = urlsplit(url).path.strip("/")
    if path.count("/") >= 1:
        score += 5
    if any(hint in lowered for hint in EXCLUDED_LISTING_HINTS):
        score -= 20
    return score


def _detect_card_selectors(parser: _EvidenceHtmlParser) -> list[str]:
    selectors = sorted(
        {
            token
            for token in parser.class_tokens
            if any(hint in token for hint in ["card", "listing", "object", "property", "woning", "result", "item"])
        }
    )
    return selectors[:6]


def _detect_detail_url_pattern(urls: list[str]) -> str:
    if not urls:
        return ""
    parsed_paths = [urlsplit(url).path.strip("/") for url in urls if urlsplit(url).path.strip("/")]
    if not parsed_paths:
        return ""
    parts = parsed_paths[0].split("/")
    pattern_parts = []
    for part in parts:
        if re.search(r"\d", part):
            pattern_parts.append("{id}")
        elif len(part) > 20:
            pattern_parts.append("{slug}")
        else:
            pattern_parts.append(part)
    return "/" + "/".join(pattern_parts)


def _estimate_card_count(parser: _EvidenceHtmlParser, detail_links: list[str], selector_candidates: list[str]) -> int:
    selector_score = len([token for token in parser.class_tokens if token in selector_candidates])
    if detail_links and selector_score:
        return min(max(len(detail_links), selector_score // 2), 24)
    if detail_links:
        return min(len(detail_links), 24)
    if selector_score:
        return min(max(selector_score // 2, 1), 24)
    return 0


def _detect_card_fields_visible(text: str, *, city: str) -> list[str]:
    lowered = (text or "").lower()
    detected: list[str] = []
    if ADDRESS_PATTERN.search(lowered):
        detected.append("address")
    if any(token in lowered for token in ["€", "eur", "k.k.", "prijs", "p/m"]):
        detected.append("price")
    if any(token in lowered for token in STATUS_HINTS):
        detected.append("status")
    if city and city.lower() in lowered or CITY_PATTERN.search(lowered):
        detected.append("city")
    if LIVING_AREA_PATTERN.search(lowered) or "woonoppervlakte" in lowered:
        detected.append("living_area")
    if ROOMS_PATTERN.search(lowered) or "slaapkamer" in lowered:
        detected.append("rooms")
    return detected


def _detect_xhr_api_candidates(text: str, parser: _EvidenceHtmlParser) -> list[str]:
    lowered = (text or "").lower()
    candidates: list[str] = []
    for hint in XHR_API_HINTS:
        if hint in lowered:
            candidates.append(hint)
    for src in [*parser.script_sources, *parser.link_hrefs]:
        lowered_src = src.lower()
        if any(hint in lowered_src for hint in ["/api/", "graphql", "wp-json", "admin-ajax.php", ".json"]):
            candidates.append(lowered_src)
    return dedupe_urls(candidates)[:6]


def _has_json_ld_property(text: str, parser: _EvidenceHtmlParser) -> bool:
    lowered = (text or "").lower()
    return "application/ld+json" in lowered and any(token in lowered for token in JSON_LD_PROPERTY_HINTS)


def _detect_iframe_funda(parser: _EvidenceHtmlParser, text: str) -> bool:
    return any("funda.nl" in value.lower() for value in parser.iframe_sources) or ("<iframe" in (text or "").lower() and "funda.nl" in (text or "").lower())


def _detect_requires_js(text: str, parser: _EvidenceHtmlParser, *, card_count_estimate: int, xhr_candidates: list[str]) -> bool:
    lowered = (text or "").lower()
    framework_signals = [
        "__next",
        "hydration",
        "data-reactroot",
        "vite",
        "webpack",
        "javascript required",
        "enable javascript",
    ]
    if card_count_estimate > 0:
        return False
    if xhr_candidates:
        return True
    return any(signal in lowered for signal in framework_signals) and len(parser.script_sources) >= 2


def _detect_commercial_only(text: str) -> bool:
    lowered = (text or "").lower()
    commercial_hits = sum(1 for hint in COMMERCIAL_HINTS if hint in lowered)
    residential_hits = sum(1 for hint in RESIDENTIAL_HINTS if hint in lowered)
    return commercial_hits >= 2 and residential_hits == 0


def detect_enriched_delivery_mode(
    *,
    homepage_html: str,
    listing_html: str,
    detail_html: str,
    website_url: str,
    listing_url: str,
    detail_url: str,
    city: str,
) -> PageSignals:
    combined_text = " \n ".join([homepage_html or "", listing_html or "", detail_html or "", website_url or "", listing_url or "", detail_url or ""])
    listing_parser = _parse_html(listing_html or homepage_html)
    detail_parser = _parse_html(detail_html)
    combined_parser = _parse_html(combined_text)
    root_domain = _extract_domain(website_url, listing_url, detail_url)
    detail_candidates = []
    for href in listing_parser.anchor_hrefs:
        absolute = urljoin(f"{listing_url.rstrip('/')}/", href)
        if _detail_link_score(absolute, listing_url=listing_url, root_domain=root_domain) > 0:
            detail_candidates.append(absolute.rstrip("/"))
    detail_candidates = dedupe_urls(detail_candidates)[:6]
    selector_candidates = _detect_card_selectors(listing_parser)
    card_count_estimate = _estimate_card_count(listing_parser, detail_candidates, selector_candidates)
    field_text = " ".join([listing_html or "", detail_html or ""]).strip()
    wordpress_signals = [signal for signal in WORDPRESS_SIGNALS if signal in combined_text.lower()]
    wp_json_status = "detected" if any("wp-json" in signal for signal in [combined_text.lower(), *combined_parser.link_hrefs, *combined_parser.script_sources]) else "not_detected"
    json_ld_found = _has_json_ld_property(field_text or homepage_html, detail_parser if detail_html else listing_parser)
    primary_field_text = field_text or (listing_html or "").strip() or (homepage_html or "").strip()
    card_fields_visible = _detect_card_fields_visible(primary_field_text, city=city)
    xhr_or_api_candidates = _detect_xhr_api_candidates(combined_text, combined_parser)
    iframe_funda_detected = _detect_iframe_funda(combined_parser, combined_text)
    requires_js_likely = _detect_requires_js(combined_text, combined_parser, card_count_estimate=card_count_estimate, xhr_candidates=xhr_or_api_candidates)
    commercial_only_signal = _detect_commercial_only(primary_field_text)
    detail_url_pattern = _detect_detail_url_pattern(detail_candidates)

    evidence: list[str] = []
    if wordpress_signals:
        evidence.append(f"wordpress:{','.join(wordpress_signals[:3])}")
    if json_ld_found:
        evidence.append("json_ld:true")
    if selector_candidates:
        evidence.append(f"selectors:{','.join(selector_candidates[:4])}")
    if xhr_or_api_candidates:
        evidence.append(f"xhr:{','.join(xhr_or_api_candidates[:3])}")
    if detail_url_pattern:
        evidence.append(f"detail_pattern:{detail_url_pattern}")

    if iframe_funda_detected:
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=json_ld_found,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=True,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=commercial_only_signal,
            detected_delivery_mode_enriched="iframe_funda_blocked",
            confidence=0.99,
            recommended_next_action="blocked_by_funda_policy",
            evidence=evidence + ["iframe_funda:true"],
        )
    if commercial_only_signal:
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=json_ld_found,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=False,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=True,
            detected_delivery_mode_enriched="commercial_only",
            confidence=0.94,
            recommended_next_action="skip_commercial_only",
            evidence=evidence + ["commercial_only:true"],
        )
    if wordpress_signals and card_count_estimate > 0 and {"price", "city"} <= set(card_fields_visible):
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=json_ld_found,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=False,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=False,
            detected_delivery_mode_enriched="wordpress_cards",
            confidence=0.88,
            recommended_next_action="create_wordpress_card_config",
            evidence=evidence + [f"card_count:{card_count_estimate}"],
        )
    if card_count_estimate > 0 and {"price", "city"} <= set(card_fields_visible):
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=json_ld_found,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=False,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=False,
            detected_delivery_mode_enriched="html_static_cards",
            confidence=0.81,
            recommended_next_action="create_html_card_config",
            evidence=evidence + [f"card_count:{card_count_estimate}"],
        )
    if json_ld_found:
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=True,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=False,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=False,
            detected_delivery_mode_enriched="json_ld",
            confidence=0.72,
            recommended_next_action="manual_review_needed",
            evidence=evidence,
        )
    if xhr_or_api_candidates:
        return PageSignals(
            wordpress_signals=wordpress_signals,
            wp_json_status=wp_json_status,
            json_ld_found=False,
            card_count_estimate=card_count_estimate,
            card_selector_candidates=selector_candidates,
            detail_url_pattern=detail_url_pattern,
            card_fields_visible=card_fields_visible,
            xhr_or_api_candidates=xhr_or_api_candidates,
            iframe_funda_detected=False,
            requires_js_likely=requires_js_likely,
            commercial_only_signal=False,
            detected_delivery_mode_enriched="xhr_api",
            confidence=0.68,
            recommended_next_action="investigate_xhr_api",
            evidence=evidence,
        )
    return PageSignals(
        wordpress_signals=wordpress_signals,
        wp_json_status=wp_json_status,
        json_ld_found=False,
        card_count_estimate=card_count_estimate,
        card_selector_candidates=selector_candidates,
        detail_url_pattern=detail_url_pattern,
        card_fields_visible=card_fields_visible,
        xhr_or_api_candidates=xhr_or_api_candidates,
        iframe_funda_detected=False,
        requires_js_likely=requires_js_likely,
        commercial_only_signal=False,
        detected_delivery_mode_enriched="unknown_manual_review",
        confidence=0.24,
        recommended_next_action="manual_review_needed",
        evidence=evidence or ["low_evidence"],
    )


def _fetch_page(fetcher: FetcherProtocol, url: str) -> FetchResponse | None:
    if not url:
        return None
    try:
        return fetcher.fetch(url)
    except Exception as exc:
        return FetchResponse(url=url.rstrip("/"), error=str(exc))


def _index_rows_by_domain(rows: list[dict[str, str]], *keys: str) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        domain = _extract_domain(*[_read_first(row, key) for key in keys])
        if domain and domain not in index:
            index[domain] = row
    return index


def _filter_candidate_rows(
    *,
    source_rows: list[dict[str, str]],
    platform_rows_by_domain: dict[str, dict[str, str]],
    delivery_rows_by_domain: dict[str, dict[str, str]],
    city: str,
    province: str,
    source_domains: list[str] | None,
) -> list[tuple[dict[str, str], dict[str, str], dict[str, str]]]:
    normalized_city = _normalize_text(city)
    normalized_province = _normalize_text(province)
    domain_filter = {domain.lower().strip() for domain in source_domains or []}
    candidates: list[tuple[dict[str, str], dict[str, str], dict[str, str]]] = []
    for row in source_rows:
        row_city = _normalize_text(_read_first(row, "gemeente"))
        row_province = _normalize_text(_read_first(row, "province", "provincie"))
        if row_city != normalized_city or row_province != normalized_province:
            continue
        domain = _extract_domain(_read_first(row, "root_domain"), _read_first(row, "website_url", "website"), _read_first(row, "aanbod_url"))
        if not domain:
            continue
        if domain_filter and domain not in domain_filter:
            continue
        delivery_row = delivery_rows_by_domain.get(domain)
        platform_row = platform_rows_by_domain.get(domain)
        if delivery_row is None or platform_row is None:
            continue
        if _read_first(delivery_row, "detected_delivery_mode") != "unknown_manual_review":
            continue
        platform_guess = _read_first(platform_row, "detected_platform").lower()
        if platform_guess not in TARGET_PLATFORM_GUESSES:
            continue
        candidates.append((row, platform_row, delivery_row))
    return candidates


def _audit_source_row(
    row: dict[str, str],
    *,
    city: str,
    fetcher: FetcherProtocol,
    platform_row: dict[str, str],
    delivery_row: dict[str, str],
) -> dict[str, str]:
    website_url = _read_first(row, "website_url", "website")
    homepage_response = _fetch_page(fetcher, website_url)
    aanbod_candidates = _collect_listing_candidates(row, homepage_response, fetcher)
    selected_aanbod_url = aanbod_candidates[0] if aanbod_candidates else ""
    listing_response = None
    if selected_aanbod_url and selected_aanbod_url.rstrip("/") != (homepage_response.url.rstrip("/") if homepage_response and homepage_response.url else website_url.rstrip("/")):
        listing_response = _fetch_page(fetcher, selected_aanbod_url)

    listing_html = listing_response.text if listing_response and listing_response.ok else ""
    homepage_html = homepage_response.text if homepage_response and homepage_response.ok else ""
    preliminary_signals = detect_enriched_delivery_mode(
        homepage_html=homepage_html,
        listing_html=listing_html,
        detail_html="",
        website_url=website_url,
        listing_url=selected_aanbod_url,
        detail_url="",
        city=city,
    )

    detail_response = None
    detail_url = ""
    if preliminary_signals.card_count_estimate > 0 and preliminary_signals.detail_url_pattern:
        parser = _parse_html(listing_html or homepage_html)
        root_domain = _extract_domain(website_url, selected_aanbod_url)
        detail_candidates = []
        for href in parser.anchor_hrefs:
            absolute = urljoin(f"{selected_aanbod_url.rstrip('/')}/", href)
            if _detail_link_score(absolute, listing_url=selected_aanbod_url, root_domain=root_domain) > 0:
                detail_candidates.append(absolute.rstrip("/"))
        detail_candidates = dedupe_urls(detail_candidates)
        if detail_candidates:
            detail_url = detail_candidates[0]
            detail_response = _fetch_page(fetcher, detail_url)

    page_signals = detect_enriched_delivery_mode(
        homepage_html=homepage_html,
        listing_html=listing_html,
        detail_html=detail_response.text if detail_response and detail_response.ok else "",
        website_url=website_url,
        listing_url=selected_aanbod_url,
        detail_url=detail_url,
        city=city,
    )

    homepage_status = _status_from_response(homepage_response, missing_label="missing_input")
    listing_page_status = "no_listing_found"
    if selected_aanbod_url:
        listing_page_status = _status_from_response(listing_response, missing_label="skipped_homepage_only")

    detected_mode = page_signals.detected_delivery_mode_enriched
    recommended_next_action = page_signals.recommended_next_action
    if detected_mode == "unknown_manual_review" and not selected_aanbod_url:
        detected_mode = "no_listing_found"
        recommended_next_action = "fix_source_master_aanbod_url"
    elif detected_mode == "unknown_manual_review" and listing_page_status in {"blocked", "http_403", "http_404", "http_500"}:
        detected_mode = "no_listing_found"
        recommended_next_action = "fix_source_master_aanbod_url"
    elif detected_mode == "unknown_manual_review" and selected_aanbod_url and listing_page_status == "ok" and not page_signals.card_count_estimate:
        recommended_next_action = "manual_review_needed"

    evidence = [
        f"platform_guess:{_read_first(platform_row, 'detected_platform') or 'missing'}",
        f"delivery_mode:{_read_first(delivery_row, 'detected_delivery_mode') or 'missing'}",
        f"homepage_status:{homepage_status}",
        f"listing_status:{listing_page_status}",
    ]
    evidence.extend(page_signals.evidence[:6])

    return {
        "source_domain": _extract_domain(_read_first(row, "root_domain"), website_url, _read_first(row, "aanbod_url")) or "missing_input",
        "source_id": _read_first(row, "source_id") or _read_first(platform_row, "source_id") or "missing_input",
        "source_name": _read_first(row, "office_name") or _read_first(platform_row, "office_name") or "missing_input",
        "website_url": website_url,
        "current_aanbod_url": _read_first(row, "aanbod_url"),
        "current_platform_guess": _read_first(platform_row, "detected_platform") or _read_first(delivery_row, "current_platform_guess") or "unknown",
        "current_delivery_mode": _read_first(delivery_row, "detected_delivery_mode") or "missing_input",
        "homepage_status": homepage_status,
        "aanbod_url_candidates": " | ".join(aanbod_candidates[:5]),
        "selected_aanbod_url": selected_aanbod_url,
        "listing_page_status": listing_page_status,
        "wordpress_signals": " | ".join(page_signals.wordpress_signals[:5]),
        "wp_json_status": page_signals.wp_json_status,
        "json_ld_found": _bool_str(page_signals.json_ld_found),
        "card_count_estimate": str(page_signals.card_count_estimate),
        "card_selector_candidates": " | ".join(page_signals.card_selector_candidates[:5]),
        "detail_url_pattern": page_signals.detail_url_pattern,
        "card_fields_visible": " | ".join(page_signals.card_fields_visible),
        "xhr_or_api_candidates": " | ".join(page_signals.xhr_or_api_candidates[:5]),
        "iframe_funda_detected": _bool_str(page_signals.iframe_funda_detected),
        "requires_js_likely": _bool_str(page_signals.requires_js_likely),
        "commercial_only_signal": _bool_str(page_signals.commercial_only_signal),
        "detected_delivery_mode_enriched": detected_mode,
        "confidence": f"{page_signals.confidence:.2f}",
        "recommended_next_action": recommended_next_action,
        "evidence": " | ".join(item for item in evidence if item),
    }


def _top_counter_items(counter: Counter[str], *, limit: int = 12) -> list[str]:
    return [f"- {name}: {count}" for name, count in counter.most_common(limit)]


def _report_domain_list(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- none"]
    return [f"- {row['source_name']} [{row['source_domain']}]" for row in rows]


def _build_report(
    *,
    run_id: str,
    city: str,
    province: str,
    source_master_path: Path,
    platform_fingerprint_path: Path | None,
    delivery_mode_inventory_path: Path | None,
    inventory_rows: list[dict[str, str]],
) -> str:
    by_mode = Counter(row["detected_delivery_mode_enriched"] for row in inventory_rows)
    by_action = Counter(row["recommended_next_action"] for row in inventory_rows)

    html_rows = [row for row in inventory_rows if row["detected_delivery_mode_enriched"] == "html_static_cards"]
    wordpress_rows = [row for row in inventory_rows if row["detected_delivery_mode_enriched"] == "wordpress_cards"]
    blocked_rows = [
        row
        for row in inventory_rows
        if row["detected_delivery_mode_enriched"] in {"iframe_funda_blocked", "commercial_only"}
    ]
    fix_rows = [row for row in inventory_rows if row["recommended_next_action"] == "fix_source_master_aanbod_url"]

    lines = [
        "# Delivery Mode Evidence Enrichment Report v1",
        "",
        f"- run_timestamp: {run_id}",
        f"- city: {city}",
        f"- province: {province}",
        f"- source_master_path: {source_master_path}",
        f"- platform_fingerprint_path: {platform_fingerprint_path or 'missing_input'}",
        f"- delivery_mode_inventory_path: {delivery_mode_inventory_path or 'missing_input'}",
        f"- total_sources_analyzed: {len(inventory_rows)}",
        "",
        "## Counts By Enriched Delivery Mode",
    ]
    lines.extend(_top_counter_items(by_mode))
    lines.extend(["", "## Counts By Recommended Next Action"])
    lines.extend(_top_counter_items(by_action))
    lines.extend(["", "## HTML Static Card Candidates"])
    lines.extend(_report_domain_list(html_rows))
    lines.extend(["", "## WordPress Card Candidates"])
    lines.extend(_report_domain_list(wordpress_rows))
    lines.extend(["", "## Blocked Or Commercial Only"])
    lines.extend(_report_domain_list(blocked_rows))
    lines.extend(["", "## Source Master Cleanup Candidates"])
    lines.extend(_report_domain_list(fix_rows))
    return "\n".join(lines) + "\n"


def run_delivery_mode_evidence_enrichment(
    *,
    city: str,
    province: str,
    input_path: Path | None = None,
    platform_fingerprint_path: Path | None = None,
    delivery_mode_inventory_path: Path | None = None,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
    source_domains: list[str] | None = None,
    timeout_seconds: float = 8.0,
    fetcher_factory: type[WebsiteFetcher] = WebsiteFetcher,
) -> DeliveryModeEvidenceResult:
    source_master_path = resolve_makelaar_sources_master(
        input_path=input_path,
        province=province,
        restore_latest=True,
    )
    source_rows = _read_csv(source_master_path)
    resolved_platform_fingerprint_path = _resolve_platform_fingerprint_path(platform_fingerprint_path)
    resolved_delivery_mode_inventory_path = _resolve_delivery_mode_inventory_path(delivery_mode_inventory_path)
    platform_rows = _read_csv_if_exists(resolved_platform_fingerprint_path)
    delivery_mode_rows = _read_csv_if_exists(resolved_delivery_mode_inventory_path)
    platform_rows_by_domain = _index_rows_by_domain(platform_rows, "root_domain", "website_url", "aanbod_url")
    delivery_rows_by_domain = _index_rows_by_domain(delivery_mode_rows, "source_domain", "website_url", "current_aanbod_url")

    candidate_rows = _filter_candidate_rows(
        source_rows=source_rows,
        platform_rows_by_domain=platform_rows_by_domain,
        delivery_rows_by_domain=delivery_rows_by_domain,
        city=city,
        province=province,
        source_domains=source_domains,
    )

    priority_order = {domain: index for index, domain in enumerate(PRIORITY_DOMAINS)}
    candidate_rows.sort(
        key=lambda item: (
            priority_order.get(_extract_domain(_read_first(item[0], "root_domain"), _read_first(item[0], "website_url", "website")), 999),
            _read_first(item[0], "office_name").lower(),
        )
    )

    fetcher = fetcher_factory(timeout_seconds=timeout_seconds, delay_seconds=0)
    try:
        inventory_rows = [
            _audit_source_row(row, city=city, fetcher=fetcher, platform_row=platform_row, delivery_row=delivery_row)
            for row, platform_row, delivery_row in candidate_rows
        ]
    finally:
        fetcher.close()

    inventory_rows.sort(
        key=lambda row: (
            row["detected_delivery_mode_enriched"] not in {"html_static_cards", "wordpress_cards"},
            row["recommended_next_action"],
            priority_order.get(row["source_domain"], 999),
            row["source_name"].lower(),
        )
    )

    run_id = _utc_run_id()
    run_dir = output_base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    inventory_path = run_dir / INVENTORY_FILENAME
    report_path = run_dir / REPORT_FILENAME
    _write_csv(inventory_path, inventory_rows)
    _write_markdown(
        report_path,
        _build_report(
            run_id=run_id,
            city=city,
            province=province,
            source_master_path=source_master_path,
            platform_fingerprint_path=resolved_platform_fingerprint_path,
            delivery_mode_inventory_path=resolved_delivery_mode_inventory_path,
            inventory_rows=inventory_rows,
        ),
    )
    return DeliveryModeEvidenceResult(
        run_id=run_id,
        run_dir=run_dir,
        report_path=report_path,
        inventory_path=inventory_path,
        inventory_rows=inventory_rows,
    )
