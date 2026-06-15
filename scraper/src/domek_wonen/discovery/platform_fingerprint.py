from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
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

TARGET_AREA_RESULT_FIELDNAMES = [
    "source_id",
    "office_name",
    "root_domain",
    "gemeente",
    "website_url",
    "aanbod_url",
    "detected_platform",
    "confidence_score",
    "detection_reasons",
    "parser_status",
    "recommended_action",
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

TARGET_AREA_SUPPORTED_PLATFORMS = {"realworks"}
TARGET_AREA_UNSUPPORTED_PLATFORMS = {"ogonline_candidate", "wordpress_candidate"}
OGONLINE_SIGNALS = [
    ("website door ogonline", 0.92, "signal:ogonline:website_door_ogonline"),
    ("ogonline", 0.88, "signal:ogonline:ogonline"),
    ("/aanbod/wonen/te-koop", 0.78, "signal:ogonline:aanbod_wonen_te_koop"),
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


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def detect_target_platform_from_text(
    homepage_html: str,
    aanbod_html: str,
    *,
    website_url: str = "",
    aanbod_url: str = "",
) -> tuple[str, float, list[str]]:
    detected_platform, confidence, evidence = detect_platform_from_text(
        homepage_html,
        aanbod_html,
        website_url=website_url,
        aanbod_url=aanbod_url,
    )
    if detected_platform == "realworks":
        return "realworks", confidence, evidence

    text = " \n ".join([homepage_html or "", aanbod_html or "", website_url or "", aanbod_url or ""]).lower()
    ogonline_matches = [(score, reason) for signal, score, reason in OGONLINE_SIGNALS if signal in text]
    if ogonline_matches:
        confidence = max(score for score, _reason in ogonline_matches)
        reasons = [reason for _score, reason in ogonline_matches]
        return "ogonline_candidate", confidence, reasons

    wp_matches = [signal for signal in WORDPRESS_SIGNALS if signal in text]
    if wp_matches:
        reasons = [f"signal:wordpress:{match}" for match in wp_matches[:3]]
        return "wordpress_candidate", 0.85, reasons

    return "unknown", 0.2, []


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


def write_target_area_results_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TARGET_AREA_RESULT_FIELDNAMES)
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


def _normalize_gemeente(value: str) -> str:
    return " ".join(value.strip().lower().replace("’", "'").split())


def _filter_rows_by_target_gemeentes(
    rows: list[dict[str, str]],
    target_gemeentes: list[str],
) -> list[dict[str, str]]:
    normalized_targets = {_normalize_gemeente(value) for value in target_gemeentes if value.strip()}
    if not normalized_targets:
        return rows
    return [row for row in rows if _normalize_gemeente(_read_first(row, "gemeente")) in normalized_targets]


def _is_unreachable(response: FetchResponse | None) -> bool:
    if response is None:
        return False
    return bool(response.error) or response.status_code >= 400


def _target_parser_status(platform: str) -> str:
    if platform in TARGET_AREA_SUPPORTED_PLATFORMS:
        return "supported"
    if platform in TARGET_AREA_UNSUPPORTED_PLATFORMS:
        return "unsupported"
    return "unknown"


def _target_recommended_action(
    platform: str,
    *,
    website_url: str,
    aanbod_url: str,
    homepage_response: FetchResponse | None,
    aanbod_response: FetchResponse | None,
) -> str:
    if not aanbod_url:
        return "no_aanbod_url"
    if (
        website_url
        and _is_unreachable(homepage_response)
        and (aanbod_response is None or _is_unreachable(aanbod_response))
    ):
        return "source_unreachable"
    if platform in TARGET_AREA_SUPPORTED_PLATFORMS:
        return "use_existing_parser"
    if platform == "ogonline_candidate":
        return "needs_parser"
    return "needs_manual_review"


def audit_target_area_source_row(row: dict[str, str], fetcher: FetcherProtocol) -> dict[str, str]:
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

    detected_platform, confidence, reasons = detect_target_platform_from_text(
        homepage_response.text if homepage_response else "",
        aanbod_response.text if aanbod_response else "",
        website_url=website_url,
        aanbod_url=aanbod_url,
    )
    if homepage_response and homepage_response.url and homepage_response.url != website_url.rstrip("/"):
        reasons.append(f"homepage_final_url:{homepage_response.url}")
    if aanbod_response and aanbod_response.url and aanbod_response.url != aanbod_url.rstrip("/"):
        reasons.append(f"aanbod_final_url:{aanbod_response.url}")
    if homepage_response and homepage_response.error:
        reasons.append(f"homepage_error:{homepage_response.error}")
    if aanbod_response and aanbod_response.error:
        reasons.append(f"aanbod_error:{aanbod_response.error}")

    parser_status = _target_parser_status(detected_platform)
    recommended_action = _target_recommended_action(
        detected_platform,
        website_url=website_url,
        aanbod_url=aanbod_url,
        homepage_response=homepage_response,
        aanbod_response=aanbod_response,
    )
    return {
        "source_id": _read_first(row, "source_id") or f"{_read_first(row, 'root_domain')}__{_read_first(row, 'gemeente')}".strip("_"),
        "office_name": _read_first(row, "office_name"),
        "root_domain": _read_first(row, "root_domain"),
        "gemeente": _read_first(row, "gemeente"),
        "website_url": website_url,
        "aanbod_url": aanbod_url,
        "detected_platform": detected_platform,
        "confidence_score": f"{confidence:.2f}",
        "detection_reasons": " | ".join(reasons[:8]),
        "parser_status": parser_status,
        "recommended_action": recommended_action,
    }


def _recommended_target_parser(rows: list[dict[str, str]]) -> tuple[str, int]:
    counts = Counter(
        row["detected_platform"]
        for row in rows
        if row["recommended_action"] == "needs_parser"
    )
    if not counts:
        return "none", 0
    return counts.most_common(1)[0]


def build_target_area_report_markdown(
    rows: list[dict[str, str]],
    *,
    run_id: str,
    target_gemeentes: list[str],
) -> str:
    by_gemeente = Counter(row["gemeente"] or "unknown" for row in rows)
    by_platform = Counter(row["detected_platform"] for row in rows)
    by_status = Counter(row["parser_status"] for row in rows)
    top_domains = Counter(
        row["root_domain"] or row["website_url"] or row["source_id"]
        for row in rows
        if row["parser_status"] in {"unsupported", "unknown"}
    )
    next_parser, next_parser_count = _recommended_target_parser(rows)
    kin_rows = [row for row in rows if (row["root_domain"] or "").lower() == "kinmakelaars.nl"]

    lines = [
        "# Target Area Platform Fingerprint Report v1",
        "",
        f"- Run timestamp: {run_id}",
        f"- Target gemeentes: {', '.join(target_gemeentes)}",
        f"- Total sources analyzed: {len(rows)}",
        "",
        "## Sources By Gemeente",
    ]
    for gemeente, count in sorted(by_gemeente.items(), key=lambda item: (-item[1], item[0].lower())):
        lines.append(f"- {gemeente}: {count}")

    lines.extend(["", "## Sources By Detected Platform"])
    for platform, count in sorted(by_platform.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {platform}: {count}")

    lines.extend(
        [
            "",
            "## Parser Status",
            f"- supported: {by_status.get('supported', 0)}",
            f"- unsupported: {by_status.get('unsupported', 0)}",
            f"- unknown: {by_status.get('unknown', 0)}",
            "",
            "## Top Unsupported Or Unknown Domains",
        ]
    )
    if top_domains:
        for domain, count in top_domains.most_common(10):
            lines.append(f"- {domain}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## KIN Check"])
    if kin_rows:
        for row in kin_rows:
            lines.append(
                f"- {row['office_name']} ({row['gemeente']}): {row['detected_platform']} "
                f"(confidence {row['confidence_score']}), action {row['recommended_action']}"
            )
    else:
        lines.append("- kinmakelaars.nl not present in filtered target area sources")

    lines.extend(["", "## Recommended Next Parser"])
    if next_parser == "none":
        lines.append("- No parser candidate stands out yet; prioritize manual review of unknown sources.")
    else:
        lines.append(
            f"- Build {next_parser} next because it affects {next_parser_count} target-area source(s) "
            "currently marked as needs_parser."
        )
    return "\n".join(lines) + "\n"


def write_target_area_report_markdown(
    path: Path,
    rows: list[dict[str, str]],
    *,
    run_id: str,
    target_gemeentes: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        build_target_area_report_markdown(rows, run_id=run_id, target_gemeentes=target_gemeentes),
        encoding="utf-8",
    )


def run_target_area_platform_fingerprint(
    *,
    input_path: Path,
    output_dir: Path,
    target_gemeentes: list[str],
    max_sources: int | None = None,
    timeout_seconds: float = 8.0,
    fetcher_factory: type[WebsiteFetcher] = WebsiteFetcher,
) -> tuple[str, list[dict[str, str]], Path, Path]:
    rows = load_source_rows(input_path)
    rows = _filter_rows_by_target_gemeentes(rows, target_gemeentes)
    if max_sources is not None:
        rows = rows[:max_sources]

    run_id = _utc_run_id()
    run_dir = output_dir / run_id
    inventory_path = run_dir / "target_area_platform_fingerprint_inventory.csv"
    report_path = run_dir / "target_area_platform_fingerprint_report.md"

    fetcher = fetcher_factory(timeout_seconds=timeout_seconds, delay_seconds=0)
    try:
        results = [audit_target_area_source_row(row, fetcher) for row in rows]
    finally:
        fetcher.close()

    write_target_area_results_csv(inventory_path, results)
    write_target_area_report_markdown(report_path, results, run_id=run_id, target_gemeentes=target_gemeentes)
    return run_id, results, inventory_path, report_path


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
