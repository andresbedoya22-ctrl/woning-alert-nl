from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.portals.adapters import funda, huislijn, pararius
from domek_wonen.portals.live_fetch import fetch_url, polite_sleep
from domek_wonen.portals.models import PortalCityResult, PortalListing, PortalSpikeResult, SourceStatus
from domek_wonen.portals.portal_inventory_spike import (
    build_default_output_dir,
    detect_blocked_page,
    generate_markdown_report,
    summarize_city_result,
    write_csv_outputs,
)

ADAPTERS = {
    "huislijn": huislijn,
    "pararius": pararius,
    "funda": funda,
}

PORTAL_LIMITS = {
    "huislijn": {"max_pages": 2, "max_listings": 30},
    "pararius": {"max_pages": 1, "max_listings": 20},
    "funda": {"max_pages": 1, "max_listings": 15},
}

DEFAULT_OUTPUT_ROOT = BASE_DIR / "data" / "diagnostics" / "portal_inventory"


@dataclass(slots=True)
class LivePortalRunContext:
    portal: str
    city: str
    delay_seconds: float
    timeout_seconds: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Portal Inventory Spike in sample or bounded live mode.")
    parser.add_argument("--live", action="store_true", help="Run bounded live fetches instead of local sample mode.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Final output directory. Defaults to data/diagnostics/portal_inventory/{timestamp}.",
    )

    parser.add_argument("--portal", choices=sorted(ADAPTERS), help="Portal adapter to use in sample mode.")
    parser.add_argument("--city", help="City query for the sample parse.")
    parser.add_argument("--sample-html", type=Path, help="Local HTML sample file for sample mode.")
    parser.add_argument("--status-code", type=int, default=200, help="Optional sample HTTP status code.")
    parser.add_argument("--page-number", type=int, default=1, help="Page number represented by the sample HTML.")

    parser.add_argument("--portals", nargs="+", choices=sorted(ADAPTERS), help="Portals to run in live mode.")
    parser.add_argument("--cities", nargs="+", help="Cities to query in live mode.")
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="Polite delay between live requests.")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Request timeout for live mode.")

    args = parser.parse_args(argv)
    if args.live:
        if not args.portals or not args.cities:
            parser.error("--live requires --portals and --cities")
    else:
        missing = [flag for flag, value in (("--portal", args.portal), ("--city", args.city), ("--sample-html", args.sample_html)) if not value]
        if missing:
            parser.error(f"sample mode requires {' '.join(missing)}")
    return args


def resolve_output_dir(args: argparse.Namespace, generated_at: str) -> Path:
    if args.output_dir is not None:
        return args.output_dir
    return build_default_output_dir(DEFAULT_OUTPUT_ROOT, generated_at)


def run_sample_mode(args: argparse.Namespace, generated_at: str) -> tuple[PortalSpikeResult, dict[str, Path]]:
    adapter = ADAPTERS[args.portal]
    sample_html = args.sample_html.read_text(encoding="utf-8")
    search_url = adapter.build_search_url(args.city, page=args.page_number)
    blocked_status = detect_blocked_page(sample_html, args.status_code)
    listings = [] if blocked_status else adapter.parse_listing_cards(sample_html, args.city, search_url, args.page_number)
    source_status = blocked_status or SourceStatus.SUCCESS
    city_result = summarize_city_result(
        portal=adapter.portal_name,
        portal_mode=adapter.portal_mode,
        city_query=args.city,
        search_url=search_url,
        source_status=source_status,
        listings=listings,
        page_number=args.page_number,
        blocked_reason=source_status.value if blocked_status else "",
        notes=["sample_only_cli", f"sample_path={args.sample_html}"],
    )
    spike_result = PortalSpikeResult(
        city_results=[city_result],
        generated_at=generated_at,
        report_title="Portal Inventory Spike",
    )
    output_dir = resolve_output_dir(args, generated_at)
    return spike_result, write_csv_outputs(spike_result, output_dir)


def _truncate_listings(listings: list[PortalListing], max_listings: int) -> list[PortalListing]:
    return listings[:max_listings]


def run_live_city(context: LivePortalRunContext) -> PortalCityResult:
    adapter = ADAPTERS[context.portal]
    limits = PORTAL_LIMITS[context.portal]
    collected_listings: list[PortalListing] = []
    blocked_reason = ""
    final_status = SourceStatus.SUCCESS
    last_page_number = 1
    notes = [
        "live_cli",
        f"max_pages={limits['max_pages']}",
        f"max_listings={limits['max_listings']}",
    ]

    for page_number in range(1, limits["max_pages"] + 1):
        search_url = adapter.build_search_url(context.city, page=page_number)
        fetch_result = fetch_url(search_url, timeout_seconds=context.timeout_seconds)
        last_page_number = page_number

        if fetch_result.source_status != SourceStatus.SUCCESS:
            final_status = fetch_result.source_status
            blocked_reason = fetch_result.error_message or fetch_result.source_status.value
            notes.append(f"fetch_status={fetch_result.source_status.value}")
            if fetch_result.status_code is not None:
                notes.append(f"http_status={fetch_result.status_code}")
            break

        page_listings = adapter.parse_listing_cards(fetch_result.html, context.city, search_url, page_number)
        if not page_listings and detect_blocked_page(fetch_result.html, fetch_result.status_code):
            final_status = detect_blocked_page(fetch_result.html, fetch_result.status_code) or SourceStatus.PARSER_BROKEN
            blocked_reason = final_status.value
            notes.append(f"fetch_status={final_status.value}")
            break

        remaining = limits["max_listings"] - len(collected_listings)
        collected_listings.extend(_truncate_listings(page_listings, remaining))
        if len(collected_listings) >= limits["max_listings"]:
            notes.append("listing_limit_reached")
            break
        if page_number < limits["max_pages"]:
            polite_sleep(context.delay_seconds)

    search_url = adapter.build_search_url(context.city, page=1)
    return summarize_city_result(
        portal=adapter.portal_name,
        portal_mode=adapter.portal_mode,
        city_query=context.city,
        search_url=search_url,
        source_status=final_status,
        listings=collected_listings,
        page_number=last_page_number,
        blocked_reason=blocked_reason,
        notes=notes,
    )


def run_live_mode(args: argparse.Namespace, generated_at: str) -> tuple[PortalSpikeResult, dict[str, Path]]:
    city_results: list[PortalCityResult] = []
    for portal in args.portals:
        for city in args.cities:
            city_results.append(
                run_live_city(
                    LivePortalRunContext(
                        portal=portal,
                        city=city,
                        delay_seconds=args.delay_seconds,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
            )

    spike_result = PortalSpikeResult(
        city_results=city_results,
        generated_at=generated_at,
        report_title="Portal Inventory Spike",
    )
    output_dir = resolve_output_dir(args, generated_at)
    return spike_result, write_csv_outputs(spike_result, output_dir)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    spike_result, output_paths = run_live_mode(args, generated_at) if args.live else run_sample_mode(args, generated_at)
    report_text = generate_markdown_report(spike_result)
    output_paths["report_md"].write_text(report_text, encoding="utf-8")
    print(output_paths["report_md"], flush=True)
    print(output_paths["listings_csv"], flush=True)
    print(output_paths["city_summary_csv"], flush=True)
    print(output_paths["dedup_summary_csv"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
