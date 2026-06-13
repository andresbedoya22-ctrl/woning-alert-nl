from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.properties.property_discovery_engine import run_property_discovery


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropertyDiscovery v1.")
    parser.add_argument("--province", required=True, help="Canonical province or alias, e.g. noord-brabant")
    parser.add_argument("--max-sources", type=int, default=20, help="Maximum number of official sources to crawl")
    parser.add_argument(
        "--max-properties-per-source",
        type=int,
        default=50,
        help="Maximum number of property cards to keep per source",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run_property_discovery(
        province=args.province,
        max_sources=args.max_sources,
        max_properties_per_source=args.max_properties_per_source,
    )
    print(output.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
