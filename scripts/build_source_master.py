from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.discovery.source_master_builder import build_source_master_from_csv, write_source_master


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build makelaar_sources_master.csv from discovered_sources.csv.")
    parser.add_argument("--input", required=True, help="Path to discovered_sources.csv")
    parser.add_argument("--output", required=True, help="Path to write makelaar_sources_master.csv")
    parser.add_argument("--run-id", default="", help="Optional run id override. Defaults to timestamp or latest.")
    return parser.parse_args(argv)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)
    run_timestamp = _timestamp()
    run_id = args.run_id.strip() or run_timestamp or "latest"
    rows = build_source_master_from_csv(input_path, run_timestamp=run_timestamp, default_run_id=run_id)
    write_source_master(output_path, rows)
    print(output_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
