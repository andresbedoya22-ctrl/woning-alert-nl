from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.matching.email_preview import (
    DEFAULT_EMAIL_PREVIEW_RUNS_DIR,
    find_latest_matching_results_csv,
    run_email_preview_v1,
)
from domek_wonen.matching.matching_v1 import DEFAULT_CLIENT_FIXTURE


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local dry HTML email preview for Matching v1.")
    parser.add_argument(
        "--results-csv",
        type=Path,
        default=None,
        help="Optional explicit path to a matching_results.csv file.",
    )
    parser.add_argument(
        "--client-fixture",
        type=Path,
        default=DEFAULT_CLIENT_FIXTURE,
        help="Path to the client fixture JSON.",
    )
    parser.add_argument(
        "--email-preview-runs-dir",
        type=Path,
        default=DEFAULT_EMAIL_PREVIEW_RUNS_DIR,
        help="Base directory for email preview outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results_csv_path = args.results_csv or find_latest_matching_results_csv()
    result = run_email_preview_v1(
        results_csv_path=results_csv_path,
        client_fixture_path=args.client_fixture,
        email_preview_runs_dir=args.email_preview_runs_dir,
    )
    print(result.html_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
