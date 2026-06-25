from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.portals.huislijn_url_discovery import resolve_output_dir, run_huislijn_url_discovery, write_outputs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded Huislijn URL discovery spike.")
    parser.add_argument("--cities", nargs="+", required=True, help="Cities to probe with at most three candidate URLs each.")
    parser.add_argument("--delay-seconds", type=float, default=3.0, help="Delay between live requests.")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Timeout per live request.")
    parser.add_argument("--max-requests", type=int, default=10, help="Global request budget for the run.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Final output directory. Defaults to data/diagnostics/portal_inventory/{timestamp}.",
    )
    args = parser.parse_args(argv)
    if args.max_requests < 1 or args.max_requests > 10:
        parser.error("--max-requests must be between 1 and 10")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_huislijn_url_discovery(
        cities=args.cities,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        max_requests=args.max_requests,
    )
    output_dir = resolve_output_dir(args.output_dir, result.generated_at)
    output_paths = write_outputs(result, output_dir)
    print(output_paths["report_md"], flush=True)
    print(output_paths["candidates_csv"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
