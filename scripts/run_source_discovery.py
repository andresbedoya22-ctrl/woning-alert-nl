from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.engine import run_discovery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Makelaar Source Discovery Engine v1.")
    parser.add_argument("--province", required=True, help="Canonical province or alias, e.g. noord-brabant")
    parser.add_argument("--mode", default="full", help="Execution mode. v1 accepts local/dry/full")
    parser.add_argument("--max-queries", type=int, default=500, help="Maximum number of generated queries to keep")
    parser.add_argument("--max-sites", type=int, default=1000, help="Maximum number of seed candidates to analyze")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = run_discovery(
        province=args.province,
        mode=args.mode,
        max_queries=args.max_queries,
        max_sites=args.max_sites,
    )
    print(output.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
