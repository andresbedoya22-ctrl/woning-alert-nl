from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.diagnostics.property_discovery_selection_quality_audit import (
    DEFAULT_OUTPUT_BASE_DIR,
    run_property_discovery_selection_quality_audit,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PropertyDiscovery Source Selection + Batch Quality Audit v1.")
    parser.add_argument("--city", required=True, help="Target city, for example Tilburg")
    parser.add_argument("--province", required=True, help="Target province, for example noord-brabant")
    parser.add_argument(
        "--property-discovery-run-dir",
        type=Path,
        required=True,
        help="PropertyDiscovery run directory to audit.",
    )
    parser.add_argument(
        "--source-domain",
        action="append",
        default=[],
        help="Repeatable root-domain filter, for example kinmakelaars.nl",
    )
    parser.add_argument("--source-master", type=Path, default=None, help="Optional explicit makelaar_sources_master.csv path")
    parser.add_argument("--override-csv", type=Path, default=None, help="Optional explicit override CSV path")
    parser.add_argument(
        "--platform-fingerprint",
        type=Path,
        default=None,
        help="Optional explicit platform_fingerprint_results.csv path",
    )
    parser.add_argument("--output-base-dir", type=Path, default=DEFAULT_OUTPUT_BASE_DIR, help="Output base directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_property_discovery_selection_quality_audit(
        city=args.city,
        province=args.province,
        property_discovery_run_dir=args.property_discovery_run_dir,
        source_domains=args.source_domain,
        source_master_path=args.source_master,
        override_csv_path=args.override_csv,
        platform_fingerprint_path=args.platform_fingerprint,
        output_base_dir=args.output_base_dir,
    )
    print(result.run_id, flush=True)
    print(result.report_path, flush=True)
    print(result.inventory_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
