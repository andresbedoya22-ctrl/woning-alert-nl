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
    parser.add_argument(
        "--missing-domain-external-resolution",
        action="store_true",
        help="Write Missing Domain External Resolution v1 artifacts and Source Completion v2 outputs.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="Per-request timeout when live HTTP is enabled.")
    parser.add_argument("--max-passes", type=int, default=8, help="Maximum bounded investigation passes.")
    parser.add_argument(
        "--max-requests-per-domain",
        type=int,
        default=3,
        help="Conservative per-domain request cap when live HTTP is enabled.",
    )
    parser.add_argument(
        "--missing-domain-external-http-budget",
        type=int,
        default=20,
        help="Global HTTP request budget for Missing Domain External Resolution.",
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
        missing_domain_external_resolution=args.missing_domain_external_resolution,
        missing_domain_external_http_budget=args.missing_domain_external_http_budget,
    )
    metrics = result.quality_metrics
    print(result.workbook_path, flush=True)
    print(result.master_csv_path, flush=True)
    print(result.review_queue_csv_path, flush=True)
    if result.realworks_audit_input_csv_path:
        print(result.realworks_audit_input_csv_path, flush=True)
    if result.realworks_audit_input_reconciliation_csv_path:
        print(result.realworks_audit_input_reconciliation_csv_path, flush=True)
    if result.missing_domain_resolution_workbook_path:
        print(result.missing_domain_resolution_workbook_path, flush=True)
    if result.missing_domain_resolution_csv_path:
        print(result.missing_domain_resolution_csv_path, flush=True)
    if result.missing_domain_resolution_review_queue_csv_path:
        print(result.missing_domain_resolution_review_queue_csv_path, flush=True)
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
        "missing_domain_attempted_count",
        "missing_domain_resolved_existing_count",
        "missing_domain_resolved_new_count",
        "missing_domain_confirmed_duplicate_count",
        "missing_domain_confirmed_inactive_count",
        "missing_domain_confirmed_no_official_domain_count",
        "missing_domain_resolved_count",
        "missing_domain_remaining_count",
        "missing_domain_needs_manual_research_count",
        "missing_domain_without_resolution_attempt_count",
        "candidate_domains_generated_count",
        "candidate_domains_verified_official_count",
        "candidate_domains_rejected_count",
        "candidate_domains_fetch_failed_count",
        "candidate_domains_blocked_by_robots_count",
        "new_sources_added_count",
        "existing_sources_updated_count",
        "accepted_aanbod_urls_added_count",
        "no_public_aanbod_confirmed_count",
        "resolved_domain_third_party_count",
        "resolved_domain_without_official_evidence_count",
        "duplicate_domain_created_count",
        "property_detail_url_as_accepted_aanbod_url_count",
        "raw_html_json_persisted_count",
        "long_descriptions_exported_count",
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
        "realworks_audit_input_row_count_unexplained_delta",
        "office_location_fabricated_count",
        "review_queue_count",
    ):
        print(f"{key}={metrics[key]}", flush=True)
    return 0 if metrics["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
