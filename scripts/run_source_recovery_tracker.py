from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.diagnostics.source_recovery_tracker import DEFAULT_BENCHMARK_CSV, DEFAULT_OUTPUT_BASE_DIR, run_source_recovery_tracker


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KIN source recovery tracker against PropertyDiscovery funnel artifacts.")
    parser.add_argument(
        "--benchmark-csv",
        type=Path,
        default=DEFAULT_BENCHMARK_CSV,
        help="Path to the benchmark CSV.",
    )
    parser.add_argument(
        "--candidates-csv",
        type=Path,
        default=None,
        help="Optional explicit path to a property_candidates.csv file.",
    )
    parser.add_argument(
        "--rejected-csv",
        type=Path,
        default=None,
        help="Optional explicit path to a property_rejected.csv file.",
    )
    parser.add_argument(
        "--inventory-csv",
        type=Path,
        default=None,
        help="Optional explicit path to a matching_ready_inventory.csv file.",
    )
    parser.add_argument(
        "--output-base-dir",
        type=Path,
        default=DEFAULT_OUTPUT_BASE_DIR,
        help="Base directory for tracker outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_source_recovery_tracker(
        benchmark_csv_path=args.benchmark_csv,
        candidates_csv_path=args.candidates_csv,
        rejected_csv_path=args.rejected_csv,
        matching_ready_csv_path=args.inventory_csv,
        output_base_dir=args.output_base_dir,
    )
    print(result.report_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
