from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.discovery.platform_fingerprint import run_platform_fingerprint_audit


DEFAULT_INPUT = BASE_DIR / "data" / "discovery" / "latest" / "makelaar_sources_master.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "discovery" / "platform_fingerprint"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CRM/platform fingerprint audit for makelaar sources.")
    parser.add_argument("--province", default="", help="Optional province filter, e.g. Noord-Brabant")
    parser.add_argument("--input", default=None, help=f"Input CSV path (default: {DEFAULT_INPUT})")
    parser.add_argument("--max-sources", type=int, default=None, help="Optional limit for number of sources")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="Per-URL HTTP timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = resolve_makelaar_sources_master(
        input_path=Path(args.input) if args.input else None,
        province=args.province,
        restore_latest=True,
    )

    output_csv_path = DEFAULT_OUTPUT_DIR / "platform_fingerprint_results.csv"
    output_summary_path = DEFAULT_OUTPUT_DIR / "platform_fingerprint_summary.md"
    run_platform_fingerprint_audit(
        input_path=input_path,
        output_csv_path=output_csv_path,
        output_summary_path=output_summary_path,
        province=args.province,
        max_sources=args.max_sources,
        timeout_seconds=args.timeout_seconds,
    )
    print(output_csv_path, flush=True)
    print(output_summary_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
