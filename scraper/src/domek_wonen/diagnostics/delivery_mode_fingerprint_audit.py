from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.discovery.platform_fingerprint import detect_target_platform_from_text
from domek_wonen.discovery.website_fetcher import FetchResponse, WebsiteFetcher


DEFAULT_OUTPUT_BASE_DIR = Path("data/diagnostics/delivery_mode_fingerprint")
DEFAULT_PLATFORM_FINGERPRINT_PATH = Path("data/discovery/platform_fingerprint/platform_fingerprint_results.csv")
INVENTORY_FILENAME = "delivery_mode_inventory.csv"
REPORT_FILENAME = "delivery_mode_report.md"
CSV_FIELDNAMES = [
    "source_domain",
    "source_name",
    "current_platform_guess",
    "detected_delivery_mode",
    "confidence",
    "parser_family_candidate",
    "config_required",
    "likely_reusable_template",
    "evidence",
    "recommended_next_action",
]
DELIVERY_MODES = [
    "realworks",
    "ogonline_xhr",
    "html_static_cards",
    "wordpress_cards",
    "json_ld",
    "xhr_api",
    "iframe_funda_blocked",
    "unknown_manual_review",
]
RECOMMENDED_ACTIONS = [
    "keep_existing_realworks",
    "keep_existing_ogonline",
    "create_html_card_config",
    "create_wordpress_card_config",
    "investigate_xhr_api",
    "blocked_by_funda_policy",
    "manual_review_needed",
]
WORDPRESS_HINTS = ["wp-content", "wp-json", "wp-includes", "wordpress", "elementor"]
CARD_CONTAINER_HINTS = ["card", "listing", "object", "property", "woning", "home", "result", "item"]
DETAIL_LINK_HINTS = ["woning", "woningen", "aanbod", "object", "huis", "huizen", "te-koop", "koop"]
PRICE_HINTS = ["€", "eur", "k.k.", "p/m", "prijs op aanvraag"]
CITY_HINTS = ["tilburg", "breda", "waalwijk", "eindhoven", "den bosch", "'s-hertogenbosch", "oisterwijk"]


class FetcherProtocol(Protocol):
    def fetch(self, url: str) -> FetchResponse: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class DeliveryModeAuditResult:
    run_id: str
    run_dir: Path
    report_path: Path
    inventory_path: Path
    inventory_rows: list[dict[str, str]]


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchor_hrefs: list[str] = []
        self.script_types: list[str] = []
        self.iframe_sources: list[str] = []
        self.class_tokens: list[str] = []
        self._current_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current_tag = tag.lower()
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        if self._current_tag == "a" and attr_map.get("href"):
            self.anchor_hrefs.append(attr_map["href"])
        if self._current_tag == "script" and attr_map.get("type"):
            self.script_types.append(attr_map["type"].lower())
        if self._current_tag == "iframe" and attr_map.get("src"):
            self.iframe_sources.append(attr_map["src"].lower())
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
    return " ".join((value or "").strip().lower().replace("_", " ").split())


def _normalize_city(value: str) -> str:
    return _normalize_text(value)


def _normalize_province(value: str) -> str:
    return _normalize_text(value).replace("-", " ")


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


