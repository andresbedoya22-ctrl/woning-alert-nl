from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.sources.makelaar_universe import (
    build_noord_brabant_makelaar_universe,
    write_makelaar_universe_csv,
    write_makelaar_universe_workbook,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Noord-Brabant Makelaar Universe from manual Funda name observations.")
    parser.add_argument(
        "--funda-raw-csv",
        default="tmp/manual_inputs/funda_makelaar_names/funda_nb_makelaar_names_raw.csv",
        help="Primary Funda raw makelaar-name CSV path.",
    )
    parser.add_argument(
        "--source-completion-csv",
        default="tmp/generated/noord_brabant_source_completion_scope_verification_v2.csv",
        help="Optional source completion verification CSV path.",
    )
    parser.add_argument(
        "--missing-domain-resolution-csv",
        default="tmp/generated/noord_brabant_missing_domain_external_resolution_v1.csv",
        help="Optional missing-domain external resolution CSV path.",
    )
    parser.add_argument(
        "--source-master-csv",
        default="data/discovery/runs/20260614T122022Z/makelaar_sources_master.csv",
        help="Optional source master CSV path.",
    )
    parser.add_argument(
        "--platform-fingerprint-csv",
        default="data/discovery/platform_fingerprint/platform_fingerprint_results.csv",
        help="Optional platform fingerprint CSV path.",
    )
    parser.add_argument(
        "--source-seed-csv",
        default="data/processed/sources_seed_noord_brabant.csv",
        help="Optional source seed CSV path.",
    )
    parser.add_argument(
        "--output-workbook",
        default="tmp/generated/noord_brabant_makelaar_universe_v1.xlsx",
        help="Workbook output path.",
    )
    parser.add_argument(
        "--output-csv",
        default="tmp/generated/noord_brabant_makelaar_universe_v1.csv",
        help="Universe CSV output path.",
    )
    parser.add_argument(
        "--output-review-queue-csv",
        default="tmp/generated/noord_brabant_makelaar_universe_v1_review_queue.csv",
        help="Review queue CSV output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_noord_brabant_makelaar_universe(
        funda_raw_csv_path=Path(args.funda_raw_csv),
        source_completion_csv_path=Path(args.source_completion_csv),
        missing_domain_resolution_csv_path=Path(args.missing_domain_resolution_csv),
        source_master_csv_path=Path(args.source_master_csv),
        platform_fingerprint_csv_path=Path(args.platform_fingerprint_csv),
        source_seed_csv_path=Path(args.source_seed_csv),
    )
    output_csv = write_makelaar_universe_csv(result.rows, Path(args.output_csv))
    output_review_queue_csv = write_makelaar_universe_csv(result.review_queue_rows, Path(args.output_review_queue_csv))
    output_workbook = write_makelaar_universe_workbook(result, Path(args.output_workbook))

    print(f"effective_input_path: {result.effective_input_path}")
    print(f"raw_rows_imported: {result.raw_rows_imported}")
    print(f"deduped_makelaars: {result.deduped_makelaars}")
    print(f"review_queue_count: {len(result.review_queue_rows)}")
    print(f"workbook_path: {output_workbook}")
    print(f"csv_path: {output_csv}")
    print(f"review_queue_csv_path: {output_review_queue_csv}")
    if result.missing_optional_inputs:
        print("missing_optional_inputs: " + ", ".join(result.missing_optional_inputs))
    for metric, value in result.quality_metrics.items():
        print(f"{metric}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
