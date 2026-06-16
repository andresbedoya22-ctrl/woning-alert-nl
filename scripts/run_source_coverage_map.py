from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.diagnostics.source_coverage_map import run_source_coverage_map


DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "diagnostics" / "source_coverage"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tilburg Source Coverage Map v1.")
    parser.add_argument("--city", required=True, help="Target city, for example Tilburg")
    parser.add_argument("--province", required=True, help="Target province, for example noord-brabant")
    parser.add_argument("--source-master", default=None, help="Optional explicit makelaar_sources_master.csv path")
    parser.add_argument(
        "--platform-fingerprint",
        default=None,
        help="Optional explicit platform_fingerprint_results.csv path",
    )
    parser.add_argument(
        "--property-discovery-run-dir",
        default=None,
        help="Optional explicit PropertyDiscovery run directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_source_coverage_map(
        city=args.city,
        province=args.province,
        source_master_path=Path(args.source_master) if args.source_master else None,
        platform_fingerprint_path=Path(args.platform_fingerprint) if args.platform_fingerprint else None,
        property_discovery_run_dir=Path(args.property_discovery_run_dir) if args.property_discovery_run_dir else None,
        output_base_dir=DEFAULT_OUTPUT_DIR,
    )
    print(result.run_id, flush=True)
    print(result.report_path, flush=True)
    print(result.inventory_output_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
