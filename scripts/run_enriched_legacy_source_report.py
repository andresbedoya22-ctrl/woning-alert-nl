from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.sources.evidence_enrichment import build_enriched_legacy_source_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline enriched legacy source report.")
    parser.add_argument("--source-master", required=True, help="Path to makelaar_sources_master.csv")
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Local evidence CSV path. May be repeated.",
    )
    parser.add_argument("--output", default="", help="Optional JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_enriched_legacy_source_report(
        source_master_path=Path(args.source_master),
        evidence_paths=[Path(path) for path in args.evidence],
    )

    delivery = report["delivery_fingerprint"]
    enrichment = report["enrichment_summary"]
    print(f"total_sources: {report['total_sources']}", flush=True)
    print(f"unique_domains: {report['unique_domains']}", flush=True)
    print(
        "unknown_manual_review: "
        f"{delivery['counts_by_delivery_mode'].get('unknown_manual_review', 0)}",
        flush=True,
    )
    print(
        f"production_parser_ready_count: {delivery['production_parser_ready_count']}",
        flush=True,
    )
    print(f"records_enriched_count: {enrichment['records_enriched_count']}", flush=True)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(output_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
