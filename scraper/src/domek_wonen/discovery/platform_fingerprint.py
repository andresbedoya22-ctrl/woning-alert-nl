from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from .website_fetcher import FetchResponse, WebsiteFetcher


PLATFORMS = [
    "realworks",
    "kolibri",
    "skarabee",
    "yes-co",
    "pararius_office",
    "pyber",
    "osre",
    "tiara",
    "wordpress_makelaar_plugin",
    "custom",
    "unknown",
]

RESULT_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "website_url",
    "aanbod_url",
    "detected_platform",
    "confidence",
    "evidence",
    "parser_priority",
    "recommended_next_action",
    "fetch_status",
    "error",
]

PARSER_WORTHY_PLATFORMS = {
    "realworks",
    "kolibri",
    "skarabee",
    "yes-co",
    "pararius_office",
    "pyber",
    "osre",
    "tiara",
}

PLATFORM_SIGNALS: dict[str, list[str]] = {
    "realworks": ["realworks", "realworks.nl", "rw-og"],
    "kolibri": ["kolibri", "kolibri crm", "kolibri.nl"],
    "skarabee": ["skarabee", "skarabee.nl"],
    "yes-co": ["yes-co", "yesco", "yes-co.nl"],
    "pararius_office": ["parariusoffice", "pararius office"],
    "pyber": ["pyber", "pyber.nl"],
    "osre": ["osre", "osre.nl"],
    "tiara": ["tiara", "tiara.nl"],
}

WORDPRESS_SIGNALS = [
    "wp-content",
    "wp-json",
    "wp-includes",
    "wordpress",
    "elementor",
    "woocommerce",
]


class FetcherProtocol(Protocol):
    def fetch(self, url: str) -> FetchResponse: ...

    def close(self) -> None: ...


def _read_first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_source_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _is_blocked_scrape_url(url: str) -> bool:
    hostname = urlsplit(url).netloc.lower()
    return any(token in hostname for token in ["funda.nl", "pararius.nl"])


def detect_platform_from_text(
    homepage_html: str,
    aanbod_html: str,
    *,
    website_url: str = "",
    aanbod_url: str = "",
) -> tuple[str, float, list[str]]:
    text = " \n ".join([homepage_html or "", aanbod_html or "", website_url or "", aanbod_url or ""]).lower()
    evidence: list[str] = []

    for platform, signals in PLATFORM_SIGNALS.items():
        matches = [signal for signal in signals if signal in text]
        if matches:
            evidence.extend(f"signal:{platform}:{match}" for match in matches[:3])
            confidence = 0.95 if any(match in (homepage_html + aanbod_html).lower() for match in matches) else 0.85
            return platform, confidence, evidence

    wp_matches = [signal for signal in WORDPRESS_SIGNALS if signal in text]
    if wp_matches:
        evidence.extend(f"signal:wordpress:{match}" for match in wp_matches[:3])
        return "wordpress_makelaar_plugin", 0.85, evidence

    if any(token in text for token in ["/api/", ".json", ".xml", "objecten", "woningaanbod", "aanbod"]):
        evidence.append("signal:custom:listing_or_feed_hint")
        return "custom", 0.55, evidence

    return "unknown", 0.2, evidence


def _build_fetch_status(homepage: FetchResponse | None, aanbod: FetchResponse | None) -> tuple[str, str]:
    statuses: list[str] = []
    errors: list[str] = []
    if homepage is None:
        statuses.append("homepage_skipped")
    elif homepage.ok:
        statuses.append("homepage_ok")
    elif homepage.error:
        statuses.append("homepage_error")
        errors.append(f"homepage: {homepage.error}")
    else:
        statuses.append(f"homepage_http_{homepage.status_code}")
    if aanbod is None:
        statuses.append("aanbod_skipped")
    elif aanbod.ok:
        statuses.append("aanbod_ok")
    elif aanbod.error:
        statuses.append("aanbod_error")
        errors.append(f"aanbod: {aanbod.error}")
    else:
        statuses.append(f"aanbod_http_{aanbod.status_code}")
    return ";".join(statuses), " | ".join(errors)


def _parser_priority(platform: str, confidence: float, fetch_status: str) -> str:
    if platform in PARSER_WORTHY_PLATFORMS and confidence >= 0.85:
        return "p1"
    if platform in PARSER_WORTHY_PLATFORMS and confidence >= 0.65:
        return "p2"
    if platform == "wordpress_makelaar_plugin" and confidence >= 0.8:
        return "p2"
    if "error" in fetch_status or "http_" in fetch_status:
        return "p4"
    if platform == "unknown":
        return "p4"
    return "p3"


def _recommended_next_action(platform: str, priority: str) -> str:
    if platform in PARSER_WORTHY_PLATFORMS:
        return f"bundle_into_{platform}_parser_backlog"
    if platform == "wordpress_makelaar_plugin":
        return "inspect_wordpress_plugin_endpoints"
    if platform == "custom":
        return "defer_to_custom_parser_queue"
    if priority == "p4":
        return "retry_or_manual_spot_check"
    return "manual_review"


