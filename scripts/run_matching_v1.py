from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.matching.matching_v1 import (
    DEFAULT_CLIENT_FIXTURE,
    DEFAULT_MATCHING_RUNS_DIR,
    find_latest_inventory_csv,
    run_matching_v1,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Matching v1 using the latest PropertyDiscovery inventory.")
    parser.add_argument(
        "--inventory-csv",
        type=Path,
        default=None,
        help="Optional explicit path to a matching_ready_inventory.csv file.",
    )
    parser.add_argument(
        "--client-fixture",
        type=Path,
        default=DEFAULT_CLIENT_FIXTURE,
        help="Path to the client fixture JSON.",
    )
    parser.add_argument(
        "--matching-runs-dir",
        type=Path,
        default=DEFAULT_MATCHING_RUNS_DIR,
        help="Base directory for matching outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inventory_csv_path = args.inventory_csv or find_latest_inventory_csv()
    result = run_matching_v1(
        inventory_csv_path=inventory_csv_path,
        client_fixture_path=args.client_fixture,
        matching_runs_dir=args.matching_runs_dir,
    )
    print(result.report_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
