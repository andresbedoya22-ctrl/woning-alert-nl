from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.properties.property_discovery_engine import run_property_discovery
from domek_wonen.properties.property_discovery_engine import DEFAULT_PLATFORM_FINGERPRINT_INPUT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropertyDiscovery v1.")
    parser.add_argument("--province", required=True, help="Canonical province or alias, e.g. noord-brabant")
    parser.add_argument("--max-sources", type=int, default=None, help="Maximum number of official sources to crawl")
    parser.add_argument(
        "--max-properties-per-source",
        type=int,
        default=None,
        help="Maximum number of property cards to keep per source",
    )
    parser.add_argument("--timeout-ms", type=int, default=30000, help="General timeout budget in milliseconds")
    parser.add_argument(
        "--source-timeout-seconds",
        type=int,
        default=90,
        help="Hard timeout per source before continuing to the next one",
    )
    parser.add_argument(
        "--page-timeout-seconds",
        type=int,
        default=30,
        help="Hard timeout per page navigation and load operations",
    )
    parser.add_argument("--max-detail-pages", type=int, default=3, help="Maximum detail pages to enrich per source")
    parser.add_argument(
        "--detail-timeout-seconds",
        type=int,
        default=10,
        help="Hard timeout per detail page navigation and load operations",
    )
    parser.add_argument("--disable-detail-extraction", action="store_true", help="Disable optional detail page enrichment")
    parser.add_argument("--platform", default="", help="Only process sources detected for a specific platform, e.g. realworks")
    parser.add_argument("--source-domain", default="", help="Only process a specific root domain, e.g. kinmakelaars.nl")
    parser.add_argument(
        "--platform-fingerprint-input",
        type=Path,
        default=DEFAULT_PLATFORM_FINGERPRINT_INPUT,
        help="Path to platform_fingerprint_results.csv",
    )
    parser.add_argument(
        "--disable-platform-parsers",
        action="store_true",
        help="Disable platform-specific parsers and use the generic flow only",
    )
    parser.add_argument(
        "--include-invalid-sources",
        action="store_true",
        help="Include sources flagged with invalid aanbod_url quality gates",
    )
    parser.add_argument("--smoke", action="store_true", help="Run a fast single-source smoke test")
    return parser.parse_args(argv)


def _effective_options(args: argparse.Namespace) -> dict[str, int | bool | str]:
    if args.smoke:
        max_sources = 1 if args.max_sources is None else args.max_sources
        max_properties_per_source = 1 if args.max_properties_per_source is None else args.max_properties_per_source
        source_timeout_seconds = min(args.source_timeout_seconds, 30)
        page_timeout_seconds = min(args.page_timeout_seconds, 15)
        max_detail_pages = min(args.max_detail_pages, 1)
        detail_timeout_seconds = min(args.detail_timeout_seconds, 5)
    else:
        max_sources = 20 if args.max_sources is None else args.max_sources
        max_properties_per_source = 50 if args.max_properties_per_source is None else args.max_properties_per_source
        source_timeout_seconds = args.source_timeout_seconds
        page_timeout_seconds = args.page_timeout_seconds
        max_detail_pages = args.max_detail_pages
        detail_timeout_seconds = args.detail_timeout_seconds
    return {
        "province": args.province,
        "max_sources": max_sources,
        "max_properties_per_source": max_properties_per_source,
        "timeout_ms": args.timeout_ms,
        "source_timeout_seconds": source_timeout_seconds,
        "page_timeout_seconds": page_timeout_seconds,
        "max_detail_pages": max_detail_pages,
        "detail_timeout_seconds": detail_timeout_seconds,
        "disable_detail_extraction": args.disable_detail_extraction,
        "platform": args.platform,
        "platform_fingerprint_input": args.platform_fingerprint_input,
        "source_domain": args.source_domain,
        "disable_platform_parsers": args.disable_platform_parsers,
        "include_invalid_sources": args.include_invalid_sources,
        "verbose": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run_property_discovery(**_effective_options(args))
    print(output.report_path, flush=True)
    return 0 if output.run_status in {"completed", "completed_with_errors"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