def _index_platform_fingerprint_rows(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_source_id: dict[str, dict[str, str]] = {}
    by_domain: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = (row.get("source_id") or "").strip().lower()
        domain = _extract_domain(row.get("root_domain", ""), row.get("website_url", ""), row.get("aanbod_url", ""))
        if source_id and source_id not in by_source_id:
            by_source_id[source_id] = row
        if domain and domain not in by_domain:
            by_domain[domain] = row
    return by_source_id, by_domain


def _parse_html_features(html_text: str) -> _AnchorParser:
    parser = _AnchorParser()
    try:
        parser.feed(html_text or "")
    except Exception:
        return parser
    return parser


def _contains_visible_cards(html_text: str) -> tuple[bool, int, list[str]]:
    parser = _parse_html_features(html_text)
    text = (html_text or "").lower()
    card_like_classes = [token for token in parser.class_tokens if any(hint in token for hint in CARD_CONTAINER_HINTS)]
    detail_links = [
        href
        for href in parser.anchor_hrefs
        if any(hint in href.lower() for hint in DETAIL_LINK_HINTS)
        and not href.lower().startswith("mailto:")
    ]
    price_signal = any(hint in text for hint in PRICE_HINTS)
    city_signal = any(hint in text for hint in CITY_HINTS)
    visible = len(detail_links) >= 2 and price_signal and city_signal and bool(card_like_classes)
    evidence = []
    if card_like_classes:
        evidence.append(f"class_tokens:{','.join(card_like_classes[:4])}")
    if detail_links:
        evidence.append(f"detail_links:{len(detail_links)}")
    if price_signal:
        evidence.append("price_signal:true")
    if city_signal:
        evidence.append("city_signal:true")
    return visible, len(detail_links), evidence


def _contains_json_ld_listing(html_text: str) -> bool:
    text = (html_text or "").lower()
    return "application/ld+json" in text and any(
        token in text for token in ['"offer"', '"residence"', '"singlefamilyresidence"', '"apartment"', '"postaladdress"']
    )


def _contains_xhr_api_signals(html_text: str, listing_url: str) -> bool:
    text = (html_text or "").lower()
    url_text = (listing_url or "").lower()
    if any(token in url_text for token in ["/api/", ".json", "/graphql"]):
        return True
    return any(
        token in text
        for token in ["fetch(", "xmlhttprequest", "/api/", "__next_data__", '"graphql"', '"objecten"', '"woningaanbod"']
    )


def _contains_funda_iframe(html_text: str, website_url: str, listing_url: str) -> bool:
    parser = _parse_html_features(html_text)
    iframe_sources = parser.iframe_sources
    combined = " ".join([html_text or "", website_url or "", listing_url or ""]).lower()
    return any("funda.nl" in source for source in iframe_sources) or ("funda.nl" in combined and "<iframe" in combined)


def detect_delivery_mode_from_text(
    homepage_html: str,
    listing_html: str,
    *,
    website_url: str = "",
    listing_url: str = "",
    current_platform_guess: str = "",
) -> tuple[str, float, list[str]]:
    homepage_text = homepage_html or ""
    listing_text = listing_html or ""
    combined = " \n ".join([homepage_text, listing_text, website_url, listing_url]).lower()
    evidence: list[str] = []
    wp_signals = [signal for signal in WORDPRESS_HINTS if signal in combined]
    visible_cards, card_count, card_evidence = _contains_visible_cards(listing_text or homepage_text)

    platform_guess = (current_platform_guess or "").strip().lower()
    if platform_guess == "realworks":
        return "realworks", 0.98, ["platform_guess:realworks"]
    if platform_guess in {"ogonline", "ogonline_candidate"}:
        return "ogonline_xhr", 0.95, [f"platform_guess:{platform_guess}"]

    if wp_signals and visible_cards:
        evidence.extend(f"signal:wordpress:{signal}" for signal in wp_signals[:3])
        evidence.extend(card_evidence[:3])
        return "wordpress_cards", 0.86, evidence

    detected_platform, platform_confidence, platform_reasons = detect_target_platform_from_text(
        homepage_text,
        listing_text,
        website_url=website_url,
        aanbod_url=listing_url,
    )
    if detected_platform == "realworks":
        evidence.extend(platform_reasons[:4])
        return "realworks", max(0.95, platform_confidence), evidence
    if detected_platform == "ogonline_candidate":
        evidence.extend(platform_reasons[:4])
        return "ogonline_xhr", max(0.92, platform_confidence), evidence

    if _contains_funda_iframe(listing_text or homepage_text, website_url, listing_url):
        return "iframe_funda_blocked", 0.99, ["signal:funda_iframe"]

    if visible_cards:
        evidence.extend(card_evidence[:4])
        return "html_static_cards", 0.78 if card_count >= 2 else 0.68, evidence

    if _contains_json_ld_listing(listing_text or homepage_text):
        return "json_ld", 0.72, ["signal:json_ld_listing"]

    if _contains_xhr_api_signals(listing_text or homepage_text, listing_url):
        return "xhr_api", 0.64, ["signal:xhr_api_hint"]

    return "unknown_manual_review", 0.25, (platform_reasons[:3] if platform_reasons else ["signal:low_evidence"])


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _parser_family_candidate(delivery_mode: str) -> str:
    mapping = {
        "realworks": "realworks",
        "ogonline_xhr": "ogonline",
        "html_static_cards": "html_static_cards",
        "wordpress_cards": "wordpress_cards",
        "json_ld": "json_ld",
        "xhr_api": "xhr_api",
        "iframe_funda_blocked": "",
        "unknown_manual_review": "",
    }
    return mapping.get(delivery_mode, "")


def _config_required(delivery_mode: str) -> bool:
    return delivery_mode in {"html_static_cards", "wordpress_cards"}


def _likely_reusable_template(delivery_mode: str) -> str:
    mapping = {
        "html_static_cards": "html_static_cards.default.json",
        "wordpress_cards": "wordpress_cards.default.json",
        "realworks": "existing_realworks_parser",
        "ogonline_xhr": "existing_ogonline_family_placeholder",
        "json_ld": "json_ld_manual_probe",
        "xhr_api": "xhr_api_manual_probe",
    }
    return mapping.get(delivery_mode, "")


def _recommended_next_action(delivery_mode: str) -> str:
    mapping = {
        "realworks": "keep_existing_realworks",
        "ogonline_xhr": "keep_existing_ogonline",
        "html_static_cards": "create_html_card_config",
        "wordpress_cards": "create_wordpress_card_config",
        "json_ld": "manual_review_needed",
        "xhr_api": "investigate_xhr_api",
        "iframe_funda_blocked": "blocked_by_funda_policy",
        "unknown_manual_review": "manual_review_needed",
    }
    return mapping[delivery_mode]


def _fetch_page(fetcher: FetcherProtocol, url: str) -> FetchResponse | None:
    if not url:
        return None
    try:
        return fetcher.fetch(url)
    except Exception as exc:
        return FetchResponse(url=url.rstrip("/"), error=str(exc))


def _current_platform_guess(
    source_row: dict[str, str],
    fingerprint_row: dict[str, str] | None,
) -> tuple[str, list[str]]:
    if fingerprint_row is not None:
        guess = (fingerprint_row.get("detected_platform") or "").strip().lower()
        evidence = []
        for key in ["detected_platform", "confidence", "fetch_status", "evidence", "error"]:
            value = (fingerprint_row.get(key) or "").strip()
            if value:
                evidence.append(f"platform_fingerprint:{key}={value}")
        return guess or "unknown", evidence[:4]

    detected_platform, _confidence, reasons = detect_target_platform_from_text(
        "",
        "",
        website_url=_read_first(source_row, "website_url", "website"),
        aanbod_url=_read_first(source_row, "aanbod_url"),
    )
    return detected_platform or "unknown", reasons[:4]


def audit_source_row(
    row: dict[str, str],
    *,
    fetcher: FetcherProtocol,
    fingerprint_row: dict[str, str] | None,
) -> dict[str, str]:
    website_url = _read_first(row, "website_url", "website")
    listing_url = _read_first(row, "aanbod_url")
    homepage_response = _fetch_page(fetcher, website_url)
    listing_response = _fetch_page(fetcher, listing_url) if listing_url and listing_url != website_url else None

    current_platform_guess, platform_evidence = _current_platform_guess(row, fingerprint_row)
    delivery_mode, confidence, delivery_evidence = detect_delivery_mode_from_text(
        homepage_response.text if homepage_response else "",
        listing_response.text if listing_response else "",
        website_url=website_url,
        listing_url=listing_url,
        current_platform_guess=current_platform_guess,
    )

    source_domain = _extract_domain(_read_first(row, "root_domain"), website_url, listing_url) or "missing_input"
    source_name = _read_first(row, "office_name") or source_domain
    evidence = list(platform_evidence)
    evidence.extend(delivery_evidence)
    if homepage_response and homepage_response.error:
        evidence.append(f"homepage_error:{homepage_response.error}")
    if listing_response and listing_response.error:
        evidence.append(f"listing_error:{listing_response.error}")

    return {
        "source_domain": source_domain,
        "source_name": source_name,
        "current_platform_guess": current_platform_guess or "unknown",
        "detected_delivery_mode": delivery_mode,
        "confidence": f"{confidence:.2f}",
        "parser_family_candidate": _parser_family_candidate(delivery_mode),
        "config_required": _bool_str(_config_required(delivery_mode)),
        "likely_reusable_template": _likely_reusable_template(delivery_mode),
        "evidence": " | ".join(item for item in evidence[:8] if item),
        "recommended_next_action": _recommended_next_action(delivery_mode),
    }


def _top_counter_items(counter: Counter[str], *, limit: int = 10) -> list[str]:
    return [f"- {name}: {count}" for name, count in counter.most_common(limit)]


def _build_report(
    *,
    run_id: str,
    city: str,
    province: str,
    source_master_path: Path,
    platform_fingerprint_path: Path | None,
    inventory_rows: list[dict[str, str]],
) -> str:
    by_delivery_mode = Counter(row["detected_delivery_mode"] for row in inventory_rows)
    by_action = Counter(row["recommended_next_action"] for row in inventory_rows)
    templates: dict[str, list[str]] = defaultdict(list)
    for row in inventory_rows:
        mode = row["detected_delivery_mode"]
        if mode not in {"html_static_cards", "wordpress_cards"}:
            continue
        if len(templates[mode]) >= 8:
            continue
        templates[mode].append(f"{row['source_name']} [{row['source_domain']}]")

    lines = [
        "# Delivery Mode Fingerprint Report v1",
        "",
        f"- run_timestamp: {run_id}",
        f"- city: {city}",
        f"- province: {province}",
        f"- source_master_path: {source_master_path}",
        f"- platform_fingerprint_path: {platform_fingerprint_path or 'missing_input'}",
        f"- total_sources_analyzed: {len(inventory_rows)}",
        "",
        "## Counts By Delivery Mode",
    ]
    lines.extend(_top_counter_items(by_delivery_mode))
    lines.extend(["", "## Counts By Recommended Next Action"])
    lines.extend(_top_counter_items(by_action))
    lines.extend(["", "## Top HTML Static Card Config Candidates"])
    if templates["html_static_cards"]:
        lines.extend(f"- {item}" for item in templates["html_static_cards"])
    else:
        lines.append("- none")
    lines.extend(["", "## Top WordPress Card Config Candidates"])
    if templates["wordpress_cards"]:
        lines.extend(f"- {item}" for item in templates["wordpress_cards"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def run_delivery_mode_fingerprint_audit(
    *,
    city: str,
    province: str,
    input_path: Path | None = None,
    platform_fingerprint_path: Path | None = None,
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR,
    max_sources: int | None = None,
    timeout_seconds: float = 8.0,
    fetcher_factory: type[WebsiteFetcher] = WebsiteFetcher,
) -> DeliveryModeAuditResult:
    source_master_path = resolve_makelaar_sources_master(
        input_path=input_path,
        province=province,
        restore_latest=True,
    )
    source_rows = _read_csv(source_master_path)
    normalized_city = _normalize_city(city)
    normalized_province = _normalize_province(province)
    filtered_rows = [
        row
        for row in source_rows
        if _normalize_city(_read_first(row, "gemeente")) == normalized_city
        and _normalize_province(_read_first(row, "province", "provincie")) == normalized_province
    ]
    if max_sources is not None:
        filtered_rows = filtered_rows[:max_sources]

    resolved_platform_fingerprint_path = _resolve_platform_fingerprint_path(platform_fingerprint_path)
    fingerprint_rows = _read_csv_if_exists(resolved_platform_fingerprint_path)
    fingerprint_by_source_id, fingerprint_by_domain = _index_platform_fingerprint_rows(fingerprint_rows)

    fetcher = fetcher_factory(timeout_seconds=timeout_seconds, delay_seconds=0)
    try:
        inventory_rows: list[dict[str, str]] = []
        for row in filtered_rows:
            source_id = (_read_first(row, "source_id") or "").lower()
            source_domain = _extract_domain(_read_first(row, "root_domain"), _read_first(row, "website"), _read_first(row, "aanbod_url"))
            fingerprint_row = None
            if source_id:
                fingerprint_row = fingerprint_by_source_id.get(source_id)
            if fingerprint_row is None and source_domain:
                fingerprint_row = fingerprint_by_domain.get(source_domain)
            inventory_rows.append(audit_source_row(row, fetcher=fetcher, fingerprint_row=fingerprint_row))
    finally:
        fetcher.close()

    inventory_rows.sort(
        key=lambda row: (
            row["detected_delivery_mode"] not in {"html_static_cards", "wordpress_cards"},
            row["recommended_next_action"],
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
            inventory_rows=inventory_rows,
        ),
    )

    return DeliveryModeAuditResult(
        run_id=run_id,
        run_dir=run_dir,
        report_path=report_path,
        inventory_path=inventory_path,
        inventory_rows=inventory_rows,
    )
