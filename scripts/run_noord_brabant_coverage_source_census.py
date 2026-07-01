from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scraper" / "src"))

from domek_wonen.sources.coverage_census import run_noord_brabant_coverage_source_census


DEFAULT_OUTPUT_DIR = BASE_DIR / "tmp" / "generated"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Noord-Brabant Coverage Source Census v1.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Local generated output directory.")
    parser.add_argument("--max-sources", type=int, default=None, help="Optional source cap for diagnostics.")
    parser.add_argument(
        "--allow-live-http",
        action="store_true",
        help="Enable bounded standard-library HTTP. Default uses local evidence only.",
    )
    parser.add_argument(
        "--completion-scope-verification",
        action="store_true",
        help="Write Source Completion & Scope Verification v1 artifacts.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Per-request timeout when live HTTP is enabled.")
    parser.add_argument("--max-passes", type=int, default=8, help="Maximum bounded investigation passes.")
    parser.add_argument(
        "--max-requests-per-domain",
        type=int,
        default=3,
        help="Conservative per-domain request cap when live HTTP is enabled.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_noord_brabant_coverage_source_census(
        repo_root=BASE_DIR,
        output_dir=Path(args.output_dir),
        allow_live_http=args.allow_live_http,
        max_sources=args.max_sources,
        max_passes=args.max_passes,
        max_requests_per_domain=args.max_requests_per_domain,
        timeout_seconds=args.timeout_seconds,
        completion_scope_verification=args.completion_scope_verification,
    )
    metrics = result.quality_metrics
    print(result.workbook_path, flush=True)
    print(result.master_csv_path, flush=True)
    print(result.review_queue_csv_path, flush=True)
    if result.realworks_audit_input_csv_path:
        print(result.realworks_audit_input_csv_path, flush=True)
    print(f"total_sources={metrics['total_sources']}", flush=True)
    print(f"deduped_sources={metrics['deduped_sources']}", flush=True)
    print(f"in_scope_noord_brabant_coverage_sources={metrics['in_scope_noord_brabant_coverage_sources']}", flush=True)
    print(f"operational_unknown_family_count={metrics['operational_unknown_family_count']}", flush=True)
    print(
        "missing_aanbod_url_without_terminal_reason_count="
        f"{metrics['missing_aanbod_url_without_terminal_reason_count']}",
        flush=True,
    )
    print(f"quality_gate_passed={metrics['quality_gate_passed']}", flush=True)
    for key in (
        "rejected_candidate_used_as_master_aanbod_url_count",
        "property_detail_url_as_aanbod_url_count",
        "funda_or_pararius_operational_aanbod_url_count",
        "realworks_without_strong_evidence_count",
        "platform_guess_realworks_but_family_custom_js_app_unreviewed_count",
        "kin_family_conflict_count",
        "custom_js_app_without_fingerprint_attempt_count",
        "gemeente_normalization_conflict_count",
        "missing_domain_queue_count",
        "office_location_unknown_count",
        "outside_office_sources_needing_review_count",
        "missing_domain_initial_count",
        "missing_domain_resolved_count",
        "missing_domain_remaining_count",
        "missing_domain_needs_manual_research_count",
        "missing_domain_without_resolution_attempt_count",
        "no_public_initial_count",
        "no_public_reclassified_count",
        "no_public_confirmed_count",
        "no_public_without_full_attempt_history_count",
        "accepted_aanbod_total_count",
        "accepted_aanbod_confirmed_nb_scope_count",
        "accepted_aanbod_broad_official_index_count",
        "accepted_aanbod_official_scope_unclear_count",
        "accepted_aanbod_out_of_scope_needs_review_count",
        "accepted_aanbod_out_of_scope_unreviewed_count",
        "realworks_verified_total_count",
        "realworks_ready_for_audit_count",
        "realworks_needs_manual_scope_check_count",
        "realworks_excluded_from_audit_count",
        "realworks_audit_input_without_scope_confirmation_count",
        "realworks_audit_input_kin_count",
        "realworks_audit_input_property_detail_url_count",
        "realworks_audit_input_without_accepted_aanbod_count",
        "office_location_fabricated_count",
        "review_queue_count",
    ):
        print(f"{key}={metrics[key]}", flush=True)
    return 0 if metrics["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
