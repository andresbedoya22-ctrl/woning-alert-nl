from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import re
import unicodedata

from domek_wonen.portals.models import PortalCityResult, PortalListing, PortalMode, PortalSpikeResult, SourceStatus

REPORT_FILL_FIELDS = (
    "address_raw",
    "postcode_raw",
    "city_raw",
    "price_raw",
    "status_raw",
    "living_area_raw",
    "rooms_raw",
    "property_type_raw",
    "broker_raw",
    "image_url",
)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_blocked_page(html: str, status_code: int | None) -> SourceStatus | None:
    if status_code == 403:
        return SourceStatus.HTTP_403
    if status_code == 429:
        return SourceStatus.HTTP_429

    normalized_html = normalize_text(html).lower()
    blocked_markers = {
        SourceStatus.BLOCKED_CAPTCHA: ("captcha", "recaptcha", "hcaptcha", "cloudflare challenge"),
        SourceStatus.PERMISSION_REQUIRED: ("sign in to continue", "log in om verder te gaan", "login required"),
        SourceStatus.REQUIRES_JS: ("enable javascript", "javascript required", "without javascript"),
    }
    for status, markers in blocked_markers.items():
        if any(marker in normalized_html for marker in markers):
            return status
    return None


def calculate_fill_rate(listings: list[PortalListing], field_name: str) -> float:
    if not listings:
        return 0.0
    populated = sum(1 for listing in listings if normalize_text(str(getattr(listing, field_name, ""))))
    return populated / len(listings)


def dedup_key_for_listing(listing: PortalListing) -> str:
    property_url = normalize_text(listing.property_url).lower()
    if property_url:
        return property_url

    fragments = [
        listing.portal,
        listing.city_query,
        listing.address_raw,
        listing.postcode_raw,
        listing.price_raw,
    ]
    return "|".join(normalize_text(fragment).lower() for fragment in fragments)


def calculate_duplicate_url_rate(listings: list[PortalListing]) -> float:
    if not listings:
        return 0.0
    dedup_keys = [dedup_key_for_listing(listing) for listing in listings]
    return (len(dedup_keys) - len(set(dedup_keys))) / len(dedup_keys)


def summarize_city_result(
    portal: str,
    portal_mode: PortalMode,
    city_query: str,
    search_url: str,
    source_status: SourceStatus,
    listings: list[PortalListing],
    page_number: int = 1,
    blocked_reason: str = "",
    notes: list[str] | None = None,
) -> PortalCityResult:
    fill_rates = {field_name: calculate_fill_rate(listings, field_name) for field_name in REPORT_FILL_FIELDS}
    recommended_use = "hold"
    if source_status == SourceStatus.SUCCESS and portal_mode == PortalMode.PRODUCTION_CANDIDATE_WITH_PERMISSION:
        recommended_use = "candidate_for_next_phase"
    elif source_status == SourceStatus.SUCCESS and portal_mode == PortalMode.BENCHMARK_ONLY_PERMISSION_REQUIRED:
        recommended_use = "benchmark_only"
    elif source_status in {SourceStatus.PERMISSION_REQUIRED, SourceStatus.BLOCKED_CAPTCHA, SourceStatus.HTTP_403, SourceStatus.HTTP_429}:
        recommended_use = "do_not_automate"
    elif source_status == SourceStatus.REQUIRES_JS:
        recommended_use = "needs_alternate_capture_strategy"

    return PortalCityResult(
        portal=portal,
        portal_mode=portal_mode,
        city_query=city_query,
        search_url=search_url,
        source_status=source_status,
        page_number=page_number,
        listings=listings,
        duplicate_url_rate=calculate_duplicate_url_rate(listings),
        fill_rates=fill_rates,
        blocked_reason=blocked_reason,
        recommended_use=recommended_use,
        notes=notes or [],
    )


