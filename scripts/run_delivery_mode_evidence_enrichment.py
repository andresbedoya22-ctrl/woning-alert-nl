from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.diagnostics.delivery_mode_evidence_enrichment import (
    run_delivery_mode_evidence_enrichment,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run delivery mode evidence enrichment for unknown/custom sources.")
    parser.add_argument("--city", required=True, help="City filter, e.g. Tilburg")
    parser.add_argument("--province", required=True, help="Province filter, e.g. noord-brabant")
    parser.add_argument("--input", default=None, help="Optional source master CSV path")
    parser.add_argument("--platform-fingerprint-input", default=None, help="Optional platform fingerprint CSV path")
    parser.add_argument("--delivery-mode-inventory-input", default=None, help="Optional delivery_mode_inventory.csv path")
    parser.add_argument("--source-domain", action="append", default=None, help="Optional domain filter, repeatable")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="Per-URL HTTP timeout in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_delivery_mode_evidence_enrichment(
        city=args.city,
        province=args.province,
        input_path=Path(args.input) if args.input else None,
        platform_fingerprint_path=Path(args.platform_fingerprint_input) if args.platform_fingerprint_input else None,
        delivery_mode_inventory_path=Path(args.delivery_mode_inventory_input) if args.delivery_mode_inventory_input else None,
        source_domains=args.source_domain,
        timeout_seconds=args.timeout_seconds,
    )
    print(result.run_id, flush=True)
    print(result.report_path, flush=True)
    print(result.inventory_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
