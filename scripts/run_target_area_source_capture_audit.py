from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.properties.source_capture_audit import (
    DEFAULT_TARGET_GEMEENTES,
    run_target_area_source_capture_audit,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Target Area Source Capture Audit v1.")
    parser.add_argument("--input", default=None, help="Optional explicit makelaar_sources_master.csv path")
    parser.add_argument(
        "--target-gemeentes",
        default=",".join(DEFAULT_TARGET_GEMEENTES),
        help="Comma-separated gemeente list to analyze",
    )
    parser.add_argument("--platform", default="", help="Optional detected platform filter, e.g. realworks")
    parser.add_argument("--root-domain", default="", help="Optional root domain filter, e.g. kinmakelaars.nl")
    parser.add_argument("--max-sources", type=int, default=None, help="Optional limit for number of sources")
    parser.add_argument(
        "--max-properties-per-source",
        type=int,
        default=20,
        help="Maximum number of properties to keep per source audit",
    )
    return parser.parse_args(argv)


def _parse_target_gemeentes(raw_value: str) -> list[str]:
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id, _rows, inventory_path, report_path = run_target_area_source_capture_audit(
        input_path=Path(args.input) if args.input else None,
        target_gemeentes=_parse_target_gemeentes(args.target_gemeentes),
        platform=args.platform,
        root_domain=args.root_domain,
        max_sources=args.max_sources,
        max_properties_per_source=args.max_properties_per_source,
    )
    print(run_id, flush=True)
    print(inventory_path, flush=True)
    print(report_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