def generate_markdown_report(result: PortalSpikeResult) -> str:
    portal_counter = Counter(city_result.portal for city_result in result.city_results)
    portal_listing_counter = Counter(city_result.portal for city_result in result.city_results for _ in city_result.listings)
    blocked_results = [
        city_result
        for city_result in result.city_results
        if city_result.source_status != SourceStatus.SUCCESS
    ]
    lines = [
        f"# {result.report_title}",
        "",
        f"Generated at: {result.generated_at or 'sample-only'}",
        "",
    ]
    status_counter = Counter(city_result.source_status.value for city_result in result.city_results)
    lines.append("## Status Summary")
    for status_value, count in sorted(status_counter.items()):
        lines.append(f"- {status_value}: {count}")
    lines.append("")

    lines.append("## Portal Totals")
    for portal_name, city_count in sorted(portal_counter.items()):
        lines.append(
            f"- {portal_name}: cities={city_count}, listings={portal_listing_counter.get(portal_name, 0)}"
        )
    lines.append("")

    lines.append("## Safe To Compare Removals")
    safe_to_compare_removals = all(city_result.source_status == SourceStatus.SUCCESS for city_result in result.city_results)
    lines.append(f"- safe_to_compare_removals: {str(safe_to_compare_removals).lower()}")
    lines.append("")

    if blocked_results:
        lines.append("## Blocked Or Failed Runs")
        for city_result in blocked_results:
            lines.append(
                f"- {city_result.portal} / {city_result.city_query}: {city_result.source_status.value}"
            )
        lines.append("")

    for city_result in result.city_results:
        lines.extend(
            [
                f"## {city_result.portal} - {city_result.city_query}",
                f"- source_status: {city_result.source_status.value}",
                f"- safe_to_compare_removals: {str(city_result.source_status == SourceStatus.SUCCESS).lower()}",
                f"- portal_mode: {city_result.portal_mode.value}",
                f"- recommended_use: {city_result.recommended_use}",
                f"- listings: {len(city_result.listings)}",
                f"- duplicate_url_rate: {city_result.duplicate_url_rate:.2%}",
            ]
        )
        if city_result.blocked_reason:
            lines.append(f"- blocked_reason: {city_result.blocked_reason}")
        for field_name, fill_rate in city_result.fill_rates.items():
            lines.append(f"- fill_rate_{field_name}: {fill_rate:.2%}")
        for note in city_result.notes:
            lines.append(f"- note: {note}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_default_output_dir(base_dir: Path, generated_at: str | None = None) -> Path:
    timestamp = generated_at or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return base_dir / timestamp


def _city_summary_rows(result: PortalSpikeResult) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for city_result in result.city_results:
        rows.append(
            {
                "portal": city_result.portal,
                "portal_mode": city_result.portal_mode.value,
                "city_query": city_result.city_query,
                "search_url": city_result.search_url,
                "source_status": city_result.source_status.value,
                "page_number": city_result.page_number,
                "listings_count": len(city_result.listings),
                "duplicate_url_rate": f"{city_result.duplicate_url_rate:.6f}",
                "safe_to_compare_removals": str(city_result.source_status == SourceStatus.SUCCESS).lower(),
                "recommended_use": city_result.recommended_use,
                "blocked_reason": city_result.blocked_reason,
            }
        )
    return rows


def _dedup_summary_rows(result: PortalSpikeResult) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    grouped_listings: dict[tuple[str, str], list[PortalListing]] = {}
    for city_result in result.city_results:
        grouped_listings[(city_result.portal, city_result.city_query)] = city_result.listings

    for (portal, city_query), listings in sorted(grouped_listings.items()):
        dedup_keys = [dedup_key_for_listing(listing) for listing in listings]
        unique_count = len(set(dedup_keys))
        duplicate_count = len(dedup_keys) - unique_count
        rows.append(
            {
                "portal": portal,
                "city_query": city_query,
                "listings_count": len(listings),
                "unique_listing_count": unique_count,
                "duplicate_count": duplicate_count,
                "duplicate_url_rate": f"{calculate_duplicate_url_rate(listings):.6f}",
            }
        )
    return rows


def write_csv_outputs(result: PortalSpikeResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    listings_path = output_dir / "portal_inventory_sample.csv"
    city_summary_path = output_dir / "portal_city_summary.csv"
    dedup_summary_path = output_dir / "portal_dedup_summary.csv"
    report_path = output_dir / "portal_inventory_report.md"

    with listings_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(PortalListing.__dataclass_fields__.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for city_result in result.city_results:
            for listing in city_result.listings:
                row = asdict(listing)
                row["portal_mode"] = listing.portal_mode.value
                writer.writerow(row)

    with city_summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "portal",
            "portal_mode",
            "city_query",
            "search_url",
            "source_status",
            "page_number",
            "listings_count",
            "duplicate_url_rate",
            "safe_to_compare_removals",
            "recommended_use",
            "blocked_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in _city_summary_rows(result):
            writer.writerow(row)

    with dedup_summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "portal",
            "city_query",
            "listings_count",
            "unique_listing_count",
            "duplicate_count",
            "duplicate_url_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in _dedup_summary_rows(result):
            writer.writerow(row)

    report_path.write_text(generate_markdown_report(result), encoding="utf-8")

    return {
        "report_md": report_path,
        "listings_csv": listings_path,
        "city_summary_csv": city_summary_path,
        "dedup_summary_csv": dedup_summary_path,
    }
