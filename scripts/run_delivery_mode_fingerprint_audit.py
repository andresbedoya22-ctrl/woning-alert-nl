from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.diagnostics.delivery_mode_fingerprint_audit import (
    run_delivery_mode_fingerprint_audit,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run delivery mode fingerprint audit for makelaar sources.")
    parser.add_argument("--city", required=True, help="City filter, e.g. Tilburg")
    parser.add_argument("--province", required=True, help="Province filter, e.g. Noord-Brabant")
    parser.add_argument("--input", default=None, help="Optional source master CSV path")
    parser.add_argument("--platform-fingerprint-input", default=None, help="Optional platform fingerprint CSV path")
    parser.add_argument("--max-sources", type=int, default=None, help="Optional max source count")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="Per-URL HTTP timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_delivery_mode_fingerprint_audit(
        city=args.city,
        province=args.province,
        input_path=Path(args.input) if args.input else None,
        platform_fingerprint_path=Path(args.platform_fingerprint_input) if args.platform_fingerprint_input else None,
        max_sources=args.max_sources,
        timeout_seconds=args.timeout_seconds,
    )
    print(result.run_id, flush=True)
    print(result.report_path, flush=True)
    print(result.inventory_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