def audit_source_row(row: dict[str, str], fetcher: FetcherProtocol) -> dict[str, str]:
    website_url = _read_first(row, "website_url", "website")
    aanbod_url = _read_first(row, "aanbod_url")
    homepage_response: FetchResponse | None = None
    aanbod_response: FetchResponse | None = None

    if website_url:
        if _is_blocked_scrape_url(website_url):
            homepage_response = FetchResponse(url=website_url.rstrip("/"), error="blocked_domain")
        else:
            try:
                homepage_response = fetcher.fetch(website_url)
            except Exception as exc:
                homepage_response = FetchResponse(url=website_url.rstrip("/"), error=str(exc))
    if aanbod_url and aanbod_url != website_url:
        if _is_blocked_scrape_url(aanbod_url):
            aanbod_response = FetchResponse(url=aanbod_url.rstrip("/"), error="blocked_domain")
        else:
            try:
                aanbod_response = fetcher.fetch(aanbod_url)
            except Exception as exc:
                aanbod_response = FetchResponse(url=aanbod_url.rstrip("/"), error=str(exc))

    detected_platform, confidence, evidence = detect_platform_from_text(
        homepage_response.text if homepage_response else "",
        aanbod_response.text if aanbod_response else "",
        website_url=website_url,
        aanbod_url=aanbod_url,
    )
    fetch_status, fetch_error = _build_fetch_status(homepage_response, aanbod_response)
    if homepage_response and homepage_response.url and homepage_response.url != website_url.rstrip("/"):
        evidence.append(f"homepage_final_url:{homepage_response.url}")
    if aanbod_response and aanbod_response.url and aanbod_response.url != aanbod_url.rstrip("/"):
        evidence.append(f"aanbod_final_url:{aanbod_response.url}")
    priority = _parser_priority(detected_platform, confidence, fetch_status)
    return {
        "source_id": _read_first(row, "source_id") or f"{_read_first(row, 'root_domain')}__{_read_first(row, 'gemeente')}".strip("_"),
        "office_name": _read_first(row, "office_name"),
        "root_domain": _read_first(row, "root_domain"),
        "website_url": website_url,
        "aanbod_url": aanbod_url,
        "detected_platform": detected_platform,
        "confidence": f"{confidence:.2f}",
        "evidence": " | ".join(evidence[:6]),
        "parser_priority": priority,
        "recommended_next_action": _recommended_next_action(detected_platform, priority),
        "fetch_status": fetch_status,
        "error": fetch_error,
    }


def write_results_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _top_parser_target(rows: list[dict[str, str]]) -> tuple[str, int]:
    counts = Counter(row["detected_platform"] for row in rows if row["detected_platform"] in PARSER_WORTHY_PLATFORMS)
    if not counts:
        return "none", 0
    return counts.most_common(1)[0]


def build_summary_markdown(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["detected_platform"] for row in rows)
    high_confidence_count = sum(1 for row in rows if float(row["confidence"]) >= 0.85)
    unknown_count = counts.get("unknown", 0)
    top_platform, top_count = _top_parser_target(rows)
    examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        platform = row["detected_platform"]
        if len(examples[platform]) < 3:
            label = row["office_name"] or row["root_domain"] or row["source_id"]
            examples[platform].append(label)

    lines = [
        "# Platform Fingerprint Audit v1",
        "",
        f"- Total sources analyzed: {len(rows)}",
        f"- High confidence count: {high_confidence_count}",
        f"- Unknown count: {unknown_count}",
        f"- Top parser target by coverage: {top_platform} ({top_count})",
        f"- Next recommended parser to build: {_recommended_parser_summary(top_platform, top_count)}",
        "",
        "## Counts By Platform",
    ]
    for platform in PLATFORMS:
        lines.append(f"- {platform}: {counts.get(platform, 0)}")
    lines.extend(["", "## Examples Per Platform"])
    for platform in PLATFORMS:
        if examples.get(platform):
            lines.append(f"- {platform}: {', '.join(examples[platform])}")
    return "\n".join(lines) + "\n"


def _recommended_parser_summary(platform: str, count: int) -> str:
    if platform == "none" or count == 0:
        return "no shared CRM stands out yet; collect more evidence or review unknown/custom sources"
    return f"build the {platform} parser first because it covers {count} detected sources"


def write_summary_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_summary_markdown(rows), encoding="utf-8")


def run_platform_fingerprint_audit(
    *,
    input_path: Path,
    output_csv_path: Path,
    output_summary_path: Path,
    province: str = "",
    max_sources: int | None = None,
    timeout_seconds: float = 8.0,
    fetcher_factory: type[WebsiteFetcher] = WebsiteFetcher,
) -> list[dict[str, str]]:
    rows = load_source_rows(input_path)
    if province:
        province_normalized = province.strip().lower()
        rows = [
            row
            for row in rows
            if _read_first(row, "province", "provincie").strip().lower() == province_normalized
        ]
    if max_sources is not None:
        rows = rows[:max_sources]

    fetcher = fetcher_factory(timeout_seconds=timeout_seconds, delay_seconds=0)
    try:
        results = [audit_source_row(row, fetcher) for row in rows]
    finally:
        fetcher.close()

    write_results_csv(output_csv_path, results)
    write_summary_markdown(output_summary_path, results)
    return results
