from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.pilots.noord_brabant_realworks_audit import run_noord_brabant_realworks_audit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Noord-Brabant Realworks Audit v1.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-workbook", required=True)
    parser.add_argument("--output-summary", required=True)
    parser.add_argument("--output-problem-sources", required=True)
    parser.add_argument("--max-sources", type=int, default=65)
    parser.add_argument("--max-listings-per-source", type=int, default=15)
    parser.add_argument("--max-detail-per-source", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--runtime-budget-seconds", type=float, default=1800.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_noord_brabant_realworks_audit(
        input_csv=Path(args.input_csv),
        output_workbook=Path(args.output_workbook),
        output_summary=Path(args.output_summary),
        output_problem_sources=Path(args.output_problem_sources),
        max_sources=args.max_sources,
        max_listings_per_source=args.max_listings_per_source,
        max_detail_per_source=args.max_detail_per_source,
        timeout_seconds=args.timeout_seconds,
        runtime_budget_seconds=args.runtime_budget_seconds,
    )
    aggregate = result.aggregate_metrics
    decision = result.family_decision
    print(result.workbook_path, flush=True)
    print(result.summary_csv_path, flush=True)
    print(result.problem_sources_csv_path, flush=True)
    print(f"input_sources={aggregate.input_sources}", flush=True)
    print(f"sources_attempted={aggregate.sources_attempted}", flush=True)
    print(f"sources_passed={aggregate.sources_passed}", flush=True)
    print(f"sources_passed_with_review_gaps={aggregate.sources_passed_with_review_gaps}", flush=True)
    print(f"sources_no_current_listings={aggregate.sources_no_current_listings}", flush=True)
    print(f"sources_blocked={aggregate.sources_blocked}", flush=True)
    print(f"sources_fetch_failed={aggregate.sources_fetch_failed}", flush=True)
    print(f"sources_needing_hardening={aggregate.sources_needing_hardening}", flush=True)
    print(f"total_parser_rows={aggregate.total_parser_rows}", flush=True)
    print(f"total_qa_clean={aggregate.total_qa_clean}", flush=True)
    print(f"total_qa_review={aggregate.total_qa_review}", flush=True)
    print(f"total_qa_rejected={aggregate.total_qa_rejected}", flush=True)
    print(f"total_detail_attempted={aggregate.total_detail_attempted}", flush=True)
    print(f"total_detail_succeeded={aggregate.total_detail_succeeded}", flush=True)
    print(f"total_detail_failed={aggregate.total_detail_failed}", flush=True)
    print(f"total_readiness_rows={aggregate.total_readiness_rows}", flush=True)
    print(f"total_export_ready={aggregate.total_export_ready}", flush=True)
    print(f"total_export_review={aggregate.total_export_review}", flush=True)
    print(f"total_export_blocked={aggregate.total_export_blocked}", flush=True)
    print(f"runtime_budget_exhausted={aggregate.runtime_budget_exhausted}", flush=True)
    print(f"family_decision={decision.family_decision}", flush=True)
    print(f"confidence={decision.confidence}", flush=True)
    print(f"next_action={decision.next_action}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
