from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
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

    for city_result in result.city_results:
        lines.extend(
            [
                f"## {city_result.portal} - {city_result.city_query}",
                f"- source_status: {city_result.source_status.value}",
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


def write_csv_outputs(result: PortalSpikeResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    listings_path = output_dir / "portal_listings.csv"
    summary_path = output_dir / "portal_summary.csv"

    with listings_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(PortalListing.__dataclass_fields__.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for city_result in result.city_results:
            for listing in city_result.listings:
                row = asdict(listing)
                row["portal_mode"] = listing.portal_mode.value
                writer.writerow(row)

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "portal",
            "portal_mode",
            "city_query",
            "search_url",
            "source_status",
            "page_number",
            "listings_count",
            "duplicate_url_rate",
            "recommended_use",
            "blocked_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for city_result in result.city_results:
            writer.writerow(
                {
                    "portal": city_result.portal,
                    "portal_mode": city_result.portal_mode.value,
                    "city_query": city_result.city_query,
                    "search_url": city_result.search_url,
                    "source_status": city_result.source_status.value,
                    "page_number": city_result.page_number,
                    "listings_count": len(city_result.listings),
                    "duplicate_url_rate": f"{city_result.duplicate_url_rate:.6f}",
                    "recommended_use": city_result.recommended_use,
                    "blocked_reason": city_result.blocked_reason,
                }
            )

    return {"listings_csv": listings_path, "summary_csv": summary_path}
