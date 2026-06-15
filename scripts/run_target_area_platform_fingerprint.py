from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.discovery_artifacts import resolve_makelaar_sources_master
from domek_wonen.discovery.platform_fingerprint import run_target_area_platform_fingerprint


DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "platform_fingerprint" / "target_area"
DEFAULT_TARGET_GEMEENTES = [
    "Tilburg",
    "Waalwijk",
    "'s-Hertogenbosch",
    "Heusden",
    "Drunen",
    "Nieuwkuijk",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Target Area Platform Fingerprint v1.")
    parser.add_argument("--input", default=None, help="Optional explicit makelaar_sources_master.csv path")
    parser.add_argument(
        "--target-gemeentes",
        default=",".join(DEFAULT_TARGET_GEMEENTES),
        help="Comma-separated gemeente list to analyze",
    )
    parser.add_argument("--max-sources", type=int, default=None, help="Optional limit for number of sources")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="Per-URL HTTP timeout in seconds")
    return parser.parse_args(argv)


def _parse_target_gemeentes(raw_value: str) -> list[str]:
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_gemeentes = _parse_target_gemeentes(args.target_gemeentes)
    input_path = resolve_makelaar_sources_master(
        input_path=Path(args.input) if args.input else None,
        restore_latest=True,
    )

    run_id, _results, inventory_path, report_path = run_target_area_platform_fingerprint(
        input_path=input_path,
        output_dir=DEFAULT_OUTPUT_DIR,
        target_gemeentes=target_gemeentes,
        max_sources=args.max_sources,
        timeout_seconds=args.timeout_seconds,
    )
    print(run_id, flush=True)
    print(inventory_path, flush=True)
    print(report_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
