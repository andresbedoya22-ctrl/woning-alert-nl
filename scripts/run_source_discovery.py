from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.engine import run_discovery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Makelaar Source Discovery Engine v2.")
    parser.add_argument("--province", required=True, help="Canonical province or alias, e.g. noord-brabant")
    parser.add_argument("--mode", default="full", help="Execution mode. v1 accepts local/dry/full")
    parser.add_argument("--max-queries", type=int, default=500, help="Maximum number of generated queries to keep")
    parser.add_argument("--max-sites", type=int, default=1000, help="Maximum number of seed candidates to analyze")
    parser.add_argument("--skip-overpass", action="store_true", help="Skip free Overpass external discovery")
    parser.add_argument("--live-aanbod", action="store_true", help="Probe broker websites live to find aanbod pages")
    parser.add_argument(
        "--max-live-sites",
        type=int,
        default=0,
        help="Maximum number of websites to probe live for aanbod repair",
    )
    parser.add_argument("--audit-aanbod", action="store_true", help="Audit aanbod URLs with headless Playwright")
    parser.add_argument(
        "--max-audited-sites",
        type=int,
        default=50,
        help="Maximum number of candidate websites to audit with Playwright",
    )
    parser.add_argument(
        "--audit-confidence-threshold",
        type=int,
        default=85,
        help="Minimum confidence required to mark an audited aanbod URL as valid",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = run_discovery(
        province=args.province,
        mode=args.mode,
        max_queries=args.max_queries,
        max_sites=args.max_sites,
        skip_overpass=args.skip_overpass,
        live_aanbod=args.live_aanbod,
        max_live_sites=args.max_live_sites,
        audit_aanbod=args.audit_aanbod,
        max_audited_sites=args.max_audited_sites,
        audit_confidence_threshold=args.audit_confidence_threshold,
    )
    print(output.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
