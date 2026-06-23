from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper" / "src"))

from domek_wonen.sources.legacy_source_adapter import build_legacy_source_intelligence_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an offline legacy source intelligence report.")
    parser.add_argument("--input", required=True, help="Path to a legacy source CSV.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    report = build_legacy_source_intelligence_report(Path(args.input))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    delivery = report["delivery_fingerprint"]
    access = report["access_policy"]
    print(f"total_sources: {report['total_sources']}")
    print(f"unique_domains: {report['unique_domains']}")
    print(f"production_parser_ready_count: {delivery['production_parser_ready_count']}")
    print(f"blocked_count: {access['blocked_count']}")
    print(f"permission_required_count: {access['permission_required_count']}")
    print(f"manual_review_count: {delivery['manual_review_count']}")
    print(f"top delivery modes: {_format_top(delivery['counts_by_delivery_mode'])}")
    print(f"top parser families: {_format_top(delivery['counts_by_parser_family_candidate'])}")
    return 0


def _format_top(counts: dict[str, int], limit: int = 5) -> str:
    items = [(key or "none", value) for key, value in counts.items()]
    top_items = sorted(items, key=lambda item: (-item[1], item[0]))[:limit]
    return ", ".join(f"{key}={value}" for key, value in top_items)


if __name__ == "__main__":
    raise SystemExit(main())
