from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.sources import build_source_intelligence_report, load_source_intelligence_csv


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic source intelligence report from a CSV fixture.")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", help="Optional path to write JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    records = load_source_intelligence_csv(Path(args.input))
    report = build_source_intelligence_report(records)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    print(f"total_sources: {report['total_sources']}")
    print(f"unique_domains: {report['unique_domains']}")
    print("top delivery modes: " + _format_top(report["counts_by_delivery_mode"]))  # type: ignore[index]
    print("top parser families: " + _format_top(report["counts_by_parser_family_candidate"]))  # type: ignore[index]
    print(f"manual review count: {len(report['manual_review_queue'])}")
    return 0


def _format_top(counter: dict[str, int], limit: int = 3) -> str:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{key or '<none>'}={value}" for key, value in items[:limit])


if __name__ == "__main__":
    raise SystemExit(main())
