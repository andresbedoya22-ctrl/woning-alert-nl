from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.portals.adapters import funda, huislijn, pararius
from domek_wonen.portals.models import PortalSpikeResult, SourceStatus
from domek_wonen.portals.portal_inventory_spike import (
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the sample-only Portal Inventory Spike.")
    parser.add_argument("--portal", choices=sorted(ADAPTERS), required=True, help="Portal adapter to use.")
    parser.add_argument("--city", required=True, help="City query for the sample parse.")
    parser.add_argument("--sample-html", type=Path, required=True, help="Local HTML sample file.")
    parser.add_argument("--status-code", type=int, default=200, help="Optional sample HTTP status code.")
    parser.add_argument("--page-number", type=int, default=1, help="Page number represented by the HTML sample.")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "tmp" / "portal_inventory_spike", help="Output directory for local artifacts.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    adapter = ADAPTERS[args.portal]
    sample_html = args.sample_html.read_text(encoding="utf-8")
    search_url = adapter.build_search_url(args.city)
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
        blocked_reason=blocked_status.value if blocked_status else "",
        notes=["sample_only_cli", f"sample_path={args.sample_html}"],
    )
    spike_result = PortalSpikeResult(
        city_results=[city_result],
        generated_at=datetime.now(UTC).isoformat(),
        report_title="Portal Inventory Spike Skeleton",
    )
    output_paths = write_csv_outputs(spike_result, args.output_dir)
    report_path = args.output_dir / "portal_inventory_spike_report.md"
    report_path.write_text(generate_markdown_report(spike_result), encoding="utf-8")
    print(report_path, flush=True)
    print(output_paths["listings_csv"], flush=True)
    print(output_paths["summary_csv"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
